"""Read-only API: endpoints, gate refusal, the private-folder ban, traversal and CORS."""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from api.main import create_app

SECRET_ROWMAP = "ROWMAP_SECRET_VALUE_123"
GATE_OK = {"passed": True, "scenario_id": "CS-S1", "blocking": [],
           "checks": [{"id": "text_leakage", "status": "pass", "reason": "ok", "source": "pets-eval"}]}  # fmt: skip
GATE_BAD = {"passed": False, "scenario_id": "CS-S1", "blocking": ["risk_vs_baseline", "text_leakage"],
            "checks": [{"id": "text_leakage", "status": "fail", "reason": "Identifying leakage is 0.5", "source": "pets-eval"}]}  # fmt: skip
PLAN = {"dataset": "customer_service", "scenario_id": "CS-S1", "released_tables": ["turns"],
        "policies": [{"table": "turns", "column": "text", "action": "redact", "params": {},
                      "reason": "used by CS-U1", "guarantee": "typed placeholders"}],
        "k": 1, "key_id": "abc123abc123"}  # fmt: skip
CARD = {"summary": {"privacy": 0.99, "utility": 0.97, "composite": 0.98, "label": "self-assessment"},
        "risk_components": {"turns: free-text identifier leakage": 0.01},
        "tables": {"turns": {"free_text": {"text": {"per_label": {
            "HEALTH": {"n": 10, "leaked": 8, "rate": 0.8}, "PERSON": {"n": 10, "leaked": 0, "rate": 0.0}}}}}}}  # fmt: skip


def make_run(runs, run_id="r1", gate=GATE_OK):
    rp = runs / run_id
    (rp / "04_release").mkdir(parents=True)
    (rp / "06_scorecard_ours").mkdir()
    (rp / "00_manifest.json").write_text(json.dumps({
        "run_id": run_id, "created_utc": "2026-11-08T00:00:00+00:00", "git_hash": "abc1234",
        "key_id": "k" * 12, "seed": 1, "llm": {"provider": "none", "model": "none"},
        "layers": {"llm": False, "ner": False, "gazetteer": True}}))  # fmt: skip
    (rp / "01_profiles.json").write_text("[]")
    (rp / "03_plan.json").write_text(json.dumps(PLAN))
    (rp / "04_transform_stats.json").write_text(json.dumps({"tables": {}, "duration_ms": 5}))
    (rp / "04_release" / "turns.csv").write_text("turn_id,conversation_id,text\nT1,cv_aa,hello [PERSON]\n")
    (rp / "05_redact_stats.json").write_text(json.dumps({"layers": ["patterns"], "duration_ms": 9}))
    (rp / "05_spans.jsonl").write_text(json.dumps({"record_id": "T1", "start": 6, "end": 11, "label": "PERSON",
                                                   "layer": "cues", "score": 0.7}) + "\n")  # fmt: skip
    (rp / "06_gate.json").write_text(json.dumps(gate))
    (rp / "06_scorecard_ours" / "scorecard.json").write_text(json.dumps(CARD))
    (rp / "06_scorecard_b2k.json").write_text(json.dumps(CARD))
    (rp / "07_plan_table.md").write_text("| Table | Column |\n")
    return rp


