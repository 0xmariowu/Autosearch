#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/ldh2068vip/36krCrawler /tmp/as-matrix/36krCrawler

if [[ -f /tmp/as-matrix/36krCrawler/requirements.txt ]]; then
  pip install -r /tmp/as-matrix/36krCrawler/requirements.txt
elif [[ -f /tmp/as-matrix/36krCrawler/pyproject.toml || -f /tmp/as-matrix/36krCrawler/setup.py ]]; then
  pip install /tmp/as-matrix/36krCrawler
else
  pip install requests javalang
fi
