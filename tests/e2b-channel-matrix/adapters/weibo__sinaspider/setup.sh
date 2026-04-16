#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/as-matrix
if [ ! -d /tmp/as-matrix/SinaSpider/.git ]; then
  rm -rf /tmp/as-matrix/SinaSpider
  git clone --depth=1 https://github.com/LiuXingMing/SinaSpider /tmp/as-matrix/SinaSpider
fi

if [ -f /tmp/as-matrix/SinaSpider/requirements.txt ]; then
  pip install -r /tmp/as-matrix/SinaSpider/requirements.txt
fi
