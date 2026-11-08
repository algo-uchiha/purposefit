"""Export web/fixtures/*.json for the front-end agent, from real run folders.

Usage (after the p4-CS-S1 and p4-CS-S3 runs exist and runs/leaderboard.csv is current):
  uv run --with ./vendor/proving_ground/toolkit --env-file .env python -m scripts.export_ui_fixtures

The payloads are produced by api/pipeline/views.py, the same code the API serves, so a fixture
and an API response for the same run are identical. Never reads row maps or runs/private. Checks
the output for the HMAC key, row-map names and local paths.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from api import cli
from api.pipeline import views as vw

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
OUT = ROOT / "web" / "fixtures"
SCENARIOS = ("CS-S1", "CS-S3")
RUN_FOR = {"CS-S1": "p4-CS-S1", "CS-S3": "p4-CS-S3"}  # run folders of the final runs


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, obj) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def export() -> list[str]:
    OUT.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("PURPOSEFIT_HMAC_KEY", "")
    write("scenarios.json", vw.scenarios_view())
    write("leaderboard.json", vw.leaderboard_view(RUNS))
    base = RUN_FOR["CS-S1"]
    findings = [*load(RUNS / "p2c-after" / "02_findings.json"),
                *load(RUNS / "p2c-after-unseen" / "02_findings.json")]  # fmt: skip
    write("findings.json", findings)
    write("stage.profile.json", vw.stage_view(RUNS, base, "profile"))
    write("stage.detect.json", vw.stage_view(RUNS, base, "detect"))
    man = load(RUNS / base / "00_manifest.json")
    write("health.json", {"status": "ok", "git_hash": man["git_hash"], "key_id": man["key_id"],
                          "llm": vw.llm_view(), "proving_ground": True})  # fmt: skip
    for sid, run_id in RUN_FOR.items():
        write(f"run.{sid}.json", vw.run_view(RUNS, run_id))
        for stage in ("plan", "transform", "redact", "verify", "report"):
            write(f"stage.{stage}.{sid}.json" if stage != "plan" else f"plan.{sid}.json",
                  vw.stage_view(RUNS, run_id, stage))  # fmt: skip
        v = vw.stage_view(RUNS, run_id, "verify")
        write(f"scorecard.ours.{sid}.json", v["ours"])
        write(f"scorecard.b2k.{sid}.json", v["baseline"])
    return check_output(key)


def check_output(key: str) -> list[str]:
    """Fail on a key, a row-map name or a local path anywhere in the fixtures."""
    problems, names = [], []
    for f in sorted(OUT.glob("*.json")):
        names.append(f.name)
        text = f.read_text(encoding="utf-8")
        if key and key in text:
            problems.append(f"{f.name}: contains the HMAC key")
        for bad in ("rowmap", "original_record_id", "/Users/", "/home/", "GEMINI_API_KEY"):
            if bad in text:
                problems.append(f"{f.name}: contains {bad!r}")
    if problems:
        raise SystemExit("fixture check failed:\n" + "\n".join(problems))
    return names


if __name__ == "__main__":
    _ = cli  # the API and the exporter share cli helpers
    files = export()
    print(f"wrote {len(files)} files to {OUT.relative_to(ROOT)}")
