#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/lzjun567/zhihu-api /tmp/as-matrix/zhihu-api
python3 -m pip install /tmp/as-matrix/zhihu-api
