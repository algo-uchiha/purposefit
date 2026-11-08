"""Stage 6: score a release with the organisers' scorecard (pets-eval) and log a leaderboard row.

This module and tests/ are the only code allowed to touch the scorer, which reads the public
field catalog. Nothing here feeds back into detect, plan or transform.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from api.pipeline import config, io
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
    return round(vals[name], 4), name if vals[name] > 0 else ""


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


def make_utility(dataset: str, scenario_id: str):
    """A scorer for the level search: mean of the scenario's required pets-eval utility tasks
    (unanswerable counts 0, as in the composite). Candidate tables are written and re-read the
    way the scorecard reads a release, so the search sees what the scorer will see."""
    import io as _io

    import pandas as pd

    _pets_eval()
    from pets_eval import io as pe_io
    from pets_eval.utility import all_tasks

    scen = pe_io.get_scenario(scenario_id, proving_ground_root())
    required = set(scen.get("utility_requirements", []))
    tasks = [t for t in all_tasks([dataset]) if t.id in required]
    orig = pe_io.load_tables(io.data_root() / dataset)

    def as_read(df: pd.DataFrame) -> pd.DataFrame:
        text = df.to_csv(index=False)
        dtype = {c: str for c in df.columns if pe_io._STRINGY.search(str(c))}
        return pd.read_csv(_io.StringIO(text), dtype=dtype, low_memory=False,
                           keep_default_na=True)  # fmt: skip

    def utility(prot: dict) -> float | None:
        p = {t: as_read(df) for t, df in prot.items()}
        scores = []
        for t in tasks:
            try:
                s = t.fn(orig, p)["score"]
            except Exception:  # noqa: BLE001  # nosec B112 (a failing task scores 0)
                s = None
            scores.append(0.0 if s is None else float(s))
        return sum(scores) / len(scores) if scores else None

    return utility


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _check(cid: str, name: str, kind: str, ok: bool, value, threshold, comparison: str,
           reason: str, source: str, details: list | None = None) -> dict:  # fmt: skip
    out = {"id": cid, "name": name, "kind": kind, "status": "pass" if ok else "fail",
           "value": value, "threshold": threshold, "comparison": comparison,
           "reason": reason, "source": source}  # fmt: skip
    if details is not None:
        out["details"] = details
    return out


def build_gate(ours: dict, baseline: dict | None, plan_policies: list[dict],
               scenario_id: str) -> dict:  # fmt: skip
    """Release gate from docs/ARCHITECTURE.md. Four checks, each with a plain reason.

    `ours` and `baseline` are pets-eval scorecards for the same scenario; `plan_policies` are
    the plan's policies as dicts (the k results written back by stage 4b). Thresholds live in
    api/pipeline/config.py. A missing input fails the check: the gate fails closed.
    """
    comps = ours.get("risk_components", {})
    checks = []

    # 1. Zero residual direct identifiers in structured columns.
    direct = {n: v for n, v in comps.items() if n.endswith("direct identifiers retained")}
    worst = max((v for v in direct.values() if v is not None), default=None)
    bad = [n.split(":")[0] for n, v in direct.items() if v is None or v > config.GATE_MAX_DIRECT_IDENTIFIERS]
    ok = bool(direct) and not bad
    reason = ("No direct identifier is retained in any released table." if ok else
              f"Direct identifiers are retained in: {', '.join(bad)}." if bad else
              "The scorecard has no direct-identifier measure, so this cannot be confirmed.")
    checks.append(_check("direct_identifiers", "Residual direct identifiers", "direct_identifiers",
                         ok, worst, config.GATE_MAX_DIRECT_IDENTIFIERS, "at_most", reason,
                         "pets-eval"))  # fmt: skip

    # 2. k >= 5 on the released quasi-identifiers, confirmed by pyCANON.
    ks = [p["params"] for p in plan_policies if p["action"] == "suppress_k"]
    if not ks:
        checks.append(_check("k_anonymity", "k-anonymity", "k", True, None, config.GATE_MIN_K,
                             "at_least", "No quasi-identifier is released, so there is nothing to "
                             "group.", "plan"))  # fmt: skip
    else:
        vals = [q.get("k_pycanon") for q in ks]
        low = min((v for v in vals if v is not None), default=None)
        ok = None not in vals and low is not None and low >= config.GATE_MIN_K
        reason = (f"pyCANON finds k = {low} on the released quasi-identifiers." if ok else
                  "pyCANON has not confirmed k for every released table." if None in vals else
                  f"pyCANON finds k = {low}, below the required {config.GATE_MIN_K}.")
        checks.append(_check("k_anonymity", "k-anonymity", "k", ok, low, config.GATE_MIN_K,
                             "at_least", reason, "pyCANON"))  # fmt: skip

    # 3. Every risk component lower than B2-k's on the same scenario.
    if baseline is None:
        checks.append(_check("risk_vs_baseline", "Risk components against B2-k", "baseline",
                             False, None, None, "lower_than", "No B2-k scorecard for this "
                             "scenario, so the comparison cannot be made.", "pets-eval"))  # fmt: skip
    else:
        base = baseline.get("risk_components", {})
        details, notlower = [], []
        for name in sorted(comps):
            if name not in base or comps[name] is None or base[name] is None:
                continue  # B2-k does not measure it (for example a withheld table)
            o, b = comps[name], base[name]
            good = o < b or o == b == 0.0
            details.append({"name": name, "ours": o, "baseline": b, "ok": good})
            if not good:
                notlower.append(name)
        ok = bool(details) and not notlower
        reason = (f"All {len(details)} shared risk components are lower than B2-k's, or zero "
                  "where B2-k is also zero." if ok else
                  "Not lower than B2-k: " + "; ".join(notlower) + "." if notlower else
                  "No risk component is shared with B2-k.")
        checks.append(_check("risk_vs_baseline", "Risk components against B2-k", "baseline", ok,
                             len(notlower), 0, "at_most", reason, "pets-eval", details))  # fmt: skip

    # 4. Identifying leakage in free text.
    rates = {}
    for tname, t in ours.get("tables", {}).items():
        for col, ft in t.get("free_text", {}).items():
            r = ft.get("identifying_leakage_rate")
            if r is not None and ft.get("evaluated", True) and ft.get("status") != "withheld":
                rates[f"{tname}.{col}"] = r
    if not rates:
        checks.append(_check("text_leakage", "Identifying leakage in free text", "text", True,
                             None, config.GATE_MAX_TEXT_LEAKAGE, "at_most",
                             "No free-text column is released.", "pets-eval"))  # fmt: skip
    else:
        name = max(rates, key=rates.get)
        v = rates[name]
        ok = v <= config.GATE_MAX_TEXT_LEAKAGE
        reason = (f"Identifying leakage is {v:.3f} in {name}, within the limit of "
                  f"{config.GATE_MAX_TEXT_LEAKAGE:.2f}." if ok else
                  f"Identifying leakage is {v:.3f} in {name}, above the limit of "
                  f"{config.GATE_MAX_TEXT_LEAKAGE:.2f}.")
        checks.append(_check("text_leakage", "Identifying leakage in free text", "text", ok,
                             round(v, 4), config.GATE_MAX_TEXT_LEAKAGE, "at_most", reason,
                             "pets-eval"))  # fmt: skip

    blocking = [c["id"] for c in checks if c["status"] == "fail"]
    return {"passed": not blocking, "scenario_id": scenario_id, "checks": checks,
            "blocking": blocking}  # fmt: skip


def baseline_scorecard(runs: Path, scenario_id: str) -> dict | None:
    """The saved B2-k scorecard for the scenario, if it has been produced."""
    f = runs / "private" / "baselines" / f"b2k_{scenario_id}" / "scorecard.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
