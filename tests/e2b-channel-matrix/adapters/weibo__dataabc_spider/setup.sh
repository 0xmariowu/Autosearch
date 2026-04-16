#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/as-matrix
if [ ! -d /tmp/as-matrix/weiboSpider/.git ]; then
  rm -rf /tmp/as-matrix/weiboSpider
  git clone --depth=1 https://github.com/dataabc/weiboSpider /tmp/as-matrix/weiboSpider
fi

if [ -f /tmp/as-matrix/weiboSpider/requirements.txt ]; then
  pip install -r /tmp/as-matrix/weiboSpider/requirements.txt
fi
