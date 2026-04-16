#!/usr/bin/env bash
set -euo pipefail

git clone --depth=1 https://github.com/iDerekLi/juejin-helper /tmp/as-matrix/juejin-helper
npm install --prefix /tmp/as-matrix/juejin-helper
