#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/slarkio/xyz-dl /tmp/as-matrix/xyz-dl
pip install /tmp/as-matrix/xyz-dl
