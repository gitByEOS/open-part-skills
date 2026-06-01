#!/usr/bin/env bash
# cc-claude.sh — 国内厂商 Claude Code 启动脚本
# 用法: bash cc-claude.sh [claude参数]
#        bash cc-claude.sh config
#        bash cc-claude.sh reset
#        bash cc-claude.sh configure [--url URL] [--token TOKEN] [--models MODELS] [--name NAME]

set -euo pipefail

CONFIG_DIR="$(cd "$(dirname "$0")/.." && pwd)/config"
CONFIG_FILE="$CONFIG_DIR/auth"

# ──────────────────────────────────────────
# 加密 / 解密 AUTH_TOKEN
# 使用 openssl AES-256-CBC，密文存配置文件
# ──────────────────────────────────────────
# 固定密码（混淆用，配合文件 600 权限防随手偷看）
_ENC_PASS="cc-claude:$(hostname):$(whoami)"

encrypt_token() {
    echo -n "$1" | openssl enc -aes-256-cbc -base64 -A -pass pass:"$_ENC_PASS" -pbkdf2 2>/dev/null
}

decrypt_token() {
    echo -n "$1" | openssl enc -aes-256-cbc -d -base64 -A -pass pass:"$_ENC_PASS" -pbkdf2 2>/dev/null
}

# 判断配置文件中的 AUTH_TOKEN 是否已加密
is_encrypted() {
    local raw="$1"
    # 加密值特征：仅含 base64 字符，长度 ≥ 16
    [[ "$raw" =~ ^[A-Za-z0-9+/=]{16,}$ ]]
}

# ──────────────────────────────────────────
# 获取 AUTH_TOKEN（从配置文件解密读取）
# ──────────────────────────────────────────
get_auth_token() {
    if [[ -f "$CONFIG_FILE" ]]; then
        local raw
        raw=$(grep '^AUTH_TOKEN=' "$CONFIG_FILE" | head -1 | cut -d= -f2-)
        if [[ -n "$raw" ]]; then
            if is_encrypted "$raw"; then
                decrypt_token "$raw" && return 0
            else
                # 兼容旧版明文存储
                echo "$raw"
                return 0
            fi
        fi
    fi

    return 1
}

