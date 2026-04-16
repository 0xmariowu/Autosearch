#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/bowenpay/wechat-spider /tmp/as-matrix/wechat-spider
pip install -r /tmp/as-matrix/wechat-spider/requirements.txt
