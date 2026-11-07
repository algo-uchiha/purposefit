import pandas as pd

from api.pipeline import profile as prof

VALUES = {
    "hetu": ["131052-308T", "010101A123N"],
    "iban": ["FI21 1234 5600 0007 85"],
    "card": ["4111 1111 1111 1111"],
    "email": ["matti.meikalainen@example.fi"],
    "phone": ["040 123 4567", "+358401234567"],
    "ipv4": ["10.0.0.1", "192.168.1.0/24"],
    "mac": ["00:1A:2B:3C:4D:5E"],
    "timestamp": ["2025-03-01 12:30:00", "2025-03-01T12:30"],
    "date": ["2025-03-01", "1.3.2025", "13/09/88"],
    "postcode": ["20100"],
    "plate": ["ABC-123"],
    "person_name": ["Mäkinen Mika Matias", "Anna Virtanen"],
    "sentence": ["Asiakas soitti ja kertoi että lasku oli väärin."],
}


def test_validators_accept_examples():
    for name, vals in VALUES.items():
        for v in vals:
            assert prof.VALIDATORS[name](v), (name, v)


def test_validators_reject_noise():
    for name in ("hetu", "iban", "card", "email", "phone", "ipv4", "plate"):
        assert not prof.VALIDATORS[name]("kissa"), name
    assert not prof.VALIDATORS["hetu"]("131052-308X")  # wrong check character


def test_profile_holds_rates_only_and_is_deterministic():
    df = pd.DataFrame({"email": ["a@b.fi", "c@d.fi", ""] * 1000})
    p1 = prof.profile_table("d", "t", df, seed=1)[0]
    p2 = prof.profile_table("d", "t", df, seed=1)[0]
    assert p1 == p2 and p1.rows_sampled == prof.SAMPLE_ROWS
    assert 0.6 < p1.fill_rate < 0.72 and p1.validator_hits["email"] == 1.0
    assert "a@b.fi" not in str(p1.to_dict())
