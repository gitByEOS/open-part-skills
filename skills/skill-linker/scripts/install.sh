#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
COMMAND_PATH="$BIN_DIR/skill-link"
LINK_ROOT=""

usage() {
  echo "用法: bash scripts/install.sh [--root path]" >&2
  echo "  --root 指向包含 skills/ 和 rules/ 的来源目录" >&2
}

detect_rc_file() {
  case "${SHELL:-}" in
    */zsh) echo "$HOME/.zshrc" ;;
    */bash) echo "$HOME/.bashrc" ;;
    *) echo "$HOME/.profile" ;;
  esac
}

detect_bash_login_rc() {
  local file
  for file in "$HOME/.bash_profile" "$HOME/.bash_login" "$HOME/.profile"; do
    if [[ -f "$file" ]]; then
      echo "$file"
      return
    fi
  done

  echo "$HOME/.bash_profile"
}

ensure_bashrc_loaded() {
  [[ "${SHELL:-}" == */bash ]] || return

  local bashrc="$HOME/.bashrc"
  local login_rc
  login_rc="$(detect_bash_login_rc)"

  touch "$bashrc" "$login_rc"

  if grep -Eq '(^|[[:space:]])(source|\.)[[:space:]]+("?\$HOME/\.bashrc"?|"?~/\.bashrc"?|"?'"$HOME"'/\.bashrc"?)' "$login_rc"; then
    echo ".bashrc 已由 $(basename "$login_rc") 加载"
    return
  fi

  cat >> "$login_rc" <<'EOF'

# Load interactive bash config.
if [ -f "$HOME/.bashrc" ]; then
  . "$HOME/.bashrc"
fi
EOF

  echo "已补充 $(basename "$login_rc") 加载 .bashrc"
}

install_fzf() {
  if command -v fzf >/dev/null 2>&1; then
    echo "fzf 已安装: $(command -v fzf)"
    return
  fi

  if command -v brew >/dev/null 2>&1; then
    brew install fzf
    return
  fi

  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y fzf
    return
  fi

  if command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y fzf
    return
  fi

  if command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm fzf
    return
  fi

  echo "未找到 fzf，也未找到 brew/apt-get/dnf/pacman，请先手动安装 fzf" >&2
  exit 1
}

ask_root() {
  local value

  if [[ -n "$LINK_ROOT" ]]; then
    echo "$LINK_ROOT"
    return
  fi

  read -r -p "SKILL_LINK_ROOT: " value
  if [[ -z "$value" ]]; then
    echo "SKILL_LINK_ROOT 不能为空" >&2
    exit 1
  fi
  echo "$value"
}

upsert_line() {
  local file="$1"
  local key="$2"
  local line="$3"

  touch "$file"
  if grep -q "^$key" "$file"; then
    local escaped_line
    escaped_line="$(printf '%s\n' "$line" | sed 's/[\/&]/\\&/g')"
    sed -i.bak "s/^$key.*/$escaped_line/" "$file"
  else
    printf '\n%s\n' "$line" >> "$file"
  fi
}

delete_line() {
  local file="$1"
  local key="$2"

  touch "$file"
  sed -i.bak "/^$key/d" "$file"
}

install_command() {
  mkdir -p "$BIN_DIR"
  cp "$SCRIPT_DIR/skill-link.sh" "$COMMAND_PATH"
  chmod +x "$COMMAND_PATH"
}

write_shell_config() {
  local rc_file="$1"
  local link_root="$2"

  delete_line "$rc_file" "export SKILL_LINK_SKILL_ROOT="
  delete_line "$rc_file" "export SKILL_LINK_RULE_ROOT="
  upsert_line "$rc_file" "export SKILL_LINK_ROOT=" "export SKILL_LINK_ROOT=\"$link_root\""

  touch "$rc_file"
  if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$rc_file"; then
    printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc_file"
  fi
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --root)
      [[ -n "${2:-}" ]] || {
        echo "缺少 --root 值" >&2
        usage
        exit 1
      }
      LINK_ROOT="$2"
      shift 2
      ;;
    --root=*)
      LINK_ROOT="${1#--root=}"
      shift
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

link_root="$(ask_root)"
if [[ ! -d "$link_root/skills" || ! -d "$link_root/rules" ]]; then
  echo "SKILL_LINK_ROOT 必须包含 skills/ 和 rules/: $link_root" >&2
  exit 1
fi
rc_file="$(detect_rc_file)"

install_fzf
install_command
write_shell_config "$rc_file" "$link_root"
ensure_bashrc_loaded

echo "已安装 skill-link: $COMMAND_PATH"
echo "已写入配置: $rc_file"
echo "重新打开终端，或执行: source \"$rc_file\""
