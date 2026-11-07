"""Shared types for every pipeline stage. Change only when asked (CLAUDE.md).

Vocabulary is copied from vendor/proving_ground/metadata/taxonomy.md. A test checks the
copy against that file whenever the proving ground is present.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PRIVACY_ROLES = frozenset(
    {
        "direct_identifier",
        "quasi_identifier",
        "sensitive_attribute",
        "technical_identifier",
        "free_text",
        "record_key",
        "non_sensitive",
    }
)

DATA_KINDS = frozenset(
    {
        "identifier", "name", "contact", "temporal", "location", "categorical",
        "numerical", "text", "aggregate", "code", "secret",
    }
)  # fmt: skip

SUBTYPES = frozenset(
    ["PERSON_NAME", "NATIONAL_ID", "EMAIL", "PHONE", "STREET_ADDRESS", "POSTCODE", "MUNICIPALITY", "GPS_COORDINATE", "LOCATION_NAME", "BIRTH_DATE", "AGE", "SEX", "LANGUAGE", "NATIONALITY", "IBAN", "PAYMENT_CARD", "CUSTOMER_ID", "ACCOUNT_ID", "EMPLOYEE_ID", "STUDENT_ID", "PATIENT_ID", "CARD_ID", "DEVICE_ID", "IP_ADDRESS", "MAC_ADDRESS", "IMEI", "HOSTNAME", "USERNAME", "URL", "USER_AGENT", "LICENSE_PLATE", "PROPERTY_ID", "METER_ID", "TIMESTAMP", "DATE", "DURATION", "HEALTH_DATA", "DIAGNOSIS_CODE", "FINANCIAL_DATA", "EDUCATION_DATA", "SOCIAL_DATA", "OCCUPATION", "ORG_NAME", "MEASUREMENT", "CATEGORY", "AGGREGATE", "SECRET", "FREE_TEXT", "RECORD_ID", "OTHER"]
)

SPAN_LABELS = frozenset(
    ["PERSON", "NATIONAL_ID", "EMAIL", "PHONE", "ADDRESS", "LOCATION", "DATE", "AGE", "IBAN", "PAYMENT_CARD", "ACCOUNT_NUMBER", "IP_ADDRESS", "LICENSE_PLATE", "ORG", "URL", "USERNAME", "SECRET", "HEALTH", "DEVICE_ID", "PROPERTY_ID"]
)

ACTIONS = frozenset(
    {"keep", "drop", "hmac", "generalise", "redact", "suppress_k", "withhold_table"}
)

LABEL_SOURCES = frozenset({"rule", "llm", "manual"})

SPAN_LAYERS = frozenset({"patterns", "normalise", "gazetteer", "cues", "ner", "health"})


def _check(value: str, allowed: frozenset[str], what: str) -> None:
    # The message names the field and the bad term only; terms are vocabulary, not data.
    if value not in allowed:
        raise ValueError(f"{what} {value!r} is not in the taxonomy vocabulary")


def _check_unit(value: float, what: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{what} must be between 0 and 1")


class _Record:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)  # type: ignore[call-overload]


@dataclass(frozen=True)
class ColumnProfile(_Record):
    """Stage 1 output for one column. Counts and rates only, never cell values."""

    dataset: str
    table: str
    column: str
    rows_sampled: int
    fill_rate: float
    distinct_ratio: float
    len_min: int
    len_max: int
    len_mean: float
    char_classes: dict[str, float] = field(default_factory=dict)
    validator_hits: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.rows_sampled < 0:
            raise ValueError("rows_sampled must not be negative")
        _check_unit(self.fill_rate, "fill_rate")
        _check_unit(self.distinct_ratio, "distinct_ratio")
        for name, rate in {**self.char_classes, **self.validator_hits}.items():
            _check_unit(rate, name)


@dataclass(frozen=True)
class FieldLabel(_Record):
    dataset: str
    table: str
    column: str
    privacy_role: str
    subtype: str
    confidence: float
    reason: str
    source: str

    def __post_init__(self) -> None:
        _check(self.privacy_role, PRIVACY_ROLES, "privacy_role")
        _check(self.subtype, SUBTYPES, "subtype")
        _check(self.source, LABEL_SOURCES, "source")
        _check_unit(self.confidence, "confidence")


@dataclass(frozen=True)
class Span(_Record):
    record_id: str
    start: int
    end: int
    label: str
    layer: str
    score: float

    def __post_init__(self) -> None:
        if not 0 <= self.start < self.end:
            raise ValueError("span needs 0 <= start < end")
        _check(self.label, SPAN_LABELS, "span label")
        _check(self.layer, SPAN_LAYERS, "layer")
        _check_unit(self.score, "score")


@dataclass(frozen=True)
class FieldPolicy(_Record):
    table: str
    column: str
    action: str
    params: dict[str, Any]
    reason: str
    guarantee: str

    def __post_init__(self) -> None:
        _check(self.action, ACTIONS, "action")


@dataclass(frozen=True)
class PolicyPlan(_Record):
    dataset: str
    scenario_id: str
    released_tables: list[str]
    policies: list[FieldPolicy]
    k: int
    key_id: str

    def __post_init__(self) -> None:
        if self.k < 1:
            raise ValueError("k must be at least 1")


@dataclass(frozen=True)
class ReleaseReport(_Record):
    plan: PolicyPlan
    scorecard_ours: dict[str, Any]
    scorecard_baselines: dict[str, dict[str, Any]]
    gate: dict[str, Any]
    residual_risks: list[str]
    ablation: list[dict[str, Any]]
