# PurposeFit architecture

Source: `PROJECT_BRIEF.md` section 6. If this file and the brief disagree, the brief wins.

## Shape

One Docker container. A FastAPI backend runs the pipeline and serves the built React front end (Carbon, theme g10). No database, no microservices, no auth. State lives in run folders on disk.

```text
                         Browser (React + Carbon)
                                   |
                                   v
 +-------------------------- FastAPI (api/main.py) ---------------------------+
 |  /api/scenarios   /api/runs   /api/runs/{id}/stages/{stage}   /export    |
 |                                   |                                        |
 |                      background pipeline runner                            |
 |                                   v                                        |
 |  1 load+profile -> 2 detect -> 3 plan -> 4 transform -> 4b generalise      |
 |        -> 5 redact text -> 6 verify -> 7 report -> 8 export                |
 |                                   |                                        |
 |  every stage reads the previous file and writes runs/<run_id>/NN_*.json   |
 +----------------------------------------------------------------------------+
        |                     |                         |
        v                     v                         v
  proving ground data    pets-eval + pyCANON      llm.py (optional)
  (vendor/, read only)   (scoring, checks)        default: Gemini 3.6 Flash
                                                  (Gemini API)
                                                  optional: Gemma 4,
                                                  Poro 2 (Featherless)
```

## Repo layout

```text
api/
  main.py                  routes, upload limits, static files
  cli.py                   purposefit run|profile|detect|plan|transform|redact|verify|report --run <id>
  pipeline/
    contracts.py           dataclasses shared by every module
    io.py profile.py detect.py plan.py transform.py generalise.py
    redact/ patterns.py normalise.py gazetteer.py cues.py ner.py health.py merge.py
    verify.py report.py llm.py
web/                       Vite + React + TypeScript + @carbon/react
data/gazetteer/            DVV name lists (CC BY 4.0), fetched by scripts/fetch_gazetteer.py
scripts/                   one-off helpers
vendor/proving_ground/     TrustED proving ground, git-ignored
runs/                      outputs, git-ignored; runs/private/ holds row maps
tests/
```

## Modules

**Stage 0, run manifest (`cli.py`).** Reads arguments and env, writes `00_manifest.json` with git hash, HMAC key id (never the key), model names and seed. Refuses to start without `PURPOSEFIT_HMAC_KEY`. Deterministic.

**Stage 1, profile (`profile.py`).** Reads the dataset CSVs (always `dtype=str, keep_default_na=False`). Per column on up to 2,000 sampled rows: fill rate, distinct ratio, length stats, character classes and python-stdnum validator hit rates. Writes `01_profiles.json`. Deterministic.

**Stage 2, detect (`detect.py`).** Ordered rules on column-name tokens (fi, sv, en) plus profiles give a `FieldLabel` with confidence and a one-line reason. Only low-confidence columns may go to `llm.py`; an answer is accepted only if it is a valid taxonomy term. Writes `02_labels.csv` in the format `pets-eval detect` expects. Deterministic except cached LLM labels.

**Stage 3, plan (`plan.py`).** Reads labels, `metadata/scenarios.json` and each utility task's `requires` list. Releases only tables and columns a scenario task requires; withholds the rest with a reason. Join keys become HMAC-SHA256 pseudonyms. Unneeded direct identifiers are dropped and their values handed to the controller gazetteer. Writes `03_plan.json` (`PolicyPlan`). Deterministic.

**Stage 4, transform (`transform.py`).** Applies the plan. Writes `04_release/*.csv` and `runs/private/rowmap_*.csv`. Row maps never leave `runs/private/`. Deterministic.

**Stage 4b, generalise (`generalise.py`).** Full-domain generalisation lattice over the remaining quasi-identifiers. Keeps level combinations with k >= 5 after at most 2 % row suppression and picks the one with the best scenario utility. Records levels and suppressed count in the plan, and k and l from pyCANON. Deterministic.

**Stage 5, redact (`redact/*`).** Layers in order, each span tagged with its `layer`:

