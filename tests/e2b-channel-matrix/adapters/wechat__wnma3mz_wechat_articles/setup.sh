#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/wnma3mz/wechat_articles_spider /tmp/as-matrix/wechat_articles_spider
pip install /tmp/as-matrix/wechat_articles_spider
