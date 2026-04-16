#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/as-matrix
if [ ! -d /tmp/as-matrix/zhihu-api-syaning/.git ]; then
  rm -rf /tmp/as-matrix/zhihu-api-syaning
  git clone --depth=1 https://github.com/syaning/zhihu-api /tmp/as-matrix/zhihu-api-syaning
fi

npm install --prefix /tmp/as-matrix/zhihu-api-syaning
