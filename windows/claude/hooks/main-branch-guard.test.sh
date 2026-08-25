#!/bin/bash
set -uo pipefail
HOOK="$HOME/.claude/hooks/main-branch-guard.sh"
SCRATCH=$(mktemp -d)
REPO="$SCRATCH/repo"
mkdir -p "$REPO"
git -C "$REPO" init -q
git -C "$REPO" config user.email t@t.com
git -C "$REPO" config user.name t
git -C "$REPO" commit -q --allow-empty -m init
git -C "$REPO" branch -M main

run_bash() {  # $1=command
  local input
  input=$(jq -n --arg cmd "$1" '{tool_name:"Bash", tool_input:{command:$cmd}}')
  printf '%s' "$input" | (cd "$REPO" && bash "$HOOK")
}

FAIL=0
assert_exit() {  # $1=expected $2=actual $3=label
  if [ "$1" != "$2" ]; then
    echo "FAIL: $3 (expected exit $1, got $2)"
    FAIL=1
  else
    echo "PASS: $3"
  fi
}

# 1. 読取専用findで 2>/dev/null を使う → 誤検知させない → exit 0
run_bash 'find /home/asama/.claude/skills -iname "*foo*" 2>/dev/null'; assert_exit 0 "$?" "find + 2>/dev/null は誤検知しない"

# 2. cat ... 2>/dev/null | head も同様 → exit 0
run_bash 'cat missing.txt 2>/dev/null | head -1'; assert_exit 0 "$?" "cat + 2>/dev/null も誤検知しない"

# 3. 標準出力の /dev/null 破棄（fd指定なし）も誤検知しない → exit 0
run_bash 'some-command > /dev/null'; assert_exit 0 "$?" "> /dev/null も誤検知しない"

# 4. 実ファイルへのリダイレクトは引き続きブロックする（回帰防止） → exit 2
run_bash 'echo hi > out.txt'; assert_exit 2 "$?" "実ファイルへのリダイレクトは引き続きブロック"

# 5. /dev/null に似た別ファイル名は引き続きブロックする（回帰防止） → exit 2
run_bash 'echo hi > /dev/nullish_file'; assert_exit 2 "$?" "/dev/null に似た別名は引き続きブロック"

# 6. rm はリダイレクト無関係に引き続きブロックする → exit 2
run_bash 'rm out.txt'; assert_exit 2 "$?" "rmは引き続きブロック"

# 7. 2>&1 は既存仕様どおり誤検知しない（回帰防止） → exit 0
run_bash 'cat missing.txt 2>&1'; assert_exit 0 "$?" "2>&1 は既存仕様どおり誤検知しない"

rm -rf "$SCRATCH"
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