@pytest.fixture
def env(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    (runs / "private" / "r1").mkdir(parents=True)
    (runs / "private" / "r1" / "rowmap_turns.csv").write_text(SECRET_ROWMAP)
    (runs / "cache" / "llm").mkdir(parents=True)
    data = tmp_path / "data" / "customer_service"
    data.mkdir(parents=True)
    (data / "turns.csv").write_text("turn_id,conversation_id,speaker,text\nT1,C1,customer,\"hello Maija, please help me with the card that you have\"\n")
    monkeypatch.setenv("PURPOSEFIT_DATA_DIR", str(tmp_path / "data"))
    make_run(runs)
    return runs, TestClient(create_app(runs, web_dist=tmp_path / "none"))


def test_refuses_to_start_without_the_key(tmp_path, monkeypatch):
    monkeypatch.delenv("PURPOSEFIT_HMAC_KEY")
    with pytest.raises(Exception, match="PURPOSEFIT_HMAC_KEY"):
        create_app(tmp_path)


def test_health_has_key_id_and_never_the_key(env):
    r = env[1].get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and len(r.json()["key_id"]) == 12
    assert "test-dummy-key-not-secret" not in r.text


def test_scenarios_endpoint(env, proving_ground, monkeypatch):
    monkeypatch.delenv("PURPOSEFIT_DATA_DIR")
    r = env[1].get("/api/scenarios")
    assert r.status_code == 200 and {s["id"] for s in r.json()["scenarios"]} >= {"CS-S1", "CS-S3"}


def test_run_and_every_stage(env):
    _, c = env
    run = c.get("/api/runs/r1").json()
    assert run["scenario_id"] == "CS-S1" and run["gate"]["passed"] is True
    assert next(s["stage"] for s in run["stages"]) == "run" and run["derived_key_id"] == "abc123abc123"
    assert c.get("/api/runs/r1/stages/plan").json()["scenario_id"] == "CS-S1"
    assert c.get("/api/runs/r1/stages/profile").json() == []
    assert c.get("/api/runs/r1/stages/transform").json()["duration_ms"] == 5
    red = c.get("/api/runs/r1/stages/redact").json()
    assert red["redacted"] and red["turns"][0]["spans"][0]["label"] == "PERSON"
    v = c.get("/api/runs/r1/stages/verify").json()
    assert v["gate"]["passed"] and v["baseline_name"] == "B2-k"
    assert any(x["id"] == "leak.health" for x in v["residual_risks"])  # a label above 5 % is named
    assert not any(x["id"] == "leak.person" for x in v["residual_risks"])
    rep = c.get("/api/runs/r1/stages/report").json()
    assert rep["policy_card"] is None  # written by the verify stage
    assert c.get("/api/runs/r1/stages/detect").status_code == 404  # not written


def test_errors_use_the_contract_shape(env):
    _, c = env
    assert c.get("/api/runs/nope").json() == {"error": {"code": "run_not_found", "message": "No run with id nope."}}
    assert c.get("/api/runs/r1/stages/bogus").status_code == 400
    assert c.get("/api/runs/r1/stages/run").status_code == 400
    assert c.post("/api/runs").status_code == 501
    assert c.get("/api/runs/" + "x" * 65).status_code == 400


def test_export_holds_only_released_tables_plan_and_card(env):
    _, c = env
    r = c.get("/api/runs/r1/export")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert 'filename="r1_release.zip"' in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert sorted(z.namelist()) == ["07_plan_table.md", "policy_card.json", "policy_card.md", "turns.csv"]
    blob = b"".join(z.read(n) for n in z.namelist())
    card = json.loads(z.read("policy_card.json"))
    assert card["pseudonymisation"]["secret"]["key_id"] == "abc123abc123"
    assert card["pseudonymisation"]["additional_information"]["held_by"] == "controller"
    assert "Pseudonymisation secret" in z.read("policy_card.md").decode()
    assert "test-dummy-key-not-secret" not in blob.decode("utf-8", "ignore")
    assert SECRET_ROWMAP.encode() not in blob and b"05_spans" not in blob and b"Maija" not in blob


def test_export_is_refused_while_the_gate_has_not_passed(env):
    runs, c = env
    make_run(runs, "bad", GATE_BAD)
    r = c.get("/api/runs/bad/export")
    assert r.status_code == 409 and r.json()["error"]["code"] == "gate_failed"
    assert "risk_vs_baseline" in r.json()["error"]["message"] and "text_leakage" in r.json()["error"]["message"]
    assert r.content[:2] != b"PK"


def test_private_folder_and_caches_are_never_served(env):
    runs, c = env
    for u in ("/api/runs/private", "/api/runs/cache", "/api/runs/private/stages/plan",
              "/api/runs/private/export", "/api/runs/%2e%2e", "/api/runs/..%2fprivate%2fr1"):  # fmt: skip
        r = c.get(u)
        assert r.status_code in (400, 404) and SECRET_ROWMAP not in r.text
    (runs / "private" / "00_manifest.json").write_text("{}")  # even a folder that looks like a run
    assert c.get("/api/runs/private").status_code == 404
    for u in ("/api/runs/r1", "/api/runs/r1/stages/verify", "/api/leaderboard"):
        assert SECRET_ROWMAP not in c.get(u).text


def test_cors_allows_only_localhost(env):
    _, c = env
    ok = c.get("/api/health", headers={"Origin": "http://localhost:5173"})
    bad = c.get("/api/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


def test_leaderboard_reads_the_csv(env):
    runs, c = env
    assert c.get("/api/leaderboard").json() == []
    head = ("created_utc,run_id,git_hash,dataset,scenario,method,privacy,utility,composite,worst_risk,"
            "worst_risk_component,k,k_pycanon,utility_tasks,note\n")
    (runs / "leaderboard.csv").write_text(head + '2026,r1,abc,customer_service,CS-S1,purposefit,0.9,1.0,0.95,0.0,,,,"{}",n\n')
    row = c.get("/api/leaderboard").json()[0]
    assert row["composite"] == 0.95 and row["k"] is None and row["worst_risk_component"] is None


def test_web_dist_is_served_from_the_same_app(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>PurposeFit</html>")
    c = TestClient(create_app(tmp_path / "runs", web_dist=dist))
    assert "PurposeFit" in c.get("/").text and c.get("/api/health").status_code == 200
    assert c.get("/api/nothing").json()["error"]["code"] == "not_found"


def test_kept_labels_are_described_as_kept_on_purpose():
    from api.pipeline import views

    gate = {"checks": []}
    rows = [{"label": "DATE", "n": 10, "leaked": 9, "rate": 0.9},
            {"label": "SECRET", "n": 10, "leaked": 1, "rate": 0.1}]  # fmt: skip
    out = {r["id"]: r["text"] for r in views.residual_risks({}, {"policies": []}, gate, rows)}
    assert "kept on purpose" in out["leak.date"] and "still recoverable" not in out["leak.date"]
    assert "still recoverable" in out["leak.secret"]
