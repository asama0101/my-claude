#!/bin/bash
set -uo pipefail
HOOK="$HOME/.claude/hooks/branch-guard.sh"
SCRATCH=$(mktemp -d)
REPO="$SCRATCH/repo"
mkdir -p "$REPO"
git -C "$REPO" init -q
git -C "$REPO" config user.email t@t.com
git -C "$REPO" config user.name t
git -C "$REPO" commit -q --allow-empty -m init
git -C "$REPO" branch -M main

CLAUDE_HOME_TEST="$SCRATCH/claude_home"
mkdir -p "$CLAUDE_HOME_TEST"

# key=value / key.sub=value 形式の引数からJSONを組み立てる(jqの代替)。
json_build() {
  node -e '
    var out = {};
    process.argv.slice(1).forEach(function (kv) {
      var i = kv.indexOf("=");
      var path = kv.slice(0, i), val = kv.slice(i + 1);
      var keys = path.split(".");
      var cur = out;
      for (var j = 0; j < keys.length - 1; j++) {
        cur[keys[j]] = cur[keys[j]] || {};
        cur = cur[keys[j]];
      }
      cur[keys[keys.length - 1]] = val;
    });
    process.stdout.write(JSON.stringify(out));
  ' "$@"
}

LAST_STDERR=""
run_bash() {  # $1=command $2=repo
  local input repo="$2"
  input=$(json_build tool_name=Bash tool_input.command="$1")
  LAST_STDERR=$(printf '%s' "$input" | (cd "$repo" && CLAUDE_CONFIG_DIR="$CLAUDE_HOME_TEST" bash "$HOOK") 2>&1 >/dev/null)
  return $?
}

