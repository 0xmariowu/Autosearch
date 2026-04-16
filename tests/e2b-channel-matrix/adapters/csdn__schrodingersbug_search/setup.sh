#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/SchrodingersBug/CSDN_SearchEngine /tmp/as-matrix/CSDN_SearchEngine

if [[ -f /tmp/as-matrix/CSDN_SearchEngine/requirements.txt ]]; then
  pip install -r /tmp/as-matrix/CSDN_SearchEngine/requirements.txt
elif [[ -f /tmp/as-matrix/CSDN_SearchEngine/pyproject.toml || -f /tmp/as-matrix/CSDN_SearchEngine/setup.py ]]; then
  pip install /tmp/as-matrix/CSDN_SearchEngine
else
  pip install requests beautifulsoup4 jieba
fi
