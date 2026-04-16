#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/Nemo2011/bilibili-api /tmp/as-matrix/bilibili-api
pip install /tmp/as-matrix/bilibili-api httpx