run_write() {  # $1=file_path $2=repo
  local input repo="$2"
  input=$(json_build tool_name=Write tool_input.file_path="$1")
  LAST_STDERR=$(printf '%s' "$input" | (cd "$repo" && CLAUDE_CONFIG_DIR="$CLAUDE_HOME_TEST" bash "$HOOK") 2>&1 >/dev/null)
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

# ── (6) main/master以外の通常ブランチは無条件許可 ──
R_FEAT=$(new_repo repo_feature)
git -C "$R_FEAT" checkout -q -b feature/x
run_bash 'rm out.txt' "$R_FEAT"; assert_exit 0 "$?" "(6) 非保護ブランチは無条件許可"

# ── (2) 非リポジトリは無条件許可 ──
NONREPO="$SCRATCH/nonrepo"; mkdir -p "$NONREPO"
run_bash 'rm out.txt' "$NONREPO"; assert_exit 0 "$?" "(2) gitリポジトリでないディレクトリは無条件許可"

# ── (3) detached HEAD は無条件許可 ──
R_DETACHED=$(new_repo repo_detached)
SHA=$(git -C "$R_DETACHED" rev-parse HEAD)
git -C "$R_DETACHED" checkout -q "$SHA"
run_bash 'rm out.txt' "$R_DETACHED"; assert_exit 0 "$?" "(3) detached HEADは無条件許可"

# ── (4) main・.git書込み可能 → ブロック ──
run_bash 'rm out.txt' "$REPO"; assert_exit 2 "$?" "(4) main・書込み権限あり → ブロック"
run_write "$REPO/f.txt" "$REPO"; assert_exit 2 "$?" "(4) Write分岐でも同様にブロック"

# ── (5) main・.git書込み不可 → 警告のみ許容(自動検知) ──
# 注: root権限で実行するとchmodによる書込み不可化がバイパスされ本テストは無効化される
# （非root環境での実行を前提とする、既知の制約）。Windows/Git Bashでは.gitディレクトリ
# 自体へのchmod -wは実効性を持たない場合があるが、HEADファイルへのchmod -wは効くため
# can_create_branch()のAND条件全体としては期待通り「不可」判定になる(実機検証済み)。
R_NOPERM=$(new_repo repo_noperm)
GITDIR=$(git -C "$R_NOPERM" rev-parse --absolute-git-dir)
chmod -w "$GITDIR" "$GITDIR/HEAD"
run_bash 'rm out.txt' "$R_NOPERM"; assert_exit 0 "$?" "(5) main・.git書込み不可 → 警告のみ許容"
printf '%s' "$LAST_STDERR" | grep -qF '警告のみで許容' && echo "PASS: (5) 警告メッセージが出力される" || { echo "FAIL: (5) 警告メッセージが出力される"; FAIL=1; }
chmod +w "$GITDIR" "$GITDIR/HEAD"

# ── (5) 監査ログに記録される ──
LOGFILE="$CLAUDE_HOME_TEST/branch-guard-bypass.log"
if [ -f "$LOGFILE" ] && grep -qF "branch=main" "$LOGFILE" && grep -qF "target=rm out.txt" "$LOGFILE"; then
  echo "PASS: (5) 警告許容が監査ログに記録される"
else
  echo "FAIL: (5) 警告許容が監査ログに記録される"
  FAIL=1
fi

# ── (1) gitコマンド自体が無い環境は fail-open ──
BASH_BIN=$(command -v bash)
NOGIT_BIN=$(mktemp -d)
for bin in grep cat node; do p=$(command -v "$bin" 2>/dev/null) && ln -sf "$p" "$NOGIT_BIN/$bin"; done
input=$(json_build tool_name=Bash tool_input.command='rm out.txt')
printf '%s' "$input" | (cd "$REPO" && PATH="$NOGIT_BIN" CLAUDE_CONFIG_DIR="$CLAUDE_HOME_TEST" "$BASH_BIN" "$HOOK") >/dev/null 2>&1
assert_exit 0 "$?" "(1) gitコマンド自体が無い環境はfail-open"
rm -rf "$NOGIT_BIN"

# ── 対象パスが全てプロジェクト外なら保護ブランチチェックをスキップ(既存踏襲) ──
run_bash 'rm /tmp/bg_test_target' "$REPO"; assert_exit 0 "$?" "対象パス全てプロジェクト外なら許可"
run_bash 'rm somefile' "$REPO"; assert_exit 2 "$?" "対象パスがプロジェクト内なら引き続きブロック"

# ── warn_if_stale: origin/<branch>より遅れている場合のみ警告 ──
R_STALE=$(new_repo repo_stale)
git -C "$R_STALE" checkout -q -b tmp
git -C "$R_STALE" commit -q --allow-empty -m ahead
AHEAD=$(git -C "$R_STALE" rev-parse tmp)
git -C "$R_STALE" checkout -q main
git -C "$R_STALE" branch -q -D tmp
git -C "$R_STALE" update-ref refs/remotes/origin/main "$AHEAD"
run_write "$R_STALE/f.txt" "$R_STALE"; assert_exit 2 "$?" "mainがorigin/mainより遅れ -> exit2"
assert_warn 1 "$LAST_STDERR" "警告あり"

R_UPTODATE=$(new_repo repo_uptodate)
SHA_UP=$(git -C "$R_UPTODATE" rev-parse main)
git -C "$R_UPTODATE" update-ref refs/remotes/origin/main "$SHA_UP"
run_write "$R_UPTODATE/f.txt" "$R_UPTODATE"; assert_exit 2 "$?" "local==origin -> exit2、警告なし"
assert_warn 0 "$LAST_STDERR" "警告なし"

# ── レフ名曖昧: mainという名のタグ併存でも正しく判定(回帰防止) ──
R_TAG=$(new_repo repo_tag)
git -C "$R_TAG" tag main
run_bash 'rm out.txt' "$R_TAG"; assert_exit 2 "$?" "mainタグ併存でもmain判定される"

# ── 未出生ブランチ(コミット0件) ──
R_UNBORN="$SCRATCH/repo_unborn"
mkdir -p "$R_UNBORN"
git -C "$R_UNBORN" -c init.defaultBranch=main init -q
run_bash 'rm out.txt' "$R_UNBORN"; assert_exit 2 "$?" "未出生ブランチ(コミット0件)でもmain判定される"

chmod -R u+w "$SCRATCH" 2>/dev/null
rm -rf "$SCRATCH"
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
