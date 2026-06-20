#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHON_SCRIPT="$SCRIPT_DIR/fetch_what_say.py"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"

log() {
  printf '%s\n' "$*" >&2
}

has_arg() {
  local target="$1"
  shift
  for arg in "$@"; do
    [[ "$arg" == "$target" ]] && return 0
  done
  return 1
}

is_preview_run() {
  has_arg "--dry-run" "$@" || has_arg "--schema" "$@" || has_arg "--view" "$@" || has_arg "--help" "$@" || has_arg "-h" "$@"
}

python_package_exists() {
  "$PYTHON_BIN" - "$1" <<'PY'
import importlib.util
import sys

raise SystemExit(0 if importlib.util.find_spec(sys.argv[1]) else 1)
PY
}

extend_python_bin_path() {
  local user_base
  user_base="$("$PYTHON_BIN" -m site --user-base 2>/dev/null || true)"
  if [[ -n "$user_base" ]]; then
    export PATH="$user_base/bin:$PATH"
  fi
}

install_python_package() {
  local package="$1"
  log "[install] pip install $package"
  "$PYTHON_BIN" -m pip install --index-url "$PIP_INDEX_URL" "$package"
  extend_python_bin_path
}

ensure_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1; then
    return
  fi
  if [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
    log "[install] brew install ffmpeg"
    brew install ffmpeg
    return
  fi
  log "缺少 ffmpeg，请先安装"
  exit 3
}

ensure_python_tools() {
  extend_python_bin_path
  if ! command -v yt-dlp >/dev/null 2>&1; then
    install_python_package "yt-dlp"
  fi
  if ! has_arg "--no-transcribe" "$@" && ! python_package_exists "mlx_whisper"; then
    install_python_package "mlx-whisper"
  fi
}

main() {
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    log "缺少 python3"
    exit 3
  fi
  if is_preview_run "$@"; then
    exec "$PYTHON_BIN" "$PYTHON_SCRIPT" "$@"
  fi
  ensure_ffmpeg
  ensure_python_tools "$@"
  exec "$PYTHON_BIN" "$PYTHON_SCRIPT" "$@"
}

main "$@"
