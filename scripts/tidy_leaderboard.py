"""Keep only final-* rows and the baseline rows in runs/leaderboard.csv; move the rest to
runs/leaderboard_history.csv. Baseline rows (B0, B2, B2-k) are rebuilt from the scorecards that
baselines/protect.py wrote under runs/private/baselines/.

  uv run --with ./vendor/proving_ground/toolkit python -m scripts.tidy_leaderboard
"""

from __future__ import annotations

import csv
import json

from api import cli
from api.pipeline import verify as vf

RUNS = cli.runs_dir()
NAMES = {"b0": "B0 (rerun)", "b2": "B2 (rerun)", "b2k": "B2-k (rerun)"}


def main() -> None:
    lb, hist = RUNS / "leaderboard.csv", RUNS / "leaderboard_history.csv"
    rows = list(csv.DictReader(lb.open(encoding="utf-8")))
    old = list(csv.DictReader(hist.open(encoding="utf-8"))) if hist.exists() else []
    keep = [r for r in rows if r["run_id"].startswith("final-")]
    move = [r for r in rows if not r["run_id"].startswith("final-") and not r["run_id"].startswith(("b0_", "b2_", "b2k_"))]
    base = []
    for level in ("b0", "b2", "b2k"):
        for scen in ("CS-S1", "CS-S2", "CS-S3"):
            f = RUNS / "private" / "baselines" / f"{level}_{scen}" / "scorecard.json"
            if not f.exists():
                continue
            rep = json.loads(f.read_text(encoding="utf-8"))
            k = 5 if level == "b2k" else None
            row = vf.leaderboard_row(rep, f"{level}_{scen}", "vendor", NAMES[level], k=k,
                                     note=f"proving ground baseline {level}; catalog labels; regex text redaction")  # fmt: skip
            base.append(row)
    with hist.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=vf.LEADERBOARD_COLUMNS)
        w.writeheader()
        w.writerows(old + move)
    with lb.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=vf.LEADERBOARD_COLUMNS)
        w.writeheader()
        w.writerows(base + keep)
    print(json.dumps({"kept": len(base) + len(keep), "moved": len(move)}))


if __name__ == "__main__":
    main()
