"""Tests for api/pipeline/llm.py. No network: providers are faked."""

from __future__ import annotations

import json
import logging

import pytest

from api.pipeline import llm

SECRET_TEXT = "Matti Meikäläinen 010101-123N"


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def generate(self, prompt, *, system, temperature, max_tokens):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


class StatusError(Exception):
    def __init__(self, code=None, status_code=None):
        super().__init__(f"error echoing input: {SECRET_TEXT}")
        self.code = code
        self.status_code = status_code


def make(tmp_path, replies, **kw):
    sleeps = []
    prov = FakeProvider(replies)
    client = llm.LLMClient(prov, cache_dir=tmp_path, sleep=sleeps.append, **kw)
    return client, prov, sleeps


def test_returns_text_and_caches(tmp_path):
    client, prov, _ = make(tmp_path, ["first"])
    r1 = client.complete("hello")
    r2 = client.complete("hello")
    assert (r1.text, r1.cached) == ("first", False)
    assert (r2.text, r2.cached) == ("first", True)
    assert prov.calls == 1
    assert r1.call_id == r2.call_id and len(r1.call_id) == 16
    assert len(list(tmp_path.rglob("*.json"))) == 1


def test_cache_key_depends_on_all_inputs(tmp_path):
    client, _, _ = make(tmp_path, [])
    base = client.cache_key("p", None, 0.0, 10)
    assert base != client.cache_key("p2", None, 0.0, 10)
    assert base != client.cache_key("p", "sys", 0.0, 10)
    assert base != client.cache_key("p", None, 0.5, 10)
    assert base != client.cache_key("p", None, 0.0, 11)


def test_cache_file_does_not_store_prompt(tmp_path):
    client, _, _ = make(tmp_path, ["ok"])
    client.complete(SECRET_TEXT)
    (path,) = tmp_path.rglob("*.json")
    assert SECRET_TEXT not in path.read_text(encoding="utf-8")


def test_use_cache_false_always_calls(tmp_path):
    client, prov, _ = make(tmp_path, ["a", "b"])
    assert client.complete("x", use_cache=False).text == "a"
    assert client.complete("x", use_cache=False).text == "b"
    assert prov.calls == 2
    assert not list(tmp_path.rglob("*.json"))


@pytest.mark.parametrize(
    "err", [StatusError(code=429), StatusError(status_code=429), StatusError(code=503)]
)
def test_retries_on_rate_limit_with_backoff(tmp_path, err):
    client, prov, sleeps = make(tmp_path, [err, err, "done"], base_delay=1.0)
    r = client.complete("x")
    assert r.text == "done" and r.attempts == 3 and prov.calls == 3
    assert len(sleeps) == 2
    assert 0.5 <= sleeps[0] <= 1.5 and 1.0 <= sleeps[1] <= 3.0


def test_gives_up_after_max_retries(tmp_path):
    errs = [StatusError(code=429)] * 4
    client, prov, sleeps = make(tmp_path, errs, max_retries=3)
    with pytest.raises(llm.LLMError):
        client.complete("x")
    assert prov.calls == 4 and len(sleeps) == 3


def test_does_not_retry_other_errors(tmp_path):
    client, prov, sleeps = make(tmp_path, [StatusError(code=400)])
    with pytest.raises(llm.LLMError):
        client.complete("x")
    assert prov.calls == 1 and sleeps == []


def test_backoff_is_capped(tmp_path):
    errs = [StatusError(code=429)] * 8 + ["ok"]
    client, _, sleeps = make(tmp_path, errs, max_retries=10, base_delay=1.0, max_delay=4.0)
    client.complete("x")
    assert max(sleeps) <= 4.0 * 1.5


def test_logs_hold_ids_model_duration_only(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="purposefit.llm")
    client, _, _ = make(
        tmp_path, [StatusError(code=429), "reply " + SECRET_TEXT, StatusError(code=400)]
    )
    client.complete("prompt " + SECRET_TEXT, system="sys " + SECRET_TEXT)
    with pytest.raises(llm.LLMError) as info:
        client.complete("other " + SECRET_TEXT)
    text = caplog.text
    assert SECRET_TEXT not in text and "Matti" not in text
    assert SECRET_TEXT not in str(info.value)
    assert "call_id" in text and "fake-model" in text and "duration_ms" in text


