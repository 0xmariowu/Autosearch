#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/moxiegushi/zhihu /tmp/as-matrix/zhihu
python3 -m pip install requests beautifulsoup4 pillow numpy keras h5py
