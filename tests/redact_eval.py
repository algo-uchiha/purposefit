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


def load_train(limit: int | None):
    d = PG / "data" / "customer_service"
    conv = pd.read_csv(d / "conversations.csv", dtype=str, keep_default_na=False)
    turns = pd.read_csv(d / "turns.csv", dtype=str, keep_default_na=False)
    train = set(conv[conv.split == "train"].conversation_id)
    turns = turns[turns.conversation_id.isin(train)]
    if limit:
        turns = turns.head(limit)
    texts = dict(zip(turns.turn_id, turns.text, strict=True))
    gold = {}
    for line in (PG / "metadata" / "pii_spans" / "customer_service__turns__text.jsonl").open():
        r = json.loads(line)
        if r["record_id"] in texts:
            gold[r["record_id"]] = r["spans"]
    return texts, gold


def measure(texts, gold, private_dir, layers: Layers) -> dict:
    res = redact(texts, None, private_dir=private_dir, layers=layers)
    pred = {rid: [{"start": s.start, "end": s.end, "label": s.label} for s in sp]
            for rid, sp in res.spans.items()}  # fmt: skip
    sc = T.span_scores(gold, pred, mode="overlap", label_agnostic=True)["micro"]
    lk = T.redaction_leakage(gold, res.redacted)
    return {"layers": layers.names(), "identifying_leakage": lk["identifying_leakage_rate"],
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
    a = ap.parse_args()
    texts, gold = load_train(a.limit)
    priv = ROOT / "runs" / "private" / a.run
    runs = {"all layers": Layers(), "DVV gazetteer only (no controller)": Layers(controller=False)}
    if a.ablation:
        for name in ("patterns", "normalise", "controller", "dvv", "cues"):
            runs[f"without {name}"] = replace(Layers(), **{name: False})
        runs["patterns only"] = Layers(normalise=False, controller=False, dvv=False, cues=False)
    out = {}
    for name, ly in runs.items():
        m = measure(texts, gold, priv, ly)
        out[name] = m
        print(f"{name:40s} identifying_leakage={m['identifying_leakage']:.4f} "
              f"precision={m['precision']:.4f} recall={m['recall']:.4f} spans={m['n_spans']}")
    if a.fp:
        false_positives(texts, gold, priv, Layers())
        misses(texts, gold, priv, Layers())
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("per label (all layers):", {k: v for k, v in out["all layers"]["per_label"].items()})


if __name__ == "__main__":
    main()