def test_none_provider_and_no_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemma")
    client = llm.get_client(no_llm=True, cache_dir=tmp_path)
    assert not client.enabled
    with pytest.raises(llm.LLMDisabled):
        client.complete("x")
    client = llm.get_client("none", cache_dir=tmp_path)
    with pytest.raises(llm.LLMDisabled):
        client.complete("x")


def test_default_provider_is_gemini_flash_thinking_off(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    client = llm.get_client(cache_dir=tmp_path)
    assert client.provider.name == "gemini"
    assert client.provider.model == "gemini-3.6-flash"
    assert client.provider.can_disable_thinking and client.fallback is None


def test_gemma_stays_selectable_by_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("LLM_PROVIDER", "gemma")
    client = llm.get_client(cache_dir=tmp_path)
    assert client.provider.model == "gemma-4-31b-it" and not client.provider.can_disable_thinking


def test_featherless_provider_configures(tmp_path, monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-not-a-real-key")
    client = llm.get_client("featherless", cache_dir=tmp_path)
    assert client.provider.model == "LumiOpen/Llama-Poro-2-8B-Instruct"
    assert str(client.provider._client.base_url).startswith("https://api.featherless.ai/v1")


@pytest.mark.parametrize(
    "name,var", [("gemini", "GEMINI_API_KEY"), ("gemma", "GEMINI_API_KEY"),
                 ("featherless", "FEATHERLESS_API_KEY")]
)
def test_missing_key_names_the_env_line(tmp_path, monkeypatch, name, var):
    monkeypatch.delenv(var, raising=False)
    with pytest.raises(llm.LLMError, match=var):
        llm.get_client(name, cache_dir=tmp_path)


def test_unknown_provider(tmp_path):
    with pytest.raises(llm.LLMError, match="Unknown"):
        llm.get_client("poro", cache_dir=tmp_path)


def test_gemma_folds_system_into_prompt(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    prov = llm.GemmaProvider()
    seen = {}

    class Resp:
        text = "ok"

    def fake_generate_content(*, model, contents, config):
        seen.update(model=model, contents=contents, config=config)
        return Resp()

    monkeypatch.setattr(prov._client.models, "generate_content", fake_generate_content)
    assert prov.generate("question", system="rules", temperature=0.0, max_tokens=5)[0] == "ok"
    assert seen["model"] == "gemma-4-31b-it"
    assert seen["contents"] == "rules\n\nquestion"
    assert seen["config"].system_instruction is None
    assert seen["config"].thinking_config is None  # Gemma rejects thinking settings
    assert seen["config"].max_output_tokens == 5


def test_llm_model_overrides_default(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("LLM_MODEL", "gemma-4-26b-a4b-it")
    client = llm.get_client("gemma", cache_dir=tmp_path)
    assert client.provider.model == "gemma-4-26b-a4b-it"
    assert llm.get_client("none", cache_dir=tmp_path).provider.model == "none"


def test_featherless_and_gemma_cache_keys_differ(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-not-a-real-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    g = llm.get_client("gemma", cache_dir=tmp_path)
    f = llm.get_client("featherless", cache_dir=tmp_path)
    assert g.cache_key("p", None, 0.0, 5) != f.cache_key("p", None, 0.0, 5)


class Timeout(Exception):
    pass


def test_gemini_model_turns_thinking_off(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    prov = llm.GeminiProvider()
    seen = {}

    class Resp:
        text = "ok"
        usage_metadata = None

    monkeypatch.setattr(prov._client.models, "generate_content",
                        lambda **kw: seen.update(kw) or Resp())
    prov.generate("q", system=None, temperature=0.0, max_tokens=5)
    assert seen["config"].thinking_config.thinking_budget == 0


def test_thinking_model_gets_headroom(tmp_path):
    seen = []

    class Thinker(FakeProvider):
        can_disable_thinking = False

        def generate(self, prompt, *, system, temperature, max_tokens):
            seen.append(max_tokens)
            return "ok"

    client = llm.LLMClient(Thinker([]), cache_dir=tmp_path, thinking_headroom=1000)
    client.complete("x", max_tokens=100)
    assert seen == [1100]


def test_server_error_500_is_retried_and_logged_as_warning(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="purposefit.llm")
    client, prov, _sleeps = make(tmp_path, [StatusError(code=500), "ok"])
    assert client.complete("x").text == "ok" and prov.calls == 2
    assert any(r.levelno == logging.WARNING and "llm_retry" in r.getMessage()
               for r in caplog.records)


def test_empty_answer_is_not_cached_and_falls_back(tmp_path):
    fb = FakeProvider(["fallback answer"])
    fb.model = "fallback-model"
    client = llm.LLMClient(FakeProvider(["", "  "]), cache_dir=tmp_path, fallback=fb,
                           sleep=lambda s: None)
    r = client.complete("x")
    assert (r.text, r.model, r.fallback) == ("fallback answer", "fallback-model", True)
    cached = client.complete("x")
    assert cached.cached and cached.model == "fallback-model"


def test_empty_answer_without_fallback_raises_and_caches_nothing(tmp_path):
    client, prov, _ = make(tmp_path, ["", ""])
    with pytest.raises(llm.EmptyResponse):
        client.complete("x")
    assert prov.calls == 2  # retried once
    assert not list(tmp_path.rglob("*.json"))


def test_empty_answer_is_never_written_to_cache(tmp_path):
    client, prov, _ = make(tmp_path, ["", "real answer"])
    r = client.complete("x")
    assert (r.text, prov.calls) == ("real answer", 2)
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    assert __import__("json").loads(files[0].read_text())["text"] == "real answer"
    assert not list(tmp_path.rglob("*.tmp"))


def test_unparseable_answer_retried_once_then_falls_back(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="purposefit.llm")
    fb = FakeProvider(['{"ok": 1}'])
    fb.model = "fallback-model"
    prov = FakeProvider(["no json", "still no json"])
    client = llm.LLMClient(prov, cache_dir=tmp_path, fallback=fb)
    r = client.complete("x", validate=lambda t: t.startswith("{"))
    assert prov.calls == 2 and r.fallback and r.text == '{"ok": 1}'
    assert "llm_invalid_retry" in caplog.text and "llm_fallback" in caplog.text
    cached = [__import__("json").loads(f.read_text())["text"] for f in tmp_path.rglob("*.json")]
    assert cached == ['{"ok": 1}']


def test_unparseable_answer_without_fallback_caches_nothing(tmp_path):
    client, _, _ = make(tmp_path, ["bad", "bad"])
    with pytest.raises(llm.EmptyResponse):
        client.complete("x", validate=lambda t: False)
    assert not list(tmp_path.rglob("*.json"))


def test_deadline_exceeded_504_counts_as_timeout(tmp_path):
    assert llm.is_timeout(StatusError(code=504))
    fb = FakeProvider(["fast"])
    fb.model = "fallback-model"
    client = llm.LLMClient(FakeProvider([StatusError(code=504)]), cache_dir=tmp_path, fallback=fb)
    assert client.complete("x").fallback


def test_timeout_falls_back(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="purposefit.llm")
    fb = FakeProvider(["fast"])
    fb.model = "fallback-model"
    client = llm.LLMClient(FakeProvider([Timeout()]), cache_dir=tmp_path, fallback=fb)
    assert client.complete("x").text == "fast"
    assert "llm_fallback" in caplog.text and SECRET_TEXT not in caplog.text


def test_timeout_without_fallback_raises(tmp_path):
    client, _, _ = make(tmp_path, [Timeout()])
    with pytest.raises(llm.LLMError):
        client.complete("x")


def test_gemma_client_has_flash_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    monkeypatch.delenv("LLM_FALLBACK_MODEL", raising=False)
    client = llm.get_client("gemma", cache_dir=tmp_path)
    assert client.fallback.model == "gemini-3.6-flash"
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "none")
    assert llm.get_client("gemma", cache_dir=tmp_path).fallback is None


def test_fingerprint_changes_with_the_answers_used(tmp_path):
    class P:
        name, model = "fake", "fake-1"

        def __init__(self, text):
            self.text = text

        def generate(self, prompt, **_kw):
            return self.text

    a = llm.LLMClient(P("one"), cache_dir=tmp_path / "a")
    b = llm.LLMClient(P("two"), cache_dir=tmp_path / "b")
    assert a.fingerprint()["calls"] == 0
    a.complete("q")
    b.complete("q")
    a2 = llm.LLMClient(P("zzz"), cache_dir=tmp_path / "a")
    a2.complete("q")  # read from a's cache: the same answer as a used
    assert a.fingerprint() == a2.fingerprint() and a.fingerprint() != b.fingerprint()
    assert a.fingerprint()["calls"] == 1 and "one" not in json.dumps(a.fingerprint())
