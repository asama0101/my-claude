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

# ── (C) Bash: 対象パスが全てプロジェクト外なら保護ブランチチェックをスキップ ──
run_bash 'rm /tmp/mbg_test_target'; assert_exit 0 "$?" "(C) rm /tmp配下は保護ブランチでも許可"
run_bash 'rm somefile'; assert_exit 2 "$?" "(C) rm 相対パス(プロジェクト内)は引き続きブロック"
run_bash 'mv /tmp/mbg_a /tmp/mbg_b'; assert_exit 0 "$?" "(C) mv /tmp配下同士は許可"
run_bash 'git commit -m x'; assert_exit 2 "$?" "(C) git commit は例外化されず引き続きブロック"
run_bash 'sed -i s/a/b/ somefile.txt'; assert_exit 2 "$?" "(C) sed -i 相対パスは引き続きブロック（実運用上の例外は近似的に無効）"

# ── レビュー指摘の修正確認（セキュリティレビューで実測された穴）──
run_bash "cp /tmp/mbg_src $HOME/.claude/hooks/main-branch-guard.sh"; assert_exit 2 "$?" "CRITICAL修正: \$CLAUDE_HOME配下(フック自身)への書き込みはexemptされずブロック"
run_bash "touch $HOME/.claude/scratch_test_file"; assert_exit 2 "$?" "CRITICAL修正: \$CLAUDE_HOME配下への単純touchもexemptされずブロック"
run_bash 'cp /tmp/mbg_outside cp'; assert_exit 2 "$?" "HIGH修正: コマンド名と同名の引数(2個目)もプロジェクト内対象として検査されブロック"
run_bash $'rm /tmp/mbg_outside\nrm somefile'; assert_exit 2 "$?" "MEDIUM修正: 改行密輸(1行目outside/2行目project内)はブロック"

# ── (B) fast-forward 可能なら git pull ヒントを出す ──
BARE="$SCRATCH/bare.git"
git init -q --bare "$BARE"

WORK="$SCRATCH/work"
mkdir -p "$WORK"
git -C "$WORK" init -q
git -C "$WORK" config user.email t@t.com
git -C "$WORK" config user.name t
git -C "$WORK" commit -q --allow-empty -m init
git -C "$WORK" branch -M main
git -C "$WORK" remote add origin "$BARE"
git -C "$WORK" push -q -u origin main
git -C "$BARE" symbolic-ref HEAD refs/heads/main

run_bash_in() {  # $1=dir $2=command → stderr を返す
  local input
  input=$(jq -n --arg cmd "$2" '{tool_name:"Bash", tool_input:{command:$cmd}}')
  printf '%s' "$input" | (cd "$1" && bash "$HOOK") 2>&1 1>/dev/null
}

OUT=$(run_bash_in "$WORK" 'rm foo.txt')
if printf '%s' "$OUT" | grep -q "ヒント"; then
  echo "FAIL: (B) upstreamと一致時はヒントなし"; FAIL=1
else
  echo "PASS: (B) upstreamと一致時はヒントなし"
fi

CLONE2="$SCRATCH/clone2"
git clone -q "$BARE" "$CLONE2"
git -C "$CLONE2" config user.email t@t.com
git -C "$CLONE2" config user.name t
git -C "$CLONE2" commit -q --allow-empty -m second
git -C "$CLONE2" push -q origin main
git -C "$WORK" fetch -q origin

OUT=$(run_bash_in "$WORK" 'rm foo.txt')
if printf '%s' "$OUT" | grep -q "ヒント"; then
  echo "PASS: (B) fast-forward可能時はヒントあり"
else
  echo "FAIL: (B) fast-forward可能時はヒントあり"; FAIL=1
fi

git -C "$WORK" commit -q --allow-empty -m "local diverge"
OUT=$(run_bash_in "$WORK" 'rm foo.txt')
if printf '%s' "$OUT" | grep -q "ヒント"; then
  echo "FAIL: (B) diverge時はヒントなし"; FAIL=1
else
  echo "PASS: (B) diverge時はヒントなし"
fi

rm -rf "$SCRATCH"
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
