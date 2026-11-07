.PHONY: test lint audit demo

test:
	LLM_PROVIDER=none uv run pytest -q

lint:
	uv run ruff check .
	uv run bandit -q -r api scripts -c pyproject.toml

audit:
	uv run pip-audit --skip-editable
	@if [ -f web/package.json ]; then cd web && npm audit --omit=dev; else echo "web/package.json not found, npm audit skipped"; fi

demo:
	uv run --env-file .env python -m api.cli run --run demo --no-llm

eval-detect:
	LLM_PROVIDER=none uv run --with ./vendor/proving_ground/toolkit pytest -q -rs tests/test_detect_scores.py
