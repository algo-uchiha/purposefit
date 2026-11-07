import json
import socket

import pytest

from api import cli


def test_refuses_to_start_without_hmac_key(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("PURPOSEFIT_HMAC_KEY")
    assert cli.main(["run", "--run", "r1"]) == 2
    assert "PURPOSEFIT_HMAC_KEY=" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


def test_run_writes_manifest_without_the_key(tmp_path):
    assert cli.main(["run", "--run", "r1", "--no-llm"]) == 0
    path = tmp_path / "runs" / "r1" / "00_manifest.json"
    text = path.read_text(encoding="utf-8")
    m = json.loads(text)
    assert "test-dummy-key-not-secret" not in text
    assert m["key_id"] == cli.key_id("test-dummy-key-not-secret") and len(m["key_id"]) == 12
    assert m["llm"] == {"provider": "none", "model": "none"}
    assert m["layers"] == {"llm": False, "ner": True, "gazetteer": True}
    assert {"git_hash", "seed", "created_utc"} <= m.keys()
    assert (tmp_path / "runs" / "private").is_dir()


def test_manifest_names_gemma_without_needing_its_key(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemma")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert cli.main(["run", "--run", "r2"]) == 0
    m = json.loads((tmp_path / "runs" / "r2" / "00_manifest.json").read_text())
    assert m["llm"] == {"provider": "gemma", "model": "gemma-4-31b-it"}


@pytest.mark.parametrize("stage", [s for s in cli.STAGES if s != "run"])
def test_every_stage_accepts_run(stage, capsys):
    assert cli.main([stage, "--run", "r1"]) == 3
    assert "not built yet" in capsys.readouterr().err


@pytest.mark.parametrize("bad", ["../escape", "a/b", "", "x" * 65])
def test_rejects_unsafe_run_ids(bad):
    with pytest.raises(SystemExit):
        cli.main(["run", "--run", bad])


def test_key_id_differs_per_key():
    assert cli.key_id("a") != cli.key_id("b")


def test_tests_cannot_reach_the_network():
    with pytest.raises(RuntimeError, match="network"):
        socket.create_connection(("example.com", 443), timeout=1)
