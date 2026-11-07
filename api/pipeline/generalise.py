"""Fixed generalisation of kept quasi-identifiers, then k-anonymity by suppression.

The rules copy the proving ground's B2 baseline (baselines/_common.py generalise): birth date
to year, age to 10-year bands with 80+, postcode to 3 digits, timestamp to the hour, GPS to 2
decimals, date to the day. No lattice search: one fixed level per subtype.

k is enforced on the quasi-identifiers the plan keeps, never on dropped ones. Rows in classes
smaller than k are suppressed while that stays within MAX_ROW_SUPPRESSION; past that, the most
detailed kept quasi-identifier is blanked in those rows only (B2-k's local suppression), one
column at a time, until the rest fits the row budget. pyCANON checks the result.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

K_TARGET = 5
MAX_ROW_SUPPRESSION = 0.02
TIMESTAMP_MIN_HIT = 0.9

# subtype -> level name. Anything else is kept exact.
LEVELS = {
    "BIRTH_DATE": "year",
    "AGE": "10-year band, 80+",
    "POSTCODE": "3 digits",
    "TIMESTAMP": "hour",
    "GPS_COORDINATE": "2 decimals",
    "DATE": "day",
}
EXACT = "exact"

_DOTTED = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{2,4}")


def _to_datetime(col: pd.Series) -> pd.Series:
    def one(v: str) -> pd.Timestamp:
        t = str(v).strip()
        if not t:
            return pd.NaT
        try:
            return pd.to_datetime(t, dayfirst=bool(_DOTTED.match(t)))
        except (ValueError, OverflowError):
            return pd.NaT

    return col.map(one)


def _num(col: pd.Series) -> pd.Series:
    return pd.to_numeric(col.str.strip().str.replace(",", ".", regex=False), errors="coerce")


def level_for(subtype: str, timestamp_hit: float) -> str:
    """The fixed level for a kept quasi-identifier. A TIMESTAMP label whose values do not parse
    as timestamps (for example a duration in seconds) is kept exact rather than destroyed."""
    if subtype == "TIMESTAMP" and timestamp_hit < TIMESTAMP_MIN_HIT:
        return EXACT
    return LEVELS.get(subtype, EXACT)


def apply_level(col: pd.Series, level: str) -> pd.Series:
    """Apply one fixed level. Empty or unparseable cells become empty."""
    if level == EXACT:
        return col
    if level == "year":
        d = _to_datetime(col)
        return d.dt.year.map(lambda v: "" if pd.isna(v) else str(int(v)))
    if level == "10-year band, 80+":
        lo = (np.floor(_num(col) / 10) * 10).clip(upper=80)
        return lo.map(lambda v: "" if pd.isna(v) else (f"{int(v)}+" if v >= 80
                                                       else f"{int(v)}-{int(v) + 9}"))  # fmt: skip
    if level == "3 digits":
        p = col.astype(str).str.replace(r"[^0-9]", "", regex=True).str[:3]
        return (p + "**").where(p.str.len() == 3, "")
    if level == "hour":
        d = _to_datetime(col)
        return d.dt.floor("h").dt.strftime("%Y-%m-%d %H:00").where(d.notna(), "")
    if level == "2 decimals":
        x = _num(col).round(2)
        return x.map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    if level == "day":
        d = _to_datetime(col)
        return d.dt.strftime("%Y-%m-%d").where(d.notna(), "")
    raise ValueError(f"unknown level {level!r}")


def class_sizes(df: pd.DataFrame, qis: list[str]) -> pd.Series:
    key = df[qis].astype(str).agg("|".join, axis=1)
    return key.map(key.value_counts())


def enforce_k(df: pd.DataFrame, qis: list[str], k: int = K_TARGET,
              max_rows: float = MAX_ROW_SUPPRESSION) -> tuple[pd.DataFrame, pd.Series, dict]:  # fmt: skip
    """Return (release, kept_mask over the input rows, stats). Counts only in stats."""
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
