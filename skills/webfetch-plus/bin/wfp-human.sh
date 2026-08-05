#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
RUNTIME_SCRIPT="$SKILL_ROOT/runtime/webfetch-plus.mjs"
DEFAULT_OUTPUT_DIR="/tmp/wfp-human-challenge"

usage() {
  cat >&2 <<'EOF'
Usage:
  bash bin/wfp-human.sh '<url>' [fetch options]

Run manual browser verification once and save the target's default session state.
On macOS, the same command automatically opens Terminal when called from a non-TTY.
EOF
}

fail() {
  printf '[wfp-human] %s\n' "$1" >&2
  exit 1
}

get_state_path() {
  WFP_HUMAN_RUNTIME="$RUNTIME_SCRIPT" WFP_HUMAN_URL="$1" node --input-type=module -e '
    const runtime = await import(process.env.WFP_HUMAN_RUNTIME);
    runtime.normalizeUrl(process.env.WFP_HUMAN_URL);
    console.log(runtime.getDefaultStatePath(process.env.WFP_HUMAN_URL));
  '
}

[ "$#" -gt 0 ] || { usage; exit 1; }

URL="$1"
STATE_PATH="$(get_state_path "$URL")" || fail "invalid URL: $URL"

if [ ! -t 0 ] || [ ! -t 1 ]; then
  [ "$(uname)" = "Darwin" ] || fail "manual verification requires an interactive TTY"
  [ "$#" -eq 1 ] || fail "non-TTY launch accepts only one URL"

  osascript - "$SCRIPT_DIR/wfp-human.sh" "$URL" <<'APPLESCRIPT'
on run argv
  set launcherPath to item 1 of argv
  set targetUrl to item 2 of argv
  tell application "Terminal"
    activate
    do script "/bin/bash " & quoted form of launcherPath & " " & quoted form of targetUrl
  end tell
end run
APPLESCRIPT
  exit $?
fi

shift
FETCH_ARGS=()
HAS_OUTPUT_DIR=false
HAS_WAIT_UNTIL=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --save-state|--state|--out|--visible)
      fail "$1 is managed by wfp-human.sh and must not be supplied"
      ;;
    --output-dir)
      [ "$#" -ge 2 ] || fail "--output-dir requires a value"
      [ -n "$2" ] && [[ "$2" != --* ]] || fail "--output-dir requires a value"
      HAS_OUTPUT_DIR=true
      FETCH_ARGS+=("$1" "$2")
      shift 2
      ;;
    --wait|--timeout|--wait-until|--retries|--selector|--format)
      [ "$#" -ge 2 ] || fail "$1 requires a value"
      [ -n "$2" ] && [[ "$2" != --* ]] || fail "$1 requires a value"
      [ "$1" != "--wait-until" ] || HAS_WAIT_UNTIL=true
      FETCH_ARGS+=("$1" "$2")
      shift 2
      ;;
    --stealth)
      FETCH_ARGS+=("$1")
      shift
      ;;
    --*)
      fail "unsupported option: $1"
      ;;
    *)
      fail "only one URL is allowed; unexpected positional argument: $1"
      ;;
  esac
done

if [ "$HAS_OUTPUT_DIR" = false ]; then
  FETCH_ARGS+=("--output-dir" "$DEFAULT_OUTPUT_DIR")
fi

if [ "$HAS_WAIT_UNTIL" = false ]; then
  FETCH_ARGS+=("--wait-until" "domcontentloaded")
fi

cd "$SKILL_ROOT"
WFP_HUMAN_CHALLENGE=1 bash bin/wfp.sh "$URL" --stealth --save-state "$STATE_PATH" "${FETCH_ARGS[@]}"
printf '[wfp-human] saved state: %s\n' "$STATE_PATH"
printf '[wfp-human] reuse headlessly: bash bin/wfp.sh %q --state %q --stealth\n' "$URL" "$STATE_PATH"
