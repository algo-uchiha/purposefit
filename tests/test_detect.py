import json
import re
from pathlib import Path

import pandas as pd
import pytest

from api.pipeline import detect as det
from api.pipeline import profile as prof
from api.pipeline.contracts import PRIVACY_ROLES, SUBTYPES, ColumnProfile

ROOT = Path(__file__).resolve().parents[1]


def label_df(df, table="t"):
    return {lab.column: lab for lab in det.detect(prof.profile_table("d", table, df, 1))}


def test_name_rules_fi_sv_en():
    n = 50
    df = pd.DataFrame({
        "asiakas_id": [f"A{i}" for i in range(n)],
        "henkilotunnus": ["x"] * n, "sukunimi": ["x"] * n, "telefon": ["x"] * n,
        "postinumero": ["x"] * n, "kommun": ["x"] * n, "diagnosis_code": ["x"] * n,
        "salary": ["x"] * n, "kuvaus": ["pitkä kuvaus tekstiä tässä näin"] * n,
        "src_ip": ["x"] * n, "customer_id": ["C1"] * n, "kieli": ["fi"] * n,
    })  # fmt: skip
    got = {c: (lab.privacy_role, lab.subtype) for c, lab in label_df(df).items()}
    assert got["asiakas_id"][0] == "record_key"
    assert got["henkilotunnus"] == ("direct_identifier", "NATIONAL_ID")
    assert got["sukunimi"] == ("direct_identifier", "PERSON_NAME")
    assert got["telefon"] == ("direct_identifier", "PHONE")
    assert got["postinumero"] == ("quasi_identifier", "POSTCODE")
    assert got["kommun"] == ("quasi_identifier", "MUNICIPALITY")
    assert got["diagnosis_code"][0] == "sensitive_attribute"
    assert got["salary"] == ("sensitive_attribute", "FINANCIAL_DATA")
    assert got["kuvaus"] == ("free_text", "FREE_TEXT")
    assert got["src_ip"] == ("technical_identifier", "IP_ADDRESS")
    assert got["customer_id"] == ("technical_identifier", "CUSTOMER_ID")
    assert got["kieli"] == ("quasi_identifier", "LANGUAGE")


def test_value_rules_for_meaningless_names():
    df = pd.DataFrame({
        "c01": [f"R{i:05d}" for i in range(40)],
        "c02": ["131052-308T", "010101A123N"] * 20,
        "c03": ["FI21 1234 5600 0007 85"] * 40,
        "c04": [f"user{i}@example.fi" for i in range(40)],
        "c05": ["Asiakas soitti ja kertoi että lasku oli väärin tänään."] * 40,
        "c06": [f"2025-01-0{i % 9 + 1}" for i in range(40)],
    })  # fmt: skip
    got = {c: (lab.privacy_role, lab.subtype) for c, lab in label_df(df).items()}
    assert got["c01"][0] == "record_key"
    assert got["c02"] == ("direct_identifier", "NATIONAL_ID")
    assert got["c03"] == ("direct_identifier", "IBAN")
    assert got["c04"] == ("direct_identifier", "EMAIL")
    assert got["c05"] == ("free_text", "FREE_TEXT")
    assert got["c06"][0] == "quasi_identifier"


def test_every_label_is_valid_and_has_reason():
    df = pd.DataFrame({"x": ["a"] * 10, "y": ["1"] * 10})
    for lab in label_df(df).values():
        assert lab.privacy_role in PRIVACY_ROLES and lab.subtype in SUBTYPES
        assert lab.reason and 0 <= lab.confidence <= 1
        assert re.search(r"\[(" + "|".join(det.RULE_FAMILIES) + r")\]", lab.reason)


def test_frozen_settings():
    assert det.LLM_CONFIDENCE_THRESHOLD == 0.6
    assert len(det.RULE_FAMILIES) == 16


class FakeResp:
    def __init__(self, text):
        self.text, self.model, self.call_id = text, "fake", "abc123"
        self.fallback, self.prompt_tokens, self.output_tokens, self.thought_tokens = 0, 10, 5, 0


class FakeClient:
    enabled = True

    def __init__(self, reply_fn):
        self.reply_fn, self.prompts, self.max_tokens = reply_fn, [], []

    def complete(self, prompt, **kw):
        self.prompts.append(json.loads(prompt))
        self.max_tokens.append(kw["max_tokens"])
        return FakeResp(self.reply_fn(json.loads(prompt)["columns"]))


def _write_table(tmp_path, n_cols):
    d = tmp_path / "ds"
    d.mkdir()
    data = {"row_id": [str(i) for i in range(30)]}
    data.update({f"x{j:02d}": ["v"] * 30 for j in range(n_cols)})
    pd.DataFrame(data).to_csv(d / "t.csv", index=False)
    return det.detect(prof.profile_dataset("ds", 1, tmp_path))


