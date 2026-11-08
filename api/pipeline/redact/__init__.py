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
from api.pipeline.redact import cues, gazetteer, normalise, patterns
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


def redact(texts: dict[str, str], plan: PolicyPlan | None = None, *,
           private_dir: Path | None = None, layers: Layers | None = None,
           controller: gazetteer.Controller | None = None) -> Result:  # fmt: skip
    """Redact each text. `plan` identifies the release; controller values come from
    `private_dir/gazetteer_values.csv` (or `controller`). Logs hold counts and timings only."""
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
    spans: dict[str, list[Span]] = {}
    out: dict[str, str] = {}
    sources: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    for rid in ids:
        text = texts[rid]
        merged = merge(_candidates(text, layers, ctl, dvv, known))
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
             "by_layer": counts, "duration_ms": int((time.monotonic() - t0) * 1000)}  # fmt: skip
    log.info(json.dumps({"stage": "redact", **{k: v for k, v in stats.items()}}))
    return Result(spans, out, sources, stats)


__all__ = ["Layers", "Result", "redact", "replace"]
