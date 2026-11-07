"""Stage 4: apply the plan to the original tables.

Writes runs/<run>/04_release/<table>.csv for released tables only. Row maps and the values
passed to the gazetteer go to runs/private/<run>/ and never into the release or the logs.
k-anonymity results (ours and pyCANON's) are written back into the plan.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import replace
from pathlib import Path

import pandas as pd

from api.pipeline import generalise as gen
from api.pipeline import io
from api.pipeline.contracts import FieldPolicy, PolicyPlan

log = logging.getLogger("purposefit.transform")

TOKEN_HEX = 20


def pseudonym(key: str, value: str) -> str:
    """Keyed pseudonym of one value. Equal inputs give equal outputs in every table."""
    v = value.strip()
    if not v:
        return ""
    return hmac.new(key.encode(), v.encode("utf-8"), hashlib.sha256).hexdigest()[:TOKEN_HEX]


def _apply_column(col: pd.Series, p: FieldPolicy, key: str) -> pd.Series:
    if p.action == "hmac":
        return col.map(lambda v: pseudonym(key, v))
    if p.action == "generalise":
        return gen.apply_level(col, p.params["level"])
    return col


def apply_plan(plan: PolicyPlan, run_path: Path, private_dir: Path, key: str,
               root: Path | None = None) -> tuple[PolicyPlan, dict]:  # fmt: skip
    t0 = time.monotonic()
    base = (root or io.data_root()) / plan.dataset
    release = run_path / "04_release"
    release.mkdir(parents=True, exist_ok=True)
    for old in release.glob("*.csv"):
        old.unlink()
    private_dir.mkdir(parents=True, exist_ok=True)

    by_table: dict[str, list[FieldPolicy]] = {}
    for p in plan.policies:
        by_table.setdefault(p.table, []).append(p)
    tables = {t: io.read_csv(base / f"{t}.csv") for t in by_table}
    record_key = {t: next((p.column for p in ps if p.params.get("role") == "record_key"), None)
                  for t, ps in by_table.items()}  # fmt: skip

    # Gazetteer: values of direct identifiers that are dropped or withheld.
    gaz = []
    for t, ps in by_table.items():
        for p in ps:
            if p.params.get("gazetteer"):
                vals = tables[t][p.column].str.strip()
                for v in sorted(set(vals[vals != ""])):
                    gaz.append((t, p.column, p.params["subtype"], v))
    pd.DataFrame(gaz, columns=["table", "column", "subtype", "value"]).to_csv(
        private_dir / "gazetteer_values.csv", index=False)

    out: dict[str, pd.DataFrame] = {}
    keep_rows: dict[str, pd.Series] = {}
    k_results: dict[str, dict] = {}
    for t in plan.released_tables:
        df = tables[t]
        cols = [p for p in by_table[t] if p.column != "*"
                and p.action not in ("drop", "withhold_table")]  # fmt: skip
        res = pd.DataFrame({p.column: _apply_column(df[p.column], p, key) for p in cols},
                           index=df.index)  # fmt: skip
        kp = next((p for p in by_table[t] if p.action == "suppress_k"), None)
        if kp:
            res, mask, stats = gen.enforce_k(res, kp.params["qis"], kp.params["k_target"],
                                             kp.params["max_row_suppression"])  # fmt: skip
            stats["k_pycanon"] = gen.pycanon_k(res, kp.params["qis"])
            k_results[t] = stats
            keep_rows[t] = mask
        out[t] = res

    # A suppressed row takes its child rows with it: drop rows whose join key points at it.
    cascaded: dict[str, int] = {}
    for t, mask in keep_rows.items():
        rk = record_key[t]
        if not rk or mask.all():
            continue
        gone = set(tables[t].loc[~mask, rk])
        for o in plan.released_tables:
            if o != t and rk in tables[o].columns and rk in out[o].columns:
                hit = tables[o].loc[out[o].index, rk].isin(gone)
                cascaded[o] = cascaded.get(o, 0) + int(hit.sum())
                out[o] = out[o][~hit]

    rows = {}
    for t, res in out.items():
        res.to_csv(release / f"{t}.csv", index=False)
        rk = record_key[t]
        if rk:
            pd.DataFrame({"protected_row": range(len(res)),
                          "original_record_id": tables[t].loc[res.index, rk].values}).to_csv(
                private_dir / f"rowmap_{t}.csv", index=False)  # fmt: skip
        rows[t] = {"rows_in": len(tables[t]), "rows_out": len(res),
                   "columns_out": int(res.shape[1])}  # fmt: skip

    policies = []
    for p in plan.policies:
        if p.action == "suppress_k" and p.table in k_results:
            r = k_results[p.table]
            p = replace(p, params={**p.params, "k": r["k"], "k_pycanon": r["k_pycanon"],
                                   "rows_suppressed": r["rows_suppressed"],
                                   "row_budget": r["row_budget"],
                                   "cells_blanked": r["cells_blanked"]})  # fmt: skip
        policies.append(p)
    ks = [r["k"] for r in k_results.values() if r["k"] is not None]
    plan = replace(plan, policies=policies, k=min(ks) if ks else plan.k)
    stats = {"tables": rows, "k": k_results, "rows_cascaded": cascaded,
             "gazetteer_values": len(gaz),
             "duration_ms": int((time.monotonic() - t0) * 1000)}  # fmt: skip
    (run_path / "04_transform_stats.json").write_text(json.dumps(stats, indent=1),
                                                      encoding="utf-8")  # fmt: skip
    log.info(json.dumps({"stage": "transform", "dataset": plan.dataset,
                         "scenario": plan.scenario_id, "tables_released": len(out),
                         "duration_ms": stats["duration_ms"]}))  # fmt: skip
    return plan, stats
