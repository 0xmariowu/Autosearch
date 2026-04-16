#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/kaixindelele/CSDN_pageviews_spider_tomysql_and_visualize /tmp/as-matrix/CSDN_pageviews_spider_tomysql_and_visualize

if [[ -f /tmp/as-matrix/CSDN_pageviews_spider_tomysql_and_visualize/requirements.txt ]]; then
  pip install -r /tmp/as-matrix/CSDN_pageviews_spider_tomysql_and_visualize/requirements.txt
elif [[ -f /tmp/as-matrix/CSDN_pageviews_spider_tomysql_and_visualize/pyproject.toml || -f /tmp/as-matrix/CSDN_pageviews_spider_tomysql_and_visualize/setup.py ]]; then
  pip install /tmp/as-matrix/CSDN_pageviews_spider_tomysql_and_visualize
else
  pip install requests pymysql matplotlib
fi
