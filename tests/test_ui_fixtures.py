"""web/fixtures hold example API responses for the front end: valid, no secrets, no row maps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.pipeline.contracts import FieldPolicy, PolicyPlan

FIXTURES = Path(__file__).resolve().parents[1] / "web" / "fixtures"
FILES = sorted(FIXTURES.glob("*.json"))


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_fixtures_exist():
    assert len(FILES) >= 20


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_fixture_is_clean_json(path):
    text = path.read_text(encoding="utf-8")
    json.loads(text)
    for bad in ("rowmap", "original_record_id", "/Users/", "/home/", "API_KEY", "HMAC_KEY"):
        assert bad not in text


@pytest.mark.parametrize("sid", ["CS-S1", "CS-S3"])
def test_plan_fixture_matches_the_contract_types(sid):
    d = _load(f"plan.{sid}.json")
    plan = PolicyPlan(**{**d, "policies": [FieldPolicy(**p) for p in d["policies"]]})
    assert plan.scenario_id == sid and plan.key_id and len(plan.key_id) == 12


def test_the_two_plans_release_different_tables():
    assert _load("plan.CS-S1.json")["released_tables"] == ["conversations", "turns"]
    assert _load("plan.CS-S3.json")["released_tables"] == ["conversations"]


@pytest.mark.parametrize("sid", ["CS-S1", "CS-S3"])
def test_verify_fixture_has_gate_and_both_scorecards(sid):
    v = _load(f"stage.verify.{sid}.json")
    assert v["ours"]["scenario"]["id"] == sid == v["baseline"]["scenario"]["id"]
    assert v["gate"]["passed"] is (sid == "CS-S3")
    assert (v["gate"]["blocking"] == []) is v["gate"]["passed"]
    assert v["ablation"] == [] and v["residual_risks"]


def test_unanswerable_utility_is_null_not_zero():
    tasks = {u["id"]: u for u in _load("scorecard.b2k.CS-S1.json")["utility"]}
    assert tasks["CS-U1"]["score"] is None and tasks["CS-U1"]["metric"] == "not answerable"


def test_turns_fixture_has_twenty_turns_and_empty_spans():
    t = _load("stage.redact.CS-S1.json")
    assert t["n_turns"] == len(t["turns"]) == 20 and t["redacted"] is False
    assert all(x["spans"] == [] and x["protected_text"] == x["original_text"] for x in t["turns"])
    assert _load("stage.redact.CS-S3.json")["turns"] == []


def test_leaderboard_numbers_are_numbers():
    rows = _load("leaderboard.json")
    assert {r["method"] for r in rows} == {"purposefit", "B2-k (rerun)"}
    assert all(isinstance(r["privacy"], float) and isinstance(r["utility_tasks"], dict)
               for r in rows)  # fmt: skip
