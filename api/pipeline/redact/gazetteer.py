"""Gazetteers. Phase 2 uses only the DVV public name lists (CC BY 4.0) for detection.

Controller gazetteers and Aho-Corasick matching are added in Phase 5.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GAZETTEER_DIR = PROJECT_ROOT / "data" / "gazetteer"
MIN_FIRST_NAME_BEARERS = 5
MIN_SURNAME_BEARERS = 20


def _read_sheets(pattern: str, sheets: tuple[str, ...] | None, min_count: int) -> frozenset[str]:
    files = sorted(GAZETTEER_DIR.glob(pattern))
    if not files:
        return frozenset()
    import openpyxl

    wb = openpyxl.load_workbook(files[-1], read_only=True)
    names: set[str] = set()
    for ws in wb.worksheets:
        if sheets and ws.title not in sheets:
            continue
        for row in ws.iter_rows(min_row=2, values_only=True):
            ok = len(row) >= 2 and isinstance(row[0], str) and isinstance(row[1], (int, float))
            if ok and row[1] >= min_count and len(row[0]) > 1:
                names.add(row[0].strip().casefold())
    wb.close()
    return frozenset(names)


@lru_cache(maxsize=1)
def dvv_names() -> tuple[frozenset[str], frozenset[str]]:
    """(first names with >= 5 bearers, surnames with >= 20 bearers), casefolded.

    Empty sets when the lists have not been fetched (scripts/fetch_gazetteer.py).
    """
    first = _read_sheets("etunimitilasto-*.xlsx", ("Miehet kaikki", "Naiset kaikki"),
                         MIN_FIRST_NAME_BEARERS)  # fmt: skip
    last = _read_sheets("sukunimitilasto-*.xlsx", ("Nimet",), MIN_SURNAME_BEARERS)
    return first, last
