#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/oGsLP/kuaishou-crawler /tmp/as-matrix/kuaishou-crawler
pip install -r /tmp/as-matrix/kuaishou-crawler/requirements.txt
