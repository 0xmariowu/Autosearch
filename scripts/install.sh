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

echo ""
echo "AutoSearch installed! Next steps:"
echo "  1. Open Claude Code"
echo "  2. Run: /autosearch:setup"
echo "  3. Run: /autosearch \"your research topic\""
