"""Rule redactor: hand-made Finnish, Swedish and English sentences for every rule label."""

from __future__ import annotations

import pytest

from api.pipeline.redact import Layers, cues, normalise, patterns, redact
from api.pipeline.redact.gazetteer import Controller, Dvv
from api.pipeline.redact.merge import Cand, merge

NONE = Layers(controller=False, dvv=False)


def red(text: str, layers: Layers = NONE, controller: Controller | None = None) -> tuple[str, list]:
    res = redact({"r": text}, layers=layers, controller=controller)
    return res.redacted["r"], res.spans["r"]


@pytest.mark.parametrize("text,label,secret", [
    ("Henkilötunnukseni on 131052-308T kiitos", "NATIONAL_ID", "131052-308T"),
    ("Mitt personnummer är 131052-308T tack", "NATIONAL_ID", "131052-308T"),
    ("My id is 131052-308T please", "NATIONAL_ID", "131052-308T"),
    ("Tilini on FI21 1234 5600 0007 85 ja se toimii", "IBAN", "FI21 1234 5600 0007 85"),
    ("Mitt konto är FI21 1234 5600 0007 85 tack", "IBAN", "FI21 1234 5600 0007 85"),
    ("The account is FI21 1234 5600 0007 85 today", "IBAN", "FI21 1234 5600 0007 85"),
    ("Kortti 4000 0012 3456 7899 on kadonnut", "PAYMENT_CARD", "4000 0012 3456 7899"),
    ("Kortet 4000 0012 3456 7899 är borta", "PAYMENT_CARD", "4000 0012 3456 7899"),
    ("The card 4000 0012 3456 7899 is lost", "PAYMENT_CARD", "4000 0012 3456 7899"),
    ("Sähköpostini on matti.meikalainen@posti.example kiitos", "EMAIL", "matti.meikalainen@posti.example"),
    ("Min e-post är anna.svensson@post.example tack", "EMAIL", "anna.svensson@post.example"),
    ("Mail me at jo.smith@mail.example today", "EMAIL", "jo.smith@mail.example"),
    ("Soita numeroon 044 123 4567 huomenna", "PHONE", "044 123 4567"),
    ("Ring mig på +358 40 123 4567 imorgon", "PHONE", "+358 40 123 4567"),
    ("Call me on 050-1234567 tomorrow", "PHONE", "050-1234567"),
    ("Uusi osoite on Kukkulakuja 21 A 1, 21620 Kaarina.", "ADDRESS", "Kukkulakuja 21 A 1, 21620 Kaarina"),
    ("Ny adress är Storgatan 5, 20100 Åbo", "ADDRESS", "Storgatan 5, 20100 Åbo"),
    ("I live at Hakakaari 1 A 3, 20780 Kaarina now", "ADDRESS", "Hakakaari 1 A 3, 20780 Kaarina"),
    ("IP-osoite 100.76.16.130 näkyy lokissa", "IP_ADDRESS", "100.76.16.130"),
    ("IP-adressen 100.76.16.130 syns i loggen", "IP_ADDRESS", "100.76.16.130"),
    ("The address 100.76.16.130 is in the log", "IP_ADDRESS", "100.76.16.130"),
    ("Laitteen IMEI on 352099001761481 kiitos", "DEVICE_ID", "352099001761481"),
    ("Kiinteistötunnus 322-534-14-123 on väärä", "PROPERTY_ID", "322-534-14-123"),
    ("Auton rekisteri on jvb-87 ok", "LICENSE_PLATE", "jvb-87"),
    ("Linkki https://oma.example/reset?token=33f36618ee593a03 tuli", "URL", "https://oma.example/reset?token=33f36618ee593a03"),
    ("Salasanani on salasana123 jos se auttaa", "SECRET", "salasana123"),
    ("Lösenordet är hemlig4567 tack", "SECRET", "hemlig4567"),
    ("The password is probably koirahalli5 sorry", "SECRET", "koirahalli5"),
    ("Käyttäjätunnukseni on arttut93.", "USERNAME", "arttut93"),
    ("Mitt användarnamn är sergeiv03", "USERNAME", "sergeiv03"),
    ("My username there is irinap72", "USERNAME", "irinap72"),
    ("Nimeni on Pertti Virtanen ja olen täällä", "PERSON", "Pertti Virtanen"),
    ("Jag heter Gunnel Lindqvist och ringer", "PERSON", "Gunnel Lindqvist"),
    ("My name is Hodan Warsame and I need help", "PERSON", "Hodan Warsame"),
])
def test_rule_layers_find_every_label(text, label, secret):
    out, spans = red(text)
    assert secret not in out
    assert f"[{label}]" in out
    assert any(s.label == label for s in spans)


