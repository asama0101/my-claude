#!/usr/bin/env bash
set -euo pipefail

input=$(cat)

# ---- colors (standard 16-color ANSI; truecolor/背景色は Claude Code の statusLine では
#      色変換で洗い出されるため使わない。参照: anthropics/claude-code#35806)
#      色は閾値(緑/黄/赤)だけに限定し、識別用テキストは無色/太字・区切りは │ に統一する ----
FG_DIR='\033[01;34m'
FG_BRANCH='\033[36m'
FG_MODEL='\033[01;95m'
FG_OK='\033[32m'
FG_WARN='\033[33m'
FG_BAD='\033[31m'
FG_DIM='\033[37m'
RESET='\033[0m'
DIV='   │   '
ICON_MODEL='⚙'
ICON_GAUGE='◔'

pct_color() {
  local pct="$1"
  if   (( pct < 60 )); then printf '%b' "$FG_OK"
  elif (( pct < 80 )); then printf '%b' "$FG_WARN"
  else                      printf '%b' "$FG_BAD"
  fi
}

# 塗り部分は閾値の色、空き部分は暗いグレーで塗り分ける(8マス)
render_bar_colored() {
  local pct="$1" color="$2" filled empty i out=""
  filled=$(( (pct * 8 + 50) / 100 ))
  (( filled > 8 )) && filled=8
  (( filled < 0 )) && filled=0
  empty=$(( 8 - filled ))
  out+=$(printf '%b' "$color")
  for ((i = 0; i < filled; i++)); do out+="█"; done
  out+=$(printf '%b' "$FG_DIM")
  for ((i = 0; i < empty; i++)); do out+="░"; done
  out+=$(printf '%b' "$RESET")
  printf '%s' "$out"
}

fmt_remaining() {
  local secs="$1" d h m rem
  if (( secs <= 0 )); then printf 'まもなく'; return; fi
  d=$(( secs / 86400 )); rem=$(( secs % 86400 ))
  h=$(( rem / 3600 )); m=$(( (rem % 3600) / 60 ))
  if (( d > 0 )); then printf '%dd%dh' "$d" "$h"
  else printf '%dh%dm' "$h" "$m"
  fi
}

