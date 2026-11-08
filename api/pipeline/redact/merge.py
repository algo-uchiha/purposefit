"""Merge overlapping candidate spans: validated match first, then longest, then earliest."""

from __future__ import annotations

from typing import NamedTuple


class Cand(NamedTuple):
    start: int
    end: int
    label: str
    layer: str
    score: float
    source: str = ""  # "controller" or "dvv" for the gazetteer layer, else ""


def merge(cands: list[Cand]) -> list[Cand]:
    ranked = sorted(cands, key=lambda c: (-round(c.score, 2), -(c.end - c.start), c.start))
    kept: list[Cand] = []
    for c in ranked:
        if all(c.end <= k.start or c.start >= k.end for k in kept):
            kept.append(c)
    return sorted(kept, key=lambda c: c.start)
