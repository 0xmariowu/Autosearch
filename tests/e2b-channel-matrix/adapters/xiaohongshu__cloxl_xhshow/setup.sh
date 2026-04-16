#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/Cloxl/xhshow /tmp/as-matrix/xhshow
pip install /tmp/as-matrix/xhshow requests
