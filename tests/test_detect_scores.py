"""Scores against the public catalog. Skips without the proving ground or pets-eval."""

import pytest

from api.pipeline.detect import run_detect
from scripts import eval_detect


def test_beats_b1_on_all_nine(proving_ground):
    pytest.importorskip("pets_eval", reason="pets-eval not installed (make eval-detect)")
    import pandas as pd

    labels, _ = run_detect(eval_detect.SPLITS["all"], 20261107)
    pred = pd.DataFrame([lab.to_dict() for lab in labels])
    res = eval_detect.score(pred, ["all"])["all"]
    assert res["macro_f1"] > 0.65
    assert res["per_role"]["sensitive_attribute"]["recall"] > 0.10
    assert res["per_role"]["quasi_identifier"]["recall"] > 0.59
