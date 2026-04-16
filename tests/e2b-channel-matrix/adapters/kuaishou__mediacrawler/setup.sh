#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/NanmiCoder/MediaCrawler /tmp/as-matrix/MediaCrawler
pip install -r /tmp/as-matrix/MediaCrawler/requirements.txt
