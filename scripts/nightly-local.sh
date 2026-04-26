#!/usr/bin/env bash
# nightly-local.sh — F101 baseline regression, driven locally.
#
# Meant for macOS launchd or cron scheduling when GitHub Actions is not the
# desired driver (no GH Actions secrets required — orchestrator reads keys
# directly from ~/.config/ai-secrets.env).
#
# Produces the same reports/nightly-YYYY-MM-DD/ layout as the CI workflow, so
# "3 consecutive nightly greens" evidence is identical regardless of scheduler.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}"

# Orchestrator Python: prefer a repo-local venv (post PR #196 layout) so the
# runner stays self-contained; fall back to the shared venv when the repo
# doesn't yet carry one.
if [ -x "${REPO_ROOT}/scripts/e2b/.venv/bin/python" ]; then
  PY="${REPO_ROOT}/scripts/e2b/.venv/bin/python"
elif [ -x "${HOME}/.claude/scripts/e2b/.venv/bin/python" ]; then
  PY="${HOME}/.claude/scripts/e2b/.venv/bin/python"
else
  echo "error: no orchestrator venv found" >&2
  echo "  tried: ${REPO_ROOT}/scripts/e2b/.venv/bin/python" >&2
  echo "  tried: ${HOME}/.claude/scripts/e2b/.venv/bin/python" >&2
  echo "  hint:  uv venv scripts/e2b/.venv --python 3.12 && uv pip install --python scripts/e2b/.venv/bin/python e2b e2b-code-interpreter rich pyyaml" >&2
  exit 2
fi

ORCHESTRATOR="${REPO_ROOT}/scripts/e2b/run_validation.py"
if [ ! -f "${ORCHESTRATOR}" ]; then
  # Scripts still living outside the repo (pre PR #196 merge).
  ORCHESTRATOR="${HOME}/.claude/scripts/e2b/run_validation.py"
fi
if [ ! -f "${ORCHESTRATOR}" ]; then
  echo "error: run_validation.py not found in repo or ~/.claude/scripts/e2b/" >&2
  exit 2
fi

SECRETS_FILE="${AUTOSEARCH_SECRETS_FILE:-${HOME}/.config/ai-secrets.env}"
if [ ! -r "${SECRETS_FILE}" ]; then
  echo "error: secrets file not readable: ${SECRETS_FILE}" >&2
  exit 2
fi

DATE="$(date -u +%Y-%m-%d)"
REPORT_DIR="reports/nightly-${DATE}"
mkdir -p "${REPORT_DIR}"

# Matrix upload steps in tests/e2b/matrix.yaml hardcode /tmp/autosearch-src.tar.gz
# as the source path, so the file on disk has to match that exact name.
TARBALL="/tmp/autosearch-src.tar.gz"

# Pack tracked files only (P0-2 fix): scripts.e2b.lib.packing applies
# git ls-files + denylist so .env / experience/ / evidence/ never enter
# the sandbox tarball, even if a developer accidentally git-add'd one.
echo "[nightly-local] packing tracked files only via scripts.e2b.lib.packing"
"${PY}" -c "from pathlib import Path; from scripts.e2b.lib.packing import pack_directory; pack_directory(Path('${REPO_ROOT}'), Path('${TARBALL}'))"

PARALLEL="${AUTOSEARCH_PARALLEL:-15}"

echo "[$(date -u +%FT%TZ)] nightly start | orchestrator=${ORCHESTRATOR} | report=${REPORT_DIR} | parallel=${PARALLEL}"

"${PY}" "${ORCHESTRATOR}" \
  --project autosearch \
  --matrix tests/e2b/matrix.yaml \
  --secrets "${SECRETS_FILE}" \
  --output "${REPORT_DIR}" \
  --parallel "${PARALLEL}" \
  --tarball "${TARBALL}"

echo "[$(date -u +%FT%TZ)] nightly done | summary=${REPORT_DIR}/summary.md"
