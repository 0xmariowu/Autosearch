#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/as-matrix
if [ ! -d /tmp/as-matrix/weibo-crawler/.git ]; then
  rm -rf /tmp/as-matrix/weibo-crawler
  git clone --depth=1 https://github.com/dataabc/weibo-crawler /tmp/as-matrix/weibo-crawler
fi

if [ -f /tmp/as-matrix/weibo-crawler/requirements.txt ]; then
  pip install -r /tmp/as-matrix/weibo-crawler/requirements.txt
fi

pip install requests lxml json5 tqdm piexif
