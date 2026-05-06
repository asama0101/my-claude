#!/usr/bin/env bash
set -euo pipefail

input=$(cat)

make_bar() {
  local pct="${1}"
  local filled=$(( pct * 10 / 100 ))
  (( filled > 10 )) && filled=10

  local color
  if   (( pct < 60 )); then color='\033[32m'
  elif (( pct < 80 )); then color='\033[33m'
  else                      color='\033[31m'
  fi

  local bar='' i
  for (( i=0; i<10; i++ )); do
    if (( i < filled )); then bar+='█'; else bar+='░'; fi
  done

  printf "%b[%s]\033[0m %d%%" "$color" "$bar" "$pct"
}

fmt_tokens() {
  local n="${1}"
  if (( n >= 1000 )); then
    printf '%d.%dk' $(( n / 1000 )) $(( (n % 1000) / 100 ))
  else
    printf '%d' "$n"
  fi
}

SEP='\033[90m | \033[0m'

# jq で全フィールドを一括取得
mapfile -t _f < <(jq -r '
  (.workspace.current_dir // .cwd // ""),
  (.model.display_name // ""),
  (.effort.level // ""),
  (.context_window.total_input_tokens  // 0 | tostring),
  (.context_window.total_output_tokens // 0 | tostring),
  (.context_window.used_percentage     // 0 | tostring)
' <<< "$input")

current_dir="${_f[0]:-}"
model_name="${_f[1]:-}"
effort_level="${_f[2]:-}"
total_in="${_f[3]:-0}"
total_out="${_f[4]:-0}"
used_pct="${_f[5]:-0}"

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

# 4. トークン消費量（セッション累計）
tokens_part=""
if (( total_in > 0 || total_out > 0 )); then
  tokens_part=$(printf 'tokens: in %s / out %s' "$(fmt_tokens "$total_in")" "$(fmt_tokens "$total_out")")
fi

# 5. コンテキストバー
used_pct_int=$(printf '%.0f' "$used_pct")
ctx_part=$(printf 'context %b' "$(make_bar "$used_pct_int")")

# 組み立て
parts=("$dir_part" "$model_part")
[[ -n "$effort_part" ]] && parts+=("$effort_part")
[[ -n "$tokens_part" ]] && parts+=("$tokens_part")
parts+=("$ctx_part")

output=$(printf '%b' "${parts[0]}")
for part in "${parts[@]:1}"; do
  output+=$(printf '%b%b' "$SEP" "$part")
done
printf '%b\n' "$output"
