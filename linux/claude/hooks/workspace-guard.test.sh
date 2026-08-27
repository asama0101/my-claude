#!/bin/bash
set -uo pipefail

# HOOK: work/内では自身と同じディレクトリのコピーを参照させる(納品版work/workspace-guard.sh
# を実際に検証するため。本番$HOME/.claude/hooks/への反映は別工程)。相対パスのままだと
# run_write/run_bash内部の`cd "$REPO"`後に解決できなくなるため絶対パス化する。
HOOK="$HOME/.claude/hooks/workspace-guard.sh"
SCRATCH=$(mktemp -d)
REPO="$SCRATCH/repo"; mkdir -p "$REPO"
FAKE_CLAUDE_HOME="$SCRATCH/claude_home"; mkdir -p "$FAKE_CLAUDE_HOME/hooks"
SESSION_TMP=$(mktemp -d "/tmp/claude-test-XXXXXX")
trap 'rm -rf "$SCRATCH" "$SESSION_TMP"' EXIT

run_write() {  # $1=file_path
  local input; input=$(jq -n --arg fp "$1" '{tool_name:"Write", tool_input:{file_path:$fp, content:"x"}}')
  printf '%s' "$input" | (cd "$REPO" && CLAUDE_CONFIG_DIR="$FAKE_CLAUDE_HOME" bash "$HOOK")
}
run_bash() {  # $1=command
  local input; input=$(jq -n --arg cmd "$1" '{tool_name:"Bash", tool_input:{command:$cmd}}')
  printf '%s' "$input" | (cd "$REPO" && CLAUDE_CONFIG_DIR="$FAKE_CLAUDE_HOME" bash "$HOOK")
}
run_tool() {  # $1=tool_name $2=json_key(file_path|notebook_path) $3=path_value
  local input; input=$(jq -n --arg tool "$1" --arg key "$2" --arg val "$3" \
    '{tool_name:$tool, tool_input:{($key):$val}}')
  printf '%s' "$input" | (cd "$REPO" && CLAUDE_CONFIG_DIR="$FAKE_CLAUDE_HOME" bash "$HOOK")
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

# ── 既存機能の回帰テスト(Write/Edit/MultiEdit/NotebookEdit/cp/tee/mv/curl/wget) ──
run_write "$REPO/a.txt"; assert_exit 0 "$?" "(regress) Write プロジェクト配下は許可"
run_write "$FAKE_CLAUDE_HOME/hooks/x"; assert_exit 0 "$?" "(regress) Write \$CLAUDE_HOME配下は許可"
run_write "$SESSION_TMP/x"; assert_exit 0 "$?" "(regress) Write セッション用tmp配下は許可"
run_write "/etc/passwd"; assert_exit 2 "$?" "(regress) Write ゾーン外はブロック"
run_tool "Edit" "file_path" "$REPO/e.txt"; assert_exit 0 "$?" "(regress) Edit プロジェクト配下は許可"
run_tool "Edit" "file_path" "/etc/passwd"; assert_exit 2 "$?" "(regress) Edit ゾーン外はブロック"
run_tool "MultiEdit" "file_path" "$REPO/me.txt"; assert_exit 0 "$?" "(regress) MultiEdit プロジェクト配下は許可"
run_tool "MultiEdit" "file_path" "/etc/passwd"; assert_exit 2 "$?" "(regress) MultiEdit ゾーン外はブロック"
run_tool "NotebookEdit" "notebook_path" "$REPO/n.ipynb"; assert_exit 0 "$?" "(regress) NotebookEdit プロジェクト配下は許可"
run_tool "NotebookEdit" "notebook_path" "/etc/n.ipynb"; assert_exit 2 "$?" "(regress) NotebookEdit ゾーン外はブロック"
run_bash "cp $REPO/a $REPO/b"; assert_exit 0 "$?" "(regress) cp プロジェクト配下同士は許可"
run_bash "cp $REPO/a /root/b"; assert_exit 2 "$?" "(regress) cp ゾーン外宛先はブロック"
run_bash "mv $REPO/a $REPO/b2"; assert_exit 0 "$?" "(regress) mv プロジェクト配下同士は許可"
run_bash "mv $REPO/a /root/b2"; assert_exit 2 "$?" "(regress) mv ゾーン外宛先はブロック"
run_bash "tee $REPO/out.txt <<< hi"; assert_exit 0 "$?" "(regress) tee プロジェクト配下は許可"
run_bash "tee /root/out.txt <<< hi"; assert_exit 2 "$?" "(regress) tee ゾーン外宛先はブロック"
run_bash "curl -o /root/out.bin http://example.com/x"; assert_exit 2 "$?" "(regress) curl -o ゾーン外宛先はブロック"
run_bash "wget -O /root/out.bin http://example.com/x"; assert_exit 2 "$?" "(regress) wget -O ゾーン外宛先はブロック"

# ── rm/rmdir/unlink(6軸: ゾーン内/ゾーン外/ゾーンルート/複合コマンド/難読化/位置非依存トリガー) ──
run_bash "rm -rf $REPO/x"; assert_exit 0 "$?" "(rm) ゾーン内は許可"
run_bash "rm -rf /etc"; assert_exit 2 "$?" "(rm) ゾーン外はブロック"
run_bash "rm -rf $REPO"; assert_exit 2 "$?" "(rm) ゾーンルート自体は不可"
run_bash "rm -rf $REPO/a && echo done"; assert_exit 0 "$?" "(rm) 複合コマンド(ゾーン内)は許可"
run_bash "sudo rm -rf /etc"; assert_exit 2 "$?" "(rm) 先頭トークン非一致でも位置非依存トリガーでブロック(最重要回帰)"
run_bash "r'm' -rf /etc"; assert_exit 2 "$?" "(rm) 難読化(クォート分割)はブロック"

# ── git rm(6軸) ──
run_bash "git rm --cached $REPO/target.txt"; assert_exit 0 "$?" "(git rm) ゾーン内は許可"
run_bash "git rm --cached /etc/passwd"; assert_exit 2 "$?" "(git rm) ゾーン外はブロック"
run_bash "git rm --cached $REPO"; assert_exit 2 "$?" "(git rm) ゾーンルート自体は不可"
run_bash "git rm --cached target.txt && git commit -m msg"; assert_exit 0 "$?" "(git rm) 複合コマンド(相対パス)は許可"
run_bash "g'i't' r'm' --cached /etc/passwd"; assert_exit 2 "$?" "(git rm) 難読化(クォート分割)はブロック"
run_bash "env git rm --cached /etc/passwd"; assert_exit 2 "$?" "(git rm) 先頭トークン非一致でも位置非依存トリガーでブロック"

# ── find -delete(6軸) ──
run_bash "find $REPO/sub -delete"; assert_exit 0 "$?" "(find) ゾーン内は許可"
run_bash "find /etc -delete"; assert_exit 2 "$?" "(find) ゾーン外はブロック"
run_bash "find $REPO -delete"; assert_exit 2 "$?" "(find) ゾーンルート自体は不可"
run_bash "find $REPO/sub -delete && echo done"; assert_exit 0 "$?" "(find) 複合コマンド(ゾーン内)は許可"
run_bash "f'i'nd /etc -de'l'ete"; assert_exit 2 "$?" "(find) 難読化はブロック"
run_bash "sudo find $REPO/sub -delete"; assert_exit 2 "$?" "(find) 先頭トークン非一致でも位置非依存トリガーでブロック"

# ── rsync --delete(6軸) ──
run_bash "rsync -a --delete $REPO/src/ $REPO/dst/"; assert_exit 0 "$?" "(rsync) ゾーン内は許可"
run_bash "rsync -a --delete /etc/ $REPO/dst/"; assert_exit 2 "$?" "(rsync) 片方ゾーン外はブロック"
run_bash "rsync -a --delete $REPO/src/ $REPO"; assert_exit 2 "$?" "(rsync) ゾーンルート自体は不可"
run_bash "rsync -a --delete $REPO/src/ $REPO/dst/ && echo ok"; assert_exit 0 "$?" "(rsync) 複合コマンド(ゾーン内)は許可"
run_bash "r'sync' -a --del'ete' /etc/ $REPO/dst/"; assert_exit 2 "$?" "(rsync) 難読化はブロック"
run_bash "sudo rsync -a --delete $REPO/src/ $REPO/dst/"; assert_exit 2 "$?" "(rsync) 先頭トークン非一致でも位置非依存トリガーでブロック"
run_bash "rsync -a --del /etc/ $REPO/dst/"; assert_exit 2 "$?" "(rsync) --delエイリアスもブロック"

# ── chmod 000/-R777(6軸) ──
run_bash "chmod 000 $REPO/f"; assert_exit 0 "$?" "(chmod) ゾーン内は許可"
run_bash "chmod -R 777 /etc"; assert_exit 2 "$?" "(chmod) ゾーン外はブロック"
run_bash "chmod -R 777 $REPO"; assert_exit 2 "$?" "(chmod) ゾーンルート自体は不可"
run_bash "chmod -R 777 /"; assert_exit 2 "$?" "(chmod) ファイルシステムルートはブロック"
run_bash "chmod 000 $REPO/f && echo ok"; assert_exit 0 "$?" "(chmod) 複合コマンド(ゾーン内)は許可"
run_bash "ch'mod' -R 7'7'7 /etc"; assert_exit 2 "$?" "(chmod) 難読化はブロック"
run_bash "sudo chmod 000 $REPO/f"; assert_exit 2 "$?" "(chmod) 先頭トークン非一致でも位置非依存トリガーでブロック"

# ── git clean -fd(6軸) ──
run_bash "git clean -fd $REPO/target"; assert_exit 0 "$?" "(git clean) ゾーン内明示パスは許可"
run_bash "git clean -fd /etc"; assert_exit 2 "$?" "(git clean) ゾーン外はブロック"
run_bash "git clean -fd $REPO"; assert_exit 2 "$?" "(git clean) ゾーンルート自体は不可"
run_bash "git clean -fd"; assert_exit 2 "$?" "(git clean) パス引数なしは不可"
run_bash "git clean -fd $REPO/target && echo ok"; assert_exit 0 "$?" "(git clean) 複合コマンド(ゾーン内)は許可"
run_bash "git clea'n' -f'd' /etc"; assert_exit 2 "$?" "(git clean) 難読化はブロック"
run_bash "env git clean -fd $REPO/target"; assert_exit 2 "$?" "(git clean) 先頭トークン非一致でも位置非依存トリガーでブロック"

# ── 機密ファイル読取(5軸。ゾーンルート自体は不可はトリガーが特定ファイル名パターン
#    依存のため該当なし=報告書に理由記載) ──
run_bash "cat $REPO/.env"; assert_exit 0 "$?" "(secret) ゾーン内.envは許可"
run_bash "cat /etc/credentials"; assert_exit 2 "$?" "(secret) ゾーン外credentialsはブロック"
run_bash "cat ~/.ssh/id_rsa"; assert_exit 2 "$?" "(secret) ~/.ssh/id_rsaはブロック"
run_bash "cat $REPO/.env && echo ok"; assert_exit 0 "$?" "(secret) 複合コマンド(ゾーン内)は許可"
run_bash "c'a't' /etc/credentials"; assert_exit 2 "$?" "(secret) 難読化はブロック"
run_bash "sudo cat $REPO/.env"; assert_exit 2 "$?" "(secret) 先頭トークン非一致でも位置非依存トリガーでブロック"

# ── リダイレクト汎用化 ──
run_bash "echo hi > $REPO/out.txt"; assert_exit 0 "$?" "(redirect) ゾーン内は許可"
run_bash "echo hi > /root/out.txt"; assert_exit 2 "$?" "(redirect) ゾーン外はブロック"
run_bash "echo hi >> ~/.bashrc"; assert_exit 2 "$?" "(redirect) motivating case: ~/.bashrc"
run_bash "echo hi >> ~/.ssh/authorized_keys"; assert_exit 2 "$?" "(redirect) motivating case: ~/.ssh/authorized_keys"
run_bash "echo hi > /var/tmp/x"; assert_exit 2 "$?" "(redirect) 既存挙動維持: /var/tmp"
run_bash "echo hi > /tmp/randomdir/x"; assert_exit 2 "$?" "(redirect) 既存挙動維持: /tmp配下の無関係ディレクトリ"
run_bash "echo hi > $SESSION_TMP/x"; assert_exit 0 "$?" "(redirect) セッション用tmp配下は許可"
run_bash "cmd 2>/dev/null"; assert_exit 0 "$?" "(redirect) /dev/null除外"
run_bash "cmd > /dev/null 2>&1"; assert_exit 0 "$?" "(redirect) fd複製+devnull除外"

# ── リダイレクトのfd番号バイパス(CRITICAL修正確認: [0-9]?→[0-9]*) ──
run_bash ": 1>$REPO/out1.txt"; assert_exit 0 "$?" "(redirect-fd) 1桁fd番号+ゾーン内は許可"
run_bash ": 1>/etc/x"; assert_exit 2 "$?" "(redirect-fd) 1桁fd番号+ゾーン外はブロック"
run_bash ": 10>/etc/x"; assert_exit 2 "$?" "(redirect-fd) 2桁fd番号でもゾーン外はブロック(CRITICAL修正)"
run_bash ": 100>/etc/x"; assert_exit 2 "$?" "(redirect-fd) 3桁fd番号でもゾーン外はブロック(CRITICAL修正)"

# ── /tmpゾーン範囲の是正確認(優先度0: /tmp/claude-*/*→/tmp/*へ拡大、rm等7カテゴリのみ) ──
run_bash "chmod -R 777 $SCRATCH"; assert_exit 0 "$?" "(zone-scope) /tmp配下ならclaude-*以外でも7カテゴリは許可"
run_bash "echo hi > $SCRATCH/x"; assert_exit 2 "$?" "(zone-scope) リダイレクト(is_ext_dest)は従来通りclaude-*限定のまま"

# ── cd/pushd/popd混入検知(_wg_frag_has_cd) ──
run_bash "rm -rf $REPO/x cd"; assert_exit 2 "$?" "(cd検知) 断片にcd等の語が含まれる場合はゾーン内相当でもブロック"

echo "----"
if [ "$FAIL" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "SOME TESTS FAILED"
fi
exit "$FAIL"
