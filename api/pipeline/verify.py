"""Stage 6: score a release with the organisers' scorecard (pets-eval) and log a leaderboard row.

This module and tests/ are the only code allowed to touch the scorer, which reads the public
field catalog. Nothing here feeds back into detect, plan or transform.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from api.pipeline import io
from api.pipeline.plan import _pets_eval, proving_ground_root

log = logging.getLogger("purposefit.verify")

LEADERBOARD_COLUMNS = ["created_utc", "run_id", "git_hash", "dataset", "scenario", "method",
                       "privacy", "utility", "composite", "worst_risk", "worst_risk_component", "k", "k_pycanon",
                       "utility_tasks", "note"]  # fmt: skip


def run_scorecard(dataset: str, scenario: str, release_dir: Path, rowmap_dir: Path,
                  out_dir: Path) -> dict:  # fmt: skip
    _pets_eval()
    from pets_eval.scorecard import run_scorecard as pe_scorecard

    rowmaps = {f.stem[len("rowmap_"):]: f for f in rowmap_dir.glob("rowmap_*.csv")}
    t0 = time.monotonic()
    rep = pe_scorecard(io.data_root() / dataset, release_dir, scenario=scenario,
                       root=proving_ground_root(), rowmaps=rowmaps, out_dir=out_dir)  # fmt: skip
    log.info(json.dumps({"stage": "verify", "dataset": dataset, "scenario": scenario,
                         "duration_ms": int((time.monotonic() - t0) * 1000)}))  # fmt: skip
    return rep


def worst_risk(rep: dict) -> tuple[float | None, str]:
    """The largest risk component and its name, as the scorecard reports it."""
    vals = {k: v for k, v in rep.get("risk_components", {}).items() if v is not None}
    if not vals:
        return None, ""
    name = max(vals, key=vals.get)
    return round(vals[name], 4), name


def leaderboard_row(rep: dict, run_id: str, git_hash: str, method: str, k=None,
                    k_pycanon=None, note: str = "") -> dict:  # fmt: skip
    s = rep["summary"]
    scen = rep.get("scenario")
    tasks = {u["id"]: (None if u["score"] is None else round(u["score"], 4))
             for u in rep.get("utility", []) if u.get("required")}  # fmt: skip
    return {"created_utc": datetime.now(UTC).isoformat(timespec="seconds"), "run_id": run_id,
            "git_hash": git_hash, "dataset": rep["dataset"],
            "scenario": scen["id"] if isinstance(scen, dict) else scen, "method": method,
            "privacy": s["privacy"], "utility": s["utility"], "composite": s["composite"],
            "worst_risk": worst_risk(rep)[0], "worst_risk_component": worst_risk(rep)[1], "k": k, "k_pycanon": k_pycanon,
            "utility_tasks": json.dumps(tasks), "note": note}  # fmt: skip


def append_leaderboard(path: Path, row: dict) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LEADERBOARD_COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)
