"""Stage 1: profile every column on up to 2,000 sampled rows.

Output holds counts and rates only, never cell values. Deterministic for a given seed.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from stdnum import iban as std_iban
from stdnum import luhn
from stdnum.fi import hetu as std_hetu

from api.pipeline import io
from api.pipeline.contracts import ColumnProfile
from api.pipeline.redact.gazetteer import dvv_names

log = logging.getLogger("purposefit.profile")

SAMPLE_ROWS = 2000

_HETU_LIKE = re.compile(r"^\d{6}\s?[-+A-FU-Y]?\s?\d{3}[0-9A-Y]$", re.IGNORECASE)
_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")
_PHONE = re.compile(r"^(\+358|00358|0)[\s-]?\d{1,3}([\s-]?\d){5,8}$")
_IPV4 = re.compile(r"^((25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(25[0-5]|2[0-4]\d|1?\d?\d)(/\d{1,2})?$")
_IPV6 = re.compile(r"^[0-9a-f]{0,4}(:[0-9a-f]{0,4}){2,7}$", re.IGNORECASE)
_MAC = re.compile(r"^[0-9a-f]{2}([:-][0-9a-f]{2}){5}$", re.IGNORECASE)
_HEX = re.compile(r"^[0-9a-f]{32,128}$", re.IGNORECASE)
_URL = re.compile(r"^(https?://|www\.)\S+$|^([a-z0-9-]+\.)+[a-z]{2,}(/\S*)?$", re.IGNORECASE)
_DATE = re.compile(
    r"^(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\.\d{1,2}\.(\d{4}|\d{2})|\d{1,2}/\d{1,2}/(\d{4}|\d{2}))$"
)
_PARTIAL_DATE = re.compile(r"^\d{4}(-\d{1,2})?([/-]\w{1,2})?$|^\d{4}-W\d{2}$|^\d{4}/\d{2,4}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}")
_POSTCODE = re.compile(r"^\d{5}$")
_PLATE = re.compile(r"^[A-ZÅÄÖ]{2,3}-\d{1,3}$")
_GPS = re.compile(r"^-?\d{1,3}\.\d{4,}$")
_INT = re.compile(r"^-?\d+$")
_DEC = re.compile(r"^-?(\d{1,3}([  ]\d{3})+|\d+)([.,]\d+)?$")
_PREFIX_CODE = re.compile(r"^[A-Z]{1,5}[-_]?\d{3,}$")
_WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)?")


def _hetu(v: str) -> bool:
    # Synthetic data uses individual numbers 900-999 (temporary ids), so allow them.
    return std_hetu.is_valid(v, allow_temporary=True)


def _iban(v: str) -> bool:
    return std_iban.is_valid(v)


def _card(v: str) -> bool:
    d = v.replace(" ", "").replace("-", "")
    return d.isdigit() and 13 <= len(d) <= 19 and luhn.is_valid(d)


def _person_name(v: str) -> bool:
    """Two to five capitalised words, at least one a DVV first name or surname."""
    first, last = dvv_names()
    words = v.replace(",", " ").split()
    if not 2 <= len(words) <= 5 or not all(w[:1].isupper() and w.replace("-", "").isalpha()
                                           for w in words):  # fmt: skip
        return False
    folded = [w.casefold() for w in words]
    return any(w in first for w in folded) and any(w in last or w in first for w in folded)


def _address(v: str) -> bool:
    return bool(re.search(r"[^\W\d_]{3,}\s+\d{1,4}\b", v)) and len(v) < 80


VALIDATORS: dict[str, Callable[[str], bool]] = {
    "hetu": _hetu,
    "hetu_like": lambda v: bool(_HETU_LIKE.match(v.strip())),
    "iban": _iban,
    "card": _card,
    "email": lambda v: bool(_EMAIL.match(v)),
    "phone": lambda v: bool(_PHONE.match(v.strip())),
    "ipv4": lambda v: bool(_IPV4.match(v)),
    "ipv6": lambda v: ":" in v and bool(_IPV6.match(v)) and not _MAC.match(v),
    "mac": lambda v: bool(_MAC.match(v)),
    "hex_hash": lambda v: bool(_HEX.match(v)),
    "url": lambda v: bool(_URL.match(v)) and not _EMAIL.match(v),
    "date": lambda v: bool(_DATE.match(v)),
    "partial_date": lambda v: bool(_PARTIAL_DATE.match(v)),
    "timestamp": lambda v: bool(_TIMESTAMP.match(v)),
    "postcode": lambda v: bool(_POSTCODE.match(v)),
    "plate": lambda v: bool(_PLATE.match(v)),
    "gps": lambda v: bool(_GPS.match(v)),
    "integer": lambda v: bool(_INT.match(v)),
    "decimal": lambda v: bool(_DEC.match(v)),
    "prefix_code": lambda v: bool(_PREFIX_CODE.match(v)),
    "person_name": _person_name,
    "address": _address,
    "sentence": lambda v: len(v.split()) >= 5 and len(_WORD.findall(v)) >= 4,
}


def _rate(values: pd.Series, fn: Callable[[str], bool]) -> float:
    return round(float(values.map(fn).mean()), 4) if len(values) else 0.0


def profile_column(dataset: str, table: str, column: str, col: pd.Series) -> ColumnProfile:
    filled = col[col.str.strip() != ""]
    n = len(col)
    lengths = filled.str.len()
    text = "".join(filled.head(500))
    total = max(len(text), 1)
    classes = {
        "alpha": sum(ch.isalpha() for ch in text) / total,
        "digit": sum(ch.isdigit() for ch in text) / total,
        "space": sum(ch.isspace() for ch in text) / total,
        "upper": sum(ch.isupper() for ch in text) / total,
        "punct": sum((not ch.isalnum()) and not ch.isspace() for ch in text) / total,
    }
    uniq = filled.drop_duplicates()
    # Validators run on distinct values (capped) so repeated values do not dominate.
    probe = uniq.head(400)
    return ColumnProfile(
        dataset=dataset,
        table=table,
        column=column,
        rows_sampled=n,
        fill_rate=round(len(filled) / n, 4) if n else 0.0,
        distinct_ratio=round(len(uniq) / len(filled), 4) if len(filled) else 0.0,
        len_min=int(lengths.min()) if len(filled) else 0,
        len_max=int(lengths.max()) if len(filled) else 0,
        len_mean=round(float(lengths.mean()), 2) if len(filled) else 0.0,
        char_classes={k: round(v, 4) for k, v in classes.items()},
        validator_hits={name: _rate(probe, fn) for name, fn in VALIDATORS.items()},
    )


def profile_table(dataset: str, table: str, df: pd.DataFrame, seed: int) -> list[ColumnProfile]:
    if len(df) > SAMPLE_ROWS:
        df = df.sample(n=SAMPLE_ROWS, random_state=seed)
    return [profile_column(dataset, table, c, df[c]) for c in df.columns]


def profile_dataset(dataset: str, seed: int, root: Path | None = None) -> list[ColumnProfile]:
    out: list[ColumnProfile] = []
    for table, path in io.dataset_tables(dataset, root):
        start = time.monotonic()
        df = io.read_csv(path)
        profs = profile_table(dataset, table, df, seed)
        out.extend(profs)
        log.info(json.dumps({"stage": "profile", "dataset": dataset, "table": table,
                             "rows_in": len(df), "columns": len(profs),
                             "duration_ms": int((time.monotonic() - start) * 1000)}))  # fmt: skip
    return out


def write_profiles(profiles: list[ColumnProfile], path: Path) -> None:
    path.write_text(json.dumps([p.to_dict() for p in profiles], indent=1), encoding="utf-8")


def read_profiles(path: Path) -> list[ColumnProfile]:
    return [ColumnProfile(**p) for p in json.loads(path.read_text(encoding="utf-8"))]
