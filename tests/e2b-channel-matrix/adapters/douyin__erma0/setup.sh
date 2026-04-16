#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/erma0/douyin /tmp/as-matrix/douyin
pip install click loguru pyexecjs requests ujson
npm install --prefix /tmp/as-matrix/douyin
