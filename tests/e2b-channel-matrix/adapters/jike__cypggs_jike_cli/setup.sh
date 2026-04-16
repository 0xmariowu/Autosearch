#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/cypggs/jike-cli /tmp/as-matrix/jike-cli
pip install /tmp/as-matrix/jike-cli click requests
