"""Layer 6 (lite): health mentions flagged by the LLM, behind a cue-word prefilter.

Only sentences with a health cue word are sent, each distinct sentence once, in batches with
id-keyed JSON answers. An answer is a span that must occur verbatim in its sentence; anything
else is dropped. The model never edits text: it only names a span, and the span is redacted
here. All calls go through llm.py, which caches and logs by call id.
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from api.pipeline.redact.merge import Cand

log = logging.getLogger("purposefit.redact.health")

BATCH = 40
PARALLEL = 4
MAX_SENTENCE_CHARS = 400
TOKENS_PER_ITEM = 60  # a span is about 15 tokens; the cap leaves room

# Stems in Finnish, Swedish and English. A cue only decides what the LLM is asked about.
CUES = re.compile(
    r"sairau|sairas|sairaa|lääk|diagno|masenn|diabet|syöpä|syövä|infarkt|dement|muistisair|leikka|"
    r"terapi|mielenterve|astma|epilep|vammai|allerg|raskau|kuntoutu|hoito|kipu|burnout|uupum|"
    r"sydän|aivo|verenpain|kemo|psykiat|ahdist|migreen|tauti|vaiva|kuulo|kuule|kuuro|näkö|sokea|"
    r"pyörätuol|liikuntarajoit|autis|adhd|tinnitus|dialyys|insuliin|proteesi|"
    r"sjuk|cancer|depress|demens|operation|medicin|läkare|ångest|hjärt|stroke|graviditet|rehab|"
    r"behandling|diabetes|funktionsneds|hörsel|hörapp|döv|rullstol|synskad|blind|"
    r"\bill\b|illness|disease|dementia|surgery|medic|doctor|anxiety|heart|therapy|disabled|"
    r"pregnan|asthma|treatment|hospital|injur|disabil|cardiac|chemo|medication|mental|diagnos|"
    r"cancer|sick|condition|stroke|epilep|allerg|blood pressure|migraine|burn.?out|hearing|deaf|"
    r"wheelchair|vision|autis|insulin|dialysis|prosthe",
    re.IGNORECASE,
)

RETRY_NOTE = ("Your earlier span was not an exact copy of the sentence. Copy the span character for "
              "character, keeping every inflection and letter exactly as written.")

SYSTEM = (
    "You review sentences from customer service chats for health information about a person "
    "(the customer, a relative or anyone else): a diagnosis, illness, injury, disability, "
    "pregnancy, medication, treatment, hospital stay, sick leave or a mental health condition. "
    "The sentences are in Finnish, Swedish or English. You get a JSON object with a list of "
    'sentences, each with an "id" and a "text". Answer with one JSON object only, keyed by the '
    'exact id of every sentence and no other keys: {"<id>": "<span>", ...}. The span is the '
    "shortest phrase copied exactly, character for character, from that sentence that states the "
    "health information. Use an empty string when the sentence says nothing about anyone's "
    "health. Mentioning a hospital only as an employer, a company or a place is not health "
    "information; a device or contract problem is not either."
)


def split_sentences(text: str) -> list[tuple[int, str]]:
    """(offset, sentence) pairs; sentences end at . ! ? or a line break."""
    out = []
    for m in re.finditer(r"[^.!?\n]+(?:[.!?]+|\n|$)", text):
        seg = m.group()
        lead = len(seg) - len(seg.lstrip())
        sent = seg.strip()
        if sent:
            out.append((m.start() + lead, sent))
    return out


def candidates(texts: dict[str, str]) -> dict[str, list[tuple[int, str]]]:
    """Per record, the sentences that pass the cue prefilter."""
    out: dict[str, list[tuple[int, str]]] = {}
    for rid, text in texts.items():
        hits = [(o, s) for o, s in split_sentences(text)
                if len(s) <= MAX_SENTENCE_CHARS and CUES.search(s)]  # fmt: skip
        if hits:
            out[rid] = hits
    return out


def parse(text: str, ids: list[str], sentences: dict[str, str]) -> dict[str, str]:
    """Verified span per id. The keys must be exactly `ids` or the batch is rejected (empty);
    a span that is not a verbatim part of its sentence is dropped."""
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return {}
    try:
        pairs = json.loads(text[a : b + 1], object_pairs_hook=list)
    except json.JSONDecodeError:
        return {}
    names = [k for k, _ in pairs]
    if len(names) != len(set(names)) or set(names) != set(ids):
        return {}
    out = {}
    for k, v in pairs:
        if isinstance(v, str) and v.strip() and v in sentences[k]:
            out[k] = v
    return out


def rejected_ids(text: str, sentences: dict[str, str]) -> list[str]:
    """Ids whose non-empty answer was dropped because the span is not in its sentence."""
    a, b = text.find("{"), text.rfind("}")
    try:
        d = json.loads(text[a : b + 1])
    except (ValueError, TypeError):
        return []
    return [k for k, v in d.items() if isinstance(v, str) and v.strip() and k in sentences
            and v not in sentences[k]]


def ask(sentences: list[str], client, *, use_cache: bool = True) -> tuple[dict[str, str], dict]:
    """Spans for distinct sentences. Returns ({sentence: span}, stats)."""
    stats = {"sentences": len(sentences), "calls": 0, "cached": 0, "failed_batches": 0,
             "prompt_tokens": 0, "output_tokens": 0, "thought_tokens": 0, "flagged": 0,
             "spans_not_verbatim": 0, "retried": 0}  # fmt: skip
    batches = [sentences[i : i + BATCH] for i in range(0, len(sentences), BATCH)]

    def run(batch: list[str], note: str | None = None):
        ids = {f"s{i}": s for i, s in enumerate(batch)}
        payload: dict = {"sentences": [{"id": k, "text": v} for k, v in ids.items()]}
        if note:
            payload = {"note": note, **payload}
        prompt = json.dumps(payload, ensure_ascii=False)
        try:
            resp = client.complete(prompt, system=SYSTEM, max_tokens=TOKENS_PER_ITEM * len(batch) + 128,
                                   use_cache=use_cache,
                                   validate=lambda t: _keys_ok(t, list(ids)))
        except Exception as exc:  # noqa: BLE001 (never block a run on the LLM)
            log.warning(json.dumps({"stage": "health", "event": "batch_failed",
                                    "error": type(exc).__name__}))  # fmt: skip
            return ids, None
        return ids, resp

    found: dict[str, str] = {}
    retry: list[str] = []

    def take(ids, resp) -> list[str]:
        """Record verified spans; return the sentences whose span was not verbatim."""
        if resp is None:
            stats["failed_batches"] += 1
            return []
        stats["calls"] += 1
        stats["cached"] += int(getattr(resp, "cached", False))
        for k in ("prompt_tokens", "output_tokens", "thought_tokens"):
            stats[k] += getattr(resp, k, 0)
        for k, span in parse(resp.text, list(ids), ids).items():
            found[ids[k]] = span
        bad = rejected_ids(resp.text, ids)
        stats["spans_not_verbatim"] += len(bad)
        return [ids[k] for k in bad]

    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        for ids, resp in pool.map(run, batches):
            retry += take(ids, resp)
        # One retry for answers whose span was reworded: ask again, asking for an exact copy.
        again = [retry[i : i + BATCH] for i in range(0, len(retry), BATCH)]
        for ids, resp in pool.map(lambda b: run(b, RETRY_NOTE), again):
            stats["retried"] += len(ids)
            take(ids, resp)
    stats["flagged"] = len(found)
    return found, stats


def _keys_ok(text: str, ids: list[str]) -> bool:
    """A reply is usable when it is one JSON object naming exactly the asked ids (an all-empty
    reply is valid: nothing flagged)."""
    a, b = text.find("{"), text.rfind("}")
    try:
        d = json.loads(text[a : b + 1])
    except (ValueError, TypeError):
        return False
    return isinstance(d, dict) and set(d) == set(ids)


def find(texts: dict[str, str], client, *, use_cache: bool = True) -> tuple[dict[str, list[Cand]], dict]:
    """HEALTH candidates per record. Needs an enabled client; otherwise nothing is flagged."""
    if client is None or not getattr(client, "enabled", False):
        return {}, {"status": "off"}
    cand = candidates(texts)
    distinct = sorted({s for hits in cand.values() for _, s in hits})
    spans, stats = ask(distinct, client, use_cache=use_cache)
    out: dict[str, list[Cand]] = {}
    for rid, hits in cand.items():
        for off, sent in hits:
            span = spans.get(sent)
            if span:
                i = sent.find(span)
                out.setdefault(rid, []).append(
                    Cand(off + i, off + i + len(span), "HEALTH", "health", 0.8))
    stats.update({"records_with_cue": len(cand),
                  "status": "partial" if stats["failed_batches"] else "ok"})
    log.info(json.dumps({"stage": "health", **stats}))
    return out, stats
