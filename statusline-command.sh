#!/usr/bin/env bash
set -euo pipefail

input=$(cat)
now=$(date +%s)

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

# $1=ラベル $2=使用率 $3=リセット時刻(Unix秒) $4="hm"(時分) or "dh"(日時)
make_rate_part() {
  local label="${1}" used="${2}" resets_at="${3}" unit="${4}"
  [[ -z "$used" || -z "$resets_at" ]] && return 0
  local used_int remaining_sec
  used_int=$(printf '%.0f' "$used")
  remaining_sec=$(( resets_at - now ))
  (( remaining_sec < 0 )) && remaining_sec=0
  if [[ "$unit" == "hm" ]]; then
    printf '%s %b 残%dh%dm' "$label" "$(make_bar "$used_int")" \
      $(( remaining_sec / 3600 )) $(( (remaining_sec % 3600) / 60 ))
  else
    printf '%s %b 残%dd%dh' "$label" "$(make_bar "$used_int")" \
      $(( remaining_sec / 86400 )) $(( (remaining_sec % 86400) / 3600 ))
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
  (.context_window.used_percentage     // 0 | tostring),
  (.rate_limits.five_hour.used_percentage  // ""),
  (.rate_limits.five_hour.resets_at    // "" | tostring),
  (.rate_limits.seven_day.used_percentage  // ""),
  (.rate_limits.seven_day.resets_at    // "" | tostring)
' <<< "$input")

current_dir="${_f[0]:-}"
model_name="${_f[1]:-}"
effort_level="${_f[2]:-}"
total_in="${_f[3]:-0}"
total_out="${_f[4]:-0}"
used_pct="${_f[5]:-0}"
five_used="${_f[6]:-}"
five_resets="${_f[7]:-}"
seven_used="${_f[8]:-}"
seven_resets="${_f[9]:-}"

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

# 6. 5時間制限
five_part=$(make_rate_part "5h-limit" "$five_used" "$five_resets" "hm")

# 7. 7日間制限
seven_part=$(make_rate_part "7d-limit" "$seven_used" "$seven_resets" "dh")

# 組み立て
parts=("$dir_part" "$model_part")
[[ -n "$effort_part" ]] && parts+=("$effort_part")
[[ -n "$tokens_part" ]] && parts+=("$tokens_part")
parts+=("$ctx_part")
[[ -n "$five_part" ]]   && parts+=("$five_part")
[[ -n "$seven_part" ]]  && parts+=("$seven_part")

output=$(printf '%b' "${parts[0]}")
for part in "${parts[@]:1}"; do
  output+=$(printf '%b%b' "$SEP" "$part")
done
printf '%b\n' "$output"
