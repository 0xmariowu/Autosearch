#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/submato/xhscrawl /tmp/as-matrix/xhscrawl
pip install requests PyExecJS