def _answer(keys, role="non_sensitive", sub="CATEGORY"):
    return {k: {"privacy_role": role, "subtype": sub} for k in keys}


def test_llm_answers_accepted_only_if_in_taxonomy(tmp_path):
    labels = _write_table(tmp_path, 3)
    low = [i for i, lab in enumerate(labels) if lab.confidence < det.LLM_CONFIDENCE_THRESHOLD]
    assert len(low) == 3

    def reply(cols):
        a, b, c = (x["key"] for x in cols)
        return json.dumps({a: {"privacy_role": "sensitive_attribute", "subtype": "SOCIAL_DATA"},
                           b: {"privacy_role": "pii", "subtype": "SOCIAL_DATA"},
                           c: {"privacy_role": "free_text", "subtype": "FREE_TEXT"}})

    client = FakeClient(reply)
    out, stats = det.llm_pass(labels, client, 1, tmp_path)
    assert (stats["sent"], stats["calls"], stats["accepted"], stats["rejected"]) == (3, 1, 2, 1)
    assert (out[low[0]].privacy_role, out[low[0]].source) == ("sensitive_attribute", "llm")
    assert out[low[1]] == labels[low[1]] and out[low[2]].subtype == "FREE_TEXT"
    assert all(len(c["sample_values"]) <= 20 for p in client.prompts for c in p["columns"])


def test_llm_answers_are_mapped_by_column_name_not_by_position(tmp_path):
    labels = _write_table(tmp_path, 4)
    kinds = {"x00": ("sensitive_attribute", "HEALTH_DATA"), "x01": ("direct_identifier", "EMAIL"),
             "x02": ("quasi_identifier", "AGE"), "x03": ("free_text", "FREE_TEXT")}  # fmt: skip

    def shuffled(cols):
        reply = {c["key"]: dict(zip(("privacy_role", "subtype"), kinds[c["column"]], strict=True))
                 for c in cols}  # fmt: skip
        return json.dumps(dict(reversed(list(reply.items()))))  # a different order than asked

    out, stats = det.llm_pass(labels, FakeClient(shuffled), 1, tmp_path)
    assert stats["accepted"] == 4
    for lab in out:
        if lab.column in kinds:
            assert (lab.privacy_role, lab.subtype) == kinds[lab.column]


@pytest.mark.parametrize("bad", ["unknown", "missing", "extra"])
def test_llm_batch_with_wrong_names_is_rejected_whole(tmp_path, bad):
    labels = _write_table(tmp_path, 3)

    def reply(cols):
        keys = [c["key"] for c in cols]
        if bad == "unknown":
            keys[0] = "c99"
        elif bad == "missing":
            keys = keys[:-1]
        else:
            keys.append("x99")
        return json.dumps(_answer(keys, "sensitive_attribute", "SOCIAL_DATA"))

    out, stats = det.llm_pass(labels, FakeClient(reply), 1, tmp_path)
    assert out == labels and stats["accepted"] == 0 and stats["rejected"] == 3


def test_llm_cache_can_be_bypassed(tmp_path):
    labels = _write_table(tmp_path, 2)
    seen = []

    class Spy(FakeClient):
        def complete(self, prompt, **kw):
            seen.append(kw["use_cache"])
            return super().complete(prompt, **kw)

    det.llm_pass(labels, Spy(lambda cols: json.dumps(_answer([c["key"] for c in cols]))), 1,
                 tmp_path, use_cache=False)
    assert seen == [False]


def test_llm_batches_of_twenty_with_output_cap(tmp_path):
    labels = _write_table(tmp_path, 45)
    client = FakeClient(lambda cols: json.dumps(_answer([c["key"] for c in cols])))
    _out, stats = det.llm_pass(labels, client, 1, tmp_path)
    sizes = sorted(len(p["columns"]) for p in client.prompts)
    assert sizes == [5, 20, 20] and stats["calls"] == 3 and stats["accepted"] == 45
    assert sorted(client.max_tokens) == [40 * 5 + 64, 40 * 20 + 64, 40 * 20 + 64]


def test_non_json_reply_rejects_whole_batch(tmp_path):
    labels = _write_table(tmp_path, 2)
    out, stats = det.llm_pass(labels, FakeClient(lambda cols: "sorry"), 1, tmp_path)
    assert stats["rejected"] == 2 and out == labels


def test_llm_failure_keeps_rule_labels(tmp_path):
    labels = _write_table(tmp_path, 3)

    class Broken(FakeClient):
        def complete(self, prompt, **kw):
            raise RuntimeError("network down")

    out, stats = det.llm_pass(labels, Broken(None), 1, tmp_path)
    assert out == labels and stats["status"] == "failed_rules_only" and stats["errors"] == 3


