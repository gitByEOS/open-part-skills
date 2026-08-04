#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"

# 检测依赖
NODE_ROOT="$SKILL_ROOT/runtime/node"
INSTALL_LOCK="$NODE_ROOT/.install.lock"

install_dependencies() {
  while ! mkdir "$INSTALL_LOCK" 2>/dev/null; do
    if [ -f "$INSTALL_LOCK/pid" ] && ! kill -0 "$(cat "$INSTALL_LOCK/pid")" 2>/dev/null; then
      rm -rf "$INSTALL_LOCK"
      continue
    fi
    sleep 1
  done

  trap 'rm -rf "$INSTALL_LOCK"' EXIT
  printf '%s\n' "$$" > "$INSTALL_LOCK/pid"
  if [ ! -d "$NODE_ROOT/node_modules" ]; then
    npm install --prefix "$NODE_ROOT" --quiet 2>/dev/null
  fi
  rm -rf "$INSTALL_LOCK"
  trap - EXIT
}

if [ ! -d "$NODE_ROOT/node_modules" ]; then
  install_dependencies
fi

if [ "$#" -gt 0 ]; then
  URL_AND_ARGS=("$@")
else
  read -r -a URL_AND_ARGS
fi

if [ "${#URL_AND_ARGS[@]}" -eq 0 ]; then
  echo "[wfp] Usage: bash bin/wfp.sh '<url> [options]' or echo '<url> [options]' | bash bin/wfp.sh"
  exit 1
fi

cd "$SKILL_ROOT" && exec node runtime/webfetch-plus.mjs "${URL_AND_ARGS[@]}"
