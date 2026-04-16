#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/freeloop4032/douyin-live /tmp/as-matrix/douyin-live
pip install requests websocket-client protobuf
