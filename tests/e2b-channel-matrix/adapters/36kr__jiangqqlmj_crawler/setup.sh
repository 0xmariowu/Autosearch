#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/jiangqqlmj/36Kr_Data_Crawler /tmp/as-matrix/36Kr_Data_Crawler

if [[ -f /tmp/as-matrix/36Kr_Data_Crawler/requirements.txt ]]; then
  pip install -r /tmp/as-matrix/36Kr_Data_Crawler/requirements.txt
elif [[ -f /tmp/as-matrix/36Kr_Data_Crawler/pyproject.toml || -f /tmp/as-matrix/36Kr_Data_Crawler/setup.py ]]; then
  pip install /tmp/as-matrix/36Kr_Data_Crawler
else
  pip install requests javalang
fi
