"""Layer 2: turn spoken digits (fi, sv, en) and spelled emails into text layer 1 can read.

`normalise(text)` returns the rewritten text and a map from each rewritten character back to
the (start, end) range of the original text it came from, so spans found in the rewritten
text can be placed on the original.
"""

from __future__ import annotations

import re
from typing import NamedTuple

DIGITS = {
    "nolla": "0", "yksi": "1", "kaksi": "2", "kolme": "3", "neljä": "4", "viisi": "5",
    "kuusi": "6", "seitsemän": "7", "kahdeksan": "8", "yhdeksän": "9",
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "noll": "0", "ett": "1", "en": "1", "två": "2", "tre": "3", "fyra": "4", "fem": "5",
    "sex": "6", "sju": "7", "åtta": "8", "nio": "9",
}  # fmt: skip
# Words that stand for a separator inside an identifier. "en" is a digit only inside a run.
SEPS = {"viiva": "-", "streck": "-", "dash": "-", "bindestreck": "-", "miinus": "-",
        "plus": "+", "pluss": "+"}  # fmt: skip
LETTER_NAMES = {"äm": "m", "ää": "a", "bee": "b", "cee": "c", "dee": "d", "ef": "f", "äf": "f",
                "gee": "g", "haa": "h", "jii": "j", "koo": "k", "äl": "l", "än": "n",
                "pee": "p", "kuu": "q", "är": "r", "äs": "s", "tee": "t", "vee": "v",
                "äks": "x", "yy": "y", "tsetta": "z"}  # fmt: skip
AT = r"(?:at|ät|snabel-a|snabela|miukumauku|kissanhäntä)"
DOT = r"(?:dot|piste|punkt|prick)"
UND = r"(?:alaviiva|underscore|understreck)"
_W = r"[\wåäöÅÄÖ]+"

_DW = "|".join(sorted((k for k in DIGITS if k != "en"), key=len, reverse=True))
_TOK = rf"(?:{_DW}|\d+|{'|'.join(SEPS)})"
_RUN = re.compile(
    rf"(?<![\wåäö])(?:[fF]\s?[iI]\s)?(?:{_TOK}(?![\wåäö])[\s,.]*)+", re.IGNORECASE)
_EMAIL = re.compile(
    rf"(?<![\wåäö])({_W}(?:\s(?:{DOT}|{UND})\s{_W})*)\s{AT}\s({_W}(?:\s{DOT}\s{_W})+)(?![\wåäö])",
    re.IGNORECASE)


class Normalised(NamedTuple):
    text: str
    origin: list[tuple[int, int]]  # per rewritten char: (start, end) in the original
    edits: list[tuple[int, int, str]]  # (start, end, rewritten text) in the original


def _email_text(m: re.Match) -> str:
    def part(s: str) -> str:
        s = re.sub(rf"\s{UND}\s", "_", s, flags=re.IGNORECASE)
        s = re.sub(rf"\s{DOT}\s", ".", s, flags=re.IGNORECASE)
        return s

    return part(m.group(1)) + "@" + part(m.group(2))


def _run_text(raw: str) -> str | None:
    """Digits and separators of a spoken run, or None when it is not a spoken identifier."""
    toks = re.findall(r"[\wåäö]+", raw.lower())
    out, n_words, n_digits = [], 0, 0
    for t in toks:
        if t in DIGITS:
            out.append(DIGITS[t]); n_words += 1; n_digits += 1
        elif t in SEPS:
            out.append(SEPS[t]); n_words += 1
        elif t.isdigit():
            out.append(t); n_digits += len(t)
        elif len(t) == 1:
            out.append(t)
    if n_words < 1 or n_digits < 4:
        return None
    return "".join(out)


def _edits(text: str) -> list[tuple[int, int, str]]:
    edits: list[tuple[int, int, str]] = []
    for m in _EMAIL.finditer(text):
        edits.append((m.start(), m.end(), _email_text(m)))
    taken = [(s, e) for s, e, _ in edits]
    for m in _RUN.finditer(text):
        s, e = m.start(), m.end()
        raw = text[s:e].rstrip(" ,.")
        e = s + len(raw)
        # a trailing check letter, spoken or single, after a dash: "... viiva 947 x" / "... äm"
        tail = re.match(r"[\s,]+([A-Za-zäåö]{1,4})(?![\wåäö])", text[e:])
        if tail and re.search(r"viiva|streck|dash|-", raw, re.IGNORECASE):
            w = tail.group(1).lower()
            if len(w) == 1 or w in LETTER_NAMES:
                raw += text[e:e + tail.end()]
                e += tail.end()
        if any(s < b and a < e for a, b in taken):
            continue
        rep = _run_text(raw)
        if rep is None:
            continue
        if tail and raw.endswith(tail.group(1)):
            rep = rep[: -len(tail.group(1))] + LETTER_NAMES.get(tail.group(1).lower(), tail.group(1).lower()[:1])
        pre = re.match(r"[fF]\s?[iI]\s", raw)
        if pre:
            rep = "FI" + rep.removeprefix("fi")
        edits.append((s, e, rep))
    return sorted(edits)


def normalise(text: str) -> Normalised:
    out: list[str] = []
    origin: list[tuple[int, int]] = []
    kept: list[tuple[int, int, str]] = []
    pos = 0
    for s, e, rep in _edits(text):
        if s < pos:
            continue
        kept.append((s, e, rep))
        for i in range(pos, s):
            out.append(text[i]); origin.append((i, i + 1))
        out.append(rep); origin.extend([(s, e)] * len(rep))
        pos = e
    for i in range(pos, len(text)):
        out.append(text[i]); origin.append((i, i + 1))
    return Normalised("".join(out), origin, kept)


def map_back(n: Normalised, start: int, end: int) -> tuple[int, int]:
    return n.origin[start][0], n.origin[end - 1][1]