# ──────────────────────────────────────────
# 引导式配置（支持交互式或非交互式）
# ──────────────────────────────────────────
do_configure() {
    mkdir -p "$CONFIG_DIR"

    local base_url="" auth_token="" model_list="" cmd_name=""

    # ── 非交互式模式：从参数读取 ──
    if [[ "${1:-}" == "--url" ]]; then
        base_url="$2"; shift 2
        auth_token="$2"; shift 2
        model_list="$2"; shift 2
        cmd_name="${2:-cc-claude}"; shift 2 2>/dev/null || true

        if [[ -z "$base_url" || -z "$auth_token" || -z "$model_list" ]]; then
            echo -e "\033[1;31m✗ 非交互式模式必须提供 --url、--token、--models\033[0m"
            return 1
        fi
    else
        # ── 交互式模式：逐步询问 ──
        echo -e "\033[1;36m══════════════════════════════════════\033[0m"
        echo -e "\033[1;36m  CC Claude 配置向导\033[0m"
        echo -e "\033[1;36m══════════════════════════════════════\033[0m"
        echo ""

        # 第一步：API URL
        echo -e "\033[1;33mStep 1/4\033[0m"
        echo -e "  请输入 Anthropic 兼容 API 地址"
        echo -e "  示例: https://api.deepseek.com/anthropic"
        echo -n "  > "
        read -r base_url
        [[ -z "$base_url" ]] && { echo -e "\033[1;31m✗ 地址不能为空\033[0m"; return 1; }
        echo ""

        # 第二步：API Key
        echo -e "\033[1;33mStep 2/4\033[0m"
        echo -e "  请输入 API Key"
        echo -n "  > "
        read -r auth_token
        [[ -z "$auth_token" ]] && { echo -e "\033[1;31m✗ Key 不能为空\033[0m"; return 1; }
        echo ""

        # 第三步：模型列表
        while true; do
            echo -e "\033[1;33mStep 3/4\033[0m"
            echo -e "  请输入该厂商支持的模型列表（逗号分隔）"
            echo -e "  示例: deepseek-v4-pro, deepseek-v4-flash"
            echo -n "  > "
            read -r model_input
            if [[ -n "$model_input" ]]; then
                model_list=$(echo "$model_input" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | grep -v '^$')
                break
            else
                echo -e "\033[1;31m✗ 模型列表不能为空，请重新输入\033[0m"
                echo ""
            fi
        done
        echo ""

        # 第四步：快捷命令名
        echo -e "\033[1;33mStep 4/4\033[0m"
        echo -e "  请输入此配置保存后的快捷命令名"
        echo -e "  默认: cc-claude"
        echo -n "  > "
        read -r cmd_name
        cmd_name="${cmd_name:-cc-claude}"
        echo ""
    fi

    # 规范化模型列表
    model_list=$(echo "$model_list" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | grep -v '^$')

    # 加密 API Key 后保存
    local encrypted
    encrypted=$(encrypt_token "$auth_token")

    cat > "$CONFIG_FILE" <<EOF
# CC Claude 配置文件
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')
BASE_URL=$base_url
AUTH_TOKEN=$encrypted
COMMAND=$cmd_name
MODELS=<<MODELS
$model_list
MODELS
EOF
    chmod 600 "$CONFIG_FILE"

    echo -e "\033[1;36m══════════════════════════════════════\033[0m"
    echo -e "\033[1;32m  ✓ 配置已保存到 $CONFIG_FILE\033[0m"
    echo -e "\033[1;32m  ✓ 快捷命令: $cmd_name\033[0m"
    echo -e "\033[1;32m  ✓ API Key 已 AES-256 加密存储\033[0m"
    echo -e "\033[1;36m══════════════════════════════════════\033[0m"
    echo ""

    # 自动写入 shell 配置文件
    local script_path target_file
    script_path="$(cd "$(dirname "$0")" && pwd)/cc-claude.sh"

    local current_shell="${SHELL##*/}"
    if [[ "$current_shell" == "zsh" ]]; then
        target_file="$HOME/.zshrc"
    else
        target_file="$HOME/.bash_profile"
    fi

    if [[ -f "$target_file" ]] && grep -q "cc-claude" "$target_file" 2>/dev/null; then
        echo -e "\033[1;33m  ⚠ $target_file 中已存在 cc-claude 配置，跳过自动写入\033[0m"
    else
        cat >> "$target_file" <<SHELLRC

# cc-claude
$cmd_name() {
    bash "$script_path" "\$@"
}
SHELLRC
        echo -e "\033[1;32m  ✓ 已自动追加到 $target_file\033[0m"
    fi
    echo -e "\033[1;36m  运行 source $target_file 或重新打开终端生效\033[0m"
}

# ──────────────────────────────────────────
# 读取模型列表
# ──────────────────────────────────────────
read_models() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        return 1
    fi

    local in_models=0
    while IFS= read -r line; do
        if [[ "$line" == "MODELS=<<MODELS" ]]; then
            in_models=1
            continue
        fi
        if [[ "$line" == "MODELS" && $in_models -eq 1 ]]; then
            break
        fi
        if [[ $in_models -eq 1 && -n "$line" ]]; then
            echo "$line"
        fi
    done < "$CONFIG_FILE"
}

