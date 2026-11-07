"""Phase 3: scenario planner, structured transforms, fixed generalisation and k check.

Synthetic data only, so these run in CI without the proving ground.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from api import cli
from api.pipeline import generalise as gen
from api.pipeline import plan as pl
from api.pipeline import report as rp
from api.pipeline import transform as tr
from api.pipeline.contracts import ColumnProfile, FieldLabel

N = 400
LABELS = [
    # table, column, role, subtype
    ("convs", "conv_id", "record_key", "RECORD_ID"),
    ("convs", "cust_id", "technical_identifier", "CUSTOMER_ID"),
    ("convs", "agent_id", "technical_identifier", "EMPLOYEE_ID"),
    ("convs", "agent_name", "direct_identifier", "PERSON_NAME"),
    ("convs", "language", "quasi_identifier", "LANGUAGE"),
    ("convs", "started_ts", "quasi_identifier", "TIMESTAMP"),
    ("convs", "handle_s", "quasi_identifier", "TIMESTAMP"),
    ("convs", "intent", "non_sensitive", "CATEGORY"),
    ("convs", "split", "non_sensitive", "CATEGORY"),
    ("custs", "cust_id", "record_key", "CUSTOMER_ID"),
    ("custs", "full_name", "direct_identifier", "PERSON_NAME"),
    ("custs", "postcode", "quasi_identifier", "POSTCODE"),
    ("turns", "turn_id", "record_key", "RECORD_ID"),
    ("turns", "conv_id", "technical_identifier", "RECORD_ID"),
    ("turns", "text", "free_text", "FREE_TEXT"),
]
TASKS = [
    pl.Task("U1", "turns", "model", ("turns.text", "convs.intent")),
    pl.Task("U2", "convs", "aggregate", ("intent", "handle_s")),
    pl.Task("U3", "convs", "aggregate", ("language", "started_ts (hour of day)")),
]
S1 = {"id": "S1", "dataset": "ds", "utility_requirements": ["U1", "U2"]}
S2 = {"id": "S2", "dataset": "ds", "utility_requirements": ["U2", "U3"]}


def _labels():
    return [FieldLabel("ds", t, c, r, s, 0.9, "test", "rule") for t, c, r, s in LABELS]


def _profiles():
    hits = {"started_ts": {"timestamp": 1.0}, "handle_s": {"integer": 1.0}}
    return [ColumnProfile("ds", t, c, N, 1.0, 0.5, 1, 9, 5.0, {}, hits.get(c, {}))
            for t, c, _, _ in LABELS]  # fmt: skip


def _plan(scenario=S1):
    return pl.build_plan(scenario, _labels(), _profiles(), TASKS, "kid")


def _by(plan):
    return {(p.table, p.column): p for p in plan.policies}


@pytest.fixture
def data(tmp_path, monkeypatch):
    root = tmp_path / "data"
    (root / "ds").mkdir(parents=True)
    ids = [f"C{i:04d}" for i in range(N)]
    pd.DataFrame({
        "conv_id": ids, "cust_id": [f"K{i % 50}" for i in range(N)],
        "agent_id": ["A1"] * N, "agent_name": ["Liisa Virtanen"] * N,
        "language": (["fi", "sv", "en", "fi"] * N)[:N],
        "started_ts": [f"2025-03-0{1 + i % 3} 1{i % 4}:{i % 60:02d}:00" for i in range(N)],
        "handle_s": [str(300 + (i % 20) * 10) for i in range(N - 3)] + ["9001", "9002", "9003"],
        "intent": (["billing", "move"] * N)[:N], "split": (["train"] * 3 + ["eval"]) * (N // 4),
    }).to_csv(root / "ds" / "convs.csv", index=False)  # fmt: skip
    pd.DataFrame({"cust_id": [f"K{i}" for i in range(50)],
                  "full_name": [f"Matti Meikäläinen{i}" for i in range(50)],
                  "postcode": ["00100"] * 50}).to_csv(root / "ds" / "custs.csv", index=False)  # fmt: skip
    pd.DataFrame({"turn_id": [f"T{i:05d}" for i in range(2 * N)],
                  "conv_id": [ids[i // 2] for i in range(2 * N)],
                  "text": ["hello there"] * (2 * N)}).to_csv(root / "ds" / "turns.csv",
                                                              index=False)  # fmt: skip
    monkeypatch.setenv("PURPOSEFIT_DATA_DIR", str(root))
    return root


# ---------------------------------------------------------------- plan


def test_plan_releases_only_what_the_tasks_use():
    plan = _plan()
    p = _by(plan)
    assert plan.released_tables == ["convs", "turns"]
    assert all(q.action == "withhold_table" for (t, _), q in p.items() if t == "custs")
    assert p[("convs", "intent")].action == "keep"
    assert p[("convs", "started_ts")].action == "drop"
    assert p[("convs", "language")].action == "drop"
    assert p[("turns", "text")].action == "redact"


def test_join_key_is_pseudonymised_in_every_table_and_row_key_kept():
    p = _by(_plan())
    assert p[("convs", "conv_id")].action == "hmac" and p[("turns", "conv_id")].action == "hmac"
    assert p[("turns", "turn_id")].action == "keep"


def test_technical_identifiers_are_dropped_unless_joined_on():
    p = _by(_plan())
    assert p[("convs", "agent_id")].action == "drop"
    assert p[("convs", "cust_id")].action == "drop"  # custs is withheld, so no join
    assert "no task needs or joins on" in p[("convs", "agent_id")].reason


def test_split_is_kept_for_a_model_task_on_another_table():
    p = _by(_plan())
    assert p[("convs", "split")].action == "keep"
    assert _by(_plan(S2))[("convs", "split")].action == "drop"


def test_direct_identifiers_feed_the_gazetteer():
    p = _by(_plan())
    assert p[("convs", "agent_name")].action == "drop" and p[("convs", "agent_name")].params["gazetteer"]
    assert p[("custs", "full_name")].params["gazetteer"]
    assert not p[("convs", "intent")].params.get("gazetteer")


def test_kept_quasi_identifiers_get_a_level_and_a_k_check():
    plan = _plan(S2)
    p = _by(plan)
    assert p[("convs", "started_ts")].action == "generalise"
    assert p[("convs", "started_ts")].params["level"] == "hour"
    # Labelled TIMESTAMP, but the values are not timestamps: kept exact, not destroyed.
    assert p[("convs", "handle_s")].params["level"] == "exact"
    k = p[("convs", "*")]
    assert k.action == "suppress_k"
    assert k.params["qis"] == ["language", "started_ts", "handle_s"]  # kept QIs only


def test_two_scenarios_give_two_plans():
    assert _plan(S1).released_tables != _plan(S2).released_tables


def test_needs_parsing_ignores_notes_and_unknown_names():
    used = pl.needed_columns(TASKS, {"convs": {"started_ts", "language"}})
    assert used == {("convs", "language"): ["U3"], ("convs", "started_ts"): ["U3"]}


def test_plan_round_trips_through_json(tmp_path):
    plan = _plan()
    pl.write_plan(plan, tmp_path / "p.json")
    assert pl.read_plan(tmp_path / "p.json") == plan


# ---------------------------------------------------------------- generalise


@pytest.mark.parametrize(("level", "values", "expected"), [
    ("year", ["1984-05-02", "02.05.1984", ""], ["1984", "1984", ""]),
    ("10-year band, 80+", ["7", "34", "85", ""], ["0-9", "30-39", "80+", ""]),
    ("3 digits", ["00100", "20 500", "x"], ["001**", "205**", ""]),
    ("hour", ["2025-03-01 14:37:09", ""], ["2025-03-01 14:00", ""]),
    ("2 decimals", ["60.123456", ""], ["60.12", ""]),
    ("exact", ["abc"], ["abc"]),
])  # fmt: skip
def test_b2_levels(level, values, expected):
    assert gen.apply_level(pd.Series(values), level).tolist() == expected


def test_k_by_row_suppression_within_budget():
    df = pd.DataFrame({"q": ["a"] * 98 + ["b", "c"]})
    out, _keep, st = gen.enforce_k(df, ["q"], 5, 0.02)
    assert st["rows_suppressed"] == 2 and st["cells_blanked"] == {} and st["k"] >= 5
    assert gen.pycanon_k(out, ["q"]) == st["k"]


def test_k_falls_back_to_blanking_past_the_row_budget():
    df = pd.DataFrame({"q": ["a"] * 50 + [str(i) for i in range(50)], "r": ["x"] * 100})
    out, _keep, st = gen.enforce_k(df, ["q", "r"], 5, 0.02)
    assert st["rows_suppressed"] <= st["row_budget"] and st["cells_blanked"]["q"] == 50
    assert st["k"] >= 5 and gen.pycanon_k(out, ["q", "r"]) == st["k"]


# ---------------------------------------------------------------- transform


def test_pseudonym_is_keyed_and_stable():
    assert tr.pseudonym("k1", "C1") == tr.pseudonym("k1", " C1 ")
    assert tr.pseudonym("k1", "C1") != tr.pseudonym("k2", "C1")
    assert tr.pseudonym("k1", "") == ""


def test_transform_writes_release_and_keeps_row_maps_private(data, tmp_path):
    run, private = tmp_path / "runs" / "r", tmp_path / "runs" / "private" / "r"
    plan, stats = tr.apply_plan(_plan(S2), run, private, "key")
    rel = run / "04_release"
    assert sorted(f.name for f in rel.iterdir()) == ["convs.csv"]
    assert not list(rel.glob("*rowmap*")) and (private / "rowmap_convs.csv").exists()
    convs = pd.read_csv(rel / "convs.csv", dtype=str, keep_default_na=False)
    assert "agent_name" not in convs and "cust_id" not in convs
    assert "C0000" not in convs.to_csv()
    k = _by(plan)[("convs", "*")].params
    assert k["k"] >= 5 and k["k_pycanon"] == k["k"] and plan.k == k["k"]
    assert k["rows_suppressed"] <= k["row_budget"]
    gaz = pd.read_csv(private / "gazetteer_values.csv", dtype=str)
    assert "Liisa Virtanen" in set(gaz.value)
    assert "Liisa" not in json.dumps(stats)


def test_join_survives_pseudonymisation(data, tmp_path):
    run = tmp_path / "runs" / "r"
    tr.apply_plan(_plan(S1), run, tmp_path / "runs" / "private" / "r", "key")
    convs = pd.read_csv(run / "04_release" / "convs.csv", dtype=str, keep_default_na=False)
    turns = pd.read_csv(run / "04_release" / "turns.csv", dtype=str, keep_default_na=False)
    assert set(turns.conv_id) <= set(convs.conv_id) and len(set(turns.conv_id)) == len(convs)
    assert list(convs.columns) == ["conv_id", "handle_s", "intent", "split"]


# ---------------------------------------------------------------- report and CLI


def test_plan_table_lists_every_field_without_em_dashes():
    md = rp.plan_table(_plan())
    assert md.count("\n| ") == len(LABELS) + 1
    assert "—" not in md and "| convs | agent_id | technical_identifier | drop |" in md


def test_plan_stage_needs_detect_first(capsys):
    assert cli.main(["plan", "--run", "r1", "--scenario", "CS-S1"]) == 2
    assert "run the detect stage" in capsys.readouterr().err


# ---------------------------------------------------------------- level search


def _ages():
    # 200 rows: every exact age 5 times; all timestamps on one day, one per minute.
    return pd.DataFrame({"age": [str(20 + i % 40) for i in range(200)],
                         "ts": [f"2025-03-03 {i % 24:02d}:{i % 60:02d}:00" for i in range(200)]})


def test_search_tries_every_combination_and_picks_best_utility():
    ladders = {"age": gen.LADDERS["AGE"], "ts": gen.LADDERS["TIMESTAMP"]}

    def score(cand):  # exact ages are worth more; timestamps do not matter
        return 0.5 if cand["age"].str.contains("-").any() else 1.0

    r = gen.search_levels(_ages(), ladders, score)
    assert r["tried"] == 16 and r["scored"] == r["qualifying"] >= 2
    assert r["chosen"]["levels"] == {"age": "exact", "ts": "day"}  # tie with week: finer wins
    assert r["runner_up"]["levels"] == {"age": "exact", "ts": "week"}
    assert gen.class_sizes(r["release"], list(ladders)).min() >= 5


def test_search_without_scorer_prefers_fewest_suppressed_then_finest():
    # Five singleton ages 81 to 85: exact and 5-year bands need 5 suppressed rows (budget 4).
    df = pd.DataFrame({"age": [str(20 + i % 40) for i in range(200)] + [str(a) for a in range(81, 86)]})
    r = gen.search_levels(df, {"age": gen.LADDERS["AGE"]}, None)
    assert r["row_budget"] == 4 and r["qualifying"] == 2
    assert r["chosen"]["levels"] == {"age": "10-year band"} and r["chosen"]["rows_suppressed"] == 0


def test_search_reports_no_qualifying_combination():
    df = pd.DataFrame({"q": [str(i) for i in range(100)]})
    r = gen.search_levels(df, {"q": ["exact"]}, None)
    assert r["qualifying"] == 0 and r["chosen"] is None and r["release"] is None


def test_transform_records_chosen_levels_and_runner_up(data, tmp_path):
    run = tmp_path / "runs" / "r"
    calls = []

    def utility(prot):
        calls.append(1)
        return 1.0 if prot["convs"]["started_ts"].str.len().max() == 16 else 0.5

    plan, _ = tr.apply_plan(_plan(S2), run, tmp_path / "runs" / "private" / "r", "key",
                            utility=utility)  # fmt: skip
    k = _by(plan)[("convs", "*")].params
    assert k["method"] == "level search" and k["search"]["tried"] == 4 and calls
    assert k["search"]["runner_up"] is not None and k["cells_blanked"] == {}
    assert k["k"] >= 5 and k["k_pycanon"] == k["k"]
    ts = _by(plan)[("convs", "started_ts")]
    assert ts.params["level"] == k["search"]["chosen"]["levels"]["started_ts"]
    assert "chosen by search, runner-up" in ts.reason
    assert "release" not in json.dumps(k["search"])


def test_transform_falls_back_and_says_so(data, tmp_path, monkeypatch):
    none = {"tried": 4, "qualifying": 0, "scored": 0, "row_budget": 8, "chosen": None,
            "runner_up": None, "release": None}  # fmt: skip
    monkeypatch.setattr(gen, "search_levels", lambda *a, **k: none)
    run = tmp_path / "runs" / "r"
    plan, _ = tr.apply_plan(_plan(S2), run, tmp_path / "runs" / "private" / "r", "key")
    k = _by(plan)[("convs", "*")].params
    assert k["method"].startswith("fallback") and k["search"]["qualifying"] == 0
    assert k["k"] >= 5 and k["k_pycanon"] == k["k"]
    ts = _by(plan)[("convs", "started_ts")]
    assert ts.params["level"] == "hour" and "no level combination reached k >= 5" in ts.reason


def test_worst_risk_names_nothing_when_all_risks_are_zero():
    from api.pipeline import verify as vf

    assert vf.worst_risk({"risk_components": {"a": 0.0, "b": 0.0}}) == (0.0, "")
    assert vf.worst_risk({"risk_components": {"a": 0.2, "b": 0.7}}) == (0.7, "b")


def test_pseudonym_has_letter_prefix_and_lowercase_hex():
    import re

    tok = tr.pseudonym("k1", "C1", "conversation_id")
    assert re.fullmatch(r"cv_[0-9a-f]{20}", tok)
    assert tr.pseudonym("k1", "C1", "customer_id").startswith("cu_")
    assert re.fullmatch(r"[a-z]{2}_[0-9a-f]{20}", tr.pseudonym("k1", "C1", "Weird Column"))
    assert not re.search(r"\d{6}", tok.split("_")[0])
    assert tr.pseudonym("k1", "C1", "conversation_id") == tr.pseudonym("k1", " C1 ", "conversation_id")
