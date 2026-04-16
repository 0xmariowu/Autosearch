#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/as-matrix
if [ ! -d /tmp/as-matrix/weibo-public-opinion-analysis/.git ]; then
  rm -rf /tmp/as-matrix/weibo-public-opinion-analysis
  git clone --depth=1 https://github.com/stay-leave/weibo-public-opinion-analysis /tmp/as-matrix/weibo-public-opinion-analysis
fi

if [ -f /tmp/as-matrix/weibo-public-opinion-analysis/requirement.txt ]; then
  pip install -r /tmp/as-matrix/weibo-public-opinion-analysis/requirement.txt
fi

if [ -f /tmp/as-matrix/weibo-public-opinion-analysis/weibo-crawler/requirements.txt ]; then
  pip install -r /tmp/as-matrix/weibo-public-opinion-analysis/weibo-crawler/requirements.txt
fi

pip install requests lxml json5 tqdm piexif
