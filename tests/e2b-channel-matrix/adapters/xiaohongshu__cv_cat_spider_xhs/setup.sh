#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/cv-cat/Spider_XHS /tmp/as-matrix/Spider_XHS
pip install -r /tmp/as-matrix/Spider_XHS/requirements.txt requests
