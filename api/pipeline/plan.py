"""Stage 3: the scenario planner. Purpose decides which tables and columns are released.

Reads the scenario (metadata/scenarios.json) and the columns each of its utility tasks uses
(the `needs` list of the pets-eval task registry). Workload-aware minimisation after LeFevre
et al.: a column is released only if a task of the scenario uses it, or it is needed to join
released tables. Everything else is dropped or withheld, with a reason.

Decisions, in order, for a column of a released table:
1. join key (record key of one released table, present in another): hmac in every table
2. record key other tables refer to: hmac; a record key nothing refers to is kept
3. `split` column of any table a model task reads: keep (the scorer picks training rows by it)
4. used by a task: keep; quasi-identifiers get the fixed B2 level (generalise.py);
   free text is marked for the text redactor; direct identifiers become hmac
5. not used: drop. Direct identifiers that are dropped or withheld feed the gazetteer.

Never reads metadata/field_catalog.csv, truth/ or adversary/.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from api.pipeline import generalise as gen
from api.pipeline import io
from api.pipeline.contracts import ColumnProfile, FieldLabel, FieldPolicy, PolicyPlan

SPLIT_COLUMN = "split"
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?")

GUARANTEE = {
    "keep": "released as is",
    "drop": "not released",
    "withhold_table": "not released",
    "hmac": "keyed pseudonym (HMAC-SHA256); still personal data",
    "generalise": "coarsened to a fixed level; checked for k >= 5",
    "redact": "free text; identifiers replaced by typed placeholders (rule redactor); leakage measured by pets-eval",
    "suppress_k": "k-anonymity on the kept quasi-identifiers",
}


@dataclass(frozen=True)
class Task:
    id: str
    table: str
    kind: str
    needs: tuple[str, ...]


def proving_ground_root() -> Path:
    return io.data_root().parent


def _pets_eval():
    try:
        import pets_eval.utility as pu
    except ImportError:
        sys.path.insert(0, str(proving_ground_root() / "toolkit"))
        import pets_eval.utility as pu
    return pu


def load_scenario(scenario_id: str, root: Path | None = None) -> dict:
    path = (root or proving_ground_root()) / "metadata" / "scenarios.json"
    for s in json.loads(path.read_text(encoding="utf-8")):
        if s["id"] == scenario_id:
            return s
    raise KeyError(f"scenario {scenario_id} not found")


def load_tasks(dataset: str) -> list[Task]:
    pu = _pets_eval()
    return [Task(t.id, t.table, t.kind, tuple(t.needs)) for t in pu.all_tasks([dataset])]


def needed_columns(tasks: list[Task], columns: dict[str, set[str]]) -> dict[tuple[str, str], list[str]]:
    """(table, column) -> task ids that use it. `needs` entries are 'col' (the task's table) or
    'table.col', sometimes with a note in brackets; names that are not columns are ignored."""
    out: dict[tuple[str, str], list[str]] = {}
    for t in tasks:
        for entry in t.needs:
            for name in _NAME.findall(re.sub(r"\(.*?\)", " ", entry)):
                table, col = name.split(".", 1) if "." in name else (t.table, name)
                if col in columns.get(table, set()):
                    out.setdefault((table, col), [])
                    if t.id not in out[(table, col)]:
                        out[(table, col)].append(t.id)
    return out


def _policy(lab: FieldLabel, action: str, reason: str, **params) -> FieldPolicy:
    return FieldPolicy(table=lab.table, column=lab.column, action=action,
                       params={"role": lab.privacy_role, "subtype": lab.subtype, **params},
                       reason=reason, guarantee=GUARANTEE[action])  # fmt: skip


def build_plan(scenario: dict, labels: list[FieldLabel], profiles: list[ColumnProfile],
               tasks: list[Task], key_id: str) -> PolicyPlan:  # fmt: skip
    dataset = scenario["dataset"]
    labels = [lab for lab in labels if lab.dataset == dataset]
    prof = {(p.table, p.column): p for p in profiles if p.dataset == dataset}
    columns: dict[str, set[str]] = {}
    for lab in labels:
        columns.setdefault(lab.table, set()).add(lab.column)
    wanted = [t for t in tasks if t.id in scenario["utility_requirements"]]
    used = needed_columns(wanted, columns)
    released = sorted({t for t, _ in used})
    model_ids = {t.id for t in wanted if t.kind == "model"}
    model_tables = {tbl for (tbl, _), tids in used.items() if model_ids & set(tids)}
    record_keys = {lab.table: lab.column for lab in labels if lab.privacy_role == "record_key"}
    referenced = {c for t, c in record_keys.items()
                  if any(c in columns[o] for o in columns if o != t)}  # fmt: skip
    join_keys = {c for t, c in record_keys.items() if t in released
                 and any(c in columns[o] for o in released if o != t)}  # fmt: skip

    policies: list[FieldPolicy] = []
    for lab in labels:
        tids = used.get((lab.table, lab.column), [])
        direct = lab.privacy_role == "direct_identifier"
        if lab.table not in released:
            policies.append(_policy(lab, "withhold_table",
                                    "no task of this scenario uses this table",
                                    gazetteer=direct))  # fmt: skip
        elif lab.column in join_keys:
            policies.append(_policy(lab, "hmac", "joins released tables; the same keyed "
                                    "pseudonym in every table keeps the join", tasks=tids))  # fmt: skip
        elif record_keys.get(lab.table) == lab.column and lab.column in referenced:
            policies.append(_policy(lab, "hmac", "row key that other tables refer to; keyed "
                                    "pseudonym stops linking to unreleased records",
                                    tasks=tids))  # fmt: skip
        elif record_keys.get(lab.table) == lab.column:
            policies.append(_policy(lab, "keep", "row key no other table refers to; links "
                                    "to nothing outside this table, rows are matched by it",
                                    tasks=tids))  # fmt: skip
        elif lab.column == SPLIT_COLUMN and lab.table in model_tables and not tids:
            policies.append(_policy(lab, "keep", "train and eval marker; the model task "
                                    "chooses its training rows by it"))  # fmt: skip
        elif tids:
            used_by = "used by " + ", ".join(tids)
            if lab.privacy_role == "quasi_identifier":
                hit = prof[(lab.table, lab.column)].validator_hits.get("timestamp", 0.0) \
                    if (lab.table, lab.column) in prof else 0.0
                level = gen.level_for(lab.subtype, hit)
                ladder = gen.ladder_for(lab.subtype, hit)
                note = ("; level chosen by the search in transform" if len(ladder) > 1
                        else "; one level only for this subtype, kept exact")  # fmt: skip
                action = "generalise" if len(ladder) > 1 else "keep"
                policies.append(_policy(lab, action, used_by + note, tasks=tids, level=level,
                                        fallback_level=level, ladder=ladder,
                                        quasi_identifier=True))  # fmt: skip
            elif lab.privacy_role == "free_text":
                policies.append(_policy(lab, "redact", used_by + "; text kept for the "
                                        "task", tasks=tids))  # fmt: skip
            elif direct or lab.privacy_role == "technical_identifier":
                policies.append(_policy(lab, "hmac", used_by + "; keyed pseudonym keeps "
                                        "equality without the value", tasks=tids))  # fmt: skip
            else:
                policies.append(_policy(lab, "keep", used_by, tasks=tids))
        else:
            why = {"direct_identifier": "direct identifier no task needs",
                   "technical_identifier": "technical identifier no task needs or joins on",
                   "quasi_identifier": "quasi-identifier no task needs",
                   "free_text": "free text no task needs",
                   "sensitive_attribute": "sensitive attribute no task needs"}.get(
                       lab.privacy_role, "no task of this scenario uses it")  # fmt: skip
            policies.append(_policy(lab, "drop", why, gazetteer=direct))

    for t in released:
        qis = [p.column for p in policies if p.table == t and p.params.get("quasi_identifier")]
        if qis:
            policies.append(FieldPolicy(table=t, column="*", action="suppress_k",
                                        params={"qis": qis, "k_target": gen.K_TARGET,
                                                "max_row_suppression": gen.MAX_ROW_SUPPRESSION},
                                        reason=f"k >= {gen.K_TARGET} on the kept "
                                               "quasi-identifiers only",
                                        guarantee=GUARANTEE["suppress_k"]))  # fmt: skip
    return PolicyPlan(dataset=dataset, scenario_id=scenario["id"], released_tables=released,
                      policies=policies, k=1, key_id=key_id)  # fmt: skip


def write_plan(plan: PolicyPlan, path: Path) -> None:
    path.write_text(json.dumps(plan.to_dict(), indent=1, ensure_ascii=False), encoding="utf-8")


def read_plan(path: Path) -> PolicyPlan:
    d = json.loads(path.read_text(encoding="utf-8"))
    d["policies"] = [FieldPolicy(**p) for p in d["policies"]]
    return PolicyPlan(**d)
