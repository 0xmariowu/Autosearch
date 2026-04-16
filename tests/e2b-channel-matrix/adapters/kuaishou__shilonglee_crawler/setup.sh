#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/ShilongLee/Crawler /tmp/as-matrix/Crawler
pip install -r /tmp/as-matrix/Crawler/requirements.txt
