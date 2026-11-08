#!/bin/bash
# One end-to-end run: scripts/final_run.sh CS-S1 [nollm]
# Run it from a clean commit with .env set; the LLM cache in runs/cache is used.
set -e
cd "$(dirname "$0")/.."
S=$1; MODE=${2:-llm}
R=final-$S; FLAGS="--llm"; NOTE="rule redactor + LLM health flags on masked text"
if [ "$MODE" = "nollm" ]; then R=$R-nollm; FLAGS=""; NOTE="AI off: rules only, no LLM calls"; fi
cli() { uv run --with ./vendor/proving_ground/toolkit --env-file .env python -m api.cli "$@"; }
NL=""; [ "$MODE" = "nollm" ] && NL="--no-llm"
cli run --run $R $NL
cli profile --run $R $NL
cli detect --run $R $FLAGS $NL
cli plan --run $R --scenario $S $NL
cli transform --run $R $NL
cli redact --run $R $NL
cli report --run $R $NL
cli verify --run $R $NL --method purposefit --note "final run: $S, $NOTE, per-recipient key"
