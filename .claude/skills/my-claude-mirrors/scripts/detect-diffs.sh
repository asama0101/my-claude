#!/bin/bash
set -euo pipefail

# detect-diffs.sh — linux/claude/ と windows/claude/ を再帰比較し、
# 台帳(ledger.json)と照合した結果をJSONで標準出力に返す。
#
# 実機(~/.claude/ 等)には一切触れない。このリポジトリ内の2ミラーの比較専用。
#
# 出力: {"new_diffs":[...], "known_diffs":[...],
#         "only_in_linux":[...], "only_in_windows":[...],
#         "known_only_in_linux":[...], "known_only_in_windows":[...]}
# - new_diffs           : 内容が違い、台帳に未記録（またはハッシュが変化した）ファイル
# - known_diffs         : 内容が違うが、台帳に同じハッシュペアで記録済み（許容差分）
# - only_in_*           : 片方のミラーにしか存在しない、台帳に未記録のファイル／空ディレクトリ
# - known_only_in_*     : 片方のミラーにしか存在しないが、台帳に記録済み（許容差分）
#
# 改行コード(CRLF/LF)は比較前に正規化する。Windows側で編集されたファイルが
# CRLF化されただけの内容同一ファイルを「差分あり」として誤検知しないため。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
LINUX_DIR="$REPO_ROOT/linux/claude"
WINDOWS_DIR="$REPO_ROOT/windows/claude"
LEDGER="$SKILL_DIR/ledger.json"

command -v jq >/dev/null 2>&1 || { echo "jq が見つかりません。" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "sha256sum が見つかりません。" >&2; exit 1; }
[ -d "$LINUX_DIR" ] || { echo "$LINUX_DIR が見つかりません。" >&2; exit 1; }
[ -d "$WINDOWS_DIR" ] || { echo "$WINDOWS_DIR が見つかりません。" >&2; exit 1; }
[ -f "$LEDGER" ] || echo "[]" > "$LEDGER"

norm_hash() {
  tr -d '\r' < "$1" | sha256sum | cut -d' ' -f1
}

LINUX_FILES=$(cd "$LINUX_DIR" && find . -type f | sed 's#^\./##' | sort)
WINDOWS_FILES=$(cd "$WINDOWS_DIR" && find . -type f | sed 's#^\./##' | sort)
LINUX_EMPTY_DIRS=$(cd "$LINUX_DIR" && find . -type d -empty | sed 's#^\./##' | sort)
WINDOWS_EMPTY_DIRS=$(cd "$WINDOWS_DIR" && find . -type d -empty | sed 's#^\./##' | sort)

ONLY_LINUX_FILES=$(comm -23 <(printf '%s\n' "$LINUX_FILES") <(printf '%s\n' "$WINDOWS_FILES"))
ONLY_WINDOWS_FILES=$(comm -13 <(printf '%s\n' "$LINUX_FILES") <(printf '%s\n' "$WINDOWS_FILES"))
COMMON_FILES=$(comm -12 <(printf '%s\n' "$LINUX_FILES") <(printf '%s\n' "$WINDOWS_FILES"))

ONLY_LINUX_DIRS=$(comm -23 <(printf '%s\n' "$LINUX_EMPTY_DIRS") <(printf '%s\n' "$WINDOWS_EMPTY_DIRS"))
ONLY_WINDOWS_DIRS=$(comm -13 <(printf '%s\n' "$LINUX_EMPTY_DIRS") <(printf '%s\n' "$WINDOWS_EMPTY_DIRS"))

NEW_DIFFS="[]"
KNOWN_DIFFS="[]"

while IFS= read -r f; do
  [ -z "$f" ] && continue
  lh=$(norm_hash "$LINUX_DIR/$f")
  wh=$(norm_hash "$WINDOWS_DIR/$f")
  [ "$lh" = "$wh" ] && continue

  match=$(jq -c --arg f "$f" --arg lh "$lh" --arg wh "$wh" \
    '[.[] | select(.file == $f and .linux_hash == $lh and .windows_hash == $wh)] | last // empty' "$LEDGER")

  if [ -n "$match" ] && [ "$match" != "null" ]; then
    KNOWN_DIFFS=$(jq -c --argjson entry "$match" '. + [$entry]' <<< "$KNOWN_DIFFS")
  else
    entry=$(jq -nc --arg f "$f" --arg lh "$lh" --arg wh "$wh" '{file:$f, linux_hash:$lh, windows_hash:$wh}')
    NEW_DIFFS=$(jq -c --argjson entry "$entry" '. + [$entry]' <<< "$NEW_DIFFS")
  fi
