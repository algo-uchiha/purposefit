"""The only module in PurposeFit that calls a language model.

One interface (`LLMClient.complete`) over four providers, chosen by `LLM_PROVIDER`:

- `gemini` (default): `gemini-3.6-flash` on the Gemini API, thinking off. google-genai SDK,
  key `GEMINI_API_KEY`.
- `gemma` (optional, env only, not exercised by default): `gemma-4-31b-it` on the Gemini API.
  It always thinks and rejects thinking settings, so its output cap gets `THINKING_HEADROOM`
  extra tokens, and it falls back to `LLM_FALLBACK_MODEL` (default gemini-3.6-flash) on
  timeout or empty answers. On 7-8 Nov 2026 it returned 500s and 30 s timeouts.
- `featherless` (optional, env only): LumiOpen/Llama-Poro-2-8B-Instruct through Featherless's
  OpenAI-compatible API, key `FEATHERLESS_API_KEY`.
- `none`: every call raises `LLMDisabled`. Selected by `LLM_PROVIDER=none` or `--no-llm`.

`LLM_MODEL` (optional) overrides the provider's default model name.

The LLM step is optional and swappable; every release is also produced and verified with it
switched off. Callers must keep working when a call fails.

Rules (CLAUDE.md, PROJECT_BRIEF.md section 7):

- Every non-empty response is cached on disk by a hash of its inputs in `runs/cache/llm/`.
- Rate-limit and server errors (429, 500, 503) are retried with exponential backoff; each
  retry is logged at WARNING.
- Logs carry only the call id, model, duration and counts. Never prompt or response text,
  never exception messages (they may echo input).
- The LLM never sets a parameter and never edits released data. Callers must validate output.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

log = logging.getLogger("purposefit.llm")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = PROJECT_ROOT / "runs" / "cache" / "llm"
DEFAULT_PROVIDER = "gemini"

GEMINI_MODEL = "gemini-3.6-flash"
GEMMA_MODEL = "gemma-4-31b-it"
FALLBACK_MODEL = "gemini-3.6-flash"
FEATHERLESS_MODEL = "LumiOpen/Llama-Poro-2-8B-Instruct"
FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"

RETRY_STATUS = {429, 500, 503}
DEFAULT_TIMEOUT_S = 30.0
THINKING_HEADROOM = 2048


class LLMError(RuntimeError):
    """A model call failed, or a provider could not be configured."""


class LLMDisabled(LLMError):
    """The LLM layer is switched off (provider `none` or --no-llm)."""


class Provider(Protocol):
    name: str
    model: str

    def generate(
        self, prompt: str, *, system: str | None, temperature: float, max_tokens: int
    ) -> str | tuple[str, dict[str, int]]: ...


def _require_env(var: str) -> str:
    value = os.environ.get(var, "").strip()
    if not value:
        raise LLMError(f"{var} is not set. Add a line {var}=... to .env")
    return value


class GemmaProvider:
    """Models on the Gemini API (google-genai SDK). Optional `gemma` provider; also the base
    class of the default `gemini` provider."""

    name = "gemma"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = GEMMA_MODEL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        from google import genai
        from google.genai import types

        self.model = model
        # Gemma rejects thinking settings (400); Gemini models accept thinking_budget=0.
        self.can_disable_thinking = model.startswith("gemini")
        self._client = genai.Client(
            api_key=api_key or _require_env("GEMINI_API_KEY"),
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
        )

    def generate(
        self, prompt: str, *, system: str | None, temperature: float, max_tokens: int
    ) -> tuple[str, dict[str, int]]:
        from google.genai import types

        # Gemma on the Gemini API does not accept a system instruction, so it is
        # placed in front of the user prompt instead.
        contents = f"{system}\n\n{prompt}" if system else prompt
        cfg: dict = {"temperature": temperature, "max_output_tokens": max_tokens}
        if self.can_disable_thinking:
            cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        resp = self._client.models.generate_content(
            model=self.model, contents=contents, config=types.GenerateContentConfig(**cfg)
        )
        u = getattr(resp, "usage_metadata", None)
        usage = {
            "prompt_tokens": (u.prompt_token_count or 0) if u else 0,
            "output_tokens": (u.candidates_token_count or 0) if u else 0,
            "thought_tokens": (u.thoughts_token_count or 0) if u else 0,
        }
        return resp.text or "", usage


class GeminiProvider(GemmaProvider):
    """Gemini Flash on the Gemini API, thinking off. The default provider."""

    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = GEMINI_MODEL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        super().__init__(api_key=api_key, model=model, timeout_s=timeout_s)


class FeatherlessProvider:
    """Poro 2 8B through Featherless (OpenAI-compatible API)."""

    name = "featherless"
    can_disable_thinking = True

    def __init__(
        self,
        api_key: str | None = None,
        model: str = FEATHERLESS_MODEL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        from openai import OpenAI

        self.model = model
        self._client = OpenAI(
            base_url=FEATHERLESS_BASE_URL,
            api_key=api_key or _require_env("FEATHERLESS_API_KEY"),
            max_retries=0,  # retries are handled by LLMClient
            timeout=timeout_s,
        )

    def generate(
        self, prompt: str, *, system: str | None, temperature: float, max_tokens: int
    ) -> str:
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat.completions.create(
            model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        return resp.choices[0].message.content or ""


class NoneProvider:
    """LLM switched off."""

    name = "none"
    model = "none"
    can_disable_thinking = True

    def generate(
        self, prompt: str, *, system: str | None, temperature: float, max_tokens: int
    ) -> str:
        raise LLMDisabled("LLM layer is disabled")


PROVIDERS: dict[str, Callable[..., Provider]] = {
    "gemini": GeminiProvider,
    "gemma": GemmaProvider,
    "featherless": FeatherlessProvider,
    "none": NoneProvider,
}


def is_retryable(exc: BaseException) -> bool:
    """True for rate-limit (429) and server (500, 503) errors from either SDK.

    google-genai's APIError carries `.code`; openai's APIStatusError carries `.status_code`.
    """
    status = getattr(exc, "code", None)
    if not isinstance(status, int):
        status = getattr(exc, "status_code", None)
    return isinstance(status, int) and status in RETRY_STATUS


def is_timeout(exc: BaseException) -> bool:
    """httpx, openai and builtin timeouts, also when wrapped by an SDK error.

    The Gemini API reports a client-side deadline as 504 DEADLINE_EXCEEDED.
    """
    seen: BaseException | None = exc
    while seen is not None:
        if isinstance(seen, TimeoutError) or "timeout" in type(seen).__name__.lower():
            return True
        if getattr(seen, "code", None) == 504 or getattr(seen, "status", None) == "DEADLINE_EXCEEDED":
            return True
        seen = seen.__cause__ or seen.__context__
    return False


class EmptyResponse(LLMError):
    """The model returned no text (for example, thinking used the whole output budget),
    or text the caller's validator rejected. Never cached."""


