#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
INPUT_FILE="$SKILL_ROOT/runtime/.wfp_input"

if [ ! -f "$INPUT_FILE" ]; then
  echo "[wfp] Error: no input file at $INPUT_FILE"
  exit 1
fi

read -r URL < "$INPUT_FILE"

if [ -z "$URL" ]; then
  echo "[wfp] Error: URL is empty"
  exit 1
fi

EXTRA_ARGS=()
while IFS= read -r line; do
  [ -n "$line" ] && EXTRA_ARGS+=("$line")
done < <(tail -n +2 "$INPUT_FILE")

cd "$SKILL_ROOT" && exec node runtime/webfetch-plus.mjs "$URL" "${EXTRA_ARGS[@]}"
