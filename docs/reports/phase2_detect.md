# Phase 2 report: profile and detect

Date: 8 Nov 2026. Scorer: `pets_eval.detect.score_detection` (pets-eval 1.0.0) against the public field catalog, run by `scripts/eval_detect.py`. Seed 20261107.

## Fixed before any held-out score was seen

Committed in `1d09fb4` before the first held-out score.

- Tune domains: customer_service, cyber, education, finance, health (331 columns).
- Held-out domains: energy, mobility, public_admin, smart_city (144 columns).
- Rule families, in order: record_key, foreign_key, value_strong, name_direct, name_technical, name_free_text, name_sensitive, name_quasi, value_text, value_quasi, value_code, default.
- LLM confidence threshold: columns below 0.6 go to the LLM. Not changed after.

## Baseline B1, rerun

All 9: macro-F1 0.65, sensitive_attribute recall 0.10, quasi_identifier recall 0.59, subtype accuracy 0.60. This matches `docs/BENCHMARK.md` of the proving ground. Held-out only: macro-F1 0.63, subtype accuracy 0.68.

## Headline scores

| Run | Split | Macro-F1 | Subtype accuracy | Accuracy | Sensitive recall |
| --- | --- | --- | --- | --- | --- |
| B1 | all 9 | 0.65 | 0.60 | 0.67 | 0.73 |
| B1 | held-out | 0.63 | 0.68 | 0.65 | 0.79 |
| Rules only | tune | 0.90 | 0.88 | 0.89 | 0.92 |
| Rules only | held-out | 0.72 | 0.82 | 0.71 | 0.82 |
| Rules only | all 9 | 0.86 | 0.86 | 0.83 | 0.89 |
| Rules + LLM | tune | 0.88 | 0.84 | 0.87 | 0.96 |
| Rules + LLM | held-out | 0.73 | 0.85 | 0.75 | 0.93 |
| Rules + LLM | all 9 | 0.85 | 0.84 | 0.83 | 0.95 |

Sensitive recall is the scorer's share of columns in any protect role that were flagged as some protect role.

The gap between tune (0.90) and held-out (0.72) shows the rules partly fit the tune domains. Held-out is the number to quote.

## Per role, all 9 (precision / recall)

| Role | n | B1 | Rules only | Rules + LLM |
| --- | --- | --- | --- | --- |
| direct_identifier | 76 | 0.82 / 0.89 | 0.94 / 0.95 | 0.94 / 0.95 |
| quasi_identifier | 128 | 0.78 / 0.59 | 0.80 / 0.80 | 0.80 / 0.87 |
| sensitive_attribute | 40 | 0.44 / 0.10 | 0.93 / 0.70 | 0.79 / 0.75 |
| technical_identifier | 38 | 0.55 / 0.84 | 0.74 / 0.97 | 0.65 / 0.97 |
| free_text | 15 | 0.63 / 0.80 | 0.83 / 1.00 | 0.75 / 1.00 |
| record_key | 39 | 0.97 / 0.74 | 1.00 / 1.00 | 1.00 / 1.00 |
| non_sensitive | 139 | 0.55 / 0.71 | 0.76 / 0.73 | 0.87 / 0.66 |

## Per role, held-out (precision / recall)

| Role | n | Rules only | Rules + LLM |
| --- | --- | --- | --- |
| direct_identifier | 22 | 0.83 / 0.91 | 0.83 / 0.91 |
| quasi_identifier | 44 | 0.66 / 0.70 | 0.67 / 0.84 |
| sensitive_attribute | 5 | 1.00 / 0.20 | 1.00 / 0.20 |
| technical_identifier | 6 | 0.38 / 0.83 | 0.38 / 0.83 |
| free_text | 3 | 1.00 / 1.00 | 1.00 / 1.00 |
| record_key | 14 | 1.00 / 1.00 | 1.00 / 1.00 |
| non_sensitive | 50 | 0.67 / 0.56 | 0.82 / 0.56 |

Held-out sensitive_attribute recall is 1 of 5 columns. This is the weakest number and the main open risk for the unseen check.

## LLM pass

Model `gemini-3.6-flash`, thinking off, batches of up to 20 columns, 4 in parallel, 30 s timeout. Answers are kept only if both terms are in the taxonomy.

| Run | Columns sent | Calls | Accepted | Rejected | Failed, kept rule label | Changed | Tokens in / out | Wall time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All 9 | 141 | 8 | 140 | 0 | 1 | 75 | 14,986 / 3,767 | 84 s |
| Unseen | 17 | 1 | 17 | 0 | 0 | 10 | 3,805 / 453 | 2.9 s |

On the earlier default, `gemma-4-31b-it`, single-column calls took 22 to 34 s each. Its thinking used up the whole 200-token output cap, so every answer was empty and all 39 cached answers were unusable. Thinking settings return 400 on that model. Gemma was dropped as the default on 8 Nov 2026.

The LLM step is optional and swappable; every release is also produced and verified with it switched off.
