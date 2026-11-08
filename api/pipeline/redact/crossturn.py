"""Spoken national ids split over several turns of one speaker.

A customer reads an id in chunks ("yksi nolla", then "a983b") with short acknowledgements from the
agent in between. Within a conversation, take the same speaker's consecutive turns that look like
id fragments (short, with a digit), join them and check whether the first k of them form a HETU shape; if so every fragment is redacted. Only validated joins are redacted.
"""

from __future__ import annotations

import re

from api.pipeline.redact import normalise
from api.pipeline.redact.merge import Cand

MAX_CHUNKS = 6
_FRAGMENT = re.compile(r"[0-9a-z+\-]{1,12}")


def _compact(text: str) -> str:
    return re.sub(r"[\s,.:;]+", "", normalise.normalise(text).text.lower())


def _spoken(text: str) -> str | None:
    """Digits of a turn made only of spoken digit words and separators (even two digits)."""
    toks = re.findall(r"[\wåäö]+", text.lower())
    out = []
    for t in toks:
        if t in normalise.DIGITS and t != "en":
            out.append(normalise.DIGITS[t])
        elif t in normalise.SEPS:
            out.append(normalise.SEPS[t])
        elif t.isdigit():
            out.append(t)
        else:
            return None
    return "".join(out) if any(t in normalise.DIGITS and t != "en" for t in toks) else None


def _fragment(text: str) -> str | None:
    c = _spoken(text) or _compact(text)
    ok = _FRAGMENT.fullmatch(c) and (re.search(r"\d", c) or len(c) <= 2)  # a lone check letter
    return c if ok else None


_SHAPE = re.compile(r"(\d\d)(\d\d)\d\d[-+a-y]\d{3}[0-9a-y]")


def _valid(s: str) -> bool:
    """A HETU: six date digits, century sign, three digits, check character. The day and month
    must be plausible. The check character is not required to be right: the data may be
    synthetic, and a spoken digit may be mis-heard."""
    m = _SHAPE.fullmatch(s.lower())
    return bool(m) and 1 <= int(m.group(1)) <= 31 and 1 <= int(m.group(2)) <= 12


def find(texts: dict[str, str], groups: dict[str, tuple[str, str]]) -> dict[str, list[Cand]]:
    """Cands per record. `groups[rid]` is (conversation, speaker); `texts` is in turn order."""
    seqs: dict[tuple[str, str], list[str]] = {}
    for rid in texts:
        if rid in groups:
            seqs.setdefault(groups[rid], []).append(rid)
    out: dict[str, list[Cand]] = {}
    for rids in seqs.values():
        frags = {rid: _fragment(texts[rid]) for rid in rids}
        i = 0
        while i < len(rids):
            hit = 0
            acc = ""
            for k in range(min(MAX_CHUNKS, len(rids) - i)):
                f = frags[rids[i + k]]
                if f is None:
                    break
                acc += f
                if k >= 1 and _valid(acc):
                    hit = k + 1
                    break
            for rid in rids[i : i + hit]:
                t = texts[rid]
                lead = len(t) - len(t.lstrip())
                out.setdefault(rid, []).append(Cand(lead, len(t.rstrip()), "NATIONAL_ID", "normalise", 0.95))
            i += max(hit, 1)
    return out
