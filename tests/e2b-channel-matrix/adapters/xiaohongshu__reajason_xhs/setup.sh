#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/ReaJason/xhs /tmp/as-matrix/xhs
pip install /tmp/as-matrix/xhs