1. `patterns`: HETU (all century signs), IBAN, card (Luhn), phone, email, IP, IMEI, property ID, plate, URL with token.
2. `normalise`: spoken digits (fi, sv, en) and spelled emails rewritten so layer 1 can validate them.
3. `gazetteer`: controller values from detected direct identifier columns, and DVV public name lists. Two sources, reported separately.
4. `cues`: "nimeni on", "jag heter", "my name is", relatives, password and PIN phrases.
5. `ner`: GLiNER2-PII on sentences with no hit; Finnish fallback finbert-ner.
6. `health`: the LLM (default Gemini 3.6 Flash) flags sentences that mention health, prefiltered by cue words.

Overlaps are merged: validated match first, then longest. Writes `05_spans.jsonl` and redacted text into the release. Deterministic except cached NER and LLM output.

**Stage 6, verify (`verify.py`).** Runs `pets-eval` on our release and on baseline B2-k for the same scenario, and pyCANON on the release. Writes `06_scorecard_ours.json`, `06_scorecard_b2k.json`, the gate verdict and an ablation table (redaction rerun with each layer off). Appends a row to `runs/leaderboard.csv`. Only `verify.py` and `tests/` may read `truth/`, `metadata/pii_spans/`, `metadata/field_catalog.csv` or `adversary/`.

**Stage 7, report (`report.py`).** Builds `07_report.md` and `07_policy_card.json` from templates filled with numbers from the scorecards. The LLM may only reword; the rewrite is rejected if any number or technique name changes. Wording only from `docs/FACTS.md`.

**Stage 8, export (`main.py`).** Zips the release without row maps.

**LLM client (`llm.py`).** The only place that calls a model. The default LLM is `gemini-3.6-flash` on the Gemini API, called with the google-genai SDK and `GEMINI_API_KEY`, with thinking off. `LLM_PROVIDER` picks `gemini` (default), `gemma` (`gemma-4-31b-it`, optional), `featherless` (Poro 2 8B, optional, `FEATHERLESS_API_KEY`) or `none`; `--no-llm` forces `none`. The optional providers are selectable by environment only and are not used by default. An optional `LLM_MODEL` overrides the provider's default model name. Gemma 4 31B was the default until 8 Nov 2026; it was dropped because every call that night returned a 500 error or hit the 30 s timeout, and its thinking cannot be switched off. The LLM step is optional and swappable; every release is also produced and verified with it switched off. If the LLM fails after retries, the run continues with rules-only labels, logs it and says so in the report. All calls go through `api/pipeline/llm.py`, which caches every non-empty, valid response by input hash in `runs/cache/llm/`, retries rate-limit and server errors with backoff (logged at WARNING) and logs only call ids, model, duration and token counts. The LLM never sets k, epsilon or any parameter and never edits released data directly.

## Shared contracts (`api/pipeline/contracts.py`)

- `FieldLabel(dataset, table, column, privacy_role, subtype, confidence, reason, source)`
- `Span(record_id, start, end, label, layer, score)`
- `FieldPolicy(table, column, action, params, reason, guarantee)`, action one of keep, drop, hmac, generalise, redact, suppress_k, withhold_table
- `PolicyPlan(dataset, scenario_id, released_tables, policies, k, key_id)`
- `ReleaseReport(plan, scorecard_ours, scorecard_baselines, gate, residual_risks, ablation)`

Vocabulary for `privacy_role`, `subtype` and span labels comes from `vendor/proving_ground/metadata/taxonomy.md`.

## Front end screens

1. Scenario: choose dataset and recipient scenario.
2. Plan: DataTable of every field with detected role, technique, guarantee and reason. Withheld tables shown.
3. Text: original and protected transcript side by side, span labels with their layer.
4. Verify: gate notification, ours vs B2-k charts, pyCANON k, ablation table, residual risks.
5. Export: download release zip and policy card.

## Scenarios

- Hero: `customer_service`, CS-S1 (external analytics vendor mining contact reasons).
- Contrast: `customer_service`, CS-S3 (aggregate volumes).
- Stretch: `health`, HEALTH-S1.

Development uses the customer_service train split. The eval split is touched only to produce the organiser submission.

## Release gate

Status: proposed starting point, to be made concrete after reading the `pets-eval` scorer and before any tuning.

- Zero residual direct identifiers in structured columns.
- k >= 5 on the released quasi-identifiers, confirmed by pyCANON.
- Every risk component lower than B2-k's on the same scenario.
- Identifying leakage in turns <= 0.10.
- Health leakage on train: first target <= 0.50.
- Span precision >= 0.95 (spike measured 0.99, label-agnostic, overlap).
