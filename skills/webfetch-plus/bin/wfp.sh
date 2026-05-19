#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"

# 检测依赖
if [ ! -d "$SKILL_ROOT/runtime/node/node_modules" ]; then
  npm install --prefix "$SKILL_ROOT/runtime/node" --quiet 2>/dev/null
fi

URL_AND_ARGS="${1:-$(cat)}"

if [ -z "$URL_AND_ARGS" ]; then
  echo "[wfp] Usage: bash bin/wfp.sh '<url>' or echo '<url>' | bash bin/wfp.sh"
  exit 1
fi

cd "$SKILL_ROOT" && exec node runtime/webfetch-plus.mjs $URL_AND_ARGS