def test_spoken_national_id_phone_and_iban_are_normalised():
    out, spans = red("henkilötunnus yksi yksi, yksi yksi, yhdeksän kuusi, viiva, yhdeksän viisi kahdeksan, äm kiitos")
    assert "yhdeksän" not in out and any(s.layer == "normalise" for s in spans)
    out, _ = red("numero nolla neljä viisi, neljä kahdeksan kaksi, seitsemän kaksi nolla, neljä kaksi")
    assert "nolla" not in out and "[PHONE]" in out
    out, _ = red("mitt nummer är noll fyra fem, fyra åtta två, sju två noll, fyra två sju")
    assert "fyra" not in out
    out, _ = red("my number is zero four five, four eight two, seven two zero, four two seven")
    assert "zero" not in out
    out, _ = red("F I yksi kuusi, yhdeksän yksi yhdeksän viisi, kaksi yksi neljä kolme, seitsemän kaksi kuusi kahdeksan, yhdeksän kolme")
    assert "yhdeksän" not in out and "[IBAN]" in out


def test_spelled_emails_are_normalised():
    for t in ("hilkka alaviiva aalto ät aurapost piste example",
              "niina piste viitasalo at nordmail dot example",
              "anna punkt svensson snabel-a post punkt example"):
        out, spans = red(f"sähköposti {t} kiitos")
        assert "[EMAIL]" in out and spans[0].layer == "normalise"


def test_plain_words_and_numbers_are_left_alone():
    t = "Hei, voisitko kertoa miten tilaus 3 etenee, kiitos paljon."
    assert red(t)[0] == t
    t = "I have two questions and one more about the invoice of 12 euros."
    assert red(t)[0] == t


def test_every_span_records_its_layer_and_a_valid_label():
    _, spans = red("Nimeni on Pertti Virtanen, puhelin 044 123 4567, tunnus 131052-308T")
    assert {s.layer for s in spans} <= {"patterns", "normalise", "cues"}
    assert {s.label for s in spans} >= {"PERSON", "PHONE", "NATIONAL_ID"}


def test_layer_flags_switch_layers_off():
    t = "Nimeni on Pertti Virtanen, puhelin 044 123 4567"
    assert "[PERSON]" not in red(t, Layers(cues=False, controller=False, dvv=False))[0]
    assert "[PHONE]" not in red(t, Layers(patterns=False, normalise=False, controller=False, dvv=False))[0]


def test_controller_gazetteer_finds_values_in_text_and_spoken_variants():
    ctl = Controller([("PERSON_NAME", "Oscar Lindberg"), ("PHONE", "044 676 2817"),
                      ("NATIONAL_ID", "070889-965Y"), ("EMAIL", "oscar.lindberg@mail.example")])  # fmt: skip
    out, spans = red("oscar lindberg här, nummer 0446762817", Layers(dvv=False), ctl)
    assert "oscar" not in out and "0446762817" not in out
    assert {s.layer for s in spans} == {"gazetteer"}
    out, _ = red("nolla neljä neljä, kuusi seitsemän kuusi, kaksi kahdeksan yksi seitsemän", Layers(dvv=False), ctl)
    assert "kuusi" not in out
    out, _ = red("oscar piste lindberg ät mail piste example", Layers(dvv=False), ctl)
    assert "oscar" not in out


