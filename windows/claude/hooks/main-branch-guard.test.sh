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

LAST_STDERR=""
run_bash() {  # $1=command $2=repo（実行対象リポジトリの絶対パス）
  local input repo="$2"
  input=$(jq -n --arg cmd "$1" '{tool_name:"Bash", tool_input:{command:$cmd}}')
  LAST_STDERR=$(printf '%s' "$input" | (cd "$repo" && bash "$HOOK") 2>&1 >/dev/null)
  return $?
}

run_write() {  # $1=file_path（repo配下の絶対パス） $2=repo（実行対象リポジトリの絶対パス）
  local input repo="$2"
  input=$(jq -n --arg fp "$1" '{tool_name:"Write", tool_input:{file_path:$fp}}')
  LAST_STDERR=$(printf '%s' "$input" | (cd "$repo" && bash "$HOOK") 2>&1 >/dev/null)
  return $?
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

assert_warn() {  # $1=expected(1=警告あり/0=警告なし) $2=stderr内容 $3=label
  local expected="$1" content="$2" label="$3" found=0
  printf '%s' "$content" | grep -q '遅れています' && found=1
  if [ "$expected" = "$found" ]; then
    echo "PASS: $label"
  else
    echo "FAIL: $label (expected warn=$expected, got warn=$found)"
    FAIL=1
  fi
}

# ${branch}/${remote_ref}が実値で正しく埋め込まれているかを警告メッセージ全文の完全一致で検証する。
# assert_warn（部分一致）だけでは、branch/remote_refをハードコード値に固定するミューテーションを
# 検出できないため、TS1/TS5でこちらも併用する（特にTS5はmaster/origin/masterでの一致確認により
# main側への固定化を確実に検出できる）。
assert_warn_msg() {  # $1=branch $2=remote_ref $3=stderr内容 $4=label
  local branch="$1" remote_ref="$2" content="$3" label="$4"
  local expected_line="⚠️  ローカルの${branch}が${remote_ref}より遅れています。先に 'git pull' を実行してから上記のブランチ作成をしてください。"
  if printf '%s' "$content" | grep -qF -- "$expected_line"; then
    echo "PASS: $label"
  else
    echo "FAIL: $label (expected exact message not found: $expected_line)"
    FAIL=1
  fi
}

new_repo() {  # $1=ディレクトリ名（$SCRATCH配下）。作成したリポジトリの絶対パスをechoする
  local dir="$SCRATCH/$1"
  mkdir -p "$dir"
  git -C "$dir" init -q
  git -C "$dir" config user.email t@t.com
  git -C "$dir" config user.name t
  git -C "$dir" commit -q --allow-empty -m init
  git -C "$dir" branch -M main
  printf '%s' "$dir"
}

# 1. 読取専用findで 2>/dev/null を使う → 誤検知させない → exit 0
run_bash 'find $HOME/.claude/skills -iname "*foo*" 2>/dev/null' "$REPO"; assert_exit 0 "$?" "find + 2>/dev/null は誤検知しない"

# 2. cat ... 2>/dev/null | head も同様 → exit 0
run_bash 'cat missing.txt 2>/dev/null | head -1' "$REPO"; assert_exit 0 "$?" "cat + 2>/dev/null も誤検知しない"

# 3. 標準出力の /dev/null 破棄（fd指定なし）も誤検知しない → exit 0
run_bash 'some-command > /dev/null' "$REPO"; assert_exit 0 "$?" "> /dev/null も誤検知しない"

# 4. 実ファイルへのリダイレクトは引き続きブロックする（回帰防止） → exit 2
run_bash 'echo hi > out.txt' "$REPO"; assert_exit 2 "$?" "実ファイルへのリダイレクトは引き続きブロック"

# 5. /dev/null に似た別ファイル名は引き続きブロックする（回帰防止） → exit 2
run_bash 'echo hi > /dev/nullish_file' "$REPO"; assert_exit 2 "$?" "/dev/null に似た別名は引き続きブロック"

# 6. rm はリダイレクト無関係に引き続きブロックする → exit 2
run_bash 'rm out.txt' "$REPO"; assert_exit 2 "$?" "rmは引き続きブロック"

# 7. 2>&1 は既存仕様どおり誤検知しない（回帰防止） → exit 0
run_bash 'cat missing.txt 2>&1' "$REPO"; assert_exit 0 "$?" "2>&1 は既存仕様どおり誤検知しない"

# ── (C) Bash: 対象パスが全てプロジェクト外なら保護ブランチチェックをスキップ ──
run_bash 'rm /tmp/mbg_test_target' "$REPO"; assert_exit 0 "$?" "(C) rm /tmp配下は保護ブランチでも許可"
run_bash 'rm somefile' "$REPO"; assert_exit 2 "$?" "(C) rm 相対パス(プロジェクト内)は引き続きブロック"
run_bash 'mv /tmp/mbg_a /tmp/mbg_b' "$REPO"; assert_exit 0 "$?" "(C) mv /tmp配下同士は許可"
run_bash 'git commit -m x' "$REPO"; assert_exit 2 "$?" "(C) git commit は例外化されず引き続きブロック"
run_bash 'sed -i s/a/b/ somefile.txt' "$REPO"; assert_exit 2 "$?" "(C) sed -i 相対パスは引き続きブロック（実運用上の例外は近似的に無効）"

# ── レビュー指摘の修正確認（セキュリティレビューで実測された穴）──
run_bash "cp /tmp/mbg_src $HOME/.claude/hooks/main-branch-guard.sh" "$REPO"; assert_exit 2 "$?" "CRITICAL修正: \$CLAUDE_HOME配下(フック自身)への書き込みはexemptされずブロック"
run_bash "touch $HOME/.claude/scratch_test_file" "$REPO"; assert_exit 2 "$?" "CRITICAL修正: \$CLAUDE_HOME配下への単純touchもexemptされずブロック"
run_bash 'cp /tmp/mbg_outside cp' "$REPO"; assert_exit 2 "$?" "HIGH修正: コマンド名と同名の引数(2個目)もプロジェクト内対象として検査されブロック"
run_bash $'rm /tmp/mbg_outside\nrm somefile' "$REPO"; assert_exit 2 "$?" "MEDIUM修正: 改行密輸(1行目outside/2行目project内)はブロック"

# ── 2周目の正確性レビュー指摘の修正確認 ──
# HIGH: find -delete/rsync --deleteはbash-guard.sh側でプロジェクト配下ならゾーン許可
# されるため、main-branch-guard.sh側のMUTATING_PATTERNSにも含めないと保護ブランチ上で
# プロジェクト内ファイルを破壊できてしまう。
run_bash 'find somedir -delete' "$REPO"; assert_exit 2 "$?" "HIGH修正: find -delete はMUTATING_PATTERNSに含まれ引き続きブロック"
run_bash 'rsync -a --delete src/ dst/' "$REPO"; assert_exit 2 "$?" "HIGH修正: rsync --delete はMUTATING_PATTERNSに含まれ引き続きブロック"
run_bash 'rsync -a --del src/ dst/' "$REPO"; assert_exit 2 "$?" "HIGH修正: rsync --del(エイリアス)もMUTATING_PATTERNSに含まれ引き続きブロック"
# MEDIUM: 安全文字集合からグロブ文字(*/?)を除去。set -fでフック内はグロブ展開されないが
# 実行シェルでは展開されるため、静的判定と実行時対象が乖離しグロブでプロジェクト内を
# 「プロジェクト外」と誤判定させ除外機構を悪用できた。
run_bash 'mv som*file /tmp/mbg_stolen' "$REPO"; assert_exit 2 "$?" "MEDIUM修正: mv対象のグロブは解析不能としてブロック(除外機構の悪用防止)"

# TS1. Write分岐: main が origin/main より1コミット遅れている（祖先） → exit 2 かつ警告あり
R1=$(new_repo repo_ts1)
git -C "$R1" checkout -q -b tmp1
git -C "$R1" commit -q --allow-empty -m ahead1
AHEAD1=$(git -C "$R1" rev-parse tmp1)
git -C "$R1" checkout -q main
git -C "$R1" branch -q -D tmp1
git -C "$R1" update-ref refs/remotes/origin/main "$AHEAD1"
run_write "$R1/f1.txt" "$R1"; assert_exit 2 "$?" "TS1: Write, mainがorigin/mainより遅れ -> exit2"
assert_warn 1 "$LAST_STDERR" "TS1: 警告あり"
assert_warn_msg "main" "origin/main" "$LAST_STDERR" "TS1: 警告文言が正確(main/origin/main)"

# TS2. Bash分岐: 同条件 → exit 2 かつ警告あり
R2=$(new_repo repo_ts2)
git -C "$R2" checkout -q -b tmp2
git -C "$R2" commit -q --allow-empty -m ahead2
AHEAD2=$(git -C "$R2" rev-parse tmp2)
git -C "$R2" checkout -q main
git -C "$R2" branch -q -D tmp2
git -C "$R2" update-ref refs/remotes/origin/main "$AHEAD2"
run_bash 'echo hi > out.txt' "$R2"; assert_exit 2 "$?" "TS2: Bash, mainがorigin/mainより遅れ -> exit2"
assert_warn 1 "$LAST_STDERR" "TS2: 警告あり"

# TS3. local main == origin/main（同一コミット） → exit 2 かつ警告なし
# 注: TS4は欠番。要件3（origin不在ケース）は既存のTC1-7が兼務しているため個別シナリオを追加していない。
R3=$(new_repo repo_ts3)
SHA3=$(git -C "$R3" rev-parse main)
git -C "$R3" update-ref refs/remotes/origin/main "$SHA3"
run_write "$R3/f3.txt" "$R3"; assert_exit 2 "$?" "TS3: local==origin -> exit2"
assert_warn 0 "$LAST_STDERR" "TS3: 警告なし"

# TS5. masterブランチで同様に遅れているケース → exit 2 かつ警告あり（対称性確認）
R5=$(new_repo repo_ts5)
git -C "$R5" branch -M master
git -C "$R5" checkout -q -b tmp5
git -C "$R5" commit -q --allow-empty -m ahead5
AHEAD5=$(git -C "$R5" rev-parse tmp5)
git -C "$R5" checkout -q master
git -C "$R5" branch -q -D tmp5
git -C "$R5" update-ref refs/remotes/origin/master "$AHEAD5"
run_write "$R5/f5.txt" "$R5"; assert_exit 2 "$?" "TS5: master, masterがorigin/masterより遅れ -> exit2"
assert_warn 1 "$LAST_STDERR" "TS5: 警告あり（master）"
assert_warn_msg "master" "origin/master" "$LAST_STDERR" "TS5: 警告文言が正確(master/origin/master)"

# TS6. diverged（相互に祖先でない） → exit 2 かつ警告なし
R6=$(new_repo repo_ts6)
git -C "$R6" checkout -q -b tmp6
git -C "$R6" commit -q --allow-empty -m origin_unique
ORIGIN_SHA6=$(git -C "$R6" rev-parse tmp6)
git -C "$R6" checkout -q main
git -C "$R6" branch -q -D tmp6
git -C "$R6" update-ref refs/remotes/origin/main "$ORIGIN_SHA6"
git -C "$R6" commit -q --allow-empty -m local_unique
run_write "$R6/f6.txt" "$R6"; assert_exit 2 "$?" "TS6: diverged -> exit2"
assert_warn 0 "$LAST_STDERR" "TS6: 警告なし（diverged）"

# TS7. local main が origin/main より進んでいる（未pushコミットあり） → exit 2 かつ警告なし
R7=$(new_repo repo_ts7)
SHA7=$(git -C "$R7" rev-parse main)
git -C "$R7" update-ref refs/remotes/origin/main "$SHA7"
git -C "$R7" commit -q --allow-empty -m local_ahead
run_write "$R7/f7.txt" "$R7"; assert_exit 2 "$?" "TS7: local ahead -> exit2"
assert_warn 0 "$LAST_STDERR" "TS7: 警告なし（local ahead）"

# TS8. レフ名曖昧: mainという名のタグが同時に存在する状態で `git rev-parse --abbrev-ref HEAD` が
# `heads/main` を返してしまい is_protected に一致しない不具合の回帰防止 → exit 2
R8=$(new_repo repo_ts8)
git -C "$R8" tag main
run_bash 'rm out.txt' "$R8"; assert_exit 2 "$?" "TS8: レフ名曖昧(mainタグ併存)でもmain判定される -> exit2"

# TS9. 未出生ブランチ（コミット0件）: `git rev-parse --abbrev-ref HEAD` が失敗し
# fail-openする不具合の回帰防止 → exit 2
# 注: new_repo()は--allow-emptyコミット＋branch -Mを内部実行するため未出生状態を再現できない。
# ここではinit直後の生リポジトリを使う。init.defaultBranchをmainに明示固定し、
# 実行環境のグローバル既定ブランチ名設定（trunk等）に左右されないようにする。
R9="$SCRATCH/repo_ts9"
mkdir -p "$R9"
git -C "$R9" -c init.defaultBranch=main init -q
run_bash 'rm out.txt' "$R9"; assert_exit 2 "$?" "TS9: 未出生ブランチ(コミット0件)でもデフォルトブランチ判定される -> exit2"

# 2周目の正確性レビュー指摘: origin不在時にwarn_if_staleが警告を出さない経路
# （rev-parse --verify失敗による早期return）の直接アサーションが無かったため追加。
run_bash 'rm out.txt' "$REPO"; assert_warn 0 "$LAST_STDERR" "origin未設定時は警告なし（rev-parse --verify失敗での早期return）"

rm -rf "$SCRATCH"
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
