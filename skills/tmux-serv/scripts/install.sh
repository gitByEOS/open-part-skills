#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/../assets/tmux.services"
TARGET="${TMUX_SERVICES_FILE:-$HOME/.tmux.services}"
BACKUP=""

usage() {
    cat <<'EOF'
用法：
  install.sh                 首次安装；目标已存在则拒绝覆盖
  install.sh --upgrade       保留用户服务区并升级公共引擎
  install.sh --target <path> 指定目标文件，便于测试或自定义位置

可组合：install.sh --upgrade --target <path>
EOF
}

fail() {
    printf '错误：%s\n' "$*" >&2
    exit 1
}

extract_region() {
    local file="$1"
    local start_marker="$2"
    local end_marker="$3"
    local output="$4"
    local state="before"
    local starts=0
    local ends=0
    local line=""

    : > "$output"
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" == "$start_marker" ]]; then
            starts=$((starts + 1))
            [[ "$state" == "before" ]] || return 1
            state="inside"
        fi

        if [[ "$state" == "inside" ]]; then
            printf '%s\n' "$line" >> "$output"
        fi

        if [[ "$line" == "$end_marker" ]]; then
            ends=$((ends + 1))
            [[ "$state" == "inside" ]] || return 1
            state="after"
        fi
    done < "$file"

    [[ "$starts" -eq 1 && "$ends" -eq 1 && "$state" == "after" ]]
}

render_upgrade() {
    local target="$1"
    local output="$2"
    local user_region="$3"
    local line=""
    local skipping=""

    extract_region "$target" \
        "# >>> tmux-serv user services >>>" \
        "# <<< tmux-serv user services <<<" \
        "$user_region" || fail "目标文件缺少唯一、完整的用户服务区标记，拒绝自动升级：$target"

    : > "$output"
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" == "# >>> tmux-serv user services >>>" ]]; then
            cat "$user_region" >> "$output"
            skipping=1
            continue
        fi
        if [[ "$line" == "# <<< tmux-serv user services <<<" ]]; then
            skipping=""
            continue
        fi
        [[ -n "$skipping" ]] || printf '%s\n' "$line" >> "$output"
    done < "$TEMPLATE"
}

upgrade=""
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --upgrade)
            upgrade=1
            shift
            ;;
        --target)
            [[ "$#" -ge 2 ]] || fail "--target 缺少路径"
            TARGET="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "未知参数：$1"
            ;;
    esac
done

[[ -f "$TEMPLATE" ]] || fail "找不到模板：$TEMPLATE"
/bin/bash -n "$TEMPLATE" || fail "模板语法无效：$TEMPLATE"
mkdir -p "$(dirname "$TARGET")"

if [[ -z "$upgrade" ]]; then
    [[ ! -e "$TARGET" && ! -L "$TARGET" ]] || fail "目标已存在，拒绝覆盖；请检查后使用 --upgrade：$TARGET"
    install -m 700 "$TEMPLATE" "$TARGET"
    printf '已安装：%s\n' "$TARGET"
    exit 0
fi

[[ -f "$TARGET" && ! -L "$TARGET" ]] || fail "升级目标必须是常规文件且不能是符号链接：$TARGET"
TMP_OUTPUT="$(mktemp "${TMPDIR:-/tmp}/tmux-services-upgrade.XXXXXX")"
USER_REGION="$(mktemp "${TMPDIR:-/tmp}/tmux-services-user.XXXXXX")"
cleanup() {
    if [[ -n "$TMP_OUTPUT" ]]; then
        rm -f "$TMP_OUTPUT"
    fi
    if [[ -n "$USER_REGION" ]]; then
        rm -f "$USER_REGION"
    fi
}
trap cleanup EXIT INT TERM

render_upgrade "$TARGET" "$TMP_OUTPUT" "$USER_REGION"
/bin/bash -n "$TMP_OUTPUT" || fail "合并后的脚本语法无效，原文件未改动"
/bin/bash "$TMP_OUTPUT" --check >/dev/null || fail "合并后的服务配置无效，原文件未改动"

BACKUP="$TARGET.bak.$(date +%Y%m%d%H%M%S)-$$"
cp -p "$TARGET" "$BACKUP"
chmod 700 "$TMP_OUTPUT"
mv "$TMP_OUTPUT" "$TARGET"
TMP_OUTPUT=""
printf '已升级：%s\n备份：%s\n' "$TARGET" "$BACKUP"
