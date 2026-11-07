# Phase 3 report: scenario planner and structured transforms

Date: 8 Nov 2026. Seed 20261107. Labels: rules only (`--no-llm`), detect rules as frozen in `b0321d9`. Scorer: `pets-eval` 1.0.0 scorecard, run by `api/pipeline/verify.py`.

Phase 4's lattice search is cut for time. Phase 3 therefore leaves a protected structured release on its own: fixed B2 generalisation of kept quasi-identifiers, then k >= 5 on those quasi-identifiers only. Free text is released raw until Phase 5.

## What the planner does

1. Reads the scenario's utility tasks and the columns each task uses (`needs` in the pets-eval task registry).
2. Releases only tables and columns a task uses. Other tables are withheld, other columns dropped.
3. A key that joins two released tables gets the same keyed pseudonym (HMAC-SHA256 with `PURPOSEFIT_HMAC_KEY`) in every table. A row key that other tables refer to is also pseudonymised. A row key nothing refers to is kept, because it links to nothing outside its table.
4. Technical identifiers no task needs or joins on are dropped (`agent_id`, `customer_id` in CS-S1). None is pseudonymised in these two scenarios, because no released table joins on them.
5. The `split` column is kept for model tasks: the CS-U1 scorer chooses training rows by it once `conversation_id` is pseudonymised.
6. Kept quasi-identifiers get the fixed B2 level for their subtype: birth date to year, age to 10-year bands with 80+, postcode to 3 digits, timestamp to the hour, GPS to 2 decimals. A subtype without a rule is kept exact. A column labelled TIMESTAMP whose values do not parse as timestamps is kept exact.
7. k >= 5 on the kept quasi-identifiers. Rows in smaller classes are suppressed up to 2 % of rows. Past that budget, the most detailed kept quasi-identifier is blanked in those rows only (B2-k's local suppression). pyCANON checks the result.
8. Direct identifiers that are dropped or withheld go to `runs/private/<run>/gazetteer_values.csv` for the Phase 5 text redactor.

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
| conversations | handle_time_s | quasi_identifier | keep | exact | used by CS-U4; no fixed rule for this subtype, kept exact |
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

k check on conversations (handle_time_s): target k 5, achieved k 5, pyCANON k 5, rows suppressed 0 (budget 238), cells blanked: handle_time_s 2390.

## CS-S3: quality-audit samples to an outsourced BPO

| Table | Column | Role | Action | Level | Reason |
| --- | --- | --- | --- | --- | --- |
| conversations | conversation_id | record_key | keyed pseudonym |  | row key that other tables refer to; keyed pseudonym stops linking to unreleased records |
| conversations | customer_id | technical_identifier | drop |  | technical identifier no task needs or joins on |
| conversations | agent_id | technical_identifier | drop |  | technical identifier no task needs or joins on |
| conversations | agent_name | direct_identifier | drop |  | direct identifier no task needs |
| conversations | channel | non_sensitive | keep |  | used by CS-U6 |
| conversations | language | quasi_identifier | keep | exact | used by CS-U6; no fixed rule for this subtype, kept exact |
| conversations | started_ts | quasi_identifier | drop |  | quasi-identifier no task needs |
| conversations | intent | non_sensitive | keep |  | used by CS-U4, CS-U7 |
| conversations | sentiment | non_sensitive | drop |  | no task of this scenario uses it |
| conversations | csat | non_sensitive | drop |  | no task of this scenario uses it |
| conversations | resolved | non_sensitive | keep |  | used by CS-U7 |
| conversations | handle_time_s | quasi_identifier | keep | exact | used by CS-U4; no fixed rule for this subtype, kept exact |
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

k check on conversations (language, handle_time_s): target k 5, achieved k 5, pyCANON k 5, rows suppressed 0 (budget 238), cells blanked: handle_time_s 5676.

The same data gives two plans: CS-S1 releases `conversations` and `turns`, CS-S3 releases only `conversations`, with `channel`, `language` and `resolved`, and withholds the transcripts.

## Scorecard on CS-S1, structured only

Both rows scored by the same pets-eval scorecard on scenario CS-S1. B2-k was regenerated with `baselines/protect.py --level b2k --scenario CS-S1`. Composite is pets-eval's self-assessment, not the official judging score.

| Method | Privacy | Utility | Composite | CS-U1 | CS-U3 | CS-U4 | CS-U5 | k (pyCANON) | Worst risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PurposeFit, Phase 3 | 0.375 | 0.928 | 0.514 | 1.00 | 1.00 | 0.71 | 1.00 | 5 (5) | turns text leakage 1.00 |
| B2-k (rerun) | 0.495 | 0.748 | 0.585 | not answerable | 1.00 | 1.00 | 0.99 | 5 | conversations text leakage 0.83 |

- Privacy is lower than B2-k because our text is raw (leakage 1.00), while B2-k runs regex redaction (0.80 to 0.83). Every structured risk component is 0.00: no direct identifiers retained, `customers` withheld, `agent_note` dropped. Phase 5 addresses the text.
- Utility is higher: CS-U1 is answerable. B2-k pseudonymises `conversation_id` in `turns` but keeps it raw in `conversations`, so the join breaks and the scorer finds no training conversations. Our join key gets the same pseudonym in both tables.
- CS-U4 is 0.71 because the detector labels `handle_time_s` a quasi-identifier, so 2,390 of 11,943 values (20 %) were blanked to reach k >= 5. In CS-S3, with `language` also kept, 5,676 values (48 %) are blanked. This is the cost of a fixed level with no lattice search.

## How it was verified

- `pytest`: 103 passed, 1 skipped (DVV name lists absent). New tests in `tests/test_plan.py` cover withholding, join keys, the split rule, gazetteer flags, each B2 level, both suppression paths with pyCANON, the keyed pseudonym, private row maps and the plan table.
- `ruff check` and `bandit`: clean.
- Release folder holds only `conversations.csv` and `turns.csv`; row maps are in `runs/private/p3-CS-S1/`.
