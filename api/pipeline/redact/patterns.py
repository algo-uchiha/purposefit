"""Layer 1: pattern recognisers with python-stdnum validators.

Each hit is a Hit(start, end, label, score). A hit that passes a checksum scores 1.0 so the
merge prefers it; a shape-only hit scores lower. No text is logged or stored here.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from stdnum import luhn
from stdnum.fi import hetu as fi_hetu
from stdnum.iban import is_valid as iban_valid


class Hit(NamedTuple):
    start: int
    end: int
    label: str
    score: float


def _hetu_ok(s: str) -> bool:
    try:
        return fi_hetu.is_valid(re.sub(r"\s", "", s).upper())
    except Exception:  # noqa: BLE001  # nosec B110 (a malformed value is simply not valid)
        return False


_RX = {
    "hetu": re.compile(r"(?<![\w])\d{6}\s?[-+A-FU-Ya-fu-y]\s?\d{3}\s?[0-9A-Ya-y](?![\w])"),
    "iban": re.compile(r"(?<![\w])[A-Za-z]{2}\d{2}(?:\s?[0-9A-Za-z]{4}){3,7}(?:\s?[0-9A-Za-z]{1,4})?(?![\w])"),
    "card": re.compile(r"(?<![\w])(?:\d[ -]?){13,19}(?![\w])"),
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    "url": re.compile(r"https?://[^\s<>\"]+"),
    "ip": re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])"),
    "phone": re.compile(r"(?<![\w])(?:\+\s?358|00\s?358|0)[\s-]?\d{1,3}[\s-]?\d{2,4}[\s-]?\d{2,4}(?:[\s-]?\d{1,4})?(?![\w])"),
    "imei": re.compile(r"(?<![\w])\d{15}(?![\w])|(?<![\w])89\d{17,19}(?![\w])|(?<![\w])\d{5}(?:\s\d{5}){2}(?![\w])"),
    "property": re.compile(r"(?<![\w])\d{3}-\d{1,3}-\d{1,4}-\d{1,4}(?![\w])"),
    "plate": re.compile(r"(?<![\w])[A-Za-zÅÄÖåäö]{2,3}-\d{1,3}(?![\w])"),
    "account": re.compile(r"(?<![\w])\d{3,4}(?:\s?\d{3,4}){1,2}\s?\d?(?![\w])"),
    "address": re.compile(
        r"(?<![\w])[A-ZÅÄÖa-zåäö]+(?:katu|tie|kuja|polku|rinne|mäki|ranta|kaari|tori|puisto|katu|gatan|vägen|gränd|road|street|väylä|aukio|raitti|penger|kuja)"
        r"\s\d+(?:\s?[A-Za-z](?!\w))?(?:\s\d+(?!\d))?(?:,?\s?\d{5}\s[A-ZÅÄÖa-zåäö]+)?"),
    "secret": re.compile(r"(?i)(?<![\wåäö])(?:salasana\w*|password|lösenord\w*|pin|puk|tunnusluku\w*|koodi\w*|code|kod)"
                         r"(?:\s+(?:on|is|är|koodi|code|kod|varmaan|probably|nog|kai))*[\s:]+(\S+)"),
    "addr2": re.compile(r"(?<![\wåäö])[A-ZÅÄÖa-zåäö][\wåäö-]+\s\d+(?:\s?[A-Za-z](?![\wåäö]))?(?:\s\d+)?,?\s\d{5}\s[A-ZÅÄÖa-zåäö]+"),
    "idfrag": re.compile(r"(?<![\w])[-+]\d{3}[0-9A-Ya-y](?![\w])"),
}
_SECRET_STOP = {"on", "is", "är", "the", "ja", "and", "och", "ei", "en", "tai", "or", "eller",
                "se", "ole", "oli", "was", "var", "että", "that", "att", "vai"}  # fmt: skip


def find(text: str) -> list[Hit]:
    out: list[Hit] = []
    for m in _RX["hetu"].finditer(text):
        out.append(Hit(m.start(), m.end(), "NATIONAL_ID", 1.0 if _hetu_ok(m.group()) else 0.8))
    for m in _RX["iban"].finditer(text):
        compact = re.sub(r"\s", "", m.group()).upper()
        if iban_valid(compact):
            out.append(Hit(m.start(), m.end(), "IBAN", 1.0))
        elif compact[:2].isalpha() and compact[:2].upper() in {"FI", "SE", "DE", "EE", "NO", "DK"}:
            out.append(Hit(m.start(), m.end(), "IBAN", 0.7))
    for m in _RX["card"].finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and len(digits) != 15 and luhn.is_valid(digits):
            out.append(Hit(m.start(), m.end(), "PAYMENT_CARD", 1.0))
        elif len(digits) in (16,) and re.fullmatch(r"\d{4}([ -]\d{4}){3}", m.group().strip()):
            out.append(Hit(m.start(), m.end(), "PAYMENT_CARD", 0.7))
    for key, label, score in (("email", "EMAIL", 0.95), ("ip", "IP_ADDRESS", 0.9),
                              ("property", "PROPERTY_ID", 0.9)):  # fmt: skip
        for m in _RX[key].finditer(text):
            if key == "ip" and not all(int(x) <= 255 for x in m.group().split(".")):
                continue
            out.append(Hit(m.start(), m.end(), label, score))
    for m in _RX["url"].finditer(text):
        if re.search(r"(?i)token|[?&]id=|email=|key=|session", m.group()):
            out.append(Hit(m.start(), m.end(), "URL", 0.9))
    for m in _RX["phone"].finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 8 <= len(digits) <= 13:
            out.append(Hit(m.start(), m.end(), "PHONE", 0.75))
    for m in _RX["imei"].finditer(text):
        digits = re.sub(r"\D", "", m.group())
        out.append(Hit(m.start(), m.end(), "DEVICE_ID", 1.0 if len(digits) == 15 and luhn.is_valid(digits) else 0.7))
    for m in _RX["plate"].finditer(text):
        out.append(Hit(m.start(), m.end(), "LICENSE_PLATE", 0.6))
    for m in _RX["account"].finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 7 <= len(digits) <= 12:
            out.append(Hit(m.start(), m.end(), "ACCOUNT_NUMBER", 0.4))
    for m in _RX["addr2"].finditer(text):
        out.append(Hit(m.start(), m.end(), "ADDRESS", 0.8))
    for m in _RX["idfrag"].finditer(text):
        out.append(Hit(m.start(), m.end(), "NATIONAL_ID", 0.55))
    for m in _RX["address"].finditer(text):
        out.append(Hit(m.start(), m.end(), "ADDRESS", 0.85))
    for m in _RX["secret"].finditer(text):
        tok = m.group(1).strip(".,;:!?")
        if tok.lower() not in _SECRET_STOP and re.search(r"\d", tok):
            out.append(Hit(m.start(1), m.end(1), "SECRET", 0.8))
    return out
