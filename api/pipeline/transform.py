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
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pandas as pd

from api.pipeline import config, io
from api.pipeline import generalise as gen
from api.pipeline.contracts import FieldPolicy, PolicyPlan

log = logging.getLogger("purposefit.transform")

PREFIXES = {"conversation_id": "cv", "customer_id": "cu", "patient_id": "pt", "account_id": "ac",
            "employee_id": "em", "student_id": "st", "card_id": "cd", "device_id": "dv",
            "session_id": "ss", "user_id": "us", "turn_id": "tn"}  # fmt: skip


def prefix_for(column: str) -> str:
    """Two lowercase letters naming the column, never digits, so a pseudonym cannot pass for
    a phone number, card or other identifier. Known columns use PREFIXES; others take the
    first two letters of the name."""
    known = PREFIXES.get(column.strip().lower())
    if known:
        return known
    letters = [c for c in column.lower() if "a" <= c <= "z"]
    return ("".join(letters[:2]) or "id").ljust(2, "x")


def derive_key(master_key: str, scenario_id: str) -> str:
    """Per-recipient key: HMAC(master, "purposefit-v1|" + scenario id). The same id gets
    different pseudonyms in two scenarios, so two recipients cannot link their releases."""
    return hmac.new(master_key.encode(), f"purposefit-v1|{scenario_id}".encode(),
                    hashlib.sha256).hexdigest()  # fmt: skip


def pseudonym(key: str, value: str, column: str = "id") -> str:
    """Keyed pseudonym of one value: a letter prefix per column, then lowercase hex.
    Equal inputs give equal outputs in every table that uses the same column name."""
    v = value.strip()
    if not v:
        return ""
    digest = hmac.new(key.encode(), v.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{prefix_for(column)}_{digest[:config.PSEUDONYM_HEX]}"


def _apply_column(col: pd.Series, p: FieldPolicy, key: str) -> pd.Series:
    if p.action == "hmac":
        return col.map(lambda v: pseudonym(key, v, p.column))
    if p.action == "generalise":
        return gen.apply_level(col, p.params["level"])
    return col


def apply_plan(plan: PolicyPlan, run_path: Path, private_dir: Path, key: str,  # master key
               root: Path | None = None,
               utility: Callable[[dict[str, pd.DataFrame]], float | None] | None = None,
               ) -> tuple[PolicyPlan, dict]:  # fmt: skip
    """`utility` scores a candidate release (dict of tables) for the level search; without it
    the search keeps the qualifying combination with the fewest suppressed rows, then the finest."""
    t0 = time.monotonic()
    key = derive_key(key, plan.scenario_id)  # callers pass the master key
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

    # First pass: every released table with its non-k transforms; kept quasi-identifiers raw.
    out: dict[str, pd.DataFrame] = {}
    for t in plan.released_tables:
        df = tables[t]
        cols = [p for p in by_table[t] if p.column != "*"
                and p.action not in ("drop", "withhold_table")]  # fmt: skip
        out[t] = pd.DataFrame({p.column: df[p.column] if p.params.get("quasi_identifier")
                               else _apply_column(df[p.column], p, key) for p in cols},
                              index=df.index)  # fmt: skip

    # Second pass: level search per table with kept quasi-identifiers; fallback if none fits.
    keep_rows: dict[str, pd.Series] = {}
    k_results: dict[str, dict] = {}
    chosen_levels: dict[tuple[str, str], str] = {}
    for t in plan.released_tables:
        kp = next((p for p in by_table[t] if p.action == "suppress_k"), None)
        if not kp:
            continue
        qis, kt, mr = kp.params["qis"], kp.params["k_target"], kp.params["max_row_suppression"]
        qpol = {p.column: p for p in by_table[t] if p.column in qis}
        ladders = {q: qpol[q].params.get("ladder") or [qpol[q].params["level"]] for q in qis}
        score = None
        if utility is not None:
            def score(cand: pd.DataFrame, t=t) -> float | None:
                return utility({**out, t: cand})
        found = gen.search_levels(out[t], ladders, score, kt, mr)
        search = {k_: v for k_, v in found.items() if k_ != "release"}
        if found["chosen"]:
            res = found["release"]
            levels = found["chosen"]["levels"]
            mask = out[t].index.isin(res.index)
            stats = {"qis": qis, "rows_suppressed": int((~mask).sum()),
                     "row_budget": found["row_budget"], "cells_blanked": {},
                     "k": int(gen.class_sizes(res, qis).min()) if len(res) else None,
                     "method": "level search"}  # fmt: skip
        else:
            levels = {q: qpol[q].params["fallback_level"] if "fallback_level" in qpol[q].params
                      else qpol[q].params["level"] for q in qis}  # fmt: skip
            fixed = out[t].copy()
            for q, lv in levels.items():
                fixed[q] = gen.apply_level(fixed[q], lv)
            res, mask, stats = gen.enforce_k(fixed, qis, kt, mr)
            stats["method"] = "fallback: fixed B2 levels and cell blanking"
            mask = mask.to_numpy()
        stats["k_pycanon"] = gen.pycanon_k(res, qis)
        stats["search"] = search
        for q, lv in levels.items():
            chosen_levels[(t, q)] = lv
        k_results[t] = stats
        keep_rows[t] = pd.Series(mask, index=out[t].index)
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
                                   "cells_blanked": r["cells_blanked"],
                                   "method": r["method"], "search": r["search"]})  # fmt: skip
        elif (p.table, p.column) in chosen_levels:
            lv = chosen_levels[(p.table, p.column)]
            r = k_results[p.table]
            used = p.reason.split(";")[0]
            if r["method"] == "level search":
                ru = (r["search"].get("runner_up") or {}).get("levels", {}).get(p.column)
                why = f"{used}; level {lv} chosen by search" + (
                    f", runner-up {ru}" if ru else "")  # fmt: skip
            else:
                why = f"{used}; no level combination reached k >= 5, fixed B2 level {lv}"
            p = replace(p, action="keep" if lv == gen.EXACT else "generalise", reason=why,
                        params={**p.params, "level": lv})  # fmt: skip
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
