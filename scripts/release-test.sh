#!/usr/bin/env bash
# release-test.sh — Pre-release testing script
#
# Usage:
#   ./scripts/release-test.sh                    # Run L1 (unit) + L2 scenario s1
#   ./scripts/release-test.sh --scenario s2      # Run specific scenario
#   ./scripts/release-test.sh --scenario all     # Run all scenarios (~$3)
#   ./scripts/release-test.sh --docker           # Run in Docker (clean env)
#   ./scripts/release-test.sh --dry-run          # Show what would run
#
# Requires: OPENROUTER_API_KEY env var for L2 tests

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
BOLD='\033[1m'; DIM='\033[0;90m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCENARIO="s1"
USE_DOCKER=false
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --scenario=*) SCENARIO="${arg#*=}" ;;
    --scenario)   shift_next=true ;;
    --docker)     USE_DOCKER=true ;;
    --dry-run)    DRY_RUN=true ;;
    *)
      if [ "${shift_next:-false}" = true ]; then
        SCENARIO="$arg"
        shift_next=false
      fi
      ;;
  esac
done

info()  { printf "${GREEN}✓${NC} %s\n" "$*"; }
fail()  { printf "${RED}✗${NC} %s\n" "$*"; }
step()  { printf "\n${BOLD}── %s${NC}\n" "$*"; }

if [ "$DRY_RUN" = true ]; then
  echo "Would run:"
  echo "  L1: pytest (unit + stress tests)"
  echo "  L2: scenario $SCENARIO via run_e2e_test.py"
  [ "$USE_DOCKER" = true ] && echo "  Environment: Docker" || echo "  Environment: local"
  exit 0
fi

# ── L1: Unit tests ──
step "L1: Unit tests (pytest)"
PYTHON="${ROOT}/.venv/bin/python3"
[ -f "$PYTHON" ] || PYTHON="python3"

if [ "$USE_DOCKER" = true ]; then
  docker build -t autosearch-test "$ROOT" 2>/dev/null
  if docker run --rm autosearch-test -x -q tests/ -k "not network and not integration"; then
    info "L1 passed (Docker)"
  else
    fail "L1 failed (Docker)"
    exit 1
  fi
else
  if cd "$ROOT" && "$PYTHON" -m pytest -x -q tests/ -k "not network and not integration"; then
    info "L1 passed"
  else
    fail "L1 failed"
    exit 1
  fi
fi

# ── L2: Scenario tests ──
step "L2: Scenario $SCENARIO (pipeline + real LLM)"

if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  fail "OPENROUTER_API_KEY not set — skipping L2"
  exit 1
fi

cd "$ROOT"
if timeout 2400 "$PYTHON" tests/integration/run_e2e_test.py --scenario "$SCENARIO"; then
  info "L2 scenario $SCENARIO passed"
else
  fail "L2 scenario $SCENARIO failed"
  exit 1
fi

# ── Summary ──
step "Release test complete"
info "All checks passed. Safe to bump version and tag."
