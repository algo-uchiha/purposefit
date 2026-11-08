"""Stage 5: rule-based redactor (layers 1 to 4 plus merge).

redact(texts, plan, private_dir=...) returns the spans per record and the text with typed
placeholders such as [PERSON]. NER and health layers are added in Phase 6.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from stdnum import luhn

from api.pipeline.contracts import PolicyPlan, Span
from api.pipeline.redact import crossturn, cues, gazetteer, health, normalise, patterns
from api.pipeline.redact.merge import Cand, merge

log = logging.getLogger("purposefit.redact")


@dataclass(frozen=True)
class Layers:
    """Per-layer flags. The gazetteer has two independent sources."""

    patterns: bool = True
    normalise: bool = True
    controller: bool = True
    dvv: bool = True
    cues: bool = True
    health: bool = True  # LLM health flags; does nothing without an enabled client

    def names(self) -> list[str]:
        return [k for k, v in self.__dict__.items() if v]


@dataclass
class Result:
    spans: dict[str, list[Span]]
    redacted: dict[str, str]
    sources: dict[str, list[str]] = field(default_factory=dict)  # per record, per span
    stats: dict = field(default_factory=dict)


def _shape_label(rep: str) -> str:
    r = rep.lower()
    if re.fullmatch(r"fi\d{16,}", r):
        return "IBAN"
    if re.fullmatch(r"\d{6}[-+a-y]\d{3}[0-9a-y]?", r):
        return "NATIONAL_ID"
    d = re.sub(r"\D", "", r)
    if len(d) == 15:
        return "DEVICE_ID"
    if re.fullmatch(r"(?:\+358|0)\d{7,12}", r):
        return "PHONE"
    if 13 <= len(d) <= 19 and luhn.is_valid(d):
        return "PAYMENT_CARD"
    return "ACCOUNT_NUMBER"


def _candidates(text: str, layers: Layers, ctl: gazetteer.Controller | None,
                dvv: gazetteer.Dvv | None, known: frozenset[str]) -> list[Cand]:  # fmt: skip
    cands: list[Cand] = []
    n = normalise.normalise(text) if layers.normalise else None
    if layers.patterns:
        cands += [Cand(h.start, h.end, h.label, "patterns", h.score) for h in patterns.find(text)]
    if n is not None and n.edits:
        edit_ranges = [(s, e) for s, e, _ in n.edits]
        covered = []
        for h in patterns.find(n.text):
            s, e = normalise.map_back(n, h.start, h.end)
            if any(s < b and a < e for a, b in edit_ranges):
                cands.append(Cand(s, e, h.label, "normalise", h.score))
                covered.append((s, e))
        if layers.controller and ctl is not None:
            for c in gazetteer.controller_cands(n.text, ctl):
                s, e = normalise.map_back(n, c.start, c.end)
                if any(s < b and a < e for a, b in edit_ranges):
                    cands.append(c._replace(start=s, end=e, layer="normalise"))
        for s, e, rep in n.edits:
            if "@" not in rep and not any(s < b and a < e and sc >= 0.7 for a, b, sc in
                                          [(c.start, c.end, c.score) for c in cands]):  # fmt: skip
                cands.append(Cand(s, e, _shape_label(rep), "normalise", 0.9))
    if layers.controller and ctl is not None:
        cands += gazetteer.controller_cands(text, ctl)
    if layers.dvv and dvv:
        cands += gazetteer.dvv_cands(text, dvv)
    if layers.cues:
        cands += cues.find(text, known)
    return cands


class Masked:
    """Text with rule spans replaced by [LABEL], and the map back to the original offsets."""

    def __init__(self, text: str, origin: list[tuple[int, int]]):
        self.text, self.origin = text, origin

    def to_original(self, start: int, end: int) -> tuple[int, int]:
        return self.origin[start][0], self.origin[end - 1][1]


def mask(text: str, spans: list[Cand]) -> Masked:
    out: list[str] = []
    origin: list[tuple[int, int]] = []
    pos = 0
    for c in spans:
        for i in range(pos, c.start):
            out.append(text[i]); origin.append((i, i + 1))
        ph = f"[{c.label}]"
        out.append(ph); origin.extend([(c.start, c.end)] * len(ph))
        pos = c.end
    for i in range(pos, len(text)):
        out.append(text[i]); origin.append((i, i + 1))
    return Masked("".join(out), origin)


def _apply_health(merged: list[Cand], flagged: list[Cand]) -> list[Cand]:
    """A health span replaces every span it overlaps and grows to cover them, so no identifier
    inside or at the edge of the health phrase is left in the text."""
    out = list(merged)
    for h in sorted(flagged, key=lambda c: c.start):
        start, end = h.start, h.end
        hit = [c for c in out if c.start < end and start < c.end]
        for c in hit:
            start, end = min(start, c.start), max(end, c.end)
            out.remove(c)
        out.append(Cand(start, end, "HEALTH", "health", h.score))
    return sorted(out, key=lambda c: c.start)


def redact(texts: dict[str, str], plan: PolicyPlan | None = None, *,
           private_dir: Path | None = None, layers: Layers | None = None,
           controller: gazetteer.Controller | None = None, client=None,
           use_cache: bool = True,
           groups: dict[str, tuple[str, str]] | None = None) -> Result:  # fmt: skip
    """Redact each text. `plan` identifies the release; controller values come from
    `private_dir/gazetteer_values.csv` (or `controller`). `groups` maps a record to its
    (conversation, speaker) so an id read out over several turns can be joined and validated.
    Logs hold counts and timings only."""
    t0 = time.monotonic()
    layers = layers or Layers()
    ctl = controller
    if ctl is None and private_dir is not None and layers.controller:
        ctl = gazetteer.load_controller(private_dir / "gazetteer_values.csv")
    if not layers.controller:
        ctl = None
    ids = list(texts)
    dvv: gazetteer.Dvv | None = None
    if layers.dvv:
        dvv = gazetteer.dvv_matcher([texts[i] for i in ids], frozenset(ctl.names) if ctl else frozenset())
    known = (frozenset(ctl.names) if ctl else frozenset()) | (dvv.safe if dvv else frozenset())
    # Rule layers first. The health layer only ever sees the text with those spans replaced by
    # typed placeholders, so no detected identifier is sent to the LLM.
    split_ids = crossturn.find(texts, groups) if (groups and layers.normalise) else {}
    base = {rid: merge(_candidates(texts[rid], layers, ctl, dvv, known) + split_ids.get(rid, []))
            for rid in ids}  # fmt: skip
    flagged: dict[str, list[Cand]] = {}
    health_stats: dict = {}
    if layers.health:
        masked = {rid: mask(texts[rid], base[rid]) for rid in ids}
        found, health_stats = health.find({rid: m.text for rid, m in masked.items()}, client,
                                          use_cache=use_cache)  # fmt: skip
        flagged = {rid: [Cand(*masked[rid].to_original(c.start, c.end), c.label, c.layer, c.score)
                         for c in cs] for rid, cs in found.items()}  # fmt: skip
    spans: dict[str, list[Span]] = {}
    out: dict[str, str] = {}
    sources: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    for rid in ids:
        text = texts[rid]
        merged = base[rid]
        if rid in flagged:
            merged = _apply_health(merged, flagged[rid])
        spans[rid] = [Span(rid, c.start, c.end, c.label, c.layer, min(1.0, c.score)) for c in merged]
        sources[rid] = [c.source for c in merged]
        pieces, pos = [], 0
        for c in merged:
            pieces += [text[pos : c.start], f"[{c.label}]"]
            pos = c.end
        out[rid] = "".join(pieces) + text[pos:]
        for c in merged:
            key = c.layer + (f":{c.source}" if c.source else "")
            counts[key] = counts.get(key, 0) + 1
    stats = {"records": len(ids), "layers": layers.names(), "spans": sum(counts.values()),
             "by_layer": counts, "health": health_stats, "duration_ms": int((time.monotonic() - t0) * 1000)}  # fmt: skip
    log.info(json.dumps({"stage": "redact", **{k: v for k, v in stats.items()}}))
    return Result(spans, out, sources, stats)


__all__ = ["Layers", "Result", "redact", "replace"]
