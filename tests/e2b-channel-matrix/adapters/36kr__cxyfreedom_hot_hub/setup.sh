#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/cxyfreedom/website-hot-hub /tmp/as-matrix/website-hot-hub

if [[ -f /tmp/as-matrix/website-hot-hub/requirements.txt ]]; then
  pip install -r /tmp/as-matrix/website-hot-hub/requirements.txt
elif [[ -f /tmp/as-matrix/website-hot-hub/pyproject.toml || -f /tmp/as-matrix/website-hot-hub/setup.py ]]; then
  pip install /tmp/as-matrix/website-hot-hub
else
  pip install requests beautifulsoup4 lxml
fi
