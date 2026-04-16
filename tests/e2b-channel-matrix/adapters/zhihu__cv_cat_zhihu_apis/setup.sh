#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/as-matrix
if [ ! -d /tmp/as-matrix/ZhihuApis/.git ]; then
  rm -rf /tmp/as-matrix/ZhihuApis
  git clone --depth=1 https://github.com/cv-cat/ZhihuApis /tmp/as-matrix/ZhihuApis
fi

if [ -f /tmp/as-matrix/ZhihuApis/requirements.txt ]; then
  pip install -r /tmp/as-matrix/ZhihuApis/requirements.txt
elif [ -f /tmp/as-matrix/ZhihuApis/requirements-dev.txt ]; then
  pip install -r /tmp/as-matrix/ZhihuApis/requirements-dev.txt
elif [ -f /tmp/as-matrix/ZhihuApis/setup.py ]; then
  pip install /tmp/as-matrix/ZhihuApis
fi
