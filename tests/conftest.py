"""Shared test setup. Tests never call a real LLM and never need .env."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROVING_GROUND = PROJECT_ROOT / "vendor" / "proving_ground"


class NetworkBlocked(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def _safe_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("PURPOSEFIT_HMAC_KEY", "test-dummy-key-not-secret")
    monkeypatch.setenv("PURPOSEFIT_RUNS_DIR", str(tmp_path / "runs"))

    def refuse(*_a, **_k):
        raise NetworkBlocked("tests may not open network connections")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def proving_ground() -> Path:
    if not PROVING_GROUND.is_dir():
        pytest.skip("vendor/proving_ground is missing (expected in CI); test needs its data")
    return PROVING_GROUND


@pytest.fixture
def dvv_lists():
    from api.pipeline.redact.gazetteer import dvv_names

    first, last = dvv_names()
    if not first or not last:
        pytest.skip("DVV name lists missing in data/gazetteer/ (git-ignored; "
                    "run scripts/fetch_gazetteer.py)")
    return first, last
