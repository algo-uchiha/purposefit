"""Export web/fixtures/*.json for the front-end agent, from real stage files.

Usage (after the p4-CS-S1 and p4-CS-S3 runs exist and runs/leaderboard.csv is current):
  uv run --env-file .env python -m scripts.export_ui_fixtures

Shapes are described in docs/API_CONTRACT.md. Reads: runs/<run>/ stage files, the two B2-k
scorecard.json files, runs/leaderboard.csv, the public scenarios and the customer_service
turns. Never reads row maps. Checks the output for the HMAC key, row-map names and local paths.
The gate comes from verify.build_gate. Parts the pipeline does not produce yet (residual
risks, ablation, spans) are placeholders computed here and marked in docs/API_CONTRACT.md.
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

from api.pipeline import io
from api.pipeline import plan as pl
from api.pipeline import verify as vf

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
OUT = ROOT / "web" / "fixtures"
SCENARIOS = ("CS-S1", "CS-S3")
N_TURNS = 20
STAGES = ("run", "profile", "detect", "plan", "transform", "redact", "verify", "report")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, obj) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def clean_scorecard(rep: dict, protected_label: str, dataset: str) -> dict:
    """Same object as pets-eval writes, with local absolute paths replaced by labels."""
    out = json.loads(json.dumps(rep))
    out["original"] = f"data/{dataset}"
    out["protected"] = protected_label
    return out


def gate_for(ours: dict, b2k: dict, plan: dict) -> dict:
    return vf.build_gate(ours, b2k, plan["policies"], plan["scenario_id"])


def residual_risks(ours: dict, plan: dict, gate: dict) -> list[dict]:
    """Plain statements. Wording follows docs/FACTS.md; numbers come from the scorecard."""
    out = []
    for c in gate["checks"]:
        if c["status"] == "fail":
            out.append({"id": c["id"], "text": c["reason"], "source": c["source"]})
    out.append({"id": "pseudonymised_is_personal_data",
                "text": "Pseudonymised data is still personal data (GDPR Recital 26).",
                "source": "docs/FACTS.md"})  # fmt: skip
    if any(p["action"] == "suppress_k" for p in plan["policies"]):
        out.append({"id": "k_scope",
                    "text": "k-anonymity limits singling out on the stated quasi-identifiers "
                            "only; it does not stop attribute inference inside a uniform group.",
                    "source": "docs/FACTS.md"})  # fmt: skip
    return out


def k_summary(plan: dict) -> list[dict]:
    return [{"table": p["table"], "qis": p["params"]["qis"], "pipeline_k": p["params"].get("k"),
             "pycanon_k": p["params"].get("k_pycanon"), "method": p["params"].get("method")}
            for p in plan["policies"] if p["action"] == "suppress_k"]  # fmt: skip


def scenarios_fixture() -> dict:
    pu = pl._pets_eval()
    scen = load(pl.proving_ground_root() / "metadata" / "scenarios.json")
    descr = {t.id: (t.table, t.kind, t.description) for t in pu.all_tasks()}
    datasets = [d for d in io.list_datasets() if d != "unseen"]
    items = []
    for s in scen:
        tasks = [{"id": t, "table": descr[t][0], "kind": descr[t][1], "description": descr[t][2]}
                 for t in s["utility_requirements"] if t in descr]  # fmt: skip
        items.append({k: s[k] for k in ("id", "dataset", "title", "recipient", "purpose",
                                        "trust_level", "threat_model",
                                        "suggested_privacy_targets")}
                     | {"utility_tasks": tasks})  # fmt: skip
    return {"datasets": [{"id": d, "available": d == "customer_service",
                          "scenario_ids": [s["id"] for s in items if s["dataset"] == d]}
                         for d in datasets], "scenarios": items}  # fmt: skip


def leaderboard_fixture() -> list[dict]:
    rows = []
    for r in csv.DictReader((RUNS / "leaderboard.csv").open(encoding="utf-8")):
        def num(v):
            return None if v == "" else float(v)

        rows.append({"created_utc": r["created_utc"], "run_id": r["run_id"],
                     "git_hash": r["git_hash"], "dataset": r["dataset"],
                     "scenario": r["scenario"], "method": r["method"],
                     "privacy": num(r["privacy"]), "utility": num(r["utility"]),
                     "composite": num(r["composite"]), "worst_risk": num(r["worst_risk"]),
                     "worst_risk_component": r["worst_risk_component"] or None,
                     "k": None if r["k"] == "" else int(r["k"]),
                     "k_pycanon": None if r["k_pycanon"] == "" else int(r["k_pycanon"]),
                     "utility_tasks": json.loads(r["utility_tasks"]), "note": r["note"]})
    return rows


def turns_fixture(scenario: str) -> dict:
    """First N_TURNS turns: original text, the released text (equal until Phase 5), no spans."""
    run = RUNS / f"p4-{scenario}"
    orig = io.read_csv(io.data_root() / "customer_service" / "turns.csv").head(N_TURNS)
    rel = io.read_csv(run / "04_release" / "turns.csv").set_index("turn_id")
    turns = []
    for tid, text in zip(orig.turn_id, orig.text, strict=True):
        turns.append({"record_id": tid, "conversation_id": rel.loc[tid, "conversation_id"],
                      "original_text": text, "protected_text": rel.loc[tid, "text"],
                      "surrogate_text": None, "spans": []})  # fmt: skip
    return {"dataset": "customer_service", "table": "turns", "column": "text",
            "redacted": False, "layers_run": [], "n_turns": len(turns), "turns": turns,
            "per_label": [], "span_labels_note": "spans are empty until Phase 5"}  # fmt: skip


def export() -> list[str]:
    OUT.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("PURPOSEFIT_HMAC_KEY", "")
    write("scenarios.json", scenarios_fixture())
    write("leaderboard.json", leaderboard_fixture())
    base = RUNS / "p4-CS-S1"
    labels = load(base / "02_labels_detail.json")
    findings = [*load(RUNS / "p2c-after" / "02_findings.json"),
                *load(RUNS / "p2c-after-unseen" / "02_findings.json")]  # fmt: skip
    write("findings.json", findings)
    write("stage.profile.json", load(base / "01_profiles.json"))
    write("stage.detect.json", {"dataset": "customer_service", "labels": labels,
                                "findings": load(base / "02_findings.json"),
                                "stats": load(base / "02_detect_stats.json")})  # fmt: skip
    write("health.json", {"status": "ok", "git_hash": load(base / "00_manifest.json")["git_hash"],
                          "key_id": load(base / "00_manifest.json")["key_id"],
                          "llm": {"provider": "none", "model": "none", "enabled": False},
                          "proving_ground": True})  # fmt: skip
    for sid in SCENARIOS:
        run = RUNS / f"p4-{sid}"
        man, plan = load(run / "00_manifest.json"), load(run / "03_plan.json")
        ours = clean_scorecard(load(run / "06_scorecard_ours" / "scorecard.json"),
                               "runs/<run_id>/04_release", "customer_service")  # fmt: skip
        b2k = clean_scorecard(
            load(RUNS / "private" / "baselines" / f"b2k_{sid}" / "scorecard.json"),
            "B2-k baseline release", "customer_service")  # fmt: skip
        gate = gate_for(ours, b2k, plan)
        stats = load(run / "04_transform_stats.json")
        write(f"plan.{sid}.json", plan)
        write(f"scorecard.ours.{sid}.json", ours)
        write(f"scorecard.b2k.{sid}.json", b2k)
        write(f"stage.transform.{sid}.json", stats)
        write(f"stage.verify.{sid}.json", {
            "scenario_id": sid, "ours": ours, "baseline": b2k, "baseline_name": "B2-k",
            "gate": gate, "k": k_summary(plan), "residual_risks": residual_risks(ours, plan, gate),
            "ablation": []})  # fmt: skip
        write(f"stage.report.{sid}.json", {"plan_table_md": (run / "07_plan_table.md").read_text(
            encoding="utf-8"), "policy_card": None})  # fmt: skip
        write(f"stage.redact.{sid}.json", turns_fixture(sid) if sid == "CS-S1" else {
            "dataset": "customer_service", "table": None, "redacted": False, "layers_run": [],
            "n_turns": 0, "turns": [], "per_label": [],
            "span_labels_note": "transcripts are withheld in this scenario"})  # fmt: skip
        status = {"profile": "done", "detect": "done", "plan": "done", "transform": "done",
                  "redact": "pending", "verify": "done", "report": "done", "run": "done"}
        dur = {"transform": stats["duration_ms"]}
        write(f"run.{sid}.json", {
            "run_id": man["run_id"], "dataset": "customer_service", "scenario_id": sid,
            "status": "done", "created_utc": man["created_utc"], "git_hash": man["git_hash"],
            "key_id": man["key_id"], "seed": man["seed"], "llm": man["llm"],
            "layers": man["layers"],
            "stages": [{"stage": s, "status": status[s], "duration_ms": dur.get(s)}
                       for s in STAGES],
            "gate": {"passed": gate["passed"], "blocking": gate["blocking"]},
            "headline": {"privacy": ours["summary"]["privacy"],
                         "utility": ours["summary"]["utility"],
                         "composite": ours["summary"]["composite"]},
            "error": None})  # fmt: skip
    return check_output(key)


def check_output(key: str) -> list[str]:
    """Fail on a key, a row-map name or a local path anywhere in the fixtures."""
    problems, names = [], []
    for f in sorted(OUT.glob("*.json")):
        names.append(f.name)
        text = f.read_text(encoding="utf-8")
        if key and key in text:
            problems.append(f"{f.name}: contains the HMAC key")
        for bad in ("rowmap", "original_record_id", "/Users/", "/home/", "GEMINI_API_KEY"):
            if bad in text:
                problems.append(f"{f.name}: contains {bad!r}")
    if problems:
        raise SystemExit("fixture check failed:\n" + "\n".join(problems))
    return names


if __name__ == "__main__":
    files = export()
    print(f"wrote {len(files)} files to {OUT.relative_to(ROOT)}")
