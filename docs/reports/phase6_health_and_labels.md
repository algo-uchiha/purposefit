# Phase 6-lite: health flags, and the LLM label fix

## LLM column labels (bug fix)

The batch prompt used numeric ids and a JSON list. On the unseen dataset the answers landed one column off (c21 to c24). Now the batch prompt asks for one JSON object keyed by the exact column name (`table.column` only when names repeat in a batch). The reply is mapped by name only. A missing, unknown or duplicated name rejects the whole batch and the rule labels stay. `detect --llm --no-llm-cache` asks again instead of reading the cache. The dependency rule already ran after the LLM pass; it now also reaches an LLM quasi-identifier guess when the values agree exactly with a sensitive column (c14 follows c13). Tests: shuffled reply, unknown, missing and extra names, cache bypass, dependency after the LLM.

Rescored on the 475 columns of the 9 domains (LLM on, rules unchanged): macro-F1 0.86, sensitive recall 0.99, subtype accuracy 0.83 (before the fix: 0.88, 0.98, 0.84). The model's answers are not identical between calls even at temperature 0, so a rerun without the cache can move a few labels (the unseen file differs in a handful of non-sensitive columns between two fresh calls).

## Health flags (`redact/health.py`)

Sentences are prefiltered with Finnish, Swedish and English health cue words. Each distinct sentence goes to the LLM once, in batches of 40, with id-keyed JSON answers `{"s3": "<span>"}`. An answer counts only if the span occurs verbatim in the sentence; a reworded span is asked again once. The span is replaced by `[HEALTH]`, and if it touches another span the two become one `[HEALTH]` span. All calls go through `llm.py` (cached, logged by call id). The layer is on by default and does nothing when the LLM is off (`--no-llm`, `--no-health`).

| customer_service train split (105k turns) | HEALTH leakage | Health span precision | Identifying leakage | All-span precision |
| --- | --- | --- | --- | --- |
| Rule layers only | 0.9557 | none made | 0.0162 | 0.9875 |
| Rule layers + health flags | 0.0114 | 1.0 (all flagged spans overlap a gold health span) | 0.0162 | 0.9877 |

Health recall (gold health spans overlapped by any span) is 0.9886. Cost on the full train split: 9 calls, 12,558 prompt tokens and 4,328 output tokens, 295 distinct cue sentences out of 1,000 turns with a cue. The cue words and prompt were tuned on the first 20,000 train turns; the full-train figures are one measurement. The price per token was not looked up, so no dollar figure is given.

## CS-S1 scorecard (whole release, gate view)

| | Privacy | Utility | Composite | Worst risk | HEALTH leakage |
| --- | --- | --- | --- | --- | --- |
| B2-k | 0.4952 | 0.7475 | 0.5849 | 0.8286 | |
| Rule redactor (Phase 5) | 0.9899 | 0.9728 | 0.982 | 0.0162 | 0.9557 |
| + health flags | 0.9899 | 0.9721 | 0.9817 | 0.0161 | 0.0029 |

The release gate still passes. The release run made 10 calls (14,370 prompt and 5,101 output tokens).

## Known gaps

- The pets-eval identifying metric does not count HEALTH, so the privacy score does not move; the HEALTH rate is reported next to it.
- Remaining health leaks are sentences without a cue word (the cue list is generic, not exhaustive) or where the model returns an empty answer for a sentence that has one.
- LOCATION, DATE and ORG are still not redacted (NER, later).
