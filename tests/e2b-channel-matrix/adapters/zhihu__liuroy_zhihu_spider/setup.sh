#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/as-matrix
if [ ! -d /tmp/as-matrix/zhihu_spider/.git ]; then
  rm -rf /tmp/as-matrix/zhihu_spider
  git clone --depth=1 https://github.com/LiuRoy/zhihu_spider /tmp/as-matrix/zhihu_spider
fi

if [ -f /tmp/as-matrix/zhihu_spider/requirements.txt ]; then
  pip install -r /tmp/as-matrix/zhihu_spider/requirements.txt
elif [ -f /tmp/as-matrix/zhihu_spider/setup.py ]; then
  pip install /tmp/as-matrix/zhihu_spider
else
  pip install scrapy
fi