done <<< "$COMMON_FILES"

# only_in_* も台帳と照合し、記録済み(known)と未記録(new)に分ける。
# ファイルは実ハッシュが台帳の該当side(linux_hash/windows_hash)と一致するかで判定、
# 空ディレクトリはハッシュ概念が無いためファイルパス一致のみで判定する。
NEW_ONLY_LINUX="[]"; KNOWN_ONLY_LINUX="[]"
NEW_ONLY_WINDOWS="[]"; KNOWN_ONLY_WINDOWS="[]"

is_known_only_file() {
  local dir="$1" hash_field="$2" f="$3" h match
  h=$(norm_hash "$dir/$f")
  match=$(jq -c --arg f "$f" --arg h "$h" --arg hf "$hash_field" \
    '[.[] | select(.file == $f and .[$hf] == $h)] | last // empty' "$LEDGER")
  [ -n "$match" ] && [ "$match" != "null" ]
}

is_known_only_dir() {
  local f="$1" match
  match=$(jq -c --arg f "$f" '[.[] | select(.file == $f)] | last // empty' "$LEDGER")
  [ -n "$match" ] && [ "$match" != "null" ]
}

while IFS= read -r f; do
  [ -z "$f" ] && continue
  if is_known_only_file "$LINUX_DIR" "linux_hash" "$f"; then
    KNOWN_ONLY_LINUX=$(jq -c --arg f "$f" '. + [$f]' <<< "$KNOWN_ONLY_LINUX")
  else
    NEW_ONLY_LINUX=$(jq -c --arg f "$f" '. + [$f]' <<< "$NEW_ONLY_LINUX")
  fi
done <<< "$ONLY_LINUX_FILES"

while IFS= read -r f; do
  [ -z "$f" ] && continue
  if is_known_only_dir "$f"; then
    KNOWN_ONLY_LINUX=$(jq -c --arg f "$f" '. + [$f]' <<< "$KNOWN_ONLY_LINUX")
  else
    NEW_ONLY_LINUX=$(jq -c --arg f "$f" '. + [$f]' <<< "$NEW_ONLY_LINUX")
  fi
done <<< "$ONLY_LINUX_DIRS"

while IFS= read -r f; do
  [ -z "$f" ] && continue
  if is_known_only_file "$WINDOWS_DIR" "windows_hash" "$f"; then
    KNOWN_ONLY_WINDOWS=$(jq -c --arg f "$f" '. + [$f]' <<< "$KNOWN_ONLY_WINDOWS")
  else
    NEW_ONLY_WINDOWS=$(jq -c --arg f "$f" '. + [$f]' <<< "$NEW_ONLY_WINDOWS")
  fi
done <<< "$ONLY_WINDOWS_FILES"

while IFS= read -r f; do
  [ -z "$f" ] && continue
  if is_known_only_dir "$f"; then
    KNOWN_ONLY_WINDOWS=$(jq -c --arg f "$f" '. + [$f]' <<< "$KNOWN_ONLY_WINDOWS")
  else
    NEW_ONLY_WINDOWS=$(jq -c --arg f "$f" '. + [$f]' <<< "$NEW_ONLY_WINDOWS")
  fi
done <<< "$ONLY_WINDOWS_DIRS"

jq -n \
  --argjson new_diffs "$NEW_DIFFS" \
  --argjson known_diffs "$KNOWN_DIFFS" \
  --argjson only_in_linux "$NEW_ONLY_LINUX" \
  --argjson only_in_windows "$NEW_ONLY_WINDOWS" \
  --argjson known_only_in_linux "$KNOWN_ONLY_LINUX" \
  --argjson known_only_in_windows "$KNOWN_ONLY_WINDOWS" \
  '{new_diffs:$new_diffs, known_diffs:$known_diffs,
    only_in_linux:$only_in_linux, only_in_windows:$only_in_windows,
    known_only_in_linux:$known_only_in_linux, known_only_in_windows:$known_only_in_windows}'
