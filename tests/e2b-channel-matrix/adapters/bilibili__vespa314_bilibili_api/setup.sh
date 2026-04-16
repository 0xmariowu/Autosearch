#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/Vespa314/bilibili-api /tmp/as-matrix/bilibili-api-vespa314
pip install /tmp/as-matrix/bilibili-api-vespa314 requests
