"""Gazetteers. Two separate sources, reported separately:

controller: values the plan dropped or withheld as direct identifiers (runs/private/<run>/
            gazetteer_values.csv): names, national ids, phones, emails, addresses, ids.
dvv:        the public DVV first-name and surname lists (CC BY 4.0).

Matching is exact on whole values (any spoken or formatted variant that normalises to the
same characters) and token by token for names. Values are never logged.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from api.pipeline.redact.merge import Cand

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GAZETTEER_DIR = PROJECT_ROOT / "data" / "gazetteer"
MIN_FIRST_NAME_BEARERS = 5
MIN_SURNAME_BEARERS = 20
MIN_NAME_LEN = 3
# A name that is also a very common word in the texts is not matched from the public list.
COMMON_WORD_SHARE = 0.0005
# With no controller names the public list is the only name source, so the filter is loosened
# to the point where span precision on the train split stays above 0.95 (0.0013 gave 0.953).
COMMON_WORD_SHARE_DVV_ONLY = 0.0013
NAME_STOP = {"the", "and", "och", "det", "jag", "hej", "aalto", "tuuli", "lumi", "ilma", "satu",
             "sini", "mari", "onni", "toivo", "usko", "aino", "ville", "pelto", "metsä",
             "kallio", "koski", "salo", "järvi", "niemi", "mäki", "laine", "lahti",
             "nolla", "yksi", "kaksi", "kolme", "kuusi", "viisi", "neljä", "noll", "tre", "fem",
             "sex", "sju", "nio", "zero", "one", "two", "three", "four", "five", "six", "seven",
             "eight", "nine"}  # fmt: skip
_WORD = re.compile(r"[A-Za-zÅÄÖåäöÉéÜüÈè]+")
_ALNUM = re.compile(r"[0-9A-Za-zÅÄÖåäöÉéÜü]+")
ID_SUBTYPES = {"NATIONAL_ID": "NATIONAL_ID", "PHONE": "PHONE", "EMAIL": "EMAIL", "IBAN": "IBAN",
               "CUSTOMER_ID": "ACCOUNT_NUMBER", "ACCOUNT_ID": "ACCOUNT_NUMBER",
               "PAYMENT_CARD": "PAYMENT_CARD", "STUDENT_ID": "ACCOUNT_NUMBER",
               "EMPLOYEE_ID": "ACCOUNT_NUMBER", "PATIENT_ID": "ACCOUNT_NUMBER"}  # fmt: skip
MAX_TOKENS_PER_VALUE = 8
MAX_COMPACT = 40


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


def compact(value: str) -> str:
    return "".join(_ALNUM.findall(value)).casefold()


class Controller:
    """Controller values grouped for matching."""

    def __init__(self, rows: list[tuple[str, str]]):
        self.names: set[str] = set()
        self.ids: dict[str, str] = {}  # compact value -> span label
        self.phrases: dict[str, str] = {}  # compact address -> label
        for subtype, value in rows:
            if subtype == "PERSON_NAME":
                for tok in _WORD.findall(value):
                    if len(tok) >= MIN_NAME_LEN and tok.casefold() not in {"the", "and"}:
                        self.names.add(tok.casefold())
            elif subtype == "STREET_ADDRESS":
                c = compact(value)
                if len(c) >= 6:
                    self.phrases[c] = "ADDRESS"
            elif subtype in ID_SUBTYPES:
                c = compact(value)
                if len(c) >= 5:
                    self.ids[c] = ID_SUBTYPES[subtype]
                    if subtype == "PHONE":
                        d = re.sub(r"\D", "", value)
                        for v in ({d.removeprefix("358"), "0" + d[3:] if d.startswith("358") else d,
                                   "358" + d[1:] if d.startswith("0") else d}):
                            if len(v) >= 6:
                                self.ids[v] = "PHONE"
        self.lengths = sorted({len(k) for k in {**self.ids, **self.phrases}})

    @property
    def size(self) -> int:
        return len(self.names) + len(self.ids) + len(self.phrases)


def load_controller(path: Path) -> Controller:
    """Read runs/private/<run>/gazetteer_values.csv (table,column,subtype,value)."""
    if not path.exists():
        return Controller([])
    with path.open(encoding="utf-8", newline="") as f:
        rows = [(r["subtype"], r["value"]) for r in csv.DictReader(f)]
    return Controller(rows)


def common_words(texts: list[str], share: float = COMMON_WORD_SHARE) -> frozenset[str]:
    """Words found in more than `share` of the texts."""
    df: Counter[str] = Counter()
    for t in texts:
        df.update({w.casefold() for w in _WORD.findall(t)})
    cut = max(5, int(len(texts) * share))
    return frozenset(w for w, n in df.items() if n > cut)


def scan_values(text: str, table: dict[str, str], lengths: list[int]) -> list[tuple[int, int, str]]:
    """Whole-value matches: runs of alphanumeric tokens whose joined characters equal a value."""
    toks = [(m.start(), m.end(), m.group().casefold()) for m in _ALNUM.finditer(text)]
    out = []
    for i in range(len(toks)):
        acc = ""
        for j in range(i, min(i + MAX_TOKENS_PER_VALUE, len(toks))):
            acc += toks[j][2]
            if len(acc) > MAX_COMPACT:
                break
            if len(acc) in lengths and acc in table:
                out.append((toks[i][0], toks[j][1], table[acc]))
    return out


def scan_names(text: str, names: frozenset[str] | set[str]) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _WORD.finditer(text) if m.group().casefold() in names]


def controller_cands(text: str, ctl: Controller) -> list[Cand]:
    out = [Cand(s, e, lab, "gazetteer", 0.97, "controller")
           for s, e, lab in scan_values(text, {**ctl.ids, **ctl.phrases}, ctl.lengths)]  # fmt: skip
    out += [Cand(s, e, "PERSON", "gazetteer", 0.9, "controller") for s, e in scan_names(text, ctl.names)]
    return out


class Dvv:
    """Public names. `safe` are the tokens that may be matched: names that are not also common
    words of the texts being redacted. `first` and `last` keep the full lists for the cues."""

    def __init__(self, safe: frozenset[str], first: frozenset[str], last: frozenset[str]):
        self.safe, self.first, self.last = safe, first, last

    def __bool__(self) -> bool:
        return bool(self.safe or self.first)


def dvv_cands(text: str, dvv: Dvv) -> list[Cand]:
    out = [Cand(s, e, "PERSON", "gazetteer", 0.85, "dvv") for s, e in scan_names(text, dvv.safe)]
    return out


def dvv_matcher(texts: list[str], exclude: frozenset[str] = frozenset()) -> Dvv:
    """DVV names that may be matched: long enough, not stop words, and single tokens not
    common words of the texts (unless the controller also lists them as a name)."""
    first, last = dvv_names()

    def ok(names: frozenset[str]) -> frozenset[str]:
        return frozenset(n for n in names if len(n) >= MIN_NAME_LEN and n not in NAME_STOP and " " not in n)

    f, l_ = ok(first), ok(last)
    common = common_words(texts, COMMON_WORD_SHARE if exclude else COMMON_WORD_SHARE_DVV_ONLY)
    safe = frozenset(n for n in f | l_ if n not in common or n in exclude)
    return Dvv(safe, f, l_)
