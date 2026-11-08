"""Read-only views of run folders, shared by the API and the fixture exporter.

Everything here reads files inside one run folder (or the public scenarios and the leaderboard).
Nothing reads runs/private, row maps, caches or keys. Payload shapes follow docs/API_CONTRACT.md.
"""

from __future__ import annotations

import csv
import io as _io
import json
import os
import re
import zipfile
from pathlib import Path

from api.pipeline import io
from api.pipeline import llm as llm_mod
from api.pipeline import plan as pl
from api.pipeline import verify as vf

STAGES = ("run", "profile", "detect", "plan", "transform", "redact", "verify", "report")
PAYLOAD_STAGES = STAGES[1:]
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
N_TURNS = 20
# Files whose presence marks a stage as done.
STAGE_FILES = {"run": "00_manifest.json", "profile": "01_profiles.json",
               "detect": "02_labels_detail.json", "plan": "03_plan.json",
               "transform": "04_transform_stats.json", "redact": "05_redact_stats.json",
               "verify": "06_gate.json", "report": "07_plan_table.md"}  # fmt: skip
# Residual-risk statements are written here from facts in docs/FACTS.md; numbers come from scorecards.
LEAK_LIMIT = 0.05


class NotFound(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class GateFailed(Exception):
    def __init__(self, blocking: list[str]):
        super().__init__("gate failed")
        self.blocking = blocking


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def run_path(runs: Path, run_id: str) -> Path:
    """The run folder, only for a safe id; never `private` or a path outside `runs`."""
    if not RUN_ID_RE.match(run_id) or run_id == "private" or run_id == "cache":
        raise NotFound("run_not_found", "No run with that id.")
    p = (runs / run_id).resolve()
    if p.parent != runs.resolve() or not (p / "00_manifest.json").is_file():
        raise NotFound("run_not_found", f"No run with id {run_id}.")
    return p


def clean_scorecard(rep: dict, protected_label: str, dataset: str) -> dict:
    """The scorecard with local absolute paths replaced by labels."""
    out = json.loads(json.dumps(rep))
    out["original"] = f"data/{dataset}"
    out["protected"] = protected_label
    return out


def residual_risks(ours: dict, plan: dict, gate: dict, per_label: list[dict] | None = None) -> list[dict]:
    """Plain statements. Wording follows docs/FACTS.md; numbers come from the scorecard."""
    out = [{"id": c["id"], "text": c["reason"], "source": c["source"]}
           for c in gate["checks"] if c["status"] == "fail"]  # fmt: skip
    out.append({"id": "pseudonymised_is_personal_data",
                "text": "Pseudonymised data is still personal data (GDPR Recital 26).",
                "source": "docs/FACTS.md"})  # fmt: skip
    if any(p["action"] == "suppress_k" for p in plan["policies"]):
        out.append({"id": "k_scope",
                    "text": "k-anonymity limits singling out on the stated quasi-identifiers "
                            "only; it does not stop attribute inference inside a uniform group.",
                    "source": "docs/FACTS.md"})  # fmt: skip
    for row in sorted(per_label or [], key=lambda r: -r["rate"]):
        if row["rate"] > LEAK_LIMIT:
            out.append({"id": f"leak.{row['label'].lower()}",
                        "text": f"{row['label']} values still recoverable in the released text: "
                                f"{row['rate']:.1%} of {row['n']} (pets-eval).",
                        "source": "pets-eval"})  # fmt: skip
    return out


def k_summary(plan: dict) -> list[dict]:
    return [{"table": p["table"], "qis": p["params"]["qis"], "pipeline_k": p["params"].get("k"),
             "pycanon_k": p["params"].get("k_pycanon"), "method": p["params"].get("method")}
            for p in plan["policies"] if p["action"] == "suppress_k"]  # fmt: skip


def per_label_rows(ours: dict) -> list[dict]:
    ft = ours.get("tables", {}).get("turns", {}).get("free_text", {}).get("text", {})
    return [{"label": k, "n": v["n"], "leaked": v["leaked"], "rate": v["rate"]}
            for k, v in sorted(ft.get("per_label", {}).items())]  # fmt: skip


def ablation_rows(runs: Path) -> list[dict]:
    """Per-layer ablation on the train split from tests/redact_eval.py output files."""
    f5, f6 = runs / "p5-redact-train-full.json", runs / "p6-health-train-full.json"
    if not f5.exists():
        return []

    def row(layer: str, m: dict) -> dict:
        return {"layer_off": layer, "leakage": m["identifying_leakage"], "precision": m["precision"],
                "health_leakage": m["per_label"].get("HEALTH"), "utility": None,
                "n_spans": m["n_spans"], "scope": "customer_service train split"}  # fmt: skip

    rows = [row(n.removeprefix("without "), m) for n, m in load(f5).items() if n.startswith("without ")]
    if f6.exists():
        rows.append(row("health", load(f6)["all layers"]))  # the run without the health layer
    return rows


def scenarios_view() -> dict:
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


def leaderboard_view(runs: Path) -> list[dict]:
    f = runs / "leaderboard.csv"
    if not f.exists():
        return []

    def num(v):
        return None if v == "" else float(v)

    rows = []
    for r in csv.DictReader(f.open(encoding="utf-8")):
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


def _scorecards(rp: Path) -> tuple[dict, dict | None]:
    ours = clean_scorecard(load(rp / "06_scorecard_ours" / "scorecard.json"),
                           "runs/<run_id>/04_release", "customer_service")  # fmt: skip
    f = rp / "06_scorecard_b2k.json"
    b2k = clean_scorecard(load(f), "B2-k baseline release", "customer_service") if f.exists() else None
    return ours, b2k


def run_view(runs: Path, run_id: str) -> dict:
    rp = run_path(runs, run_id)
    man = load(rp / "00_manifest.json")
    plan = load(rp / "03_plan.json") if (rp / "03_plan.json").exists() else None
    dur = {}
    for stage, name in (("transform", "04_transform_stats.json"), ("redact", "05_redact_stats.json")):
        if (rp / name).exists():
            dur[stage] = load(rp / name).get("duration_ms")
    gate = headline = None
    if (rp / "06_gate.json").exists():
        g = load(rp / "06_gate.json")
        gate = {"passed": g["passed"], "blocking": g["blocking"]}
        s = load(rp / "06_scorecard_ours" / "scorecard.json")["summary"]
        headline = {"privacy": s["privacy"], "utility": s["utility"], "composite": s["composite"]}
    scenario = plan["scenario_id"] if plan else None
    return {"run_id": run_id, "dataset": plan["dataset"] if plan else None, "scenario_id": scenario,
            "status": "done" if gate is not None or (rp / STAGE_FILES["report"]).exists() else "running",
            "created_utc": man["created_utc"], "git_hash": man["git_hash"], "key_id": man["key_id"],
            "derived_key_id": plan["key_id"] if plan else None,
            "seed": man["seed"], "llm": man["llm"], "layers": man["layers"],
            "stages": [{"stage": s, "status": "done" if (rp / STAGE_FILES[s]).exists() else "pending",
                        "duration_ms": dur.get(s)} for s in STAGES],
            "gate": gate, "headline": headline, "error": None}  # fmt: skip


def policy_card(plan: dict, gate: dict | None, ours: dict | None,
                residual: list[dict] | None = None, recipient: str | None = None) -> dict:  # fmt: skip
    """What was done to each field and why, the gate, the residual risks and the pseudonymisation
    terms of EDPB Guidelines 01/2025: the secret is named by its key id only, the domain is the
    named recipient, and the additional information (row maps) is held by the controller."""
    return {"scenario_id": plan["scenario_id"], "dataset": plan["dataset"],
            "pseudonymisation": {
                "secret": {"key_id": plan["key_id"], "held_by": "controller",
                           "note": "Derived per scenario; the key itself is never in a release."},
                "domain": {"recipient": recipient or plan["scenario_id"],
                           "note": "Pseudonyms are not valid outside this recipient's release."},
                "additional_information": {"held_by": "controller", "kept_in": "runs/private",
                                           "items": ["row maps", "gazetteer values"]}},
            "released_tables": plan["released_tables"],
            "fields": [{"table": p["table"], "column": p["column"], "action": p["action"],
                        "reason": p["reason"], "guarantee": p["guarantee"]}
                       for p in plan["policies"]],
            "gate": gate, "residual_risks": residual or [],
            "headline_label": ours["summary"]["label"] if ours else None,
            "note": "Pseudonymised data is still personal data (GDPR Recital 26)."}


def policy_card_md(card: dict) -> str:
    ps = card["pseudonymisation"]
    out = [f"# Policy card: {card['scenario_id']}", "",
           "## Pseudonymisation (EDPB Guidelines 01/2025 terms)", "",
           f"- Pseudonymisation secret: key id `{ps['secret']['key_id']}`, held by the controller. The key is never released.",
           f"- Pseudonymisation domain: {ps['domain']['recipient']}.",
           "- Additional information: row maps and gazetteer values, held by the controller.", "",
           "## Fields", "", "| Table | Column | Action | Reason | Guarantee |", "| --- | --- | --- | --- | --- |"]
    for f in card["fields"]:
        out.append(f"| {f['table']} | {f['column']} | {f['action']} | {f['reason']} | {f['guarantee']} |")
    out += ["", "## Release gate", ""]
    if card["gate"]:
        out.append(f"Result: {'passed' if card['gate']['passed'] else 'failed'}.")
        out += [f"- {c['status']}: {c['name'] if 'name' in c else c['id']}. {c['reason']}" for c in card["gate"]["checks"]]
    out += ["", "## Residual risks", ""] + [f"- {r['text']}" for r in card["residual_risks"]]
    out += ["", card["note"], ""]
    return "\n".join(out)


def write_policy_card(rp: Path) -> None:
    """07_policy_card.json and .md for a run whose verify stage has finished."""
    plan, gate = load(rp / "03_plan.json"), load(rp / "06_gate.json")
    ours = load(rp / "06_scorecard_ours" / "scorecard.json")
    risks = residual_risks(clean_scorecard(ours, "", plan["dataset"]), plan, gate, per_label_rows(ours))
    card = policy_card(plan, gate, ours, risks, _recipient(plan["scenario_id"]))
    (rp / "07_policy_card.json").write_text(json.dumps(card, indent=1, ensure_ascii=False), encoding="utf-8")
    (rp / "07_policy_card.md").write_text(policy_card_md(card), encoding="utf-8")


def _recipient(scenario_id: str) -> str | None:
    try:
        scen = load(pl.proving_ground_root() / "metadata" / "scenarios.json")
    except OSError:
        return None
    return next((s["recipient"] for s in scen if s["id"] == scenario_id), None)


def redact_view(rp: Path, plan: dict, ours: dict) -> dict:
    if "turns" not in plan["released_tables"] or not (rp / "05_spans.jsonl").exists():
        return {"dataset": plan["dataset"], "table": None, "redacted": False, "layers_run": [],
                "n_turns": 0, "turns": [], "per_label": [],
                "span_labels_note": "transcripts are withheld in this scenario"}  # fmt: skip
    orig = io.read_csv(io.data_root() / plan["dataset"] / "turns.csv").head(N_TURNS)
    rel = io.read_csv(rp / "04_release" / "turns.csv").set_index("turn_id")
    want = set(orig.turn_id)
    spans: dict[str, list[dict]] = {t: [] for t in want}
    with (rp / "05_spans.jsonl").open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["record_id"] in want:
                spans[r["record_id"]].append({k: r[k] for k in ("start", "end", "label", "layer", "score")})
    turns = [{"record_id": tid, "conversation_id": rel.loc[tid, "conversation_id"],
              "original_text": text, "protected_text": rel.loc[tid, "text"],
              "surrogate_text": None, "spans": spans[tid]}
             for tid, text in zip(orig.turn_id, orig.text, strict=True)]  # fmt: skip
    stats = load(rp / "05_redact_stats.json")
    return {"dataset": plan["dataset"], "table": "turns", "column": "text", "redacted": True,
            "layers_run": stats["layers"], "n_turns": len(turns), "turns": turns,
            "per_label": per_label_rows(ours),
            "span_labels_note": "rule layers and LLM health flags; NER is not run yet"}  # fmt: skip


def stage_view(runs: Path, run_id: str, stage: str):
    rp = run_path(runs, run_id)
    if stage not in PAYLOAD_STAGES:
        raise NotFound("stage_not_found", "Unknown stage.")
    f = rp / STAGE_FILES[stage]
    if not f.exists():
        raise NotFound("stage_not_found", f"The {stage} stage has not run for {run_id}.")
    if stage == "profile":
        return load(f)
    if stage == "detect":
        return {"dataset": "customer_service", "labels": load(rp / "02_labels_detail.json"),
                "findings": load(rp / "02_findings.json"), "stats": load(rp / "02_detect_stats.json")}  # fmt: skip
    if stage in ("plan", "transform"):
        return load(f)
    plan = load(rp / "03_plan.json")
    if stage == "report":
        card = load(rp / "07_policy_card.json") if (rp / "07_policy_card.json").exists() else None
        return {"plan_table_md": f.read_text(encoding="utf-8"), "policy_card": card}
    ours, b2k = _scorecards(rp)
    if stage == "redact":
        return redact_view(rp, plan, ours)
    gate = load(rp / "06_gate.json")
    return {"scenario_id": plan["scenario_id"], "ours": ours, "baseline": b2k, "baseline_name": "B2-k",
            "gate": gate, "k": k_summary(plan),
            "residual_risks": residual_risks(ours, plan, gate, per_label_rows(ours)),
            "ablation": ablation_rows(runs) if "turns" in plan["released_tables"] else []}  # fmt: skip


def export_zip(runs: Path, run_id: str) -> bytes:
    """Released tables, the plan table and the policy card. Refused unless the gate passed."""
    rp = run_path(runs, run_id)
    if not (rp / "06_gate.json").exists():
        raise GateFailed(["verify_not_run"])
    gate = load(rp / "06_gate.json")
    if not gate["passed"]:
        raise GateFailed(gate["blocking"])
    plan = load(rp / "03_plan.json")
    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for table in plan["released_tables"]:
            if not re.fullmatch(r"[A-Za-z0-9_]+", table):
                continue
            f = rp / "04_release" / f"{table}.csv"
            if f.is_file():
                z.write(f, f"{table}.csv")
        z.writestr("07_plan_table.md", (rp / "07_plan_table.md").read_text(encoding="utf-8"))
        if not (rp / "07_policy_card.json").exists():
            write_policy_card(rp)
        z.writestr("policy_card.json", (rp / "07_policy_card.json").read_text(encoding="utf-8"))
        z.writestr("policy_card.md", (rp / "07_policy_card.md").read_text(encoding="utf-8"))
    return buf.getvalue()


def llm_view() -> dict:
    """Provider and model names from the environment; no client, no key."""
    prov = (os.environ.get("LLM_PROVIDER") or llm_mod.DEFAULT_PROVIDER).strip().lower()
    defaults = {"gemini": llm_mod.GEMINI_MODEL, "gemma": llm_mod.GEMMA_MODEL,
                "featherless": llm_mod.FEATHERLESS_MODEL}  # fmt: skip
    model = "none" if prov == "none" else (os.environ.get("LLM_MODEL", "").strip()
                                           or defaults.get(prov, "unknown"))  # fmt: skip
    return {"provider": prov, "model": model, "enabled": prov != "none"}


__all__ = [
    "GateFailed",
    "NotFound",
    "export_zip",
    "leaderboard_view",
    "llm_view",
    "run_view",
    "scenarios_view",
    "stage_view",
    "vf",
]
