#!/usr/bin/env bash
set -euo pipefail

LINK_ROOT="${SKILL_LINK_ROOT:-}"
SKILLS_SOURCE_DIR="$LINK_ROOT/skills"
RULES_SOURCE_DIR="$LINK_ROOT/rules"

PATH_IDS=(cursor claude-code codex)
PATH_DIRS=("$HOME/.cursor" "$HOME/.claude" "$HOME/.codex")

usage() {
  echo "用法:" >&2
  echo "  skill-link" >&2
  echo "  skill-link --list [--target cursor|claude-code|codex]" >&2
  echo "  skill-link [--target cursor|claude-code|codex] <skill-name|rule-name>..." >&2
  echo "无名称参数时进入 fzf：Tab 多选，←/→ 切换 Path" >&2
  echo "选中项会切换链接状态：已链接则取消链接，未链接则创建链接" >&2
}

require_roots() {
  if [[ -z "$LINK_ROOT" ]]; then
    echo "缺少 SKILL_LINK_ROOT" >&2
    echo "请先运行 skill-linker 的 scripts/install.sh --root <path>" >&2
    exit 1
  fi

  if [[ ! -d "$SKILLS_SOURCE_DIR" || ! -d "$RULES_SOURCE_DIR" ]]; then
    echo "SKILL_LINK_ROOT 必须包含 skills/ 和 rules/: $LINK_ROOT" >&2
    exit 1
  fi
}

display_path() {
  local dir="$1"
  if [[ "$dir" == "$HOME" ]]; then
    echo "~"
  elif [[ "$dir" == "$HOME/"* ]]; then
    echo "~/${dir#"$HOME/"}"
  else
    echo "$dir"
  fi
}

target_for() {
  local type="$1"
  local name="$2"
  local profile_dir="$3"
  local target_dir="rules"
  [[ "$type" == "skill" ]] && target_dir="skills"
  echo "$profile_dir/$target_dir/$name"
}

is_same_link() {
  local source="$1"
  local target="$2"
  [[ -L "$target" && "$(readlink "$target")" == "$source" ]]
}

item_status() {
  local source="$1"
  local target="$2"

  if is_same_link "$source" "$target"; then
    echo "已链接"
  elif [[ -L "$target" ]]; then
    echo "其他链接"
  elif [[ -e "$target" ]]; then
    echo "已存在"
  else
    echo "未安装"
  fi
}

link_item() {
  local type="$1"
  local name="$2"
  local source="$3"
  local profile_dir="$4"
  local target
  target="$(target_for "$type" "$name" "$profile_dir")"

  mkdir -p "$(dirname "$target")"

  if [[ -e "$target" || -L "$target" ]]; then
    if is_same_link "$source" "$target"; then
      rm "$target"
      echo "Unlinked $type: $target"
      return
    fi

    echo "目标已存在: $target" >&2
    exit 1
  fi

  ln -s "$source" "$target"
  echo "Linked $type: $target -> $source"
}

