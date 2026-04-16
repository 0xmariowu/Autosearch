#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/1dot75cm/xueqiu /tmp/as-matrix/xueqiu
pip install /tmp/as-matrix/xueqiu
