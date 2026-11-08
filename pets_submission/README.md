# Organiser submission

Built by `scripts/make_submission.py` from the final CS-S1 run (`runs/final-CS-S1`, see `runs/final-CS-S1/00_manifest.json` for the git hash, models and key id).

| File | What it is |
| --- | --- |
| `unseen_field_labels.csv` | Column labels for `data/unseen/export_2025_q4.csv` (rules plus LLM, mapped by column name). |
| `customer_service_eval_redacted.csv` | `turn_id,text` for the eval-split turns, from the final redactor (rule layers plus health flags). |
| `customer_service/` | The protected CS-S1 tables (`conversations.csv`, `turns.csv`) and their row maps `rowmap_<table>.csv`. |
| `unseen_text_spans.jsonl` | Spans found in the free-text column `c16` of the unseen dataset (`record_id` is the value of `c01`). |

Row-map exception: the project rule is that row maps stay in `runs/private/` and never leave it. The organisers ask for them in this folder so the scorer can align protected rows with originals. The data is the synthetic proving ground, the maps are used only for scoring, and nothing else leaves `runs/private/` (no gazetteer values, no keys, no caches). Do not publish this folder outside the submission.
