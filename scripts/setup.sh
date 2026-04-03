#!/bin/bash
set -e

VENV_DIR="$HOME/.autosearch/venv"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REQ_FILE="$SCRIPT_DIR/../requirements.txt"

echo "Setting up AutoSearch..."

# Find Python 3.10+
PYTHON=""
# Check PATH first, then uv-managed Pythons
candidates=(python3.13 python3.12 python3.11 python3.10 python3)
# Add uv-managed Python paths
for uv_py in "$HOME"/.local/share/uv/python/cpython-3.1*/bin/python3; do
    [ -x "$uv_py" ] && candidates+=("$uv_py")
done

for candidate in "${candidates[@]}"; do
    if command -v "$candidate" &>/dev/null || [ -x "$candidate" ]; then
        version=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null) || continue
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10+ required. Install it first:"
    echo "  brew install python@3.11"
    echo "  # or: uv python install 3.11"
    exit 1
fi

echo "Using $PYTHON ($($PYTHON --version))"

# Create venv if needed
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

# Install/upgrade dependencies
echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -r "$REQ_FILE"

echo "AutoSearch setup complete!"
echo "Venv: $VENV_DIR"
echo "Python: $("$VENV_DIR/bin/python" --version)"