# ──────────────────────────────────────────
# 选模型并启动
# ──────────────────────────────────────────
do_select_and_run() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo -e "\033[1;33m未找到配置，请先配置厂商地址和 API Key\033[0m"
        echo ""
        do_configure || return 1
    fi

    local base_url auth_token cmd_name
    base_url=$(grep '^BASE_URL=' "$CONFIG_FILE" | head -1 | cut -d= -f2-)
    auth_token=$(get_auth_token || true)
    cmd_name=$(grep '^COMMAND=' "$CONFIG_FILE" | head -1 | cut -d= -f2-)

    if [[ -z "$base_url" || -z "$auth_token" ]]; then
        echo -e "\033[1;31m配置不完整，请重新配置\033[0m"
        do_configure || return 1
        base_url=$(grep '^BASE_URL=' "$CONFIG_FILE" | head -1 | cut -d= -f2-)
        auth_token=$(get_auth_token || true)
        cmd_name=$(grep '^COMMAND=' "$CONFIG_FILE" | head -1 | cut -d= -f2-)
    fi

    # 读取模型列表
    local model_list
    model_list=$(read_models)
    if [[ -z "$model_list" ]]; then
        echo -e "\033[1;31m未找到模型列表，请重新配置\033[0m"
        do_configure || return 1
        model_list=$(read_models)
    fi

    # 选择模型（优先 fzf，无则降级 bash select）
    local model_choice
    if command -v fzf &>/dev/null; then
        model_choice=$(echo "$model_list" | fzf \
            --prompt="选择模型 > " \
            --height=20 \
            --border=rounded \
            --header="Enter 确认 | ESC 取消")
    else
        echo -e "\033[1;33m  安装fzf，获得更好的使用体验。$ brew install fzf\033[0m"
        local choices=()
        while IFS= read -r m; do
            choices+=("$m")
        done <<< "$model_list"
        echo -e "\033[1;36m  请选择模型：\033[0m"
        PS3="  请输入编号 > "
        select model_choice in "${choices[@]}"; do
            [[ -n "$model_choice" ]] && break
            echo -e "\033[1;31m  无效编号，请重新输入\033[0m"
        done
    fi

    [[ -z "$model_choice" ]] && return 1

    echo -e "\033[1;33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
    echo -e "\033[1;32m  模型:\033[0m   $model_choice"
    echo -e "\033[1;32m  地址:\033[0m   $base_url"
    echo -e "\033[1;32m  推理:\033[0m   max"
    echo -e "\033[1;32m  Agent Teams:\033[0m on"
    echo -e "\033[1;33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
    echo ""

    # 启动 Claude
    exec env \
        ANTHROPIC_BASE_URL="$base_url" \
        ANTHROPIC_AUTH_TOKEN="$auth_token" \
        CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
        CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1 \
        CLAUDE_CODE_ATTRIBUTION_HEADER=0 \
        CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \
        CLAUDE_CODE_ENABLE_AUTO_MODE=1 \
        CLAUDE_CODE_SUBAGENT_MODEL="$model_choice" \
        ANTHROPIC_MODEL="$model_choice" \
        ANTHROPIC_SMALL_FAST_MODEL="$model_choice" \
        ANTHROPIC_DEFAULT_SONNET_MODEL="$model_choice" \
        ANTHROPIC_DEFAULT_OPUS_MODEL="$model_choice" \
        ANTHROPIC_DEFAULT_HAIKU_MODEL="$model_choice" \
        claude --permission-mode auto --effort max --model "$model_choice" "$@"
}

