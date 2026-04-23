#!/usr/bin/env bash
set -e

REPO="https://raw.githubusercontent.com/0xmariowu/Autosearch/main"
BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

info()    { echo -e "${BOLD}$*${RESET}"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}!${RESET} $*"; }
die()     { echo -e "${RED}✗${RESET} $*" >&2; exit 1; }

echo ""
echo -e "${BOLD}  AutoSearch — Install${RESET}"
echo "  ─────────────────────────────────────"
echo ""

# ── 1. Find Python 3.12+ ────────────────────────────────────────────────────
find_python() {
  for cmd in python3.13 python3.12 python3 python; do
    if command -v "$cmd" &>/dev/null; then
      version=$("$cmd" -c "import sys; print(sys.version_info[:2])" 2>/dev/null)
      if echo "$version" | grep -qE "\(3, (1[2-9]|[2-9][0-9])"; then
        echo "$cmd"; return 0
      fi
    fi
  done
  return 1
}

# ── 2. Install autosearch ────────────────────────────────────────────────────
install_autosearch() {
  # uv tool install (best: isolated, cross-platform, fast)
  if command -v uv &>/dev/null; then
    info "Installing via uv..."
    uv tool install autosearch --quiet && success "Installed via uv" && return 0
  fi

  # pipx (also isolated, widely available)
  if command -v pipx &>/dev/null; then
    info "Installing via pipx..."
    pipx install autosearch && success "Installed via pipx" && return 0
  fi

  # pip with Python 3.12+
  PYTHON=$(find_python || true)
  if [ -n "$PYTHON" ]; then
    info "Installing via pip ($PYTHON)..."
    "$PYTHON" -m pip install --quiet --upgrade --break-system-packages autosearch 2>/dev/null \
      || "$PYTHON" -m pip install --quiet --upgrade autosearch
    success "Installed via pip" && return 0
  fi

  die "Could not install autosearch. Install Python 3.12+ first: https://python.org"
}

# ── 3. Ensure autosearch is in PATH ─────────────────────────────────────────
fix_path() {
  # uv tool bin
  if command -v uv &>/dev/null; then
    UV_BIN=$(uv tool dir 2>/dev/null | sed 's|tools$|bin|' || echo "")
    if [ -n "$UV_BIN" ] && [ -d "$UV_BIN" ] && [[ ":$PATH:" != *":$UV_BIN:"* ]]; then
      export PATH="$UV_BIN:$PATH"
    fi
  fi

  # ~/.local/bin (pipx default)
  if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    export PATH="$HOME/.local/bin:$PATH"
  fi
}

# ── 4. Persist PATH to shell profile ─────────────────────────────────────────
persist_path() {
  local line='export PATH="$HOME/.local/bin:$PATH"'
  for profile in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile"; do
    if [ -f "$profile" ] && ! grep -q '.local/bin' "$profile" 2>/dev/null; then
      echo "" >> "$profile"
      echo "# Added by AutoSearch installer" >> "$profile"
      echo "$line" >> "$profile"
      warn "Added ~/.local/bin to PATH in $profile"
      break
    fi
  done
}

# ── Main ─────────────────────────────────────────────────────────────────────
install_autosearch
fix_path

if ! command -v autosearch &>/dev/null; then
  persist_path
  fix_path
fi

if ! command -v autosearch &>/dev/null; then
  echo ""
  warn "autosearch not found in PATH. Restart your terminal, then run: autosearch init"
  exit 0
fi

echo ""
echo "  ─────────────────────────────────────"
echo ""

# Run init — this shows the full AutoSearch setup screen
autosearch init
