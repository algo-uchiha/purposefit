# Phase 3 and 4 report: scenario planner, structured transforms, level search

Date: 8 Nov 2026. Seed 20261107. Labels: rules only (`--no-llm`), detect rules as frozen in `0a45371`. Scorer: `pets-eval` 1.0.0 scorecard, run by `api/pipeline/verify.py`. Composite is pets-eval's self-assessment, not the official judging score.

Phase 4 is done in a small version inside the generalise step: a short ladder of levels per kept quasi-identifier and an exhaustive search over their combinations. Free text is released raw until Phase 5.

## What the planner does

1. Reads the scenario's utility tasks and the columns each task uses (`needs` in the pets-eval task registry).
2. Releases only tables and columns a task uses. Other tables are withheld, other columns dropped.
3. A key that joins two released tables gets the same keyed pseudonym (HMAC-SHA256 with `PURPOSEFIT_HMAC_KEY`) in every table. A row key that other tables refer to is also pseudonymised. A row key nothing refers to is kept (see limitations).
4. Technical identifiers no task needs or joins on are dropped (`agent_id`, `customer_id`). None is pseudonymised in these two scenarios, because no released table joins on them.
5. The `split` column is kept for model tasks: the CS-U1 scorer chooses training rows by it once `conversation_id` is pseudonymised.
6. Direct identifiers that are dropped or withheld go to `runs/private/<run>/gazetteer_values.csv` for the Phase 5 text redactor.

## Level search (Phase 4, small version)

- Ladders, finest first. Timestamp: minute, hour, day, week. Age: exact, 5-year band, 10-year band, 10-year band with 80+. Postcode: 5, 3, 2 digits. Birth date: day, month, year. Date: day, week, month. GPS: 3, 2, 1 decimals. Other subtypes have one level, exact.
- Every combination of levels for the kept quasi-identifiers of a table is tried. A combination qualifies if k >= 5 is reached by suppressing at most 2 % of rows, with no cell blanking.
- Each qualifying combination is scored with the scenario's required pets-eval utility tasks (mean, unanswerable counts 0), on tables written and re-read the way the scorecard reads them. Ties go to fewer suppressed rows, then the finer combination. The chosen levels and the runner-up are recorded in the plan.
- If none qualifies, the fixed B2 levels and B2-k's cell blanking are used, and the plan says so.
- k is checked on the kept quasi-identifiers only, and again with pyCANON.

## Detector fix: durations

New frozen rule family `name_duration` (commit `0a45371`, before rescoring): a numeric column whose name has duration, kesto or varaktighet, a long unit (seconds, minutes, hours), or a short unit (s, ms) next to a time word is `non_sensitive / DURATION`. The short-unit guard keeps `wind_ms`, a wind speed, out. The dependency rule can still make such a column sensitive: `health.ed_visits.los_minutes` stays `sensitive_attribute`.

| Split | Macro-F1 before | after | Subtype accuracy before | after | Accuracy before | after |
| --- | --- | --- | --- | --- | --- | --- |
| Held-out | 0.72 | 0.72 | 0.82 | 0.83 | 0.71 | 0.71 |
| All 9 | 0.86 | 0.86 | 0.86 | 0.86 | 0.83 | 0.84 |

Two labels changed: `customer_service.conversations.handle_time_s` (was `quasi_identifier / TIMESTAMP`) and `mobility.bike_trips.duration_s` (was `MEASUREMENT`), both now `DURATION`.

## CS-S1: transcripts to an external LLM analytics vendor

