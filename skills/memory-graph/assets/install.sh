#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PACKAGE="memory-graph-0.2.1-darwin-universal"
ZIP="$ROOT/$PACKAGE.zip"
INSTALL_ROOT="${MEMORY_GRAPH_HOME:-$HOME/.memory-graph/tools}"
TARGET="$INSTALL_ROOT/memory-graph"
BIN_DIR="${MEMORY_GRAPH_BIN_DIR:-$HOME/.local/bin}"
BIN="$BIN_DIR/memory-graph"

if ! command -v node >/dev/null 2>&1; then
  echo "node 未安装，无法运行 memory-graph" >&2
  exit 1
fi

if ! command -v unzip >/dev/null 2>&1; then
  echo "unzip 未安装，无法解压 $ZIP" >&2
  exit 1
fi

if [ ! -f "$ZIP" ]; then
  echo "安装包不存在: $ZIP" >&2
  exit 1
fi

mkdir -p "$INSTALL_ROOT"
unzip -oq "$ZIP" -d "$INSTALL_ROOT"
case "$(uname -m)" in
  x86_64) NATIVE_ARCH="x64" ;;
  arm64) NATIVE_ARCH="arm64" ;;
  *)
    echo "不支持的 mac 架构: $(uname -m)" >&2
    exit 1
    ;;
esac
cp "$INSTALL_ROOT/node_modules/kuzu/prebuilt/kuzujs-darwin-$NATIVE_ARCH.node" "$INSTALL_ROOT/node_modules/kuzu/kuzujs.node"
mkdir -p "$BIN_DIR"
ln -sf "$TARGET" "$BIN"
"$TARGET" init >/dev/null

echo "Installed memory-graph -> $TARGET"
echo "Linked command -> $BIN"
case ":${PATH:-}:" in
  *":$BIN_DIR:"*) ;;
  *) echo "提示: 当前 PATH 不包含 ${BIN_DIR}，直接运行请先执行: export PATH=\"${BIN_DIR}:\$PATH\"" ;;
esac
echo "Initialized global store -> $HOME/.memory-graph"