def test_high_confidence_columns_never_reach_llm():
    labels = det.detect(prof.profile_table("d", "t", pd.DataFrame({"email": ["a@b.fi"] * 5}), 1))
    client = FakeClient(lambda cols: "{}")
    out, stats = det.llm_pass(labels, client, 1)
    assert stats["sent"] == 0 and out == labels and client.prompts == []


def test_unseen_format(tmp_path):
    labels = det.detect(prof.profile_table("unseen", "export", pd.DataFrame({"c01": ["1"]}), 1))
    det.write_labels(labels, tmp_path / "u.csv", unseen_format=True)
    assert (tmp_path / "u.csv").read_text().splitlines()[0] == "column,privacy_role,subtype"


FORBIDDEN = ("field_catalog", "pii_spans", "truth", "adversary")


def test_api_never_reads_forbidden_files():
    for path in (ROOT / "api").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for word in FORBIDDEN:
            # Docstrings may name the rule; code may not use the word in a string or path.
            code = re.sub(r'"""[\s\S]*?"""', "", text)
            code = "\n".join(line.split("#")[0] for line in code.splitlines())
            assert word not in code, f"{path.relative_to(ROOT)} mentions {word}"


def _dataset(tmp_path, df, readme=""):
    d = tmp_path / "ds"
    d.mkdir()
    df.to_csv(d / "t.csv", index=False)
    if readme:
        (d / "README.md").write_text(readme, encoding="utf-8")
    profiles = prof.profile_dataset("ds", 1, tmp_path)
    return det.detect_pipeline(profiles, 1, None, tmp_path)


def test_unkeyed_hash_of_identifier_inherits_its_label(tmp_path):
    import hashlib

    hetus = ["131052-308T", "010101A123N", "311299-999E", "150590-123J"] * 100
    df = pd.DataFrame({
        "row_id": [str(i) for i in range(400)],
        "c1": hetus,
        "c2": [hashlib.sha256(h.lower().encode()).hexdigest().upper() for h in hetus],
    })  # fmt: skip
    labels, _, findings = _dataset(tmp_path, df)
    got = {lab.column: lab for lab in labels}
    assert (got["c2"].privacy_role, got["c2"].subtype) == ("direct_identifier", "NATIONAL_ID")
    assert got["c2"].reason.startswith("unkeyed hash of c1, reversible by enumeration")
    assert findings[0]["kind"] == "unkeyed_hash" and findings[0]["algorithm"] == "SHA-256"
    assert findings[0]["variant"] == "lower"
    assert "131052" not in json.dumps(findings)


def test_hash_of_messy_hetu_matches_after_canonicalising(tmp_path):
    import hashlib

    # Mostly clean, as in the unseen file, plus label prefixes, a missing century sign,
    # lower case and a stray space. The hash is always of the canonical HETU.
    canonical = ["131052-308T", "010101A123N", "311299-999E", "150590-123J", "131052-308T",
                 "010101A123N", "311299-999E", "150590-123J"]  # fmt: skip
    messy = ["131052-308T", "010101A123N", "311299-999E", "150590-123J", "HETU 131052-308T",
             "010101a123n", "311299999E", "hetu: 150590 123J"]  # fmt: skip
    df = pd.DataFrame({
        "row_id": [str(i) for i in range(400)],
        "c1": messy * 50,
        "c2": [hashlib.sha256(h.encode()).hexdigest().upper() for h in canonical * 50],
    })  # fmt: skip
    labels, _, findings = _dataset(tmp_path, df)
    got = {lab.column: lab for lab in labels}
    assert (got["c2"].privacy_role, got["c2"].subtype) == ("direct_identifier", "NATIONAL_ID")
    assert findings[0]["kind"] == "unkeyed_hash" and findings[0]["match_rate"] == 1.0
    assert findings[0]["variant"] == "canonical_hetu"
    assert "131052" not in json.dumps(findings)


def test_canonical_candidates_try_every_century_sign():
    from api.pipeline.detect import HETU_CENTURY_SIGNS, _canon_candidates

    got = _canon_candidates("311299999E", "hetu")
    assert got == ["311299" + c + "999E" for c in HETU_CENTURY_SIGNS] and len(got) == 13
    assert _canon_candidates("IBAN fi21 1234 5600 0007 85", "iban") == ["FI2112345600000785"]


def test_random_hex_is_not_called_a_hash(tmp_path):
    import secrets

    df = pd.DataFrame({"row_id": [str(i) for i in range(50)], "c1": ["a"] * 50,
                       "c2": [secrets.token_hex(32) for _ in range(50)]})  # fmt: skip
    labels, _, findings = _dataset(tmp_path, df)
    assert findings == [] and "hash_of_column" not in labels[2].reason


