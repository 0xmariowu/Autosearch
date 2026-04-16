#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/ds19991999/csdn-spider /tmp/as-matrix/csdn-spider

if [[ -f /tmp/as-matrix/csdn-spider/requirements.txt ]]; then
  pip install -r /tmp/as-matrix/csdn-spider/requirements.txt
elif [[ -f /tmp/as-matrix/csdn-spider/pyproject.toml || -f /tmp/as-matrix/csdn-spider/setup.py ]]; then
  pip install /tmp/as-matrix/csdn-spider
else
  pip install requests beautifulsoup4 markdownify
fi
