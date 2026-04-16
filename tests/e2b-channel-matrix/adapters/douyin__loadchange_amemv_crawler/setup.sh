#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/loadchange/amemv-crawler /tmp/as-matrix/amemv-crawler
pip install requests six
