#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/NanmiCoder/MediaCrawler /tmp/as-matrix/MediaCrawler
apt-get update -qq && apt-get install -y libgl1 libglib2.0-0  # e2b sandbox runs as root
pip install -r /tmp/as-matrix/MediaCrawler/requirements.txt
