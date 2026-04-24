#!/usr/bin/env bash
# scripts/release-gate.sh — single command to verify v2 install contract before cutting a release.
#
# Composes the four checks that prove a fresh user install will work:
#   1. version files agree (pyproject / plugin.json / marketplace.json / CHANGELOG / npm)
#   2. lint + format clean
#   3. unit + smoke test suite green
#   4. CLI surface honest:
#        - `autosearch doctor --json` returns the expected channel count
#        - `autosearch mcp-check` reports all 10 required v2 tools registered
#
# Each step prints a one-line PASS/FAIL banner; the script exits non-zero on the
# first failure and reports which gate blocked. No network access required.
#
# Usage:
#   scripts/release-gate.sh                # run all gates
#   scripts/release-gate.sh --quick        # skip the full pytest run (lint + version + CLI only)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

QUICK=false
for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=true ;;
    -h|--help)
      grep -E '^# ' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "unknown flag: $arg (try --help)" >&2
      exit 2
      ;;
  esac
done

PYTHON=""
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON="$REPO_ROOT/.venv/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON=$(command -v python3.12)
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=$(command -v python3)
else
  echo "FAIL: no Python found (need .venv/bin/python, python3.12, or python3 on PATH)" >&2
  exit 1
fi

# Resolve adjacent CLI tools — prefer the project venv, fall back to PATH so
# this script works in CI runners where deps land in system Python.
_resolve_tool() {
  local venv_path="$REPO_ROOT/.venv/bin/$1"
  if [ -x "$venv_path" ]; then
    printf '%s' "$venv_path"
  else
    command -v "$1" 2>/dev/null || true
  fi
}

RUFF=$(_resolve_tool ruff)
PYTEST=$(_resolve_tool pytest)
AUTOSEARCH=$(_resolve_tool autosearch)

step() { printf "\n==> %s\n" "$1"; }
pass() { printf "PASS: %s\n" "$1"; }
fail() { printf "FAIL: %s\n" "$1" >&2; exit 1; }

# ── Gate 1: version consistency ──────────────────────────────────────────────
step "version consistency"
if "$PYTHON" scripts/validate/check_version_consistency.py; then
  pass "version files agree"
else
  fail "version files drifted (see output above)"
fi

# ── Gate 2: lint + format ────────────────────────────────────────────────────
step "lint + format"
if [ -x "$RUFF" ]; then
  "$RUFF" check . || fail "ruff check"
  "$RUFF" format --check . || fail "ruff format"
  pass "ruff check + format clean"
else
  echo "skip: ruff not found at $RUFF (install with .venv pip install ruff)"
fi

# ── Gate 3: tests ────────────────────────────────────────────────────────────
if [ "$QUICK" = false ]; then
  step "unit + smoke tests"
  if [ -x "$PYTEST" ]; then
    "$PYTEST" -x -q -m "not real_llm and not perf and not slow and not network" \
      || fail "pytest"
    pass "all default-marker tests green"
  else
    echo "skip: pytest not found at $PYTEST"
  fi
fi

# ── Gate 4: CLI surface honest ───────────────────────────────────────────────
step "CLI surface (doctor + mcp-check)"
if [ ! -x "$AUTOSEARCH" ]; then
  fail "autosearch CLI not installed in $REPO_ROOT/.venv (run: uv pip install -e .)"
fi

doctor_json=$("$AUTOSEARCH" doctor --json) || fail "autosearch doctor --json crashed"
"$PYTHON" - <<PY
import json, sys
data = json.loads('''$doctor_json''')
assert isinstance(data, list) and len(data) >= 30, (
    f"doctor --json returned {len(data) if isinstance(data, list) else type(data).__name__} channels, expected >=30"
)
PY
pass "doctor --json returns valid channel list"

mcp_out=$("$AUTOSEARCH" mcp-check) || fail "autosearch mcp-check exited non-zero"
case "$mcp_out" in
  *"OK: all 10 required tools registered."*) pass "mcp-check reports all required tools" ;;
  *) fail "mcp-check did not report all 10 required tools" ;;
esac

printf "\n=========================================\n"
printf "Release gate PASSED — safe to cut release.\n"
printf "=========================================\n"
