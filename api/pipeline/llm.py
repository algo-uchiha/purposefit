"""The only module in PurposeFit that calls a language model.

One interface (`LLMClient.complete`) over three providers:

- `gemma` (default): Google's open-weights Gemma 3 model, served through the Gemini API
  for the demo. google-genai SDK, model `gemma-3-27b-it`, key `GEMINI_API_KEY`.
- `featherless` (optional): LumiOpen/Llama-Poro-2-8B-Instruct through Featherless's
  OpenAI-compatible API, key `FEATHERLESS_API_KEY`.
- `none`: every call raises `LLMDisabled`. Selected by `LLM_PROVIDER=none` or `--no-llm`.

Rules (CLAUDE.md, PROJECT_BRIEF.md section 7):

- Every response is cached on disk by a hash of its inputs in `runs/cache/llm/`.
- Rate-limit and temporary-unavailable errors are retried with exponential backoff.
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
DEFAULT_PROVIDER = "gemma"

GEMMA_MODEL = "gemma-3-27b-it"
FEATHERLESS_MODEL = "LumiOpen/Llama-Poro-2-8B-Instruct"
FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"

RETRY_STATUS = {429, 503}


class LLMError(RuntimeError):
    """A model call failed, or a provider could not be configured."""


class LLMDisabled(LLMError):
    """The LLM layer is switched off (provider `none` or --no-llm)."""


class Provider(Protocol):
    name: str
    model: str

    def generate(
        self, prompt: str, *, system: str | None, temperature: float, max_tokens: int
    ) -> str: ...


def _require_env(var: str) -> str:
    value = os.environ.get(var, "").strip()
    if not value:
        raise LLMError(f"{var} is not set. Add a line {var}=... to .env")
    return value


class GemmaProvider:
    """Gemma 3 27B through the Gemini API (google-genai SDK)."""

    name = "gemma"

    def __init__(self, api_key: str | None = None, model: str = GEMMA_MODEL) -> None:
        from google import genai

        self.model = model
        self._client = genai.Client(api_key=api_key or _require_env("GEMINI_API_KEY"))

    def generate(
        self, prompt: str, *, system: str | None, temperature: float, max_tokens: int
    ) -> str:
        from google.genai import types

        # Gemma on the Gemini API does not accept a system instruction, so it is
        # placed in front of the user prompt instead.
        contents = f"{system}\n\n{prompt}" if system else prompt
        resp = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=temperature, max_output_tokens=max_tokens
            ),
        )
        return resp.text or ""


class FeatherlessProvider:
    """Poro 2 8B through Featherless (OpenAI-compatible API)."""

    name = "featherless"

    def __init__(self, api_key: str | None = None, model: str = FEATHERLESS_MODEL) -> None:
        from openai import OpenAI

        self.model = model
        self._client = OpenAI(
            base_url=FEATHERLESS_BASE_URL,
            api_key=api_key or _require_env("FEATHERLESS_API_KEY"),
            max_retries=0,  # retries are handled by LLMClient
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

    def generate(
        self, prompt: str, *, system: str | None, temperature: float, max_tokens: int
    ) -> str:
        raise LLMDisabled("LLM layer is disabled")


PROVIDERS: dict[str, Callable[[], Provider]] = {
    "gemma": GemmaProvider,
    "featherless": FeatherlessProvider,
    "none": NoneProvider,
}


def is_retryable(exc: BaseException) -> bool:
    """True for rate-limit (429) and temporarily unavailable (503) errors from either SDK.

    google-genai's APIError carries `.code`; openai's APIStatusError carries `.status_code`.
    """
    status = getattr(exc, "code", None)
    if not isinstance(status, int):
        status = getattr(exc, "status_code", None)
    return isinstance(status, int) and status in RETRY_STATUS


@dataclass(frozen=True)
class LLMResponse:
    text: str
    call_id: str
    provider: str
    model: str
    cached: bool
    duration_ms: int
    attempts: int


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
    ) -> None:
        self.provider = provider
        self.cache_dir = Path(cache_dir)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
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

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        use_cache: bool = True,
    ) -> LLMResponse:
        if not self.enabled:
            raise LLMDisabled("LLM layer is disabled")

        key = self.cache_key(prompt, system, temperature, max_tokens)
        call_id = key[:16]
        path = self._cache_path(key)
        start = time.monotonic()

        if use_cache and path.exists():
            text = json.loads(path.read_text(encoding="utf-8"))["text"]
            return self._done(text, call_id, start, cached=True, attempts=0)

        attempt = 0
        while True:
            attempt += 1
            try:
                text = self.provider.generate(
                    prompt, system=system, temperature=temperature, max_tokens=max_tokens
                )
                break
            except Exception as exc:
                if not is_retryable(exc) or attempt > self.max_retries:
                    log.warning(
                        json.dumps(
                            {
                                "event": "llm_error",
                                "call_id": call_id,
                                "model": self.provider.model,
                                "attempts": attempt,
                                "error": type(exc).__name__,
                            }
                        )
                    )
                    raise LLMError(f"LLM call {call_id} failed: {type(exc).__name__}") from exc
                delay = min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
                delay *= 0.5 + random.random()  # nosec B311 (jitter, not security)
                log.info(
                    json.dumps(
                        {
                            "event": "llm_retry",
                            "call_id": call_id,
                            "model": self.provider.model,
                            "attempt": attempt,
                            "delay_ms": int(delay * 1000),
                        }
                    )
                )
                self._sleep(delay)

        if use_cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(
                    {"provider": self.provider.name, "model": self.provider.model, "text": text},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            tmp.replace(path)
        return self._done(text, call_id, start, cached=False, attempts=attempt)

    def _done(
        self, text: str, call_id: str, start: float, *, cached: bool, attempts: int
    ) -> LLMResponse:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.info(
            json.dumps(
                {
                    "event": "llm_call",
                    "call_id": call_id,
                    "model": self.provider.model,
                    "duration_ms": duration_ms,
                    "cached": cached,
                    "attempts": attempts,
                }
            )
        )
        return LLMResponse(
            text=text,
            call_id=call_id,
            provider=self.provider.name,
            model=self.provider.model,
            cached=cached,
            duration_ms=duration_ms,
            attempts=attempts,
        )


def get_client(
    provider: str | None = None, *, no_llm: bool = False, cache_dir: Path | None = None
) -> LLMClient:
    """Build the client from `LLM_PROVIDER` (default `gemma`). `no_llm=True` forces `none`."""
    name = "none" if no_llm else (provider or os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER)
    name = name.strip().lower()
    if name not in PROVIDERS:
        raise LLMError(f"Unknown LLM_PROVIDER {name!r}; use one of {sorted(PROVIDERS)}")
    return LLMClient(PROVIDERS[name](), cache_dir=cache_dir or DEFAULT_CACHE_DIR)
