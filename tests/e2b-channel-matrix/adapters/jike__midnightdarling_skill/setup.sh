#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/MidnightDarling/jike-skill /tmp/as-matrix/jike-skill
pip install /tmp/as-matrix/jike-skill qrcode[pil]
