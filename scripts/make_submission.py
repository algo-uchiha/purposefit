"""Build pets_submission/ for the organiser checks (vendor/proving_ground/docs/EVALUATION.md).

  uv run --env-file .env python -m scripts.make_submission --run final-CS-S1

Writes, from a finished CS-S1 run:
  customer_service_eval_redacted.csv   turn_id,text for the eval-split turns
  customer_service/<table>.csv         the protected CS-S1 tables
  customer_service/rowmap_<table>.csv  their row maps (see the note below)
  unseen_text_spans.jsonl              spans in the free-text column c16 of the unseen dataset
unseen_field_labels.csv is kept as it is. This is the one place a row map leaves runs/private:
the organisers ask for it, the data is synthetic and the maps are used only for scoring. The
gazetteer values are never copied.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

from api import cli
from api.pipeline import io
from api.pipeline.redact import Layers, redact
from api.pipeline.redact.gazetteer import Controller

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "pets_submission"
TEXT_COLUMN = "c16"
# Unseen labels -> gazetteer subtypes for the controller values of the unseen export.
GAZ_SUBTYPES = {"PERSON_NAME", "NATIONAL_ID", "PHONE", "EMAIL", "IBAN", "STREET_ADDRESS"}


def eval_redacted(run: Path) -> int:
    base = io.data_root() / "customer_service"
    conv = io.read_csv(base / "conversations.csv")
    turns = io.read_csv(base / "turns.csv")
    eval_ids = set(conv[conv.split == "eval"].conversation_id)
    eval_turns = list(turns[turns.conversation_id.isin(eval_ids)].turn_id)
    rel = io.read_csv(run / "04_release" / "turns.csv").set_index("turn_id")
    with (OUT / "customer_service_eval_redacted.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["turn_id", "text"])
        for tid in eval_turns:
            w.writerow([tid, rel.loc[tid, "text"]])
    return len(eval_turns)


def protected_tables(run: Path, private: Path) -> list[str]:
    dest = OUT / "customer_service"
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    names = []
    for f in sorted((run / "04_release").glob("*.csv")):
        shutil.copy(f, dest / f.name)
        rm = private / f"rowmap_{f.stem}.csv"
        if rm.exists():
            shutil.copy(rm, dest / rm.name)
        names.append(f.stem)
    return names


def unseen_spans(client) -> int:
    base = io.data_root() / "unseen"
    f = next(base.glob("*.csv"))
    df = io.read_csv(f)
    labels = {r["column"]: r for r in csv.DictReader((OUT / "unseen_field_labels.csv").open(encoding="utf-8"))}
    rows = [(lab["subtype"], v) for c, lab in labels.items()
            if lab["privacy_role"] == "direct_identifier" and lab["subtype"] in GAZ_SUBTYPES
            for v in df[c] if v.strip()]  # fmt: skip
    ctl = Controller(rows)
    texts = {rid: t for rid, t in zip(df["c01"], df[TEXT_COLUMN], strict=True) if t.strip()}
    res = redact(texts, layers=Layers(), controller=ctl, client=client)
    with (OUT / "unseen_text_spans.jsonl").open("w", encoding="utf-8") as out:
        for rid, spans in res.spans.items():
            out.write(json.dumps({"record_id": rid, "spans": [
                {"start": s.start, "end": s.end, "label": s.label} for s in spans]}) + "\n")  # fmt: skip
    return len(texts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="final-CS-S1")
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    run = cli.runs_dir() / a.run
    n = eval_redacted(run)
    tables = protected_tables(run, cli.runs_dir() / "private" / a.run)
    from api.pipeline import llm

    client = llm.get_client(no_llm=a.no_llm)
    m = unseen_spans(client)
    print(json.dumps({"eval_turns": n, "tables": tables, "unseen_texts": m}))


if __name__ == "__main__":
    main()
