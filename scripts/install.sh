#!/bin/bash
set -e

# install.sh — Install or update AutoSearch for Claude Code
# Also serves as the update script: re-run to get the latest version.

# Check claude is available
if ! command -v claude &>/dev/null; then
    echo "Error: claude command not found. Install Claude Code first:"
    echo "  https://claude.com/download"
    exit 1
fi

# Detect if already installed
PLUGIN_CACHE="$HOME/.claude/plugins/cache/autosearch/autosearch"
if [ -d "$PLUGIN_CACHE" ]; then
    OLD_VERSION=$(ls -t "$PLUGIN_CACHE" 2>/dev/null | head -1)
    echo "Updating AutoSearch (current: ${OLD_VERSION:-unknown})..."
    claude plugin update autosearch@autosearch 2>/dev/null \
        || claude plugin install autosearch@autosearch
else
    echo "Installing AutoSearch for Claude Code..."
    claude plugin marketplace add 0xmariowu/autosearch
    claude plugin install autosearch@autosearch
fi

# Install/update /autosearch global command (clean name without namespace)
LATEST=$(ls -t "$PLUGIN_CACHE" 2>/dev/null | head -1)
CMD_SRC="$PLUGIN_CACHE/$LATEST/commands/autosearch.md"
CMD_DST="$HOME/.claude/commands/autosearch.md"

if [ -f "$CMD_SRC" ]; then
    mkdir -p "$HOME/.claude/commands"
    cp "$CMD_SRC" "$CMD_DST"
    echo "Synced /autosearch command"
else
    echo "Warning: could not find command template, use /autosearch:autosearch instead"
fi

# Show installed version
if [ -n "$LATEST" ]; then
    PLUGIN_JSON="$PLUGIN_CACHE/$LATEST/.claude-plugin/plugin.json"
    if [ -f "$PLUGIN_JSON" ]; then
        VERSION=$(python3 -c "import json; print(json.load(open('$PLUGIN_JSON'))['version'])" 2>/dev/null || echo "$LATEST")
    else
        VERSION="$LATEST"
    fi
    echo ""
    echo "AutoSearch v${VERSION} ready! Start a new Claude Code session and run:"
    echo "  /autosearch \"your research topic\""
    echo ""
    echo "To auto-update: /plugin → Marketplaces → autosearch → Enable auto-update"
else
    echo ""
    echo "AutoSearch installed! Start a new Claude Code session and run:"
    echo "  /autosearch \"your research topic\""
fi
