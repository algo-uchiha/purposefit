# Phase 5: rule-based text redactor

Layers 1 to 4 plus merge. No NER, no health flags, typed placeholders only.

## What it does

Code: `api/pipeline/redact/` (`patterns`, `normalise`, `gazetteer`, `cues`, `merge`, entry point `redact()` in `__init__.py`). CLI stage: `purposefit redact --run <id>` with `--no-patterns`, `--no-normalise`, `--no-controller`, `--no-dvv`, `--no-cues` (`--no-gazetteer` switches both gazetteer sources off). It rewrites the `redact` text columns of the release, writes `05_spans.jsonl` (offsets, label, layer, score, gazetteer source; never text) and `05_redact_stats.json` (counts and timings).

- Patterns: HETU, IBAN and card checksums (python-stdnum, Luhn), email, IP, IMEI, phone, property id, plate, URL with token, address anchored on a postcode, password and PIN phrases.
- Normalise: spoken digits (fi, sv, en), spoken separators and check letters, spelled emails. Spans map back to the original offsets.
- Gazetteer: two sources. Controller values come from `runs/private/<run>/gazetteer_values.csv` (66,077 values: names, ids, phones, emails, addresses). DVV is the public first-name and surname lists. A DVV name that is also a common word of the texts is skipped.
- Cues: "nimeni on", "jag heter", "my name is", relatives, usernames, last four card digits, first digits of a phone number.
- Merge: validated match first, then longest.

## Measured on the customer_service train split (105k turns)

Measured by `tests/redact_eval.py` (the only place that reads the gold spans). Leakage is pets-eval identifying leakage in the redacted text. Precision is label-agnostic overlap.

| Configuration | Identifying leakage | Span precision | Span recall |
| --- | --- | --- | --- |
| All layers (target: leakage 0.076 or lower, precision 0.95 or higher) | 0.0162 | 0.9875 | 0.8578 |
| DVV names only, no controller values (other layers on) | 0.1263 | 0.9547 | 0.7637 |
| Without patterns | 0.1545 | 0.9855 | 0.7390 |
| Without normalise | 0.1200 | 0.9861 | 0.7687 |
| Without controller gazetteer | 0.1263 | 0.9547 | 0.7637 |
| Without DVV gazetteer | 0.0167 | 0.9998 | 0.8469 |
| Without cues | 0.0295 | 0.9873 | 0.8464 |
| Patterns only | 0.6268 | 1.0000 | 0.3194 |

The DVV-only row uses a looser common-word filter (share 0.0013 instead of 0.0005) because the public list is then the only name source. It was chosen on the first 30,000 train turns as the loosest setting with precision above 0.95, and the full-train figures above are the result. With the controller values the DVV list adds almost nothing (0.0167 to 0.0162) and costs precision.

## CS-S1 scorecard (whole release, as the gate sees it)

| | Privacy | Utility | Composite | Worst risk |
| --- | --- | --- | --- | --- |
| B2-k | 0.4952 | 0.7475 | 0.5849 | 0.8286 |
| PurposeFit before Phase 5 | 0.375 | 1.0 | 0.5238 | 1.0 |
| PurposeFit with rule redactor | 0.9899 | 0.9728 | 0.982 | 0.0162 |

The release gate passes: no direct identifier retained, no quasi-identifier released, every shared risk component lower than B2-k's, identifying text leakage 0.016 (limit 0.10). CS-U5 (common word retention) fell from 1.0 to 0.891 because names and numbers in the text are replaced.

## Known gaps

- Names of places, dates, organisations and health mentions are not touched by the rule layers (leakage 0.88 to 0.96 for LOCATION, DATE, ORG, HEALTH). These are not counted as identifying by pets-eval. Phase 6 adds NER and the health layer.
- Spoken national ids that lose a fragment across turns still leak (NATIONAL_ID 0.1146), and some secrets without a digit (SECRET 0.073).
- Names that are neither in the controller values, the DVV lists nor after a cue phrase are not found. The DVV-only figure shows how much the controller values help in this synthetic data, where the name pool is small.
- The gate figure includes the eval split, as agreed; all tuning used the train split.