# jq で必要フィールドだけ取得
mapfile -t _f < <(jq -r '
  (.workspace.current_dir // .cwd // ""),
  (.model.display_name // ""),
  (.effort.level // ""),
  (.context_window.used_percentage // 0 | tostring),
  (.worktree.branch // ""),
  (.rate_limits.five_hour.used_percentage // "" | tostring),
  (.rate_limits.five_hour.resets_at // "" | tostring),
  (.rate_limits.seven_day.used_percentage // "" | tostring),
  (.rate_limits.seven_day.resets_at // "" | tostring),
  (.workspace.repo.host // ""),
  (.workspace.repo.owner // ""),
  (.workspace.repo.name // ""),
  (.cost.total_cost_usd // 0 | tostring)
' <<< "$input" | tr -d '\r')
# tr -d '\r': Windows の jq.exe は stdout がテキストモードのため CRLF を出力する。
# mapfile -t が落とすのは \n だけなので、除去しないと used_percentage が "42\r" のような
# 値になり printf '%.0f' が "invalid number" で失敗する（$(...) は MSYS bash が CR ごと
# 落とすためフック側では顕在化せず、mapfile を使うこのスクリプトだけが影響を受ける）。

current_dir="${_f[0]:-}"
model_name="${_f[1]:-}"
effort_level="${_f[2]:-}"
used_pct="${_f[3]:-0}"
worktree_branch="${_f[4]:-}"
five_hour_pct="${_f[5]:-}"
five_hour_reset="${_f[6]:-}"
seven_day_pct="${_f[7]:-}"
seven_day_reset="${_f[8]:-}"
repo_host="${_f[9]:-}"
repo_owner="${_f[10]:-}"
repo_name="${_f[11]:-}"
total_cost="${_f[12]:-0}"

# ブランチ取得: worktree.branch → git コマンド (--no-optional-locks) の順で解決
if [[ -n "$worktree_branch" ]]; then
  git_branch="$worktree_branch"
elif [[ -n "$current_dir" ]]; then
  git_branch=$(git -C "$current_dir" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null || \
               git -C "$current_dir" --no-optional-locks rev-parse --short HEAD 2>/dev/null || echo "")
else
  git_branch=""
fi

now=$(date +%s)

if [[ "$current_dir" == "$HOME"* ]]; then
  display_dir="~${current_dir#"$HOME"}"
else
  display_dir="$current_dir"
fi

# ブランチ表示: repo host/owner/name が揃っていれば OSC8 でGitHubへのハイパーリンク化
branch_display="$git_branch"
if [[ -n "$git_branch" && -n "$repo_host" && -n "$repo_owner" && -n "$repo_name" ]]; then
  repo_url="https://${repo_host}/${repo_owner}/${repo_name}"
  branch_display=$(printf '\033]8;;%s\033\\%s\033]8;;\033\\' "$repo_url" "$git_branch")
fi

# 現在地・ブランチ
line=$(printf '%b%s%b' "$FG_DIR" "$display_dir" "$RESET")
[[ -n "$git_branch" ]] && line+=$(printf '  %b⎇ %s%b' "$FG_BRANCH" "$branch_display" "$RESET")

# モデル・effort
if [[ -n "$model_name" ]]; then
  model_part="$model_name"
  [[ -n "$effort_level" ]] && model_part+="/${effort_level}"
  line+=$(printf '%s%b%s %s%b' "$DIV" "$FG_MODEL" "$ICON_MODEL" "$model_part" "$RESET")
fi

# コンテキスト使用率(バー)
used_pct_int=$(printf '%.0f' "$used_pct")
ctx_color=$(pct_color "$used_pct_int")
ctx_bar=$(render_bar_colored "$used_pct_int" "$ctx_color")
line+=$(printf '%s%s ctx %s %b%d%%%b' "$DIV" "$ICON_GAUGE" "$ctx_bar" "$ctx_color" "$used_pct_int" "$RESET")

# レート制限 (5時間 / 週次、リセットまでの残り時間つき)
if [[ -n "$five_hour_pct" && "$five_hour_pct" != "null" ]]; then
  five_hour_int=$(printf '%.0f' "$five_hour_pct" 2>/dev/null || echo 0)
  five_color=$(pct_color "$five_hour_int")
  line+=$(printf '%s%s 5h %b%d%%%b' "$DIV" "$ICON_GAUGE" "$five_color" "$five_hour_int" "$RESET")
  if [[ -n "$five_hour_reset" && "$five_hour_reset" != "null" ]]; then
    remain_secs=$(( ${five_hour_reset%.*} - now ))
    line+=$(printf ' %b(%s後)%b' "$FG_DIM" "$(fmt_remaining "$remain_secs")" "$RESET")
  fi
fi

if [[ -n "$seven_day_pct" && "$seven_day_pct" != "null" ]]; then
  seven_day_int=$(printf '%.0f' "$seven_day_pct" 2>/dev/null || echo 0)
  seven_color=$(pct_color "$seven_day_int")
  line+=$(printf '%s%s 7d %b%d%%%b' "$DIV" "$ICON_GAUGE" "$seven_color" "$seven_day_int" "$RESET")
  if [[ -n "$seven_day_reset" && "$seven_day_reset" != "null" ]]; then
    remain_secs=$(( ${seven_day_reset%.*} - now ))
    line+=$(printf ' %b(%s後)%b' "$FG_DIM" "$(fmt_remaining "$remain_secs")" "$RESET")
  fi
fi

# コスト
cost_float=$(printf '%.2f' "$total_cost" 2>/dev/null || echo "0.00")
if [[ "$cost_float" != "0.00" ]]; then
  line+=$(printf '%s%b$%s%b' "$DIV" "$FG_DIM" "$cost_float" "$RESET")
fi

# %b ではなく %s で出力する。$line は組み立て時の printf '%b' で既に実 ESC 文字へ展開済みで、
# ここで再度 %b にかけるとパス中のバックスラッシュまでエスケープ解釈される
# （Windows の C:\Users\... が "missing unicode digit for \U" で壊れる）。
printf '%s\n' "$line"
