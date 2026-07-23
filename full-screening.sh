#!/bin/bash
# CrawlLama Full Screening — Linux/macOS
#
# One command that merges the two testing layers into a single gate:
#
#   1. pytest test suite      — deterministic unit/integration correctness of
#                               every tool and module.
#   2. arena validate         — scenarios/suites are well-formed.
#   3. arena coverage --gate  — every registered capability/tool maps to at
#                               least one arena scenario ("jedes Tool getestet").
#   4. arena run smoke        — deterministic, network-/LLM-free behaviour gate.
#   5. arena run capabilities — the real SearchAgent / MultiHopAgent, offline.
#   6. arena run live         — real tools (web search, page read, wiki, RAG).
#                               Only with --live (needs network + Ollama).
#
# The arena only begins once pytest is green: a failing unit suite aborts the
# run before any screening. Stages are fail-fast and the final line is a clear
# PASS/FAIL verdict, so this is usable as a CI gate.
#
# Usage:
#   ./full-screening.sh                         # pytest + arena (deterministic)
#   ./full-screening.sh --profile arena/scenarios/profiles/ollama-llama31-8b.json
#   ./full-screening.sh --live                  # also run the live tool suite
#   ./full-screening.sh --no-store              # do not persist arena runs

set -o pipefail

PROFILE="mock"
RUN_LIVE=0
STORE_FLAG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile) PROFILE="$2"; shift 2 ;;
        --profile=*) PROFILE="${1#*=}"; shift ;;
        --live) RUN_LIVE=1; shift ;;
        --no-store) STORE_FLAG="--no-store"; shift ;;
        -h|--help)
            sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed. Install it, then run ./setup.sh." >&2
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/scripts/uv-env.sh"
crawllama_setup_uv_env "$SCRIPT_DIR"
cd "$SCRIPT_DIR"

FAILED_STAGE=""

# Run a named stage; on failure record it and stop the pipeline (fail-fast).
run_stage() {
    local name="$1"; shift
    echo ""
    echo "============================================================"
    echo "  ▶ $name"
    echo "     \$ $*"
    echo "============================================================"
    if ! "$@"; then
        FAILED_STAGE="$name"
        return 1
    fi
    return 0
}

START_TS=$(date +%s)

{
    run_stage "1/6  pytest test suite"       uv run pytest tests/ -q                     && \
    run_stage "2/6  arena validate"          uv run python -m arena validate             && \
    run_stage "3/6  arena coverage gate"     uv run python -m arena coverage --gate      && \
    run_stage "4/6  arena smoke suite"       uv run python -m arena run --suite smoke        --profile "$PROFILE" $STORE_FLAG && \
    run_stage "5/6  arena capabilities suite" uv run python -m arena run --suite capabilities --profile "$PROFILE" $STORE_FLAG
} || true

# The live suite is opt-in and never blocks the deterministic verdict on its own,
# but a failure here is still reported.
if [[ -z "$FAILED_STAGE" && "$RUN_LIVE" -eq 1 ]]; then
    run_stage "6/6  arena live suite"        uv run python -m arena run --suite live         --profile "$PROFILE" $STORE_FLAG || true
fi

ELAPSED=$(( $(date +%s) - START_TS ))

echo ""
echo "============================================================"
if [[ -n "$FAILED_STAGE" ]]; then
    echo "  ❌ FULL SCREENING FAILED  —  stage: $FAILED_STAGE  (${ELAPSED}s)"
    echo "============================================================"
    exit 1
fi
echo "  ✅ FULL SCREENING PASSED  —  profile=$PROFILE  (${ELAPSED}s)"
[[ "$RUN_LIVE" -eq 0 ]] && echo "     (live tool suite skipped — pass --live to include web/page/wiki/RAG)"
echo "============================================================"
exit 0
