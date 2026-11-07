"""Generalisation of kept quasi-identifiers and k-anonymity, with a small level search.

Each kept quasi-identifier has a short ladder of levels (LADDERS). search_levels tries every
combination of levels for the kept quasi-identifiers of a table, keeps those that reach k >= 5
by suppressing at most MAX_ROW_SUPPRESSION of rows with no cell blanking, scores each with the
scenario's utility tasks, and picks the best. If none qualifies, the caller falls back to the
fixed B2 levels (LEVELS, copied from the proving ground's baselines/_common.py) and enforce_k,
which blanks cells past the row budget (B2-k's local suppression).

k is enforced on the quasi-identifiers the plan keeps, never on dropped ones. pyCANON checks it.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable

import numpy as np
import pandas as pd

K_TARGET = 5
MAX_ROW_SUPPRESSION = 0.02
TIMESTAMP_MIN_HIT = 0.9
MAX_SCORED = 200
EXACT = "exact"

# Fixed B2 levels: the fallback when no combination qualifies.
LEVELS = {
    "BIRTH_DATE": "year",
    "AGE": "10-year band, 80+",
    "POSTCODE": "3 digits",
    "TIMESTAMP": "hour",
    "GPS_COORDINATE": "2 decimals",
    "DATE": "day",
}
# Ladders for the search, finest first. Subtypes not listed have one level: exact.
LADDERS = {
    "TIMESTAMP": ["minute", "hour", "day", "week"],
    "AGE": [EXACT, "5-year band", "10-year band", "10-year band, 80+"],
    "POSTCODE": ["5 digits", "3 digits", "2 digits"],
    "BIRTH_DATE": ["day", "month", "year"],
    "DATE": ["day", "week", "month"],
    "GPS_COORDINATE": ["3 decimals", "2 decimals", "1 decimal"],
}

_DOTTED = re.compile(r"^\s*\d{1,2}\.\d{1,2}\.\d{2,4}")


def _to_datetime(col: pd.Series) -> pd.Series:
    col = col.astype(str).str.strip()
    dotted = col.str.match(_DOTTED)
    a = pd.to_datetime(col.where(~dotted & (col != "")), errors="coerce", format="mixed")
    b = pd.to_datetime(col.where(dotted), errors="coerce", format="mixed", dayfirst=True)
    return a.fillna(b)


def _num(col: pd.Series) -> pd.Series:
    return pd.to_numeric(col.astype(str).str.strip().str.replace(",", ".", regex=False),
                         errors="coerce")  # fmt: skip


def _timestamp_ok(subtype: str, timestamp_hit: float) -> bool:
    return subtype != "TIMESTAMP" or timestamp_hit >= TIMESTAMP_MIN_HIT


def level_for(subtype: str, timestamp_hit: float) -> str:
    """The fixed B2 level. A TIMESTAMP label whose values do not parse as timestamps is kept
    exact rather than destroyed."""
    return LEVELS.get(subtype, EXACT) if _timestamp_ok(subtype, timestamp_hit) else EXACT


def ladder_for(subtype: str, timestamp_hit: float) -> list[str]:
    return LADDERS.get(subtype, [EXACT]) if _timestamp_ok(subtype, timestamp_hit) else [EXACT]


def _band(col: pd.Series, width: int, top: int | None) -> pd.Series:
    lo = np.floor(_num(col) / width) * width
    if top is not None:
        lo = lo.clip(upper=top)

    def lab(v: float) -> str:
        if pd.isna(v):
            return ""
        if top is not None and v >= top:
            return f"{int(v)}+"
        return f"{int(v)}-{int(v) + width - 1}"

    return lo.map(lab)


def _digits(col: pd.Series, n: int) -> pd.Series:
    d = col.astype(str).str.replace(r"[^0-9]", "", regex=True)
    p = d.str[:n]
    return (p + "*" * (5 - n)).where(d.str.len() >= n, "")


def _dt(col: pd.Series, fmt: str) -> pd.Series:
    d = _to_datetime(col)
    return d.dt.strftime(fmt).where(d.notna(), "")


def _floor(col: pd.Series, unit: str, fmt: str) -> pd.Series:
    d = _to_datetime(col)
    return d.dt.floor(unit).dt.strftime(fmt).where(d.notna(), "")


def _week(col: pd.Series) -> pd.Series:
    d = _to_datetime(col)
    iso = d.dt.isocalendar()
    return (iso.year.astype("Int64").astype(str) + "-W"
            + iso.week.astype("Int64").astype(str).str.zfill(2)).where(d.notna(), "")  # fmt: skip


def _decimals(col: pd.Series, n: int) -> pd.Series:
    x = _num(col).round(n)
    return x.map(lambda v: "" if pd.isna(v) else f"{v:.{n}f}")


_APPLY: dict[str, Callable[[pd.Series], pd.Series]] = {
    "year": lambda c: _dt(c, "%Y"),
    "month": lambda c: _dt(c, "%Y-%m"),
    "day": lambda c: _dt(c, "%Y-%m-%d"),
    "week": _week,
    "hour": lambda c: _floor(c, "h", "%Y-%m-%d %H:00"),
    "minute": lambda c: _floor(c, "min", "%Y-%m-%d %H:%M"),
    "5-year band": lambda c: _band(c, 5, None),
    "10-year band": lambda c: _band(c, 10, None),
    "10-year band, 80+": lambda c: _band(c, 10, 80),
    "5 digits": lambda c: _digits(c, 5),
    "3 digits": lambda c: _digits(c, 3),
    "2 digits": lambda c: _digits(c, 2),
    "3 decimals": lambda c: _decimals(c, 3),
    "2 decimals": lambda c: _decimals(c, 2),
    "1 decimal": lambda c: _decimals(c, 1),
}


def apply_level(col: pd.Series, level: str) -> pd.Series:
    """Apply one level. Empty or unparseable cells become empty."""
    if level == EXACT:
        return col
    if level not in _APPLY:
        raise ValueError(f"unknown level {level!r}")
    return _APPLY[level](col)


def class_sizes(df: pd.DataFrame, qis: list[str]) -> pd.Series:
    key = df[qis].astype(str).agg("|".join, axis=1)
    return key.map(key.value_counts())


def search_levels(df: pd.DataFrame, ladders: dict[str, list[str]],
                  score: Callable[[pd.DataFrame], float | None] | None,
                  k: int = K_TARGET, max_rows: float = MAX_ROW_SUPPRESSION) -> dict:  # fmt: skip
    """Try every combination of levels. A combination qualifies if suppressing the rows in
    classes smaller than k stays within the row budget. Qualifying ones are scored (utility,
    higher is better); ties go to fewer suppressed rows, then the finer combination.

    Returns counts and the chosen and runner-up levels; `release` holds the chosen table.
    """
    qis = list(ladders)
    budget = int(np.floor(max_rows * len(df)))
    cols = {q: {lv: apply_level(df[q], lv) for lv in ladders[q]} for q in qis}
    qualifying = []
    combos = list(itertools.product(*(ladders[q] for q in qis)))
    for combo in combos:
        cand = pd.DataFrame({q: cols[q][lv] for q, lv in zip(qis, combo, strict=True)})
        small = class_sizes(cand, qis) < k
        if small.sum() <= budget:
            fineness = sum(ladders[q].index(lv) for q, lv in zip(qis, combo, strict=True))
            qualifying.append((combo, ~small, int(small.sum()), fineness))
    scored = []
    for combo, keep, n_sup, fineness in qualifying[:MAX_SCORED]:
        out = df.copy()
        for q, lv in zip(qis, combo, strict=True):
            out[q] = cols[q][lv]
        out = out[keep]
        u = score(out) if score else None
        scored.append({"levels": dict(zip(qis, combo, strict=True)),
                       "utility": None if u is None else round(float(u), 4),
                       "rows_suppressed": n_sup, "fineness": fineness, "release": out})  # fmt: skip
    scored.sort(key=lambda r: (-(r["utility"] if r["utility"] is not None else -1.0),
                               r["rows_suppressed"], r["fineness"]))  # fmt: skip
    result = {"tried": len(combos), "qualifying": len(qualifying), "scored": len(scored),
              "row_budget": budget, "chosen": None, "runner_up": None, "release": None}  # fmt: skip
    if scored:
        result["release"] = scored[0]["release"]
        result["chosen"] = {k_: v for k_, v in scored[0].items() if k_ not in ("release", "fineness")}
        if len(scored) > 1:
            result["runner_up"] = {k_: v for k_, v in scored[1].items()
                                   if k_ not in ("release", "fineness")}  # fmt: skip
    return result


def enforce_k(df: pd.DataFrame, qis: list[str], k: int = K_TARGET,
              max_rows: float = MAX_ROW_SUPPRESSION) -> tuple[pd.DataFrame, pd.Series, dict]:  # fmt: skip
    """Fallback. Return (release, kept_mask over the input rows, stats). Counts only in stats."""
    out = df.copy()
    keep = pd.Series(True, index=df.index)
    blanked: dict[str, int] = {}
    if not qis:
        return out, keep, {"qis": [], "rows_suppressed": 0, "cells_blanked": {}, "k": None}
    budget = int(np.floor(max_rows * len(df)))
    order = sorted(qis, key=lambda c: -out[c].nunique())
    for c in [None, *order]:
        if c is not None:
            small = class_sizes(out, qis) < k
            out.loc[small, c] = ""
            blanked[c] = int(small.sum())
        small = class_sizes(out, qis) < k
        if small.sum() <= budget:
            break
    keep = ~small
    out = out[keep]
    sizes = class_sizes(out, qis)
    return out, keep, {
        "qis": qis,
        "rows_suppressed": int((~keep).sum()),
        "row_budget": budget,
        "cells_blanked": blanked,
        "k": int(sizes.min()) if len(out) else None,
    }  # fmt: skip


def pycanon_k(df: pd.DataFrame, qis: list[str]) -> int | None:
    """k as computed by pyCANON, the independent check."""
    if not qis or df.empty:
        return None
    from pycanon import anonymity

    return int(anonymity.k_anonymity(df[qis].astype(str).reset_index(drop=True), qis))
