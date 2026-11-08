.PHONY: test lint audit demo serve fixtures submission verify-claims leaderboard eval-detect

test:
	LLM_PROVIDER=none uv run pytest -q

lint:
	uv run ruff check .
	uv run bandit -q -r api scripts -c pyproject.toml

audit:
	uv run pip-audit --skip-editable
	@if [ -f web/package.json ]; then cd web && npm audit --omit=dev; else echo "web/package.json not found, npm audit skipped"; fi

ENVFILE := $(if $(wildcard .env),--env-file .env,)
RUN := uv run --with ./vendor/proving_ground/toolkit $(ENVFILE)
HOST ?= 127.0.0.1
PORT ?= 8000

# The final runs (LLM on, with the cache), the AI-off run, the leaderboard and the fixtures, then the server.
demo:
	scripts/final_run.sh CS-S1 llm
	scripts/final_run.sh CS-S3 llm
	scripts/final_run.sh CS-S2 llm
	scripts/final_run.sh CS-S1 nollm
	$(RUN) python -m scripts.tidy_leaderboard
	$(RUN) python -m scripts.export_ui_fixtures
	$(MAKE) serve

serve:
	uv run $(ENVFILE) uvicorn api.main:create_app --factory --host $(HOST) --port $(PORT)

fixtures:
	$(RUN) python -m scripts.export_ui_fixtures

leaderboard:
	$(RUN) python -m scripts.tidy_leaderboard

submission:
	$(RUN) python -m scripts.make_submission --run final-CS-S1

verify-claims:
	$(RUN) python -m scripts.verify_claims

eval-detect:
	LLM_PROVIDER=none uv run --with ./vendor/proving_ground/toolkit pytest -q -rs tests/test_detect_scores.py