def test_dvv_names_are_a_separate_source_and_skip_common_words():
    first = frozenset({"pertti", "kuusi"})
    from api.pipeline.redact import gazetteer as g

    dvv = Dvv(frozenset({"pertti"}), first, frozenset({"virtanen"}))
    assert [(c.source, c.label) for c in g.dvv_cands("hei pertti, kuusi viestiä", dvv)] == [("dvv", "PERSON")]
    ctl = Controller([("PERSON_NAME", "Pertti Virtanen")])
    assert {c.source for c in g.controller_cands("pertti", ctl)} == {"controller"}


def test_merge_prefers_validated_then_longest():
    got = merge([Cand(0, 10, "ACCOUNT_NUMBER", "patterns", 0.4), Cand(2, 8, "PAYMENT_CARD", "patterns", 1.0),
                 Cand(20, 25, "PERSON", "cues", 0.7), Cand(22, 30, "PERSON", "gazetteer", 0.7)])  # fmt: skip
    assert [(c.start, c.end) for c in got] == [(2, 8), (22, 30)]


def test_pattern_validators_reject_bad_checksums_with_lower_score():
    good = next(h for h in patterns.find("131052-308T") if h.label == "NATIONAL_ID")
    bad = next(h for h in patterns.find("131052-308X") if h.label == "NATIONAL_ID")
    assert good.score == 1.0 and bad.score < 1.0


def test_normalise_maps_spans_back_to_the_original():
    t = "yksi kaksi kolme neljä"
    n = normalise.normalise(t)
    assert n.text == "1234" and normalise.map_back(n, 0, 4) == (0, len(t))


def test_cue_names_need_a_known_name_for_weak_cues():
    assert not cues.find("this is the end", frozenset())
    assert cues.find("this is roosa", frozenset({"roosa"}))
    assert cues.find("my name is Zxq", frozenset())


def test_redacted_text_has_only_placeholders_where_spans_were():
    out, spans = red("puhelin 044 123 4567 kiitos")
    s = spans[0]
    assert out == "puhelin [PHONE] kiitos" and s.start == 8


def test_redact_stage_rewrites_the_release_and_writes_spans_without_text(tmp_path):
    import csv
    import json

    from api import cli
    from api.pipeline import plan as pl
    from api.pipeline.contracts import FieldPolicy, PolicyPlan

    run, priv = tmp_path / "runs" / "r9", tmp_path / "runs" / "private" / "r9"
    (run / "04_release").mkdir(parents=True)
    priv.mkdir(parents=True)
    pol = FieldPolicy("turns", "text", "redact", {}, "text", "typed placeholders")
    pl.write_plan(PolicyPlan("customer_service", "CS-S1", ["turns"], [pol], 5, "kid"), run / "03_plan.json")
    with (run / "04_release" / "turns.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows([["turn_id", "text"], ["T1", "kiitos, soita numeroon 044 123 4567"], ["T2", "ei mitään"]])
    (priv / "gazetteer_values.csv").write_text("table,column,subtype,value\n", encoding="utf-8")
    assert cli.main(["redact", "--run", "r9", "--no-dvv"]) == 0
    rows = list(csv.DictReader((run / "04_release" / "turns.csv").open(encoding="utf-8")))
    assert rows[0]["text"] == "kiitos, soita numeroon [PHONE]" and rows[1]["text"] == "ei mitään"
    spans = (run / "05_spans.jsonl").read_text(encoding="utf-8")
    assert "044" not in spans and json.loads(spans.splitlines()[0])["layer"] == "patterns"
    stats = json.loads((run / "05_redact_stats.json").read_text(encoding="utf-8"))
    assert stats["layers"] == ["patterns", "normalise", "controller", "cues"]