| Table | Column | Role | Action | Level | Reason |
| --- | --- | --- | --- | --- | --- |
| conversations | conversation_id | record_key | keyed pseudonym |  | joins released tables; the same keyed pseudonym in every table keeps the join |
| conversations | customer_id | technical_identifier | drop |  | technical identifier no task needs or joins on |
| conversations | agent_id | technical_identifier | drop |  | technical identifier no task needs or joins on |
| conversations | agent_name | direct_identifier | drop |  | direct identifier no task needs |
| conversations | channel | non_sensitive | drop |  | no task of this scenario uses it |
| conversations | language | quasi_identifier | drop |  | quasi-identifier no task needs |
| conversations | started_ts | quasi_identifier | drop |  | quasi-identifier no task needs |
| conversations | intent | non_sensitive | keep |  | used by CS-U1, CS-U3, CS-U4 |
| conversations | sentiment | non_sensitive | drop |  | no task of this scenario uses it |
| conversations | csat | non_sensitive | drop |  | no task of this scenario uses it |
| conversations | resolved | non_sensitive | drop |  | no task of this scenario uses it |
| conversations | handle_time_s | non_sensitive | keep |  | used by CS-U4 |
| conversations | n_turns | non_sensitive | drop |  | no task of this scenario uses it |
| conversations | split | non_sensitive | keep |  | train and eval marker; the model task chooses its training rows by it |
| conversations | agent_note | free_text | drop |  | free text no task needs |
| customers | customer_id | record_key | withhold (table) |  | no task of this scenario uses this table |
| customers | customer_number | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | full_name | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | hetu | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | street_address | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | postcode | quasi_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | city | quasi_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | email | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | phone | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | preferred_language | quasi_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | customer_since | quasi_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | products | non_sensitive | withhold (table) |  | no task of this scenario uses this table |
| customers | contract_number | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | payment_method | non_sensitive | withhold (table) |  | no task of this scenario uses this table |
| customers | iban | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | marketing_consent | non_sensitive | withhold (table) |  | no task of this scenario uses this table |
| customers | payment_default_flag | sensitive_attribute | withhold (table) |  | no task of this scenario uses this table |
| customers | accessibility_needs | sensitive_attribute | withhold (table) |  | no task of this scenario uses this table |
| turns | turn_id | record_key | keep |  | row key no other table refers to; links to nothing outside this table, rows are matched by it |
| turns | conversation_id | technical_identifier | keyed pseudonym |  | joins released tables; the same keyed pseudonym in every table keeps the join |
| turns | seq | non_sensitive | drop |  | no task of this scenario uses it |
| turns | speaker | non_sensitive | drop |  | no task of this scenario uses it |
| turns | ts | quasi_identifier | drop |  | quasi-identifier no task needs |
| turns | text | free_text | keep for text redaction |  | used by CS-U1, CS-U5; text kept for the task |

No quasi-identifier is kept, so there is no k check and no level search. `language`, `started_ts` and `ts` are dropped because no task of CS-S1 uses them.

## CS-S3: quality-audit samples to an outsourced BPO

| Table | Column | Role | Action | Level | Reason |
| --- | --- | --- | --- | --- | --- |
| conversations | conversation_id | record_key | keyed pseudonym |  | row key that other tables refer to; keyed pseudonym stops linking to unreleased records |
| conversations | customer_id | technical_identifier | drop |  | technical identifier no task needs or joins on |
| conversations | agent_id | technical_identifier | drop |  | technical identifier no task needs or joins on |
| conversations | agent_name | direct_identifier | drop |  | direct identifier no task needs |
| conversations | channel | non_sensitive | keep |  | used by CS-U6 |
| conversations | language | quasi_identifier | keep | exact | used by CS-U6; level exact chosen by search |
| conversations | started_ts | quasi_identifier | drop |  | quasi-identifier no task needs |
| conversations | intent | non_sensitive | keep |  | used by CS-U4, CS-U7 |
| conversations | sentiment | non_sensitive | drop |  | no task of this scenario uses it |
| conversations | csat | non_sensitive | drop |  | no task of this scenario uses it |
| conversations | resolved | non_sensitive | keep |  | used by CS-U7 |
| conversations | handle_time_s | non_sensitive | keep |  | used by CS-U4 |
| conversations | n_turns | non_sensitive | drop |  | no task of this scenario uses it |
| conversations | split | non_sensitive | drop |  | no task of this scenario uses it |
| conversations | agent_note | free_text | drop |  | free text no task needs |
| customers | customer_id | record_key | withhold (table) |  | no task of this scenario uses this table |
| customers | customer_number | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | full_name | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | hetu | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | street_address | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | postcode | quasi_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | city | quasi_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | email | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | phone | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | preferred_language | quasi_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | customer_since | quasi_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | products | non_sensitive | withhold (table) |  | no task of this scenario uses this table |
| customers | contract_number | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | payment_method | non_sensitive | withhold (table) |  | no task of this scenario uses this table |
| customers | iban | direct_identifier | withhold (table) |  | no task of this scenario uses this table |
| customers | marketing_consent | non_sensitive | withhold (table) |  | no task of this scenario uses this table |
| customers | payment_default_flag | sensitive_attribute | withhold (table) |  | no task of this scenario uses this table |
| customers | accessibility_needs | sensitive_attribute | withhold (table) |  | no task of this scenario uses this table |
| turns | turn_id | record_key | withhold (table) |  | no task of this scenario uses this table |
| turns | conversation_id | technical_identifier | withhold (table) |  | no task of this scenario uses this table |
| turns | seq | non_sensitive | withhold (table) |  | no task of this scenario uses this table |
| turns | speaker | non_sensitive | withhold (table) |  | no task of this scenario uses this table |
| turns | ts | quasi_identifier | withhold (table) |  | no task of this scenario uses this table |
| turns | text | free_text | withhold (table) |  | no task of this scenario uses this table |

