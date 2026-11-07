# PurposeFit: project brief for Claude Code

Read this file first, then `CLAUDE.md`, then `docs/BUILD_GUIDE.md`. This file is the vision and the architecture. The build guide is the step by step plan. If they disagree, this file wins and you tell me.

## 1. Who you are working with

I am the product owner. I do not write code. You write, run and test all of it.

- Explain what you are about to do in plain language before you do it, in 3 to 6 short lines.
- After each task, tell me: what changed, how you checked it, the result (numbers), and what I should look at.
- Never ask me to edit code. If you need a decision, give me 2 or 3 options with your recommendation.
- Never ask me to paste API keys into the chat. Tell me which line to add to `.env` and I will do it.
- Run every check yourself and show me the output. Do not say "it should work".

## 2. The vision in one paragraph

Organisations hold support transcripts, patient notes and transaction logs that partners, researchers and AI vendors want to use. The common fix, "remove the names", fails: in the TrustED proving ground, regex redaction still leaks 71 to 88 % of identifying values in free text, because people say ID numbers aloud and spell out emails. PurposeFit asks three questions (who receives the data, for what purpose, who might attack it) and compiles a release for that purpose. It keeps only what the purpose needs, gives join keys keyed pseudonyms, coarsens quasi-identifiers until k-anonymity holds, scrubs identifiers from free text using the organisation's own records and public name lists, then re-runs real attacks before it lets anything be exported. Every choice comes with a plain reason and every claim with a measured number.

## 3. The challenge (Since AI Hackathon 2026, TrustED PETs Transformer)

The tool must show, for one realistic sharing scenario:

1. the data types it detected,
2. the privacy enhancing technique chosen for each,
3. the transformed dataset,
4. analytical utility before and after,
5. the sharing scenario the output is fit for,
6. reduced disclosure risk and honest limitations.

Judging criteria: technical implementation, innovation, impact (less risk, same utility), presentation. Data: only the synthetic proving ground. Submission: working prototype, short English video, description, repo.

## 4. What makes us different (keep these three visible everywhere)

1. **Controller knowledge finds identifiers in text.** Values from columns detected as direct identifiers, plus official Finnish name lists, are matched inside free text in every spoken, spelled and formatted variant.
2. **The purpose decides the protection.** The scenario's utility tasks decide which tables and columns are released and how coarse each quasi-identifier can be. Two recipients of the same data get two different plans.
3. **Verify before release.** The organisers' own scorer (`pets-eval`) and an independent library (pyCANON) run on every release. A failed check blocks export and names the open risk.

## 5. Evidence we already have (feasibility spike, customer_service, train split)

| Measure | Classic baseline (B2 or B2-k) | Spike |
| --- | --- | --- |
| Identifying values leaked in transcripts | 0.80 | 0.076 |
| Person names leaked | 1.00 | 0.00 |
| CS-S1 privacy score | 0.50 | 0.86 |
| CS-S1 utility score | 0.75 | 0.97 |
| CS-S1 composite | 0.58 | 0.91 |

The spike code is in `spike/redact_spike.py` and `spike/e2e_cs2.py`. Start the redactor from it. Known gaps: health mentions (100 % leaked), names in agent notes (44 %), secrets, card numbers, addresses. The name result is helped by the synthetic name pool, so we must also report results with public name lists only.

## 6. Architecture

### 6.1 Shape

One Docker container. A FastAPI backend runs the pipeline and serves the built React front end. No database, no microservices, no auth. State lives in run folders on disk.

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
  (vendor/, read only)   (scoring, checks)        default: Gemma 3 27B
                                                  (Gemini API)
                                                  optional: Poro 2 8B
                                                  (Featherless)
