#!/usr/bin/env bash
set -e

REPO="https://raw.githubusercontent.com/0xmariowu/Autosearch/main"
BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"
ORIGINAL_PATH="$PATH"

info()    { echo -e "${BOLD}$*${RESET}"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}!${RESET} $*"; }
die()     { echo -e "${RED}✗${RESET} $*" >&2; exit 1; }

# ── Flag parsing ─────────────────────────────────────────────────────────────
DRY_RUN=false
NO_INIT=false
CHECK_PATH_PERSISTENCE=false
VERSION=""

usage() {
  cat <<EOF
AutoSearch installer

Usage:
  install.sh [--dry-run] [--no-init] [--version VERSION]

Flags:
  --dry-run         Print every install command without executing it.
                    No package install, no shell-profile edit, no init.
  --no-init         Install AutoSearch but skip the final 'autosearch init'.
                    Use this in CI / unattended setups that already provision
                    config separately.
  --version VER     Pin a specific version (e.g. 2026.04.24.4) instead of
                    installing the latest. Applies to uv / pipx / pip.
  --check-path-persistence
                    Check shell-profile PATH persistence logic, then exit.
  -h, --help        Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)     DRY_RUN=true; shift ;;
    --no-init)     NO_INIT=true; shift ;;
    --check-path-persistence) CHECK_PATH_PERSISTENCE=true; shift ;;
    --version)     [[ -z "${2:-}" ]] && die "--version requires an argument"; VERSION="$2"; shift 2 ;;
    --version=*)   VERSION="${1#--version=}"; shift ;;
    -h|--help)     usage; exit 0 ;;
    *)             die "unknown flag: $1 (try --help)" ;;
  esac
done

if [[ -n "$VERSION" ]]; then
  if ! [[ "$VERSION" =~ ^[0-9]+(\.[0-9]+){0,3}((a|b|rc)[0-9]+|\.post[0-9]+|\.dev[0-9]+|\+[A-Za-z0-9.]+)?$ ]]; then
    die "--version must be a PEP 440-style version (e.g. 2026.04.25.1)"
  fi
fi

# Wrapper: in dry-run mode, print the command instead of running it.
run() {
  if [[ "$DRY_RUN" == true ]]; then
    printf "  [dry-run] %s\n" "$*"
  else
    "$@"
  fi
}

PKG_SPEC="autosearch"
[[ -n "$VERSION" ]] && PKG_SPEC="autosearch==$VERSION"

echo ""
echo -e "${BOLD}  AutoSearch — Install${RESET}"
echo "  ─────────────────────────────────────"
[[ "$DRY_RUN" == true ]] && warn "DRY RUN — no commands will execute"
[[ -n "$VERSION" ]]      && info "  Pinned version: $VERSION"
[[ "$NO_INIT" == true ]] && info "  Will skip 'autosearch init' after install"
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
    run uv tool install "$PKG_SPEC" --quiet && success "Installed via uv ($PKG_SPEC)" && return 0
  fi

  # pipx (also isolated, widely available)
  if command -v pipx &>/dev/null; then
    info "Installing via pipx..."
    run pipx install "$PKG_SPEC" && success "Installed via pipx ($PKG_SPEC)" && return 0
  fi

  # pip with Python 3.12+
  PYTHON=$(find_python || true)
  if [ -n "$PYTHON" ]; then
    info "Installing via pip ($PYTHON)..."
    run "$PYTHON" -m pip install --quiet --upgrade --break-system-packages "$PKG_SPEC" \
      || run "$PYTHON" -m pip install --quiet --upgrade "$PKG_SPEC"
    success "Installed via pip ($PKG_SPEC)" && return 0
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
shell_profile() {
  case "$(basename "${SHELL:-}")" in
    zsh)  echo "$HOME/.zshrc" ;;
    bash)
      for profile in "$HOME/.bash_profile" "$HOME/.bashrc" "$HOME/.profile"; do
        if [[ -f "$profile" ]]; then
          echo "$profile"
          return 0
        fi
      done
      echo "$HOME/.bashrc"
      ;;
    *)    echo "$HOME/.bashrc" ;;
  esac
}

persist_path() {
  local line='export PATH="$HOME/.local/bin:$PATH"'
  local profile

  if [[ ":$ORIGINAL_PATH:" == *":$HOME/.local/bin:"* ]]; then
    return 0
  fi

  profile="$(shell_profile)"
  if [[ -f "$profile" ]] && grep -Fqx "$line" "$profile" 2>/dev/null; then
    return 0
  fi

  if [[ "$DRY_RUN" == true ]]; then
    printf "  [dry-run] would append PATH export to %s\n" "$profile"
    return 0
  fi

  mkdir -p "$(dirname "$profile")"
  touch "$profile"
  echo "" >> "$profile"
  echo "# Added by AutoSearch installer" >> "$profile"
  echo "$line" >> "$profile"
  warn "Added ~/.local/bin to PATH in $profile"
}

# ── Main ─────────────────────────────────────────────────────────────────────
if [[ "$CHECK_PATH_PERSISTENCE" == true ]]; then
  persist_path
  exit 0
fi

install_autosearch
fix_path

# In dry-run mode the binary is not actually present, so the PATH check below
# would always fail and noisily ask the user to restart their shell. Skip.
if [[ "$DRY_RUN" == true ]]; then
  echo ""
  if [[ "$NO_INIT" == true ]]; then
    echo "  [dry-run] would skip 'autosearch init' (--no-init)"
  else
    echo "  [dry-run] would run: autosearch init"
  fi
  exit 0
fi

persist_path

if ! command -v autosearch &>/dev/null; then
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

if [[ "$NO_INIT" == true ]]; then
  success "Install complete. Run 'autosearch init' when you're ready to set up."
else
  # Run init — this shows the full AutoSearch setup screen
  autosearch init
fi
