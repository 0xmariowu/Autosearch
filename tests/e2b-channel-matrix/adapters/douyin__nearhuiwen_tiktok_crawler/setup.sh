#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/NearHuiwen/TiktokCrawler /tmp/as-matrix/TiktokCrawler
pip install requests six