```

### 6.2 Stages, inputs and outputs

| # | Stage | Module | Reads | Writes | Deterministic |
| --- | --- | --- | --- | --- | --- |
| 0 | Run manifest | `cli.py` | arguments, env | `00_manifest.json` (git hash, key id, models, seed) | yes |
| 1 | Profile | `profile.py` | dataset CSVs | `01_profiles.json` | yes |
| 2 | Detect | `detect.py` (+ `llm.py` for low confidence only) | profiles | `02_labels.csv` (pets-eval format) | yes, except the optional LLM labels, which are cached |
| 3 | Plan | `plan.py` | labels, `scenarios.json`, utility task requirements | `03_plan.json` (PolicyPlan) | yes |
| 4 | Transform | `transform.py` | plan, CSVs | `04_release/*.csv`, `runs/private/rowmap_*.csv` | yes |
| 4b | Generalise | `generalise.py` | plan, release | updated release, chosen levels in plan, pyCANON k and l | yes |
| 5 | Redact | `redact/*` | release text columns, gazetteers | `05_spans.jsonl`, redacted text in release | yes, except NER and LLM, which are cached |
| 6 | Verify | `verify.py` | release, originals | `06_scorecard_ours.json`, `06_scorecard_b2k.json`, gate verdict, ablation | yes |
| 7 | Report | `report.py` | plan, scorecards | `07_report.md`, `07_policy_card.json` | yes; LLM may only reword, numbers re-checked |
| 8 | Export | `main.py` | release | zip without row maps | yes |

### 6.3 Redactor layers (stage 5)

Run in this order. Merge overlapping spans: validated match first, then longest. Every span keeps its `layer`.

1. `patterns`: HETU (python-stdnum, all century signs), IBAN, card (Luhn), phone, email, IP, IMEI, property ID, plate, URL with token.
2. `normalise`: spoken digits (fi, sv, en) and spelled emails turned into text that layer 1 can validate.
3. `gazetteer`: controller values from detected direct identifier columns, and DVV public name lists. Two separate sources, reported separately.
4. `cues`: "nimeni on", "jag heter", "my name is", relatives, password and PIN phrases.
5. `ner`: GLiNER2-PII on sentences with no hit; Finnish fallback finbert-ner.
6. `health`: the LLM (default Gemma 3 27B) flags sentences that mention health, prefiltered by cue words.

### 6.4 Shared contracts (`api/pipeline/contracts.py`)

- `FieldLabel(dataset, table, column, privacy_role, subtype, confidence, reason, source)`
- `Span(record_id, start, end, label, layer, score)`
- `FieldPolicy(table, column, action, params, reason, guarantee)` where action is one of keep, drop, hmac, generalise, redact, suppress_k, withhold_table
- `PolicyPlan(dataset, scenario_id, released_tables, policies, k, key_id)`
- `ReleaseReport(plan, scorecard_ours, scorecard_baselines, gate, residual_risks, ablation)`

Vocabulary for `privacy_role`, `subtype` and span labels comes from `vendor/proving_ground/metadata/taxonomy.md`. Do not invent new terms.

### 6.5 Front end screens (Carbon, theme g10, no custom radius)

1. Scenario: choose dataset and recipient scenario.
2. Plan: DataTable of every field with detected role, technique, guarantee and reason. Withheld tables shown.
3. Text: original and protected transcript side by side, span labels with their layer.
4. Verify: gate notification, ours vs B2-k charts, pyCANON k, ablation table, residual risks.
5. Export: download release zip and policy card.

### 6.6 Hero and second scenarios

- Hero: `customer_service`, scenario CS-S1 (external analytics vendor mining contact reasons).
- Contrast: the same dataset with CS-S3 (aggregate volumes) to show the plan changes with purpose.
- Stretch: `health`, HEALTH-S1.

### 6.7 LLM provider

The default LLM is Gemma 3 27B (`gemma-3-27b-it`): Google's open-weights Gemma 3 model, served through the Gemini API for the demo. It is called with the google-genai SDK and `GEMINI_API_KEY`. Poro 2 8B (`LumiOpen/Llama-Poro-2-8B-Instruct`) on Featherless stays available as an optional provider with `FEATHERLESS_API_KEY`. `LLM_PROVIDER` picks `gemma`, `featherless` or `none`; `--no-llm` forces `none`. All calls go through `api/pipeline/llm.py`, which caches every response by input hash in `runs/cache/llm/`, retries rate-limit errors with backoff and logs only call ids, model and duration.

## 7. Non-negotiables

- Detection and transformation never read `truth/`, `metadata/pii_spans/`, `metadata/field_catalog.csv` or `adversary/`. Only tests and `verify.py` may.
- Row maps never leave `runs/private/`.
- Logs hold ids, counts and timings only.
- Keys only from environment variables. The app refuses to start without `PURPOSEFIT_HMAC_KEY`.
- The LLM never sets k, epsilon or any parameter, never edits released data directly, and its output is validated.
- UI and report wording only from `docs/FACTS.md`. No "anonymous", "GDPR compliant" or "secure". No em dashes, no emoji, sentence case.
- Use the customer_service train split for development. Touch the eval split only to produce the organiser submission.

## 8. How we work, every phase

1. I tell you the phase number from `docs/BUILD_GUIDE.md`.
2. You read the phase, then show me a short plan. Wait for my "go".
3. You build, run the tests and the phase's check, and fix until green.
4. You commit with a clear message so we can roll back.
5. You report: what changed, the check output, the leaderboard row if there is one, what to look at next.

If something in the guide is wrong or a library does not behave as described, stop and tell me, with a recommendation.

## 9. Files you have

| File | What it is |
| --- | --- |
| `PROJECT_BRIEF.md` | This file |
| `CLAUDE.md` | Short rules, loaded every session |
| `docs/BUILD_GUIDE.md` | Phases 0 to 10 with prompts and checks |
| `docs/FACTS.md` | The only facts the product may state, with sources |
| `docs/challenge/` | Official challenge PDF and the detailed brief |
| `vendor/proving_ground/` | Unzipped TrustED proving ground (data, pets-eval, baselines, scenarios) |
| `spike/` | Feasibility spike scripts with the results above |
