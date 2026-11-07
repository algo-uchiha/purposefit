# PurposeFit rules for coding agents

Read PROJECT_BRIEF.md first. It holds the vision and the architecture. docs/BUILD_GUIDE.md holds the phases.

- Python 3.11, FastAPI, pandas. Read every CSV with dtype=str, keep_default_na=False.
- Shared types live only in api/pipeline/contracts.py. Change them only when asked.
- Inside api/: never read vendor/proving_ground/truth, metadata/pii_spans, metadata/field_catalog.csv or adversary/. Only tests/ and verify.py may.
- Row maps go to runs/private/ only. Never return them from the API, never log them.
- Logs contain ids, counts and timings only. Never cell values or text.
- Keys come from env: PURPOSEFIT_HMAC_KEY, GEMINI_API_KEY, optional FEATHERLESS_API_KEY. Refuse to start without the HMAC key. Never ask the user to paste keys into chat; tell them which line to add to .env.
- All LLM calls go through api/pipeline/llm.py, are logged by id and can be disabled with --no-llm.
- UI and report text may only state facts from docs/FACTS.md. No em dashes, no emoji, sentence case.
- The user does not write code. Explain plans in plain words, run every check yourself, show the output.
- Every task ends with: pytest green, ruff clean, a git commit, and a short note of what changed and how it was verified.
