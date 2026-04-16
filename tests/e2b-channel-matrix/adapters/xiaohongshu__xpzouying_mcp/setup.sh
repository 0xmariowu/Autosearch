#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/xpzouying/xiaohongshu-mcp /tmp/as-matrix/xiaohongshu-mcp
if command -v go >/dev/null 2>&1; then
  (
    cd /tmp/as-matrix/xiaohongshu-mcp
    go build -o /tmp/as-matrix/xiaohongshu-mcp/xiaohongshu-mcp .
  )
fi
pip install requests
