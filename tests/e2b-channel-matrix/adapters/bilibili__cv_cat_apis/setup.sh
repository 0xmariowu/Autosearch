#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/as-matrix
if [ ! -d /tmp/as-matrix/BilibiliApis/.git ]; then
  rm -rf /tmp/as-matrix/BilibiliApis
  git clone --depth=1 https://github.com/cv-cat/BilibiliApis /tmp/as-matrix/BilibiliApis
fi

if [ -f /tmp/as-matrix/BilibiliApis/requirements.txt ]; then
  pip install -r /tmp/as-matrix/BilibiliApis/requirements.txt
fi
