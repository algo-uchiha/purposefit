"""Score a labels file against the public field catalog with the organisers' scorer.

This script and tests/ are the only code allowed to read metadata/field_catalog.csv.
Usage:
  uv run --with ./vendor/proving_ground/toolkit python -m scripts.eval_detect PRED.csv [--json OUT]
Prints macro-F1, sensitive recall, subtype accuracy and per-role precision/recall for the
tune domains, the held-out domains and all nine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "vendor" / "proving_ground" / "metadata" / "field_catalog.csv"

# Fixed before any held-out score was looked at. Do not change.
TUNE_DOMAINS = ["customer_service", "cyber", "education", "finance", "health"]
HELDOUT_DOMAINS = ["energy", "mobility", "public_admin", "smart_city"]
SPLITS = {"tune": TUNE_DOMAINS, "heldout": HELDOUT_DOMAINS, "all": TUNE_DOMAINS + HELDOUT_DOMAINS}


def catalog() -> pd.DataFrame:
    return pd.read_csv(CATALOG, dtype=str, keep_default_na=False)


def score(pred: pd.DataFrame, splits: list[str]) -> dict:
    from pets_eval.detect import score_detection

    cat = catalog()
    return {s: score_detection(pred, cat, SPLITS[s]) for s in splits}


def table(results: dict) -> str:
    lines = []
    for split, r in results.items():
        lines.append(
            f"[{split}] fields={r['n_fields']} macro_f1={r['macro_f1']:.2f} "
            f"sensitive_recall={r['sensitive_recall']:.2f} "
            f"subtype_acc={r.get('subtype_accuracy') or 0:.2f} accuracy={r['accuracy']:.2f}"
        )
        lines.append(f"  {'role':22} {'prec':>5} {'rec':>5} {'f1':>5} {'n':>4}")
        for role, m in r["per_role"].items():
            lines.append(
                f"  {role:22} {m['precision']:5.2f} {m['recall']:5.2f} {m['f1']:5.2f} "
                f"{m['support']:4d}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pred")
    ap.add_argument("--splits", default="tune,heldout,all")
    ap.add_argument("--json")
    ap.add_argument("--errors", type=int, default=0, help="print N errors (tune split only)")
    a = ap.parse_args(argv)
    pred = pd.read_csv(a.pred, dtype=str, keep_default_na=False)
    splits = a.splits.split(",")
    res = score(pred, splits)
    print(table(res))
    if a.errors and "tune" in res:
        for e in res["tune"]["errors"][: a.errors]:
            print(e)
    if a.json:
        slim = {s: {k: v for k, v in r.items() if k not in ("errors", "confusion")}
                for s, r in res.items()}  # fmt: skip
        Path(a.json).write_text(json.dumps(slim, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
