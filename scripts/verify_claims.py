"""Check every number quoted in README.md against the run files and the leaderboard.

A quoted number is written `0.9817 <!--c:lb.final-CS-S1.composite-->`. The script
  1. reads those markers from README.md;
  2. compares each value with docs/claims.json (a snapshot of the computed claims);
  3. when the run files exist (runs/leaderboard.csv), recomputes every claim from them and
     compares again; --write refreshes docs/claims.json from the run files first.
Without run files (CI) only steps 1 and 2 run. Exit code 1 on any difference.

  make verify-claims            # locally, needs the runs and the proving ground
  uv run python -m scripts.verify_claims --write
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
README = ROOT / "README.md"
SNAPSHOT = ROOT / "docs" / "claims.json"
MARK = re.compile(r"([0-9][0-9.,]*%?)\s*<!--c:([\w.\-]+)-->")
LB_RUNS = ["b0_CS-S1", "b2_CS-S1", "b2k_CS-S1", "final-CS-S1", "final-CS-S1-nollm", "final-CS-S2",
           "final-CS-S3", "b2k_CS-S3"]  # fmt: skip
STAGES = ("profile", "detect", "plan", "transform", "redact", "report", "verify")


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def computed() -> dict[str, str]:
    out: dict[str, str] = {}
    for r in csv.DictReader((RUNS / "leaderboard.csv").open(encoding="utf-8")):
        if r["run_id"] in LB_RUNS:
            for f in ("privacy", "utility", "composite", "worst_risk"):
                out[f"lb.{r['run_id']}.{f}"] = f"{float(r[f]):.4f}"
    ev = load(RUNS / "redact-train-full.json")  # tests/redact_eval.py --ablation --health
    rules, with_health = ev["all layers"], ev["all layers + health"]
    out["health.train_before"] = pct(rules["per_label"]["HEALTH"])
    out["health.train_after"] = pct(with_health["per_label"]["HEALTH"])
    out["health.train_precision"] = f"{with_health['health_precision']:.2f}"
    out["redact.train_leakage"] = f"{rules['identifying_leakage']:.4f}"
    out["redact.train_precision"] = f"{rules['precision']:.4f}"
    dvv = ev["DVV gazetteer only (no controller)"]
    out["redact.dvvonly_leakage"] = f"{dvv['identifying_leakage']:.4f}"
    out["redact.dvvonly_precision"] = f"{dvv['precision']:.4f}"
    out["redact.nationalid_after"] = pct(rules["per_label"]["NATIONAL_ID"])
    out["redact.nationalid_before"] = pct(load(RUNS / "p5-redact-train-full.json")["all layers"]["per_label"]["NATIONAL_ID"])
    ours = load(RUNS / "final-CS-S1" / "06_scorecard_ours" / "scorecard.json")
    out["health.release_after"] = pct(ours["tables"]["turns"]["free_text"]["text"]["per_label"]["HEALTH"]["rate"])
    h = with_health["health"]
    out["health.train_calls"] = str(h["calls"])
    out["health.train_prompt_tokens"] = f"{h['prompt_tokens']:,}"
    out["health.train_output_tokens"] = f"{h['output_tokens']:,}"
    out["health.release_calls"] = str(load(RUNS / "final-CS-S1" / "00_manifest.json")["llm_answers_redact"]["calls"])
    for run in ("final-CS-S1", "final-CS-S1-nollm"):
        ms = load(RUNS / run / "00_manifest.json")["stage_ms"]
        for s in STAGES:
            out[f"timing.{run}.{s}"] = f"{ms[s] / 1000:.1f}"
    out.update(detection())
    return out


def detection() -> dict[str, str]:
    import pandas as pd

    sys.path.insert(0, str(ROOT))
    from scripts.eval_detect import score

    out = {}
    files = {"rules": RUNS / "final-detect-rules" / "02_labels.csv",
             "llm": RUNS / "final-detect-llm" / "02_labels.csv",
             "b1": ROOT / "vendor" / "proving_ground" / "results" / "b1_field_labels.csv"}  # fmt: skip
    for name, f in files.items():
        res = score(pd.read_csv(f, dtype=str, keep_default_na=False), ["heldout", "all"])
        for split in ("heldout", "all"):
            out[f"detect.{name}.{split}.macro_f1"] = f"{res[split]['macro_f1']:.2f}"
            out[f"detect.{name}.{split}.sensitive_recall"] = f"{res[split]['sensitive_recall']:.2f}"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="refresh docs/claims.json from the run files")
    ap.add_argument("--fix-readme", action="store_true",
                    help="rewrite the quoted values in README.md from the run files (then review the text)")
    a = ap.parse_args()
    if a.fix_readme and (RUNS / "leaderboard.csv").exists():
        fresh_now = computed()
        text = MARK.sub(lambda m: f"{fresh_now.get(m.group(2), m.group(1))} <!--c:{m.group(2)}-->",
                        README.read_text(encoding="utf-8"))  # fmt: skip
        README.write_text(text, encoding="utf-8")
    quoted = [(m.group(2), m.group(1)) for m in MARK.finditer(README.read_text(encoding="utf-8"))]
    if not quoted:
        print("README.md quotes no checked numbers")
        return 1
    have_runs = (RUNS / "leaderboard.csv").exists()
    if have_runs:
        fresh = computed()
        if a.write:
            SNAPSHOT.write_text(json.dumps(dict(sorted(fresh.items())), indent=1) + "\n", encoding="utf-8")
    snap = load(SNAPSHOT)
    bad = []
    for key, value in quoted:
        if snap.get(key) != value:
            bad.append(f"{key}: README says {value}, docs/claims.json has {snap.get(key)}")
        if have_runs and fresh.get(key) != value:
            bad.append(f"{key}: README says {value}, the run files give {fresh.get(key)}")
    if have_runs:
        for key in snap:
            if key in fresh and snap[key] != fresh[key]:
                bad.append(f"{key}: docs/claims.json has {snap[key]}, the run files give {fresh[key]}")
    for line in bad:
        print("DIFF", line)
    mode = "against the run files and the snapshot" if have_runs else "against the snapshot only (no run files)"
    print(f"{len(quoted)} quoted numbers checked {mode}: {'FAILED' if bad else 'all match'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
