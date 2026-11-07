import re

import pytest

from api.pipeline import contracts as c


def label(**kw):
    base = {
        "dataset": "customer_service", "table": "customers", "column": "hetu",
        "privacy_role": "direct_identifier", "subtype": "NATIONAL_ID", "confidence": 0.9,
        "reason": "name token hetu", "source": "rule",
    }  # fmt: skip
    return c.FieldLabel(**{**base, **kw})


def test_valid_records_build():
    lab = label()
    assert lab.to_dict()["subtype"] == "NATIONAL_ID"
    span = c.Span("t1", 0, 5, "PERSON", "gazetteer", 1.0)
    pol = c.FieldPolicy("customers", "hetu", "hmac", {}, "join key", "keyed pseudonym")
    plan = c.PolicyPlan("customer_service", "CS-S1", ["turns"], [pol], 5, "abc")
    rep = c.ReleaseReport(plan, {}, {"b2k": {}}, {"passed": False}, [], [])
    assert rep.to_dict()["plan"]["policies"][0]["action"] == "hmac"
    assert span.end == 5


@pytest.mark.parametrize("kw", [{"privacy_role": "pii"}, {"subtype": "SSN"},
                                {"source": "guess"}, {"confidence": 1.5}])  # fmt: skip
def test_field_label_rejects_bad_values(kw):
    with pytest.raises(ValueError):
        label(**kw)


@pytest.mark.parametrize("args", [("t", 0, 5, "NAME", "patterns", 1.0),
                                  ("t", 0, 5, "PERSON", "magic", 1.0),
                                  ("t", 5, 5, "PERSON", "patterns", 1.0)])  # fmt: skip
def test_span_rejects_bad_values(args):
    with pytest.raises(ValueError):
        c.Span(*args)


def test_policy_actions_are_the_seven():
    assert c.ACTIONS == {"keep", "drop", "hmac", "generalise", "redact", "suppress_k",
                         "withhold_table"}  # fmt: skip
    with pytest.raises(ValueError):
        c.FieldPolicy("t", "c", "encrypt", {}, "", "")
    with pytest.raises(ValueError):
        c.PolicyPlan("d", "s", [], [], 0, "k")


def _block(text, heading):
    section = text.split(heading, 1)[1]
    return set(re.search(r"```\n(.*?)```", section, re.DOTALL).group(1).replace(",", " ").split())


def test_vocabulary_matches_taxonomy_md(proving_ground):
    text = (proving_ground / "metadata" / "taxonomy.md").read_text(encoding="utf-8")
    roles = set(re.findall(r"^\| `([a-z_]+)` \|", text, re.MULTILINE))
    assert roles == c.PRIVACY_ROLES
    assert _block(text, "## subtype") == c.SUBTYPES
    assert _block(text, "## Span labels") == c.SPAN_LABELS