profile_dir_for() {
  local target_id="$1"
  local index

  for ((index = 0; index < ${#PATH_IDS[@]}; index += 1)); do
    if [[ "${PATH_IDS[$index]}" == "$target_id" ]]; then
      echo "${PATH_DIRS[$index]}"
      return
    fi
  done

  echo "未知 target: $target_id" >&2
  usage
  exit 1
}

profile_index_for() {
  local target_id="$1"
  local index

  for ((index = 0; index < ${#PATH_IDS[@]}; index += 1)); do
    if [[ "${PATH_IDS[$index]}" == "$target_id" ]]; then
      echo "$index"
      return
    fi
  done

  echo "未知 target: $target_id" >&2
  usage
  exit 1
}

resolve_named_item() {
  local raw_name="$1"
  local skill_source="$SKILLS_SOURCE_DIR/$raw_name"

  if [[ -d "$skill_source" ]]; then
    echo "skill"$'\t'"$raw_name"$'\t'"$skill_source"
    return
  fi

  local rule_name="$raw_name"
  [[ "$rule_name" == *.mdc ]] || rule_name="$rule_name.mdc"
  local rule_source="$RULES_SOURCE_DIR/$rule_name"

  if [[ -f "$rule_source" ]]; then
    echo "rule"$'\t'"$rule_name"$'\t'"$rule_source"
    return
  fi

  echo "skill/rule 不存在: $raw_name" >&2
  exit 1
}

collect_items() {
  {
    local source

    if [[ -d "$SKILLS_SOURCE_DIR" ]]; then
      for source in "$SKILLS_SOURCE_DIR"/*; do
        [[ -d "$source" ]] || continue
        echo "skill"$'\t'"$(basename "$source")"$'\t'"$source"
      done
    fi

    if [[ -d "$RULES_SOURCE_DIR" ]]; then
      for source in "$RULES_SOURCE_DIR"/*.mdc; do
        [[ -f "$source" ]] || continue
        echo "rule"$'\t'"$(basename "$source")"$'\t'"$source"
      done
    fi
  } | sort
}

list_items() {
  local profile_dir="$1"
  local type name source target status

  while IFS=$'\t' read -r type name source; do
    [[ -n "${type:-}" ]] || continue
    target="$(target_for "$type" "$name" "$profile_dir")"
    status="$(item_status "$source" "$target")"
    printf '%s\t%s\t%s\t%s\n' "$type" "$name" "$status" "$target"
  done < <(collect_items)
}

parse_fzf_output() {
  local result="$1"
  FZF_QUERY="${result%%$'\n'*}"

  local rest=""
  [[ "$result" == *$'\n'* ]] && rest="${result#*$'\n'}"

  local second="${rest%%$'\n'*}"
  if [[ "$second" == "left" || "$second" == "right" ]]; then
    FZF_KEY="$second"
    FZF_LINES=""
    [[ "$rest" == *$'\n'* ]] && FZF_LINES="${rest#*$'\n'}"
  else
    FZF_KEY=""
    FZF_LINES="$rest"
  fi
}

select_items() {
  local path_index="$1"

  command -v fzf >/dev/null 2>&1 || {
    echo "未找到 fzf，请先运行 skill-linker 的 scripts/install.sh" >&2
    exit 1
  }

  local types=()
  local names=()
  local sources=()
  local type name source

  while IFS=$'\t' read -r type name source; do
    [[ -n "${type:-}" ]] || continue
    types+=("$type")
    names+=("$name")
    sources+=("$source")
  done < <(collect_items)

  if [[ "${#types[@]}" -eq 0 ]]; then
    echo "没有可链接的 skill/rule" >&2
    exit 1
  fi

  local query=""

  while true; do
    local profile_id="${PATH_IDS[$path_index]}"
    local profile_dir="${PATH_DIRS[$path_index]}"
    local input=""
    local index target status

    for ((index = 0; index < ${#types[@]}; index += 1)); do
      target="$(target_for "${types[$index]}" "${names[$index]}" "$profile_dir")"
      status="$(item_status "${sources[$index]}" "$target")"
      input+="$index"$'\t'"${types[$index]}"$'\t'"${names[$index]}"$'\t'"$status"$'\t'"$target"$'\n'
    done

    set +e
    local result
    result="$(printf "%s" "$input" | fzf \
      --multi \
      --delimiter=$'\t' \
      --with-nth=2,3,4,5 \
      --header="Path: $(display_path "$profile_dir") | Tab 多选，←/→ 切换 Path，Enter 链接/取消链接，Esc 退出" \
      --prompt="$profile_id> " \
      --expect=left,right \
      --print-query \
      --query="$query")"
    local fzf_status=$?
    set -e

    parse_fzf_output "$result"
    query="$FZF_QUERY"

    if [[ "$FZF_KEY" == "left" || "$FZF_KEY" == "right" ]]; then
      if [[ "$FZF_KEY" == "left" ]]; then
        path_index=$(( (path_index + ${#PATH_IDS[@]} - 1) % ${#PATH_IDS[@]} ))
      else
        path_index=$(( (path_index + 1) % ${#PATH_IDS[@]} ))
      fi
      continue
    fi

    if [[ "$fzf_status" -ne 0 ]]; then
      echo "已取消"
      exit 0
    fi

    if [[ -z "$FZF_LINES" ]]; then
      echo "fzf 未返回选择" >&2
      exit 1
    fi

    local selected_line item_index
    while IFS= read -r selected_line; do
      [[ -n "$selected_line" ]] || continue
      item_index="${selected_line%%$'\t'*}"
      if [[ ! "$item_index" =~ ^[0-9]+$ || -z "${types[$item_index]+x}" ]]; then
        echo "fzf 返回了无效选择" >&2
        exit 1
      fi

      link_item "${types[$item_index]}" "${names[$item_index]}" "${sources[$item_index]}" "$profile_dir"
    done <<< "$FZF_LINES"
    return
  done
}

mode="toggle"
target_id="cursor"
names=()

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --list)
      mode="list"
      shift
      ;;
    --target)
      [[ -n "${2:-}" ]] || {
        echo "缺少 --target 值" >&2
        usage
        exit 1
      }
      target_id="$2"
      shift 2
      ;;
    --target=*)
      target_id="${1#--target=}"
      shift
      ;;
    -*)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
    *)
      names+=("$1")
      shift
      ;;
  esac
done

require_roots

profile_dir="$(profile_dir_for "$target_id")"

if [[ "$mode" == "list" ]]; then
  [[ "${#names[@]}" -eq 0 ]] || {
    echo "--list 不接受名称参数" >&2
    usage
    exit 1
  }
  list_items "$profile_dir"
  exit 0
fi

if [[ "${#names[@]}" -eq 0 ]]; then
  select_items "$(profile_index_for "$target_id")"
  exit 0
fi

for raw_name in "${names[@]}"; do
  IFS=$'\t' read -r type name source < <(resolve_named_item "$raw_name")
  link_item "$type" "$name" "$source" "$profile_dir"
done