# ──────────────────────────────────────────
# 查看配置
# ──────────────────────────────────────────
do_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        echo -e "\033[1;36m=== 当前配置 ===\033[0m"
        while IFS= read -r line; do
            if [[ "$line" =~ ^AUTH_TOKEN= ]]; then
                local raw="${line#AUTH_TOKEN=}"
                if is_encrypted "$raw"; then
                    # 解密后脱敏显示
                    local decrypted
                    decrypted=$(decrypt_token "$raw" 2>/dev/null) || decrypted="解密失败"
                    if [[ ${#decrypted} -ge 10 ]]; then
                        echo "AUTH_TOKEN=${decrypted:0:5}****${decrypted: -5} (AES-256 加密存储)"
                    else
                        echo "AUTH_TOKEN=**** (AES-256 加密存储)"
                    fi
                else
                    # 兼容旧版明文
                    echo "AUTH_TOKEN=**** (明文存储，建议重新配置)"
                fi
            else
                echo "$line"
            fi
        done < "$CONFIG_FILE"
    else
        echo "未配置，请运行 cc-claude 进行初始化"
    fi
}

# ──────────────────────────────────────────
# 增加模型
# ──────────────────────────────────────────
do_add_model() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo -e "\033[1;31m未找到配置，请先运行 cc-claude 进行初始化\033[0m"
        return 1
    fi

    local new_model="${1:-}"
    if [[ -z "$new_model" ]]; then
        echo -e "\033[1;31m用法: cc-claude add-model <模型名>\033[0m"
        return 1
    fi

    local current_models=""
    current_models=$(read_models)
    if [[ -z "$current_models" ]]; then
        echo -e "\033[1;31m当前配置中没有模型\033[0m"
        return 1
    fi

    # 检查是否已存在
    if echo "$current_models" | grep -qxF "$new_model"; then
        echo -e "\033[1;33m模型 $new_model 已存在，跳过\033[0m"
        return 0
    fi

    local base_url auth_token cmd_name
    base_url=$(grep '^BASE_URL=' "$CONFIG_FILE" | head -1 | cut -d= -f2-)
    auth_token=$(get_auth_token || true)
    cmd_name=$(grep '^COMMAND=' "$CONFIG_FILE" | head -1 | cut -d= -f2-)

    # 追加新模型
    local all_models
    all_models=$(echo "$current_models"; echo "$new_model")

    local encrypted
    encrypted=$(encrypt_token "$auth_token")

    cat > "$CONFIG_FILE" <<EOF
# CC Claude 配置文件
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')
BASE_URL=$base_url
AUTH_TOKEN=$encrypted
COMMAND=$cmd_name
MODELS=<<MODELS
$all_models
MODELS
EOF
    chmod 600 "$CONFIG_FILE"

    echo -e "\033[1;32m  ✓ 已添加模型: $new_model\033[0m"
}

# ──────────────────────────────────────────
# 修改 API Key
# ──────────────────────────────────────────
do_change_token() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo -e "\033[1;31m未找到配置，请先运行 cc-claude 进行初始化\033[0m"
        return 1
    fi

    local new_token="${1:-}"
    if [[ -z "$new_token" ]]; then
        echo -e "\033[1;31m用法: cc-claude change-token <新Key>\033[0m"
        return 1
    fi

    local base_url cmd_name
    base_url=$(grep '^BASE_URL=' "$CONFIG_FILE" | head -1 | cut -d= -f2-)
    cmd_name=$(grep '^COMMAND=' "$CONFIG_FILE" | head -1 | cut -d= -f2-)

    local current_models
    current_models=$(read_models)
    if [[ -z "$current_models" ]]; then
        echo -e "\033[1;31m当前配置中没有模型\033[0m"
        return 1
    fi

    local encrypted
    encrypted=$(encrypt_token "$new_token")

    cat > "$CONFIG_FILE" <<EOF
# CC Claude 配置文件
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')
BASE_URL=$base_url
AUTH_TOKEN=$encrypted
COMMAND=$cmd_name
MODELS=<<MODELS
$current_models
MODELS
EOF
    chmod 600 "$CONFIG_FILE"

    echo -e "\033[1;32m  ✓ API Key 已更新（AES-256 加密存储）\033[0m"
}

# ──────────────────────────────────────────
# 入口
# ──────────────────────────────────────────
case "${1:-}" in
    reset)          do_configure ;;
    config)         do_config ;;
    configure)      shift; do_configure "$@" ;;
    add-model)      do_add_model "${2:-}" ;;
    change-token)   do_change_token "${2:-}" ;;
    *)              do_select_and_run "$@" ;;
esac
