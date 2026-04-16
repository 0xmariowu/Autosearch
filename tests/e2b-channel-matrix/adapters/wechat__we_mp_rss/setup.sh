#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/rachelos/we-mp-rss /tmp/as-matrix/we-mp-rss
python3 -m pip install feedparser
