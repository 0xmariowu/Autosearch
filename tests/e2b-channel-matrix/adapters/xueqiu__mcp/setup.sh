#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/liqiongyu/xueqiu_mcp /tmp/as-matrix/xueqiu_mcp
pip install /tmp/as-matrix/xueqiu_mcp
