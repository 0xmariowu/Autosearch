#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/as-matrix
if [ ! -d /tmp/as-matrix/Unofficial-Zhihu-API/.git ]; then
  rm -rf /tmp/as-matrix/Unofficial-Zhihu-API
  git clone --depth=1 https://github.com/littlepai/Unofficial-Zhihu-API /tmp/as-matrix/Unofficial-Zhihu-API
fi

pip install requests beautifulsoup4 pillow numpy tqdm
