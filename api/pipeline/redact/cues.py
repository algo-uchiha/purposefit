"""Layer 4: cue phrases that introduce a name, a relative or a secret."""

from __future__ import annotations

import re

from api.pipeline.redact.merge import Cand

_NAME = r"[A-Za-zÅÄÖåäöÉéÜü]{2,}"
STRONG = (r"nimeni\s+on|nimeni\s+olisi|minun\s+nimeni\s+on|nimi\s+on|jag\s+heter|mitt\s+namn\s+är|"
          r"my\s+name\s+is|my\s+name's|name\s+is|"
          r"namn\s+är|namnet\s+är")  # fmt: skip
WEAK = (r"this\s+is|i\s+am|i'm|olen|minä\s+olen|det\s+här\s+är|det\s+är|hej\s+det\s+är|here\s+is|"
        r"puhelimessa")  # fmt: skip
RELATIVE = (r"mieheni|vaimoni|aviomieheni|puolisoni|poikani|tyttäreni|äitini|isäni|veljeni|sisarukseni|"
            r"siskoni|ystäväni|naapurini|lapseni|my\s+(?:wife|husband|son|daughter|mother|father|"
            r"brother|sister|friend|partner|neighbour)|min\s+(?:fru|man|son|dotter|mamma|pappa|bror|syster)|"
            r"hänen\s+nimensä\s+on")  # fmt: skip
_STOP = {"the", "a", "an", "and", "on", "is", "ja", "och", "att", "että", "not", "very", "ok", "here", "there",
         "calling", "looking", "trying", "just", "so", "in", "at", "to", "for", "with", "still", "now",
         "tässä", "täällä", "vain", "myös", "sitten", "jo", "nyt", "ei", "en", "vi", "ni", "inte",
         "customer", "asiakas", "kund", "using", "having", "also", "again", "about", "sorry", "back",
         "sure", "fine", "good", "well", "glad", "happy", "ready", "from", "your", "you", "he", "she",
         "han", "hon", "den", "det", "ett", "som", "med", "för", "till", "kiitos", "hei", "moi",
         "päivää", "hyvää", "terve"}  # fmt: skip
_STRONG = re.compile(rf"(?<![\wåäö])(?:{STRONG})\s+({_NAME}(?:\s+{_NAME})?)", re.IGNORECASE)
_WEAK = re.compile(rf"(?<![\wåäö])(?:{WEAK})\s+({_NAME}(?:\s+{_NAME})?)", re.IGNORECASE)
_REL = re.compile(rf"(?<![\wåäö])(?:{RELATIVE})\s+({_NAME}(?:\s+{_NAME})?)", re.IGNORECASE)
# a name followed by greetings words in "<name> täällä / here / speaking"
_SPEAK = re.compile(rf"(?<![\wåäö])({_NAME})\s+(?:täällä|tässä|speaking|här|på\s+linjan)(?![\wåäö])", re.IGNORECASE)


def _names(m: re.Match, known: frozenset[str], need_known: bool) -> list[tuple[int, int]]:
    """Token spans in group 1 that look like names (stop words dropped, first token must pass)."""
    spans = []
    for tm in re.finditer(_NAME, m.group(1)):
        w = tm.group().casefold()
        if w in _STOP:
            break
        if need_known and w not in known:
            break
        spans.append((m.start(1) + tm.start(), m.start(1) + tm.end()))
    return spans


def find(text: str, known_names: frozenset[str]) -> list[Cand]:
    out: list[Cand] = []
    for rx, need_known, score in ((_STRONG, False, 0.8), (_REL, True, 0.78), (_WEAK, True, 0.7)):
        for m in rx.finditer(text):
            sp = _names(m, known_names, need_known)
            if sp:
                out.append(Cand(sp[0][0], sp[-1][1], "PERSON", "cues", score))
    out += find_values(text)
    for m in _SPEAK.finditer(text):
        w = m.group(1).casefold()
        if w not in _STOP and (w in known_names or m.group(1)[0].isupper()):
            out.append(Cand(m.start(1), m.end(1), "PERSON", "cues", 0.7))
    return out


# Cue plus a short value: usernames, the start of a phone number, the last four card digits.
_USER = re.compile(r"(?i)(?<![\wåäö])(?:käyttäjätunnukse\w*|username(?:\s+there)?|användarnamn\w*|"
                   r"tunnus\w*)\s+(?:on|is|är)\s+(\S+)")
_PHONE_START = re.compile(r"(?i)(?<![\wåäö])(?:numero|numeero|number|numret|numrret|nummer)\s+(?:on|is|är)\s+(0\d{1,2})(?![\w])")
_CARD_END = re.compile(r"(?i)(?<![\wåäö])(?:ending(?:\s+in)?|päättyy|slutar\s+på|loppuu)\s+(\d{4})(?![\w])")


def find_values(text: str) -> list[Cand]:
    out: list[Cand] = []
    for m in _USER.finditer(text):
        tok = m.group(1).rstrip(".,;:!?")
        if re.search(r"\d", tok) or len(tok) >= 5:
            out.append(Cand(m.start(1), m.start(1) + len(tok), "USERNAME", "cues", 0.75))
    for m in _PHONE_START.finditer(text):
        out.append(Cand(m.start(1), m.end(1), "PHONE", "cues", 0.75))
    for m in _CARD_END.finditer(text):
        out.append(Cand(m.start(1), m.end(1), "PAYMENT_CARD", "cues", 0.75))
    return out
