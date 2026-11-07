"""Stage 7: report. Renders the plan as a field-by-field table (Markdown) from the plan file.

Numbers come from the plan and the scorecard only. Wording follows docs/FACTS.md.
"""

from __future__ import annotations

from api.pipeline.contracts import PolicyPlan

ACTION_WORDS = {
    "keep": "keep",
    "drop": "drop",
    "withhold_table": "withhold (table)",
    "hmac": "keyed pseudonym",
    "generalise": "generalise",
    "redact": "keep for text redaction",
    "suppress_k": "k check",
}


def _cell(s: str) -> str:
    return str(s).replace("|", "/").replace("\n", " ")


def plan_table(plan: PolicyPlan) -> str:
    """One row per field: column, role, action, level, reason. Then one line per k check."""
    lines = ["| Table | Column | Role | Action | Level | Reason |",
             "| --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    for p in plan.policies:
        if p.action == "suppress_k":
            continue
        level = p.params.get("level", "")
        lines.append(f"| {p.table} | {p.column} | {p.params.get('role', '')} | "
                     f"{ACTION_WORDS[p.action]} | {level} | {_cell(p.reason)} |")  # fmt: skip
    for p in plan.policies:
        if p.action != "suppress_k":
            continue
        q = p.params
        blanked = ", ".join(f"{c} {n}" for c, n in q.get("cells_blanked", {}).items()) or "none"
        lines.append("")
        lines.append(f"k check on {p.table} ({', '.join(q['qis'])}): target k {q['k_target']}, "
                     f"achieved k {q.get('k')}, pyCANON k {q.get('k_pycanon')}, "
                     f"rows suppressed {q.get('rows_suppressed')} (budget {q.get('row_budget')}), "
                     f"cells blanked: {blanked}.")  # fmt: skip
        se = q.get("search")
        if se:
            def lv(r):
                return ", ".join(f"{c} {v}" for c, v in r["levels"].items()) + \
                    f" (utility {r['utility']}, rows suppressed {r['rows_suppressed']})"
            line = (f"Level search: {se['tried']} combinations tried, {se['qualifying']} reach "
                    f"k {q['k_target']} within the row budget with no cell blanking, "
                    f"{se['scored']} scored. Method: {q.get('method')}.")  # fmt: skip
            if se.get("chosen"):
                line += f" Chosen: {lv(se['chosen'])}."
            if se.get("runner_up"):
                line += f" Runner-up: {lv(se['runner_up'])}."
            lines.append("")
            lines.append(line)
    return "\n".join(lines)
