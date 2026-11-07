import json
import re
from pathlib import Path

import pandas as pd

from api.pipeline import detect as det
from api.pipeline import profile as prof
from api.pipeline.contracts import PRIVACY_ROLES, SUBTYPES

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
    assert len(det.RULE_FAMILIES) == 12


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


def test_llm_answers_accepted_only_if_in_taxonomy(tmp_path):
    labels = _write_table(tmp_path, 3)
    low = [i for i, lab in enumerate(labels) if lab.confidence < det.LLM_CONFIDENCE_THRESHOLD]
    assert len(low) == 3

    def reply(cols):
        a, b, _c = (x["id"] for x in cols)
        return json.dumps([
            {"id": a, "privacy_role": "sensitive_attribute", "subtype": "SOCIAL_DATA"},
            {"id": b, "privacy_role": "pii", "subtype": "SOCIAL_DATA"},
            {"id": 999, "privacy_role": "free_text", "subtype": "FREE_TEXT"},
        ])  # c missing, 999 unknown

    client = FakeClient(reply)
    out, stats = det.llm_pass(labels, client, 1, tmp_path)
    assert (stats["sent"], stats["calls"], stats["accepted"], stats["rejected"]) == (3, 1, 1, 2)
    assert (out[low[0]].privacy_role, out[low[0]].source) == ("sensitive_attribute", "llm")
    assert out[low[1]] == labels[low[1]] and out[low[2]] == labels[low[2]]
    assert all(len(c["sample_values"]) <= 20 for p in client.prompts for c in p["columns"])


def test_llm_batches_of_twenty_with_output_cap(tmp_path):
    labels = _write_table(tmp_path, 45)
    client = FakeClient(lambda cols: json.dumps(
        [{"id": c["id"], "privacy_role": "non_sensitive", "subtype": "CATEGORY"} for c in cols]))
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
    client = FakeClient(lambda cols: "[]")
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
