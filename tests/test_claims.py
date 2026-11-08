"""The README quotes only numbers that match the committed claims snapshot."""

from scripts import verify_claims as vc


def test_readme_numbers_match_the_snapshot(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(vc, "RUNS", tmp_path)  # no run files, as in CI: the snapshot check only
    monkeypatch.setattr("sys.argv", ["verify_claims"])
    assert vc.main() == 0
    assert "all match" in capsys.readouterr().out


def test_a_changed_number_is_caught(tmp_path, monkeypatch, capsys):
    text = vc.README.read_text(encoding="utf-8").replace("0.9817 <!--c:lb.final-CS-S1.composite-->",
                                                         "0.9999 <!--c:lb.final-CS-S1.composite-->", 1)
    fake = tmp_path / "README.md"
    fake.write_text(text, encoding="utf-8")
    monkeypatch.setattr(vc, "RUNS", tmp_path)
    monkeypatch.setattr(vc, "README", fake)
    monkeypatch.setattr("sys.argv", ["verify_claims"])
    assert vc.main() == 1
    assert "lb.final-CS-S1.composite" in capsys.readouterr().out
