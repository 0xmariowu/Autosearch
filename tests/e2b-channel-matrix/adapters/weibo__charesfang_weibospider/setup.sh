#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/as-matrix
if [ ! -d /tmp/as-matrix/WeiboSpider/.git ]; then
  rm -rf /tmp/as-matrix/WeiboSpider
  git clone --depth=1 https://github.com/CharesFang/WeiboSpider /tmp/as-matrix/WeiboSpider
fi

if [ -f /tmp/as-matrix/WeiboSpider/requirements.txt ]; then
  pip install -r /tmp/as-matrix/WeiboSpider/requirements.txt
fi
