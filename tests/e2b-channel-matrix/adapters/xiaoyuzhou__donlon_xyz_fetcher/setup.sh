#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/donlon/xyz-fetcher /tmp/as-matrix/xyz-fetcher
pip install -r /tmp/as-matrix/xyz-fetcher/requirements.txt
