"""Measure the rule redactor on the customer_service TRAIN split (development only).

This file and verify.py are the only code allowed to read metadata/pii_spans. Never run on the
eval split. Usage:
  uv run --with ./vendor/proving_ground/toolkit --env-file .env python tests/redact_eval.py \
      [--run p4-CS-S1] [--json OUT] [--ablation] [--limit N]
Reports identifying leakage, span precision and recall (label-agnostic overlap), per-label
leakage, and with --ablation each layer switched off. The DVV-only line uses no controller values.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from pets_eval import text as T

from api.pipeline.redact import Layers, redact

PG = ROOT / "vendor" / "proving_ground"


GROUPS: dict = {}


def load_train(limit: int | None):
    d = PG / "data" / "customer_service"
    conv = pd.read_csv(d / "conversations.csv", dtype=str, keep_default_na=False)
    turns = pd.read_csv(d / "turns.csv", dtype=str, keep_default_na=False)
    train = set(conv[conv.split == "train"].conversation_id)
    turns = turns[turns.conversation_id.isin(train)]
    if limit:
        turns = turns.head(limit)
    texts = dict(zip(turns.turn_id, turns.text, strict=True))
    GROUPS.clear()
    GROUPS.update({t: (c, sp) for t, c, sp in zip(turns.turn_id, turns.conversation_id, turns.speaker, strict=True)})
    gold = {}
    for line in (PG / "metadata" / "pii_spans" / "customer_service__turns__text.jsonl").open():
        r = json.loads(line)
        if r["record_id"] in texts:
            gold[r["record_id"]] = r["spans"]
    return texts, gold


def health_precision(gold, res) -> dict:
    """Of the HEALTH spans we made, the share overlapping a gold HEALTH span; and of the gold
    HEALTH spans, the share overlapped by any span of ours (label-agnostic)."""
    pred = tp = gold_n = hit = 0
    for rid, sp in res.spans.items():
        g = [x for x in gold.get(rid, []) if x["label"] == "HEALTH"]
        gold_n += len(g)
        for s in sp:
            if s.label == "HEALTH":
                pred += 1
                tp += any(s.start < x["end"] and x["start"] < s.end for x in g)
        hit += sum(any(s.start < x["end"] and x["start"] < s.end for s in sp) for x in g)
    return {"health_precision": round(tp / pred, 4) if pred else None,
            "health_spans": pred, "health_recall": round(hit / gold_n, 4) if gold_n else None}


def measure(texts, gold, private_dir, layers: Layers, client=None) -> dict:
    res = redact(texts, None, private_dir=private_dir, layers=layers, client=client,
                 groups=GROUPS or None)
    pred = {rid: [{"start": s.start, "end": s.end, "label": s.label} for s in sp]
            for rid, sp in res.spans.items()}  # fmt: skip
    sc = T.span_scores(gold, pred, mode="overlap", label_agnostic=True)["micro"]
    lk = T.redaction_leakage(gold, res.redacted)
    hp = health_precision(gold, res)
    return {"layers": layers.names(), "health": res.stats.get("health", {}), **hp, "identifying_leakage": lk["identifying_leakage_rate"],
            "leakage": lk["leakage_rate"], "precision": sc["precision"], "recall": sc["recall"],
            "per_label": {k: v["rate"] for k, v in lk["per_label"].items()},
            "n_spans": res.stats["spans"], "by_layer": res.stats["by_layer"],
            "examples": lk["examples"][:12]}  # fmt: skip


def false_positives(texts, gold, private_dir, layers: Layers, top: int = 12) -> None:
    from collections import Counter

    res = redact(texts, None, private_dir=private_dir, layers=layers)
    by_layer: Counter = Counter()
    ex: dict = {}
    for rid, sp in res.spans.items():
        g = gold.get(rid, [])
        for s, src in zip(sp, res.sources[rid], strict=True):
            if not any(s.start < x["end"] and x["start"] < s.end for x in g):
                key = f"{s.layer}:{src}:{s.label}" if src else f"{s.layer}:{s.label}"
                by_layer[key] += 1
                ex.setdefault(key, Counter())[texts[rid][s.start : s.end].lower()] += 1
    print("false positives by layer:label", dict(by_layer.most_common(15)))
    for key, _ in by_layer.most_common(8):
        print("  ", key, ex[key].most_common(top))


def misses(texts, gold, private_dir, layers: Layers, top: int = 14) -> None:
    res = redact(texts, None, private_dir=private_dir, layers=layers)
    lk = T.redaction_leakage(gold, res.redacted)
    print("leak examples:", [(e["label"], e["value"]) for e in lk["examples"][:top]])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="p4-CS-S1")
    ap.add_argument("--json")
    ap.add_argument("--ablation", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--fp", action="store_true")
    ap.add_argument("--health", action="store_true", help="also run the LLM health layer")
    ap.add_argument("--health-only", action="store_true", help="only the base and the health run")
    a = ap.parse_args()
    texts, gold = load_train(a.limit)
    priv = ROOT / "runs" / "private" / a.run
    runs = {"all layers": Layers(health=False),
            "DVV gazetteer only (no controller)": Layers(controller=False, health=False)}  # fmt: skip
    client = None
    if a.health:
        from api.pipeline import llm

        client = llm.get_client()
        runs["all layers + health"] = Layers()
    if a.ablation:
        for name in ("patterns", "normalise", "controller", "dvv", "cues"):
            runs[f"without {name}"] = replace(Layers(health=False), **{name: False})
        runs["patterns only"] = Layers(normalise=False, controller=False, dvv=False, cues=False, health=False)
    out = {}
    for name, ly in runs.items():
        m = measure(texts, gold, priv, ly, client)
        out[name] = m
        print(f"{name:40s} identifying_leakage={m['identifying_leakage']:.4f} "
              f"precision={m['precision']:.4f} recall={m['recall']:.4f} spans={m['n_spans']} "
              f"HEALTH_leak={m['per_label'].get('HEALTH')} health_prec={m['health_precision']} "
              f"health_recall={m['health_recall']} {m['health'] or ''}")
    if a.fp:
        false_positives(texts, gold, priv, Layers(health=False))
        misses(texts, gold, priv, Layers(health=False))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("per label (all layers):", {k: v for k, v in out["all layers"]["per_label"].items()})


if __name__ == "__main__":
    main()
