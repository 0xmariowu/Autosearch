#!/bin/bash
set -e

echo "Installing AutoSearch for Claude Code..."

# Check claude is available
if ! command -v claude &>/dev/null; then
    echo "Error: claude command not found. Install Claude Code first:"
    echo "  https://claude.com/download"
    exit 1
fi

# Add marketplace and install plugin
claude plugin marketplace add 0xmariowu/autosearch
claude plugin install autosearch@autosearch

# Install /autosearch global command (clean name without namespace)
PLUGIN_CACHE="$HOME/.claude/plugins/cache/autosearch/autosearch"
LATEST=$(ls -t "$PLUGIN_CACHE" 2>/dev/null | head -1)
CMD_SRC="$PLUGIN_CACHE/$LATEST/commands/autosearch.md"
CMD_DST="$HOME/.claude/commands/autosearch.md"

if [ -f "$CMD_SRC" ]; then
    mkdir -p "$HOME/.claude/commands"
    cp "$CMD_SRC" "$CMD_DST"
    echo "Installed /autosearch command"
else
    echo "Warning: could not find command template, use /autosearch:autosearch instead"
fi

echo ""
echo "AutoSearch installed! Start a new Claude Code session and run:"
echo "  /autosearch \"your research topic\""