@dataclass(frozen=True)
class LLMResponse:
    text: str
    call_id: str
    provider: str
    model: str
    cached: bool
    duration_ms: int
    attempts: int
    prompt_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    fallback: bool = False


class LLMClient:
    def __init__(
        self,
        provider: Provider,
        *,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        max_retries: int = 5,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        fallback: Provider | None = None,
        thinking_headroom: int = THINKING_HEADROOM,
    ) -> None:
        self.provider = provider
        self.fallback = fallback
        self.cache_dir = Path(cache_dir)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.thinking_headroom = thinking_headroom
        self._sleep = sleep

    @property
    def enabled(self) -> bool:
        return self.provider.name != "none"

    def cache_key(
        self, prompt: str, system: str | None, temperature: float, max_tokens: int
    ) -> str:
        payload = json.dumps(
            {
                "provider": self.provider.name,
                "model": self.provider.model,
                "system": system,
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json"

    def _cap(self, provider: Provider, max_tokens: int) -> int:
        if getattr(provider, "can_disable_thinking", True):
            return max_tokens
        return max_tokens + self.thinking_headroom

    def _call(
        self, provider: Provider, call_id: str, prompt: str, system: str | None,
        temperature: float, max_tokens: int, validate: Callable[[str], bool] | None = None,
    ) -> tuple[str, dict[str, int], int]:  # fmt: skip
        attempt = 0
        invalid_retried = False
        while True:
            attempt += 1
            try:
                out = provider.generate(
                    prompt, system=system, temperature=temperature,
                    max_tokens=self._cap(provider, max_tokens),
                )  # fmt: skip
                text, usage = out if isinstance(out, tuple) else (out, {})
                if not text.strip() or (validate is not None and not validate(text)):
                    reason = "empty" if not text.strip() else "unparseable"
                    if invalid_retried:
                        raise EmptyResponse(f"LLM call {call_id} returned {reason} text")
                    invalid_retried = True
                    log.warning(json.dumps({"event": "llm_invalid_retry", "call_id": call_id,
                                            "model": provider.model, "reason": reason}))  # fmt: skip
                    continue
                return text, usage, attempt
            except EmptyResponse:
                raise
            except Exception as exc:
                if not is_retryable(exc) or attempt > self.max_retries:
                    log.warning(json.dumps({
                        "event": "llm_error", "call_id": call_id, "model": provider.model,
                        "attempts": attempt, "error": type(exc).__name__,
                        "status": getattr(exc, "code", None) or getattr(exc, "status_code", None),
                        "timeout": is_timeout(exc),
                    }))  # fmt: skip
                    raise
                delay = min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
                delay *= 0.5 + random.random()  # nosec B311 (jitter, not security)
                log.warning(json.dumps({
                    "event": "llm_retry", "call_id": call_id, "model": provider.model,
                    "attempt": attempt, "status": getattr(exc, "code", None)
                    or getattr(exc, "status_code", None), "delay_ms": int(delay * 1000),
                }))  # fmt: skip
                self._sleep(delay)

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        use_cache: bool = True,
        validate: Callable[[str], bool] | None = None,
    ) -> LLMResponse:
        """`validate`, if given, must return True for usable text. An empty or invalid answer
        is retried once on the same model, then sent to the fallback, and never cached."""
        if not self.enabled:
            raise LLMDisabled("LLM layer is disabled")

        key = self.cache_key(prompt, system, temperature, max_tokens)
        call_id = key[:16]
        path = self._cache_path(key)
        start = time.monotonic()

        if use_cache and path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            return self._done(cached["text"], call_id, start, cached=True, attempts=0,
                              model=cached.get("model", self.provider.model), usage={},
                              fallback=cached.get("fallback", False))  # fmt: skip

        provider, used_fallback = self.provider, False
        try:
            text, usage, attempts = self._call(
                provider, call_id, prompt, system, temperature, max_tokens, validate
            )
        except Exception as exc:
            if self.fallback is None or not (is_timeout(exc) or isinstance(exc, EmptyResponse)):
                if isinstance(exc, LLMError):
                    raise
                raise LLMError(f"LLM call {call_id} failed: {type(exc).__name__}") from exc
            log.warning(json.dumps({
                "event": "llm_fallback", "call_id": call_id, "from": provider.model,
                "to": self.fallback.model,
                "reason": "empty" if isinstance(exc, EmptyResponse) else "timeout",
            }))  # fmt: skip
            provider, used_fallback = self.fallback, True
            try:
                text, usage, attempts = self._call(
                    provider, call_id, prompt, system, temperature, max_tokens
                )
            except LLMError:
                raise
            except Exception as exc2:
                raise LLMError(f"LLM call {call_id} failed: {type(exc2).__name__}") from exc2

        if use_cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f".{os.getpid()}.{random.random():.6f}.tmp")  # nosec B311
            tmp.write_text(
                json.dumps({"provider": self.provider.name, "model": provider.model,
                            "fallback": used_fallback, "text": text}, ensure_ascii=False),
                encoding="utf-8",
            )  # fmt: skip
            tmp.replace(path)
        return self._done(text, call_id, start, cached=False, attempts=attempts,
                          model=provider.model, usage=usage, fallback=used_fallback)  # fmt: skip

    def _done(
        self, text: str, call_id: str, start: float, *, cached: bool, attempts: int,
        model: str, usage: dict[str, int], fallback: bool,
    ) -> LLMResponse:  # fmt: skip
        duration_ms = int((time.monotonic() - start) * 1000)
        log.info(json.dumps({
            "event": "llm_call", "call_id": call_id, "model": model,
            "duration_ms": duration_ms, "cached": cached, "attempts": attempts,
            "fallback": fallback, **usage,
        }))  # fmt: skip
        return LLMResponse(
            text=text, call_id=call_id, provider=self.provider.name, model=model,
            cached=cached, duration_ms=duration_ms, attempts=attempts,
            prompt_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            thought_tokens=usage.get("thought_tokens", 0), fallback=fallback,
        )  # fmt: skip


def get_client(
    provider: str | None = None, *, no_llm: bool = False, cache_dir: Path | None = None
) -> LLMClient:
    """Build the client from `LLM_PROVIDER` (default `gemini`). `no_llm=True` forces `none`.

    `LLM_MODEL`, if set, overrides the provider's default model name. It has no effect on
    `none`. Only the optional `gemma` provider gets a fallback model (`LLM_FALLBACK_MODEL`).
    """
    name = "none" if no_llm else (provider or os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER)
    name = name.strip().lower()
    if name not in PROVIDERS:
        raise LLMError(f"Unknown LLM_PROVIDER {name!r}; use one of {sorted(PROVIDERS)}")
    model = os.environ.get("LLM_MODEL", "").strip()
    impl = PROVIDERS[name](model=model) if model and name != "none" else PROVIDERS[name]()
    fallback = None
    fb_model = os.environ.get("LLM_FALLBACK_MODEL", "").strip() or FALLBACK_MODEL
    if name == "gemma" and fb_model.lower() != "none" and fb_model != impl.model:
        fallback = GemmaProvider(model=fb_model)
    return LLMClient(impl, cache_dir=cache_dir or DEFAULT_CACHE_DIR, fallback=fallback)