def test_dependency_on_sensitive_column(tmp_path):
    n = 200
    union = ["AY-HL" if i % 3 else "" for i in range(n)]
    fee = ["12,50" if u else "0,00" for u in union]
    df = pd.DataFrame({"row_id": [str(i) for i in range(n)], "union_code": union, "c9": fee})
    labels, _, findings = _dataset(tmp_path, df)
    got = {lab.column: lab for lab in labels}
    assert got["union_code"].privacy_role == "sensitive_attribute"
    assert got["c9"].privacy_role == "sensitive_attribute"
    assert "union_code" in got["c9"].reason and findings[-1]["kind"] == "dependency"


def test_dependency_runs_after_the_llm_and_sees_its_sensitive_labels(tmp_path):
    n = 200
    note = ["x" if i % 3 else "" for i in range(n)]
    df = pd.DataFrame({"row_id": [str(i) for i in range(n)], "c13": note,
                       "c14": ["12,50" if v else "0,00" for v in note]})  # fmt: skip
    d = tmp_path / "ds"
    d.mkdir()
    df.to_csv(d / "t.csv", index=False)
    profiles = prof.profile_dataset("ds", 1, tmp_path)

    labels, _, findings = det.detect_pipeline(profiles, 1, _Pair(), tmp_path)
    got = {x.column: x for x in labels}
    assert got["c13"].source == "llm" and got["c14"].privacy_role == "sensitive_attribute"
    assert "[dependency]" in got["c14"].reason and findings[-1]["kind"] == "dependency"


class _Pair(FakeClient):
    def __init__(self):
        super().__init__(None)

    def complete(self, prompt, **kw):
        cols = json.loads(prompt)["columns"]
        kind = {"c13": ("sensitive_attribute", "SOCIAL_DATA"), "c14": ("quasi_identifier", "AGE")}
        return FakeResp(json.dumps({c["key"]: dict(zip(("privacy_role", "subtype"), kind[c["column"]],
                                                       strict=True)) for c in cols if c["column"] in kind}))


def test_dependency_never_relabels_an_identifier(tmp_path):
    n = 200
    hr = ["80" if i % 3 else "" for i in range(n)]
    df = pd.DataFrame({"row_id": [str(i) for i in range(n)], "heart_rate": hr,
                       "postcode": ["20100" if h else "" for h in hr]})  # fmt: skip
    labels, _, findings = _dataset(tmp_path, df)
    assert {x.column: x for x in labels}["postcode"].privacy_role == "quasi_identifier"
    assert findings == []


def test_repeating_code_is_a_person_id_by_context(tmp_path):
    n = 300
    df = pd.DataFrame({"row_id": [f"R{i:05d}" for i in range(n)],
                       "c2": [f"KC-{1000 + i % 60}" for i in range(n)]})  # fmt: skip
    labels, _, _ = _dataset(tmp_path, df, readme="HR and payroll export of employees.")
    lab = {x.column: x for x in labels}["c2"]
    assert (lab.privacy_role, lab.subtype) == ("technical_identifier", "EMPLOYEE_ID")
    assert "[person_code]" in lab.reason


def test_llm_prompt_carries_readme(tmp_path):
    d = tmp_path / "ds"
    d.mkdir()
    pd.DataFrame({"row_id": [str(i) for i in range(30)], "x": ["v"] * 30}).to_csv(
        d / "t.csv", index=False)
    (d / "README.md").write_text("Care company HR export.", encoding="utf-8")
    labels = det.detect(prof.profile_dataset("ds", 1, tmp_path))
    client = FakeClient(lambda cols: "{}")
    det.llm_pass(labels, client, 1, tmp_path)
    assert client.prompts[0]["dataset_description"] == "Care company HR export."
    assert "trade union" in det.LLM_SYSTEM and "shift" in det.LLM_SYSTEM


@pytest.mark.parametrize(("name", "expected"), [
    ("handle_time_s", True), ("duration_s", True), ("los_minutes", True), ("response_ms", True),
    ("puhelun_kesto", True), ("kestoaika", True), ("dwell_seconds", True),
    ("wind_ms", False), ("temp_min", False), ("visits", False), ("time_of_day", False),
])  # fmt: skip
def test_duration_names(name, expected):
    assert bool(det._duration_token(det.tokens(name))) is expected


def test_numeric_duration_is_not_a_quasi_identifier():
    p = ColumnProfile("ds", "t", "handle_time_s", 100, 1.0, 0.5, 2, 4, 3.0, {},
                      {"integer": 1.0, "decimal": 1.0})  # fmt: skip
    r = det.classify(p, 3)
    assert (r.role, r.subtype, r.family) == ("non_sensitive", "DURATION", "name_duration")
