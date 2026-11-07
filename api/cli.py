"""PurposeFit command line: purposefit <stage> --run <id>.

Stage 0 (`run`) writes runs/<id>/00_manifest.json. Later stages are built in later phases.
Refuses to start without PURPOSEFIT_HMAC_KEY. Logs hold ids, counts and timings only.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import re
import subprocess  # nosec B404 (fixed git command, no shell, no user input)
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from api.pipeline import llm

log = logging.getLogger("purposefit.cli")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGES = ("run", "profile", "detect", "plan", "transform", "redact", "verify", "report")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
DEFAULT_SEED = 20261107


class ConfigError(RuntimeError):
    """Missing or invalid configuration. The message says which .env line to add."""


def runs_dir() -> Path:
    return Path(os.environ.get("PURPOSEFIT_RUNS_DIR") or PROJECT_ROOT / "runs")


def require_hmac_key() -> str:
    key = os.environ.get("PURPOSEFIT_HMAC_KEY", "").strip()
    if not key:
        raise ConfigError(
            "PURPOSEFIT_HMAC_KEY is not set. Add a line PURPOSEFIT_HMAC_KEY=<output of "
            "openssl rand -hex 32> to .env"
        )
    return key


def key_id(key: str) -> str:
    """A short public id for the key. One-way: the key cannot be recovered from it."""
    return hmac.new(key.encode(), b"purposefit-key-id", hashlib.sha256).hexdigest()[:12]


def git_hash() -> str:
    try:
        out = subprocess.run(  # nosec B603 B607
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=5, check=True,
        )  # fmt: skip
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def check_run_id(run_id: str) -> str:
    if not RUN_ID_RE.match(run_id):
        raise argparse.ArgumentTypeError(
            "run id: letters, digits, _ and - only, up to 64 characters"
        )
    return run_id


def build_manifest(args: argparse.Namespace, key: str) -> dict:
    # Names only: building a provider client here would need its API key.
    provider = "none" if args.no_llm else (os.environ.get("LLM_PROVIDER") or llm.DEFAULT_PROVIDER)
    provider = provider.strip().lower()
    defaults = {"gemini": llm.GEMINI_MODEL, "gemma": llm.GEMMA_MODEL,
                "featherless": llm.FEATHERLESS_MODEL, "none": "none"}  # fmt: skip
    model = "none" if provider == "none" else (
        os.environ.get("LLM_MODEL", "").strip() or defaults.get(provider, "unknown")
    )  # fmt: skip
    return {
        "run_id": args.run,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_hash": git_hash(),
        "key_id": key_id(key),
        "seed": args.seed,
        "llm": {"provider": provider, "model": model},
        "layers": {"llm": not args.no_llm, "ner": not args.no_ner,
                   "gazetteer": not args.no_gazetteer},
    }  # fmt: skip


def cmd_run(args: argparse.Namespace, key: str) -> int:
    run_path = runs_dir() / args.run
    run_path.mkdir(parents=True, exist_ok=True)
    (runs_dir() / "private").mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(args, key)
    (run_path / "00_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


def _datasets(args: argparse.Namespace) -> list[str]:
    from api.pipeline import io

    if args.datasets == "all":
        return [d for d in io.list_datasets() if d != "unseen"]
    return [d.strip() for d in args.datasets.split(",") if d.strip()]


def cmd_profile(args: argparse.Namespace, key: str) -> int:
    from api.pipeline.profile import profile_dataset, write_profiles

    run_path = runs_dir() / args.run
    run_path.mkdir(parents=True, exist_ok=True)
    profiles = [p for d in _datasets(args) for p in profile_dataset(d, args.seed)]
    write_profiles(profiles, run_path / "01_profiles.json")
    return 0


def cmd_detect(args: argparse.Namespace, key: str) -> int:
    from api.pipeline import detect as det
    from api.pipeline import llm as llm_mod
    from api.pipeline.profile import read_profiles

    run_path = runs_dir() / args.run
    if not (run_path / "01_profiles.json").exists():
        cmd_profile(args, key)
    labels = det.detect(read_profiles(run_path / "01_profiles.json"))
    stats: dict = {"status": "off"}
    if args.llm and not args.no_llm:
        try:
            client = llm_mod.get_client()
        except llm_mod.LLMError:
            # Never block a run on the LLM: keep the rules-only labels and say so.
            log.warning(json.dumps({"run_id": args.run, "stage": "detect",
                                    "event": "llm_unavailable"}))  # fmt: skip
            stats = {"status": "unavailable"}
        else:
            labels, stats = det.llm_pass(labels, client, args.seed)
    det.write_labels(labels, run_path / "02_labels.csv")
    det.write_label_details(labels, run_path / "02_labels_detail.json")
    (run_path / "02_detect_stats.json").write_text(json.dumps(
        {"columns": len(labels), "llm": stats,
         "llm_threshold": det.LLM_CONFIDENCE_THRESHOLD}, indent=2), encoding="utf-8")  # fmt: skip
    if args.unseen_out:
        out = Path(args.unseen_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        det.write_labels(labels, out, unseen_format=True)
    return 0


HANDLERS = {"run": cmd_run, "profile": cmd_profile, "detect": cmd_detect}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="purposefit", description="Purpose-fit data release")
    sub = p.add_subparsers(dest="stage", required=True)
    for stage in STAGES:
        s = sub.add_parser(stage)
        s.add_argument("--run", required=True, type=check_run_id, help="run id")
        s.add_argument("--seed", type=int, default=DEFAULT_SEED)
        s.add_argument("--no-llm", action="store_true", help="switch off every LLM call")
        s.add_argument("--no-ner", action="store_true", help="switch off the NER layer")
        s.add_argument("--no-gazetteer", action="store_true", help="switch off gazetteers")
        s.add_argument("--datasets", default="customer_service",
                       help="comma-separated dataset ids, or all")
        if stage == "detect":
            s.add_argument("--llm", action="store_true",
                           help="send low-confidence columns to the LLM (off by default)")
            s.add_argument("--unseen-out", help="also write column,privacy_role,subtype here")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    args = parser().parse_args(argv)
    try:
        key = require_hmac_key()
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    start = time.monotonic()
    if args.stage in HANDLERS:
        code = HANDLERS[args.stage](args, key)
    else:
        print(f"Stage {args.stage} is not built yet.", file=sys.stderr)
        code = 3
    log.info(json.dumps({"run_id": args.run, "stage": args.stage, "exit": code,
                         "duration_ms": int((time.monotonic() - start) * 1000)}))  # fmt: skip
    return code


if __name__ == "__main__":
    raise SystemExit(main())
