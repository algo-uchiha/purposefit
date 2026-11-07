"""Send one short call to the configured LLM provider. Prints OK or the error.

Run from the project root: uv run --env-file .env python -m scripts.check_llm [provider]
"""

from __future__ import annotations

import sys

from api.pipeline.llm import LLMError, get_client


def main() -> int:
    provider = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        client = get_client(provider)
        client.complete("Reply with the single word OK.", max_tokens=5, use_cache=False)
    except LLMError as exc:
        cause = exc.__cause__
        detail = f" ({str(cause)[:300]})" if cause else ""
        print(f"ERROR: {exc}{detail}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
