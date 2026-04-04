#!/bin/bash
set -euo pipefail
VENV_PYTHON="$HOME/.autosearch/venv/bin/python"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SEARCH_RUNNER="$SCRIPT_DIR/../lib/search_runner.py"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "[AutoSearch] Not set up. Run /autosearch:setup first." >&2
    exit 1
fi

PYTHONPATH="$SCRIPT_DIR/.." exec "$VENV_PYTHON" "$SEARCH_RUNNER" "$@"
