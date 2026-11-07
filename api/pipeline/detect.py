"""Stage 2: label every column with a privacy role and subtype.

Ordered rule families on column-name tokens (fi, sv, en) plus the stage 1 profile. Each label
carries a confidence and a one-line reason. Columns below LLM_CONFIDENCE_THRESHOLD may go to
the optional LLM pass; its answer is accepted only if both terms are in the taxonomy.

The rule families and the threshold were fixed before any held-out score was looked at
(Phase 2 report). Never reads metadata/field_catalog.csv.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path

from api.pipeline import io
from api.pipeline.contracts import PRIVACY_ROLES, SUBTYPES, ColumnProfile, FieldLabel

log = logging.getLogger("purposefit.detect")

# Frozen in Phase 2 before held-out scoring. Do not tune.
LLM_CONFIDENCE_THRESHOLD = 0.6
LLM_SAMPLE_VALUES = 20
RULE_FAMILIES = (
    "record_key",        # first column, unique, id-like name or code values
    "foreign_key",       # other *_id / reference columns
    "value_strong",      # validated identifier values (HETU, IBAN, card, email, phone, IP...)
    "name_direct",       # direct identifier name tokens
    "name_technical",    # technical identifier name tokens
    "name_free_text",    # free text name tokens
    "name_sensitive",    # sensitive attribute name tokens
    "name_quasi",        # quasi-identifier name tokens
    "value_text",        # long multi-word values
    "value_quasi",       # dates, timestamps, postcodes, coordinates by value
    "value_code",        # code-like or hash values
    "default",           # nothing matched
)  # fmt: skip

LABEL_COLUMNS = ["dataset", "table", "column", "privacy_role", "subtype"]
UNSEEN_COLUMNS = ["column", "privacy_role", "subtype"]


@dataclass(frozen=True)
class Rule:
    family: str
    role: str
    subtype: str
    reason: str
    confidence: float


def tokens(name: str) -> list[str]:
    name = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
    return [t for t in re.split(r"[^a-zåäö]+|(?<=[a-z])(?=\d)", name.casefold()) if t]


def _has(toks: list[str], words: set[str]) -> str | None:
    for t in toks:
        if t in words:
            return t
    return None


def _joined(toks: list[str], phrases: set[str]) -> str | None:
    j = "_".join(toks)
    for p in phrases:
        if re.search(rf"(^|_){re.escape(p)}($|_)", j):
            return p
    return None


# ---- token vocabularies (fi, sv, en) ---------------------------------------------------

PERSON_QUALIFIERS = {
    "patient", "physician", "doctor", "author", "teacher", "agent", "guardian", "reporter",
    "full", "first", "last", "given", "display", "sender", "holder", "customer", "driver",
    "owner", "employee", "staff", "contact", "from", "nurse", "parent", "applicant", "student",
    "resident", "user", "person", "manager", "caller", "witness", "victim", "suspect",
    "beneficiary", "recipient", "payer", "tenant", "client", "member",
}  # fmt: skip
NOT_PERSON = {
    "merchant", "school", "test", "course", "subject", "rule", "process", "file",
    "attachment", "org", "company", "product", "street", "host", "device", "station",
    "site", "unit", "service", "stop", "route", "line", "place", "venue", "provider",
    "facility", "building", "zone", "area", "category", "event", "app", "brand", "model",
}  # fmt: skip
NAME_WORDS = {"name", "names", "nimi", "namn", "surname", "etunimi", "sukunimi", "fornamn",
              "efternamn", "firstname", "lastname", "fullname"}  # fmt: skip

DIRECT = [
    ({"hetu", "ssn", "henkilotunnus", "henkilötunnus", "personnummer", "sotu", "hetunumero"},
     "NATIONAL_ID"),
    ({"email", "sahkoposti", "sähköposti", "epost", "mail", "recipients"}, "EMAIL"),
    ({"phone", "puhelin", "puh", "gsm", "mobile", "telefon", "tel", "mobiili"}, "PHONE"),
    ({"iban", "tilinumero", "kontonummer"}, "IBAN"),
    ({"pan"}, "PAYMENT_CARD"),
    ({"plate", "rekisterinumero", "registreringsnummer"}, "LICENSE_PLATE"),
    ({"address", "osoite", "katuosoite", "adress", "gatuadress", "street"}, "STREET_ADDRESS"),
    ({"upn"}, "USERNAME"),
]  # fmt: skip
DIRECT_PHRASES = {
    "national_id": "NATIONAL_ID", "personal_id": "NATIONAL_ID", "card_number": "PAYMENT_CARD",
    "card_pan": "PAYMENT_CARD", "account_no": "IBAN", "bank_account": "IBAN",
    "customer_number": "CUSTOMER_ID", "asiakasnumero": "CUSTOMER_ID",
    "contract_number": "ACCOUNT_ID", "account_number": "ACCOUNT_ID",
    "license_plate": "LICENSE_PLATE", "registration_number": "LICENSE_PLATE",
}  # fmt: skip

TECHNICAL = [
    ({"ip", "ipv4", "ipv6"}, "IP_ADDRESS"),
    ({"mac"}, "MAC_ADDRESS"),
    ({"imei"}, "IMEI"),
    ({"hostname", "host"}, "HOSTNAME"),
    ({"gsrn", "meter", "metering", "mittari"}, "METER_ID"),
    ({"username", "login", "kayttajatunnus", "användarnamn"}, "USERNAME"),
    ({"device", "laite"}, "DEVICE_ID"),
]  # fmt: skip
TECH_PHRASES = {"user_agent": "USER_AGENT", "device_name": "HOSTNAME", "answer": "IP_ADDRESS"}

FREE_TEXT = {
    "text", "note", "notes", "message", "description", "comment", "comments", "complaint",
    "body", "subject", "viesti", "kommentti", "kuvaus", "huomautus", "huomio", "anteckning",
    "beskrivning", "meddelande", "kommentar", "selite", "narrative", "summary", "remarks",
    "attachment", "transcript", "feedback", "palaute",
}  # fmt: skip
FREE_TEXT_PHRASES = {"command_line": "FREE_TEXT", "file_path": "FREE_TEXT", "url": "URL"}

SENSITIVE = [
    ({"icd", "icd10", "diagnoosi", "diagnos"}, "DIAGNOSIS_CODE"),
    ({"diagnosis", "health", "triage", "disposition", "readmit", "disability", "sick",
      "sairaus", "illness", "allergy", "medication", "lääkitys", "abnormal", "accessibility",
      "terveys", "hälsa", "symptom", "treatment", "therapy", "sairausloma", "pregnancy"},
     "HEALTH_DATA"),
    ({"systolic", "diastolic", "bp", "heart", "pulse", "spo2", "resp", "pain", "bmi",
      "glucose", "cholesterol"}, "MEASUREMENT"),
    ({"income", "salary", "palkka", "wage", "wages", "tulot", "debt", "velka", "kyc",
      "credit", "default", "lön", "arrears", "benefit", "tuki", "allowance"},
     "FINANCIAL_DATA"),
    ({"grade", "points", "unexcused", "late", "arvosana", "betyg"}, "EDUCATION_DATA"),
    ({"union", "ammattiliitto", "religion", "ethnicity", "ethnic", "uskonto", "criminal",
      "conviction", "welfare", "custody", "asylum"}, "SOCIAL_DATA"),
    ({"pep"}, "OTHER"),
]  # fmt: skip
SENSITIVE_PHRASES = {"special_support": "HEALTH_DATA", "second_language": "SOCIAL_DATA",
                     "excused_hours": "HEALTH_DATA", "temp_c": "MEASUREMENT"}  # fmt: skip

QUASI = [
    ({"birth", "dob", "birthdate", "syntymäaika", "syntymaaika", "född", "födelsedatum"},
     "BIRTH_DATE"),
    ({"age", "ikä", "ika", "ålder", "alder"}, "AGE"),
    ({"sex", "gender", "sukupuoli", "kön"}, "SEX"),
    ({"postcode", "zip", "postal", "postinumero", "postnummer"}, "POSTCODE"),
    ({"municipality", "kunta", "kommun", "city", "town", "kaupunki", "stad", "paikkakunta"},
     "MUNICIPALITY"),
    ({"lat", "lon", "lng", "latitude", "longitude"}, "GPS_COORDINATE"),
    ({"country", "office", "region", "location", "maa", "land", "district"}, "LOCATION_NAME"),
    ({"language", "lang", "kieli", "språk"}, "LANGUAGE"),
    ({"nationality", "kansalaisuus"}, "NATIONALITY"),
    ({"occupation", "ammatti", "profession", "nimike", "yrke"}, "OCCUPATION"),
    ({"employer", "department", "workplace", "työpaikka", "tyopaikka", "organisation",
      "organization", "school", "arbetsgivare", "työnantaja"}, "ORG_NAME"),
    ({"domain", "query"}, "URL"),
    ({"ts", "timestamp", "utc", "time", "datetime", "aika", "tid"}, "TIMESTAMP"),
    ({"date", "pvm", "päivä", "datum", "week", "since", "expiry", "start", "end",
      "session", "issued"}, "DATE"),
]  # fmt: skip
QUASI_PHRASES = {"job_title": "OCCUPATION", "created_utc": "TIMESTAMP"}
LOCATION_PREFIX = {"merchant", "geo", "pos", "store", "home"}

FK_SUBTYPES = [
    ({"customer", "asiakas", "client"}, "CUSTOMER_ID"),
    ({"student", "learner", "pupil", "oppilas"}, "STUDENT_ID"),
    ({"patient", "potilas"}, "PATIENT_ID"),
    ({"staff", "employee", "agent", "physician", "author", "teacher", "nurse", "worker",
      "doctor", "officer", "henkilöstö", "caseworker", "handler"}, "EMPLOYEE_ID"),
    ({"account", "tili"}, "ACCOUNT_ID"),
    ({"card", "kortti"}, "CARD_ID"),
    ({"device", "laite"}, "DEVICE_ID"),
    ({"meter", "metering", "gsrn"}, "METER_ID"),
    ({"property", "kiinteistö"}, "PROPERTY_ID"),
]  # fmt: skip
ID_WORDS = {"id", "no", "nr", "ref", "number", "numero", "tunnus", "nro", "key", "uuid"}


def _hits(p: ColumnProfile, name: str) -> float:
    return p.validator_hits.get(name, 0.0)


def _numeric(p: ColumnProfile) -> bool:
    return _hits(p, "decimal") >= 0.9


def _value_strong(p: ColumnProfile) -> Rule | None:
    checks = [
        ("hetu", 0.3, "direct_identifier", "NATIONAL_ID", "values pass the HETU checksum"),
        ("hetu_like", 0.8, "direct_identifier", "NATIONAL_ID", "values have the HETU shape"),
        ("iban", 0.6, "direct_identifier", "IBAN", "values pass the IBAN mod 97 check"),
        ("card", 0.8, "direct_identifier", "PAYMENT_CARD", "values pass the Luhn card check"),
        ("email", 0.6, "direct_identifier", "EMAIL", "values are email addresses"),
        ("phone", 0.7, "direct_identifier", "PHONE", "values are Finnish phone numbers"),
        ("mac", 0.6, "technical_identifier", "MAC_ADDRESS", "values are MAC addresses"),
        ("ipv4", 0.6, "technical_identifier", "IP_ADDRESS", "values are IP addresses"),
        ("ipv6", 0.6, "technical_identifier", "IP_ADDRESS", "values are IP addresses"),
        ("plate", 0.6, "direct_identifier", "LICENSE_PLATE", "values are licence plates"),
        ("person_name", 0.6, "direct_identifier", "PERSON_NAME",
         "values are person names found in the DVV name lists"),
    ]  # fmt: skip
    for key, thr, role, sub, why in checks:
        h = _hits(p, key)
        if h >= thr and not (key == "phone" and _hits(p, "integer") >= 0.9 and p.len_mean < 9):
            return Rule("value_strong", role, sub, f"{why} ({h:.0%} of sampled values)", 0.9)
    if (_hits(p, "address") >= 0.7 and _hits(p, "sentence") < 0.3 and p.len_mean < 60
            and p.distinct_ratio > 0.05):  # fmt: skip
        return Rule("value_strong", "direct_identifier", "STREET_ADDRESS",
                    "values look like street addresses", 0.8)  # fmt: skip
    return None


def _name_rule(toks: list[str], p: ColumnProfile) -> Rule | None:
    # direct identifiers
    for phrase, sub in DIRECT_PHRASES.items():
        if _joined(toks, {phrase}):
            return Rule("name_direct", "direct_identifier", sub, f"column name has '{phrase}'", 0.85)
    for words, sub in DIRECT:
        t = _has(toks, words)
        if t and not (sub == "STREET_ADDRESS" and _has(toks, {"ip", "mac", "email"})):
            if sub == "EMAIL" and _has(toks, {"gateway", "server"}):
                continue
            return Rule("name_direct", "direct_identifier", sub, f"column name has '{t}'", 0.85)
    name_tok = _has(toks, NAME_WORDS)
    if name_tok and not _has(toks, NOT_PERSON):
        qual = _has(toks, PERSON_QUALIFIERS)
        if qual or len(toks) == 1 or name_tok != "name" or _hits(p, "person_name") >= 0.4:
            why = f"column name has '{name_tok}'" + (f" with '{qual}'" if qual else "")
            return Rule("name_direct", "direct_identifier", "PERSON_NAME", why, 0.85)
    # technical identifiers
    for phrase, sub in TECH_PHRASES.items():
        if _joined(toks, {phrase}):
            return Rule("name_technical", "technical_identifier", sub,
                        f"column name has '{phrase}'", 0.8)  # fmt: skip
    for words, sub in TECHNICAL:
        t = _has(toks, words)
        if t:
            return Rule("name_technical", "technical_identifier", sub,
                        f"column name has '{t}'", 0.8)  # fmt: skip
    # free text
    for phrase, sub in FREE_TEXT_PHRASES.items():
        if _joined(toks, {phrase}):
            return Rule("name_free_text", "free_text", sub, f"column name has '{phrase}'", 0.8)
    t = _has(toks, FREE_TEXT)
    if t and (p.len_mean >= 15 or _hits(p, "sentence") >= 0.2):
        return Rule("name_free_text", "free_text", "FREE_TEXT",
                    f"column name has '{t}' and values are text", 0.85)  # fmt: skip
    # sensitive attributes
    for phrase, sub in SENSITIVE_PHRASES.items():
        if _joined(toks, {phrase}):
            return Rule("name_sensitive", "sensitive_attribute", sub,
                        f"column name has '{phrase}'", 0.8)  # fmt: skip
    for words, sub in SENSITIVE:
        t = _has(toks, words)
        if t:
            return Rule("name_sensitive", "sensitive_attribute", sub,
                        f"column name has '{t}'", 0.75)  # fmt: skip
    # quasi-identifiers
    for phrase, sub in QUASI_PHRASES.items():
        if _joined(toks, {phrase}):
            return Rule("name_quasi", "quasi_identifier", sub, f"column name has '{phrase}'", 0.8)
    for words, sub in QUASI:
        t = _has(toks, words)
        if not t:
            continue
        if sub == "MUNICIPALITY" and _has(toks, LOCATION_PREFIX - {"home"}):
            sub = "LOCATION_NAME"
        if sub in ("DATE", "TIMESTAMP"):
            if _hits(p, "timestamp") >= 0.6:
                sub = "TIMESTAMP"
            elif _hits(p, "date") >= 0.6:
                sub = "DATE"
        return Rule("name_quasi", "quasi_identifier", sub, f"column name has '{t}'", 0.75)
    return None


def _id_subtype(toks: list[str]) -> str:
    for words, sub in FK_SUBTYPES:
        if _has(toks, words):
            return sub
    return "RECORD_ID"


def classify(p: ColumnProfile, position: int) -> Rule:
    toks = tokens(p.column)
    id_like = bool(_has(toks, ID_WORDS)) or p.column.casefold().endswith("id")
    # 1. record key: first column, unique values
    if position == 0 and p.distinct_ratio >= 0.98 and (id_like or _hits(p, "prefix_code") >= 0.9):
        return Rule("record_key", "record_key", _id_subtype(toks) if id_like else "RECORD_ID",
                    "first column with a unique value in every row", 0.9)  # fmt: skip
    # 2. validated identifier values beat names
    strong = _value_strong(p)
    if strong and strong.subtype != "PERSON_NAME":
        return strong
    # 3. named direct identifiers that look like ids (customer_number, contract_number)
    for phrase, sub in DIRECT_PHRASES.items():
        if _joined(toks, {phrase}):
            return Rule("name_direct", "direct_identifier", sub, f"column name has '{phrase}'", 0.85)
    # 4. foreign keys and references
    if id_like and _has(toks, ID_WORDS) and not _has(toks, {"campaign"}):
        sub = _id_subtype(toks)
        if p.distinct_ratio < 0.01 and sub == "RECORD_ID":
            return Rule("foreign_key", "non_sensitive", "CATEGORY",
                        "identifier with very few distinct values", 0.6)  # fmt: skip
        return Rule("foreign_key", "technical_identifier", sub,
                    "identifier that links to another record", 0.8)  # fmt: skip
    # 5. name tokens
    rule = _name_rule(toks, p)
    if rule:
        return rule
    if strong:
        return strong
    # 6. values only
    if _hits(p, "sentence") >= 0.4 and p.len_mean >= 25:
        return Rule("value_text", "free_text", "FREE_TEXT",
                    f"values are multi-word text, mean length {p.len_mean:.0f}", 0.7)  # fmt: skip
    if _hits(p, "timestamp") >= 0.6:
        return Rule("value_quasi", "quasi_identifier", "TIMESTAMP", "values are timestamps", 0.7)
    if _hits(p, "date") >= 0.6:
        return Rule("value_quasi", "quasi_identifier", "DATE", "values are dates", 0.55)
    if _hits(p, "gps") >= 0.8:
        return Rule("value_quasi", "quasi_identifier", "GPS_COORDINATE",
                    "values are decimal coordinates", 0.6)  # fmt: skip
    if _hits(p, "postcode") >= 0.9 and not _numeric(p) or (
        _hits(p, "postcode") >= 0.9 and p.len_min == p.len_max == 5
    ):
        return Rule("value_quasi", "quasi_identifier", "POSTCODE", "values are 5-digit codes", 0.55)
    if _hits(p, "hex_hash") >= 0.8:
        return Rule("value_code", "technical_identifier", "OTHER",
                    "values are long hexadecimal hashes", 0.55)  # fmt: skip
    if _hits(p, "partial_date") >= 0.8:
        return Rule("value_quasi", "quasi_identifier", "DATE", "values are partial dates", 0.5)
    if _hits(p, "prefix_code") >= 0.9 and p.distinct_ratio >= 0.2:
        return Rule("value_code", "technical_identifier", "OTHER",
                    "values are many distinct codes", 0.5)  # fmt: skip
    if _numeric(p):
        return Rule("default", "non_sensitive", "MEASUREMENT", "numeric values, no name match", 0.4)
    return Rule("default", "non_sensitive", "CATEGORY", "no name or value rule matched", 0.4)


def detect(profiles: list[ColumnProfile]) -> list[FieldLabel]:
    out: list[FieldLabel] = []
    position: dict[tuple[str, str], int] = {}
    for p in profiles:
        key = (p.dataset, p.table)
        pos = position.get(key, 0)
        position[key] = pos + 1
        r = classify(p, pos)
        out.append(FieldLabel(p.dataset, p.table, p.column, r.role, r.subtype, r.confidence,
                              f"{r.reason} [{r.family}]", "rule"))  # fmt: skip
    return out


# ---- optional LLM pass ---------------------------------------------------------------

LLM_SYSTEM = (
    "You classify columns of tabular datasets for privacy review. You get a JSON object with a "
    "list of columns, each with an id, table, column name and sample values. Answer with a JSON "
    'list only, one item per column, in the same order: [{"id": ..., "privacy_role": ..., '
    '"subtype": ...}]. privacy_role must be one of: '
    + ", ".join(sorted(PRIVACY_ROLES))
    + ". subtype must be one of: "
    + ", ".join(sorted(SUBTYPES))
    + ". Health, union membership, religion, ethnicity, income and similar protected facts are "
    "sensitive_attribute. Values that identify a person on their own are direct_identifier."
)
LLM_BATCH_SIZE = 20
LLM_PARALLEL = 4
LLM_TOKENS_PER_COLUMN = 40  # one JSON item is about 25 tokens
LLM_VALUE_CHARS = 80


def _parse_llm_batch(text: str, ids: list[int]) -> dict[int, tuple[str, str]]:
    """Valid (role, subtype) per id. Items with unknown ids or non-taxonomy terms are dropped."""
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return {}
    try:
        items = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    out: dict[int, tuple[str, str]] = {}
    wanted = set(ids)
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            cid = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        role = str(item.get("privacy_role", "")).strip()
        sub = str(item.get("subtype", "")).strip()
        if cid in wanted and cid not in out and role in PRIVACY_ROLES and sub in SUBTYPES:
            out[cid] = (role, sub)
    return out


def _table_samples(labels: list[FieldLabel], seed: int, root: Path | None
                   ) -> dict[tuple[str, str, str], list[str]]:  # fmt: skip
    """Up to LLM_SAMPLE_VALUES distinct values per column; each table is read once."""
    by_table: dict[tuple[str, str], list[str]] = {}
    for lab in labels:
        by_table.setdefault((lab.dataset, lab.table), []).append(lab.column)
    out = {}
    for (dataset, table), cols in by_table.items():
        df = io.read_csv((root or io.data_root()) / dataset / f"{table}.csv")
        for c in cols:
            col = df[c][df[c].str.strip() != ""].drop_duplicates()
            n = min(LLM_SAMPLE_VALUES, len(col))
            vals = col.sample(n=n, random_state=seed).str.slice(0, LLM_VALUE_CHARS).tolist()
            out[(dataset, table, c)] = vals if n else []
    return out


def sample_values(dataset: str, table: str, column: str, seed: int, root: Path | None = None
                  ) -> list[str]:  # fmt: skip
    lab = FieldLabel(dataset, table, column, "non_sensitive", "OTHER", 0.0, "", "rule")
    return _table_samples([lab], seed, root)[(dataset, table, column)]


def llm_pass(labels: list[FieldLabel], client, seed: int, root: Path | None = None
             ) -> tuple[list[FieldLabel], dict[str, int]]:  # fmt: skip
    """Relabel low-confidence columns with the LLM, in batches, in parallel.

    Invalid or missing answers keep the rule label.
    """
    from concurrent.futures import ThreadPoolExecutor

    from api.pipeline.llm import LLMError

    low = [i for i, lab in enumerate(labels) if lab.confidence < LLM_CONFIDENCE_THRESHOLD]
    stats = {"sent": len(low), "calls": 0, "accepted": 0, "rejected": 0, "errors": 0,
             "changed": 0, "fallback_calls": 0, "prompt_tokens": 0, "output_tokens": 0,
             "thought_tokens": 0}  # fmt: skip
    if not low:
        return list(labels), {**stats, "status": "ok"}
    start = time.monotonic()
    samples = _table_samples([labels[i] for i in low], seed, root)
    batches = [low[k : k + LLM_BATCH_SIZE] for k in range(0, len(low), LLM_BATCH_SIZE)]

    def ask(batch: list[int]):
        cols = [{"id": i, "table": labels[i].table, "column": labels[i].column,
                 "sample_values": samples[(labels[i].dataset, labels[i].table,
                                           labels[i].column)]} for i in batch]  # fmt: skip
        prompt = json.dumps({"columns": cols}, ensure_ascii=False)
        try:
            return batch, client.complete(
                prompt, system=LLM_SYSTEM, max_tokens=LLM_TOKENS_PER_COLUMN * len(batch) + 64,
                validate=lambda text: bool(_parse_llm_batch(text, batch)),
            )
        except Exception as exc:  # noqa: BLE001 (never block a run on the LLM)
            if not isinstance(exc, LLMError):
                log.warning(json.dumps({"stage": "detect_llm", "event": "llm_batch_failed",
                                        "error": type(exc).__name__}))  # fmt: skip
            return batch, None

    with ThreadPoolExecutor(max_workers=LLM_PARALLEL) as pool:
        results = list(pool.map(ask, batches))

    out = list(labels)
    for batch, resp in results:
        stats["calls"] += 1
        if resp is None:
            stats["errors"] += len(batch)
            continue
        stats["fallback_calls"] += int(getattr(resp, "fallback", False))
        for k in ("prompt_tokens", "output_tokens", "thought_tokens"):
            stats[k] += getattr(resp, k, 0)
        parsed = _parse_llm_batch(resp.text, batch)
        for i in batch:
            lab = labels[i]
            if i not in parsed:
                stats["rejected"] += 1
                continue
            stats["accepted"] += 1
            if parsed[i] != (lab.privacy_role, lab.subtype):
                stats["changed"] += 1
            out[i] = replace(lab, privacy_role=parsed[i][0], subtype=parsed[i][1],
                             confidence=0.7, source="llm",
                             reason=f"LLM label ({resp.model}), call {resp.call_id}; "
                                    f"rule said: {lab.reason}")  # fmt: skip
    stats["duration_ms"] = int((time.monotonic() - start) * 1000)
    stats["status"] = ("failed_rules_only" if stats["errors"] == stats["sent"]
                       else "partial" if stats["errors"] else "ok")  # fmt: skip
    level = logging.WARNING if stats["errors"] else logging.INFO
    log.log(level, json.dumps({"stage": "detect_llm", **stats}))
    return out, stats


# ---- running and writing -------------------------------------------------------------


def run_detect(datasets: list[str], seed: int, client=None, root: Path | None = None
               ) -> tuple[list[FieldLabel], dict[str, int]]:  # fmt: skip
    from api.pipeline.profile import profile_dataset

    start = time.monotonic()
    profiles = [p for d in datasets for p in profile_dataset(d, seed, root)]
    labels = detect(profiles)
    stats: dict[str, int] = {}
    if client is not None and client.enabled:
        labels, stats = llm_pass(labels, client, seed, root)
    log.info(json.dumps({"stage": "detect", "datasets": len(datasets), "columns": len(labels),
                         "duration_ms": int((time.monotonic() - start) * 1000)}))  # fmt: skip
    return labels, stats


def write_labels(labels: list[FieldLabel], path: Path, unseen_format: bool = False) -> None:
    cols = UNSEEN_COLUMNS if unseen_format else LABEL_COLUMNS
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for lab in labels:
            d = lab.to_dict()
            w.writerow([d[c] for c in cols])


def write_label_details(labels: list[FieldLabel], path: Path) -> None:
    path.write_text(json.dumps([lab.to_dict() for lab in labels], indent=1, ensure_ascii=False),
                    encoding="utf-8")  # fmt: skip
