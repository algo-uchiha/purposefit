# API export and residual-risk checks

## 1. Turn sample in the Text view
`redact_view` (api/pipeline/views.py) now picks 12 turns: up to 9 English turns that have at least one span, plus 3 English turns longer than 40 characters with none. English means at least 6 words with 20% or more common English function words. Turns keep corpus order, so they are grouped by conversation. The empty-turn note reads "No private words found in this turn". Nothing new is logged. Fixtures were regenerated and the tests updated.

## 2. Why DATE, LOCATION and ORG show 87 to 91% in residual risks
- DATE 90.7% of 2,837, LOCATION 86.9% of 1,281, ORG 86.8% of 1,351.
- The identifying-text gate (0.0086) counts only labels in `IDENTIFYING` in vendor/proving_ground/toolkit/pets_eval/text.py line 20. The comment on line 18 says LOCATION, DATE and ORG are context. So they are not in the gate number.
- Our redactor never emits those labels. A count of runs/final-CS-S1/05_spans.jsonl shows none. NER is not run, so these three are kept.
- Old behaviour: `residual_risks` printed every label above 5% as "still recoverable". Now `KEPT_LABELS` in api/pipeline/views.py handles DATE, LOCATION and ORG with "kept on purpose: not identifying on its own, needed for meaning". Other labels still say "still recoverable". NATIONAL_ID (5.3%) and SECRET (7.3%) are real remaining leaks and keep that wording.
- Caveat: "not identifying on its own" is the evaluator's definition. Combined with other facts, a date or place can still help re-identify someone.

## 3. Export endpoint, run on a local server
| Run | HTTP | Zip bytes | Files (bytes) |
| --- | --- | --- | --- |
| final-CS-S1 | 200 | 2,444,863 | conversations.csv 586,673; turns.csv 11,701,083; 07_plan_table.md 4,234; policy_card.json 10,611; policy_card.md 5,431 |
| final-CS-S2 | 200 | 2,427,222 | conversations.csv 653,974; turns.csv 11,701,083; 07_plan_table.md 4,201; policy_card.json 10,565; policy_card.md 5,385 |
| final-CS-S3 | 200 | 223,695 | conversations.csv 682,994; 07_plan_table.md 4,471; policy_card.json 9,839; policy_card.md 5,010 |

- No file name contains rowmap, key, private, spans or cache.
- The master HMAC key from .env does not occur in any extracted file. The policy card holds only the derived key id (CS-S1: d8a26adaa22f), which is a fingerprint, not the key.
- A temporary copy of final-CS-S3 with a failed 06_gate.json returned 409 with code gate_failed and the message naming direct_identifiers. The real runs were not touched and the copy was deleted. This used the app's test client on the same `create_app`, not curl. Also: an export request for the run id "private" returned 404 and the encoded `../private` returned 404.
