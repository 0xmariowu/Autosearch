#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/cv-cat/DouYin_Spider /tmp/as-matrix/DouYin_Spider
pip install -r /tmp/as-matrix/DouYin_Spider/requirements.txt beautifulsoup4 protobuf-to-dict
npm install --prefix /tmp/as-matrix/DouYin_Spider
