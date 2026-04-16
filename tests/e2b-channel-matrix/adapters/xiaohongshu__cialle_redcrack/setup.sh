#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/Cialle/RedCrack /tmp/as-matrix/RedCrack
pip install aiohttp aiohttp-socks getuseragent loguru PyExecJS quickjs requests
