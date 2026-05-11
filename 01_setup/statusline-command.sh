#!/usr/bin/env bash
set -euo pipefail

input=$(cat)

fmt_pct() {
  local pct="${1}"
  local color
  if   (( pct < 60 )); then color='\033[32m'
  elif (( pct < 80 )); then color='\033[33m'
  else                      color='\033[31m'
  fi
  printf "%b%d%%\033[0m" "$color" "$pct"
}

SEP='\033[90m | \033[0m'

# jq で全フィールドを一括取得
mapfile -t _f < <(jq -r '
  (.workspace.current_dir // .cwd // ""),
  (.model.display_name // ""),
  (.effort.level // ""),
  (.context_window.used_percentage // 0 | tostring),
  (.worktree.branch // ""),
  (.cost.total_cost_usd // 0 | tostring),
  (.rate_limits.five_hour.used_percentage // "" | tostring),
  (.workspace.git_worktree // "")
' <<< "$input")

current_dir="${_f[0]:-}"
model_name="${_f[1]:-}"
effort_level="${_f[2]:-}"
used_pct="${_f[3]:-0}"
worktree_branch="${_f[4]:-}"
total_cost="${_f[5]:-0}"
five_hour_pct="${_f[6]:-}"
git_worktree="${_f[7]:-}"

# ブランチ取得: worktree.branch → git コマンド (--no-optional-locks) の順で解決
if [[ -n "$worktree_branch" ]]; then
  git_branch="$worktree_branch"
elif [[ -n "$current_dir" ]]; then
  git_branch=$(git -C "$current_dir" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null || \
               git -C "$current_dir" --no-optional-locks rev-parse --short HEAD 2>/dev/null || echo "")
else
  git_branch=""
fi

# 1. ユーザー@ホスト:ディレクトリ
if [[ "$current_dir" == "$HOME"* ]]; then
  display_dir="~${current_dir#"$HOME"}"
else
  display_dir="$current_dir"
fi
user_host=$(printf '\033[01;32m%s@%s\033[00m' "$USER" "${HOSTNAME%%.*}")
dir_colored=$(printf '\033[01;34m%s\033[00m' "$display_dir")
dir_part=$(printf '%b:%b' "$user_host" "$dir_colored")

# 2. モデル名
model_part=$(printf '🤖  \033[37m%s\033[0m' "$model_name")

# 3. effort
effort_part=""
[[ -n "$effort_level" ]] && effort_part=$(printf '⚡  \033[91m%s\033[0m' "$effort_level")

# 4. Git ブランチ
branch_part=""
[[ -n "$git_branch" ]] && branch_part=$(printf '\033[36m⎇  %s\033[0m' "$git_branch")

# 5. コンテキスト使用率
used_pct_int=$(printf '%.0f' "$used_pct")
ctx_part=$(printf 'ctx %b' "$(fmt_pct "$used_pct_int")")

# 6. セッションコスト
cost_part=""
cost_float=$(printf '%.4f' "$total_cost" 2>/dev/null || echo "0.0000")
if [[ "$cost_float" != "0.0000" ]]; then
  cost_part=$(printf '\033[90m$%.4f\033[0m' "$cost_float")
fi

# 7. 5時間枠レート制限
rate_part=""
if [[ -n "$five_hour_pct" && "$five_hour_pct" != "null" && "$five_hour_pct" != "" ]]; then
  five_hour_int=$(printf '%.0f' "$five_hour_pct" 2>/dev/null || echo "0")
  rate_part=$(printf 'rate %b' "$(fmt_pct "$five_hour_int")")
fi

# 組み立て
parts=("$dir_part" "$model_part")
[[ -n "$effort_part" ]] && parts+=("$effort_part")
[[ -n "$branch_part" ]] && parts+=("$branch_part")
parts+=("$ctx_part")
[[ -n "$rate_part" ]] && parts+=("$rate_part")
[[ -n "$cost_part" ]] && parts+=("$cost_part")

output=$(printf '%b' "${parts[0]}")
for part in "${parts[@]:1}"; do
  output+=$(printf '%b%b' "$SEP" "$part")
done
printf '%b\n' "$output"
