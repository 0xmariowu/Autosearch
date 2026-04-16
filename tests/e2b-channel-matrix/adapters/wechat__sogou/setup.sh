#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/chyroc/WechatSogou /tmp/as-matrix/WechatSogou
pip install -r /tmp/as-matrix/WechatSogou/requirements.txt
