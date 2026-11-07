"""The release gate: thresholds from api/pipeline/config.py, a reason on every check."""

from api.pipeline import config
from api.pipeline import verify as vf

POL = [{"action": "suppress_k", "params": {"k_pycanon": 7}}]


def card(direct=0.0, leak=0.05, extra=None):
    comps = {"turns: direct identifiers retained": direct,
             "turns: free-text identifier leakage": leak} | (extra or {})  # fmt: skip
    return {"risk_components": comps,
            "tables": {"turns": {"free_text": {"text": {"evaluated": True,
                                                         "identifying_leakage_rate": leak}}}}}  # fmt: skip


B2K = {"risk_components": {"turns: direct identifiers retained": 0.0,
                           "turns: free-text identifier leakage": 0.8}}  # fmt: skip


def ids(g, status):
    return [c["id"] for c in g["checks"] if c["status"] == status]


def test_all_four_checks_pass_and_each_has_a_reason():
    g = vf.build_gate(card(), B2K, POL, "CS-S1")
    assert g["passed"] and g["blocking"] == []
    assert [c["id"] for c in g["checks"]] == ["direct_identifiers", "k_anonymity",
                                              "risk_vs_baseline", "text_leakage"]  # fmt: skip
    assert all(c["reason"] for c in g["checks"])


def test_text_leakage_uses_config_limit():
    assert config.GATE_MAX_TEXT_LEAKAGE == 0.10
    assert "text_leakage" in vf.build_gate(card(leak=0.11), B2K, POL, "S")["blocking"]
    assert "text_leakage" not in vf.build_gate(card(leak=0.10), B2K, POL, "S")["blocking"]


def test_a_retained_direct_identifier_blocks():
    assert "direct_identifiers" in vf.build_gate(card(direct=0.01), B2K, POL, "S")["blocking"]


def test_k_must_be_confirmed_by_pycanon_and_at_least_five():
    low = [{"action": "suppress_k", "params": {"k_pycanon": 4}}]
    none = [{"action": "suppress_k", "params": {}}]
    assert "k_anonymity" in vf.build_gate(card(), B2K, low, "S")["blocking"]
    assert "k_anonymity" in vf.build_gate(card(), B2K, none, "S")["blocking"]
    assert "k_anonymity" not in vf.build_gate(card(), B2K, [], "S")["blocking"]


def test_every_shared_component_must_be_lower_than_b2k():
    b = {"risk_components": B2K["risk_components"] | {"turns: other": 0.1}}
    g = vf.build_gate(card(extra={"turns: other": 0.1}), b, POL, "S")
    assert "risk_vs_baseline" in g["blocking"]
    assert "turns: other" in next(c for c in g["checks"] if c["id"] == "risk_vs_baseline")["reason"]


def test_components_b2k_does_not_measure_are_skipped_and_no_baseline_fails_closed():
    g = vf.build_gate(card(extra={"conversations: only ours": 0.0}), B2K, POL, "S")
    assert g["passed"]
    assert "risk_vs_baseline" in vf.build_gate(card(), None, POL, "S")["blocking"]