k check on conversations (language): target k 5, achieved k 751, pyCANON k 751, rows suppressed 0 (budget 238), cells blanked: none.

Level search: 1 combinations tried, 1 reach k 5 within the row budget with no cell blanking, 1 scored. Method: level search. Chosen: language exact (utility 1.0, rows suppressed 0).

Chosen levels: `language` exact, the only level for its subtype. No runner-up exists.

The same data gives two plans: CS-S1 releases `conversations` and `turns`; CS-S3 releases only `conversations`, with `channel`, `language` and `resolved`, and withholds the transcripts.

## Scorecards, structured only

| Scenario | Method | Privacy | Utility | Composite | Tasks | k (pyCANON) | Worst risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CS-S1 | PurposeFit, Phase 4 | 0.375 | 1.000 | 0.524 | U1 1.00, U3 1.00, U4 1.00, U5 1.00 | no kept QI | turns text leakage 1.00 |
| CS-S1 | PurposeFit, Phase 3 | 0.375 | 0.928 | 0.514 | U1 1.00, U3 1.00, U4 0.71, U5 1.00 | 5 (5) | turns text leakage 1.00 |
| CS-S1 | B2-k (rerun) | 0.495 | 0.748 | 0.585 | U1 not answerable, U3 1.00, U4 1.00, U5 0.99 | 5 | conversations text leakage 0.83 |
| CS-S3 | PurposeFit, Phase 4 | 1.000 | 1.000 | 1.000 | U4 1.00, U6 1.00, U7 1.00 | 751 (751) | none |
| CS-S3 | B2-k (rerun) | 0.495 | 1.000 | 0.643 | U4 1.00, U6 1.00, U7 1.00 | 5 | conversations text leakage 0.83 |

- CS-S1: CS-U4 is back to 1.00 because `handle_time_s` is no longer blanked. Privacy is still below B2-k because our text is raw; every structured risk component is 0.00. Phase 5 addresses the text.
- CS-S3: every risk component the scorecard measures is 0.00, because transcripts and `agent_note` are not released. That is a statement about the scorecard's measured risks, not a guarantee.

## Limitations

- `turn_id` is released unchanged. It is a meaningless sequential record key, and the organisers' CS-U5 scorer looks up text by it: pseudonymising it scores CS-U5 at 0.
- Free text is released raw until Phase 5.
- The search is trivial on these two scenarios (zero or one kept quasi-identifier). A check run on HEALTH-S1 (plan and transform only, not on the leaderboard) tried 16 combinations of `municipality`, `arrival_ts` and `discharge_ts`; none reached k >= 5 within 2 % rows, so it fell back to fixed B2 levels and blanked 41,141 and 46,388 timestamp cells. HEALTH-S1 needs a coarser ladder or fewer kept quasi-identifiers.
- Utility scores in the search use the scenario's own tasks. They measure fitness for that purpose, not for other uses.

## How it was verified

- `pytest`: 120 passed, 1 skipped (DVV name lists absent). `tests/test_plan.py` covers the planner, every level, the search (all combinations, best utility, tie-break, runner-up, no qualifying combination), the fallback path, pyCANON agreement and private row maps. `tests/test_detect.py` covers the duration names, including `wind_ms` and `temp_min` as non-durations.
- `ruff check` and `bandit`: clean.
- Release folders hold only released tables; row maps are in `runs/private/<run>/`.
