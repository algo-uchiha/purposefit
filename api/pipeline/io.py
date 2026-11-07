"""Reading datasets. Every CSV is read with dtype=str, keep_default_na=False.

Only data/ is reachable from here. truth/, metadata/pii_spans, metadata/field_catalog.csv and
adversary/ are never read inside api/ (CLAUDE.md).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def data_root() -> Path:
    default = PROJECT_ROOT / "vendor" / "proving_ground" / "data"
    return Path(os.environ.get("PURPOSEFIT_DATA_DIR") or default)


def read_csv(path: Path, nrows: int | None = None) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, nrows=nrows)


def dataset_tables(dataset: str, root: Path | None = None) -> Iterator[tuple[str, Path]]:
    """Yield (table, path) for every CSV of a dataset, in name order."""
    base = (root or data_root()) / dataset
    if not base.is_dir():
        raise FileNotFoundError(f"dataset folder not found: {dataset}")
    for path in sorted(base.glob("*.csv")):
        yield path.stem, path


def list_datasets(root: Path | None = None) -> list[str]:
    base = root or data_root()
    return sorted(p.name for p in base.iterdir() if p.is_dir() and any(p.glob("*.csv")))
