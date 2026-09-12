#!/bin/bash
set -uo pipefail

HOOK="$HOME/.claude/hooks/workspace-guard.sh"
SCRATCH=$(mktemp -d)
REPO="$SCRATCH/repo"; mkdir -p "$REPO"
FAKE_CLAUDE_HOME="$SCRATCH/claude_home"; mkdir -p "$FAKE_CLAUDE_HOME/hooks"
SESSION_TMP=$(mktemp -d "/tmp/claude-test-XXXXXX")
trap 'rm -rf "$SCRATCH" "$SESSION_TMP"' EXIT

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

run_write() {  # $1=file_path
  local input; input=$(json_build tool_name=Write tool_input.file_path="$1" tool_input.content=x)
  printf '%s' "$input" | (cd "$REPO" && CLAUDE_CONFIG_DIR="$FAKE_CLAUDE_HOME" bash "$HOOK")
}
run_bash() {  # $1=command
  local input; input=$(json_build tool_name=Bash tool_input.command="$1")
  printf '%s' "$input" | (cd "$REPO" && CLAUDE_CONFIG_DIR="$FAKE_CLAUDE_HOME" bash "$HOOK")
}
run_tool() {  # $1=tool_name $2=json_key(file_path|notebook_path) $3=path_value
  local input; input=$(json_build tool_name="$1" "tool_input.$2=$3")
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

# ── Write/Edit/MultiEdit/NotebookEdit のゾーン判定(既存維持) ──
run_write "$REPO/a.txt"; assert_exit 0 "$?" "Write プロジェクト配下は許可"
run_write "$FAKE_CLAUDE_HOME/hooks/x"; assert_exit 0 "$?" "Write \$CLAUDE_HOME配下は許可"
run_write "$SESSION_TMP/x"; assert_exit 0 "$?" "Write セッション用tmp配下は許可"
run_write "/etc/passwd"; assert_exit 2 "$?" "Write ゾーン外はブロック"
run_write "relative_new_file.txt"; assert_exit 0 "$?" "Write 相対パス(プロジェクト内)は許可"
run_tool "Edit" "file_path" "$REPO/e.txt"; assert_exit 0 "$?" "Edit プロジェクト配下は許可"
run_tool "Edit" "file_path" "/etc/passwd"; assert_exit 2 "$?" "Edit ゾーン外はブロック"
run_tool "MultiEdit" "file_path" "$REPO/me.txt"; assert_exit 0 "$?" "MultiEdit プロジェクト配下は許可"
run_tool "MultiEdit" "file_path" "/etc/passwd"; assert_exit 2 "$?" "MultiEdit ゾーン外はブロック"
run_tool "NotebookEdit" "notebook_path" "$REPO/n.ipynb"; assert_exit 0 "$?" "NotebookEdit プロジェクト配下は許可"
run_tool "NotebookEdit" "notebook_path" "/etc/n.ipynb"; assert_exit 2 "$?" "NotebookEdit ゾーン外はブロック"

# ── Bash: このフックはもう一切関与しない(2026-08-29再設計でスコープ縮小) ──
run_bash "rm -rf /etc"; assert_exit 0 "$?" "縮小: rm -rf /etc はworkspace-guard.sh単体では無制限に許可"
run_bash "git rm --cached /etc/passwd"; assert_exit 0 "$?" "縮小: git rm --cached /etc/passwd は無制限に許可"
run_bash "find /etc -delete"; assert_exit 0 "$?" "縮小: find -delete /etc は無制限に許可"
run_bash "rsync -a --delete /etc/ /root/"; assert_exit 0 "$?" "縮小: rsync --delete /etc は無制限に許可"
run_bash "chmod -R 777 /"; assert_exit 0 "$?" "縮小: chmod -R 777 / は無制限に許可"
run_bash "git clean -fd"; assert_exit 0 "$?" "縮小: git clean -fd(パス引数なし) は無制限に許可"
run_bash "cat /etc/credentials"; assert_exit 0 "$?" "縮小: 機密ファイル読取は無制限に許可"
run_bash "echo hi > /root/out.txt"; assert_exit 0 "$?" "縮小: リダイレクトのゾーン外書込みは無制限に許可"
run_bash "cp $REPO/a /root/b"; assert_exit 0 "$?" "縮小: cp のゾーン外宛先は無制限に許可"
run_bash "mv $REPO/a /root/b2"; assert_exit 0 "$?" "縮小: mv のゾーン外宛先は無制限に許可"
run_bash "tee /root/out.txt <<< hi"; assert_exit 0 "$?" "縮小: tee のゾーン外宛先は無制限に許可"
run_bash "curl -o /root/out.bin http://example.com/x"; assert_exit 0 "$?" "縮小: curl -o のゾーン外宛先は無制限に許可"

# ── node不在時はfail-close(既存維持) ──
NOJQ_BIN=$(mktemp -d)
BASH_BIN=$(command -v bash)
input='{"tool_name":"Write","tool_input":{"file_path":"x"}}'
printf '%s' "$input" | (cd "$REPO" && PATH="$NOJQ_BIN" "$BASH_BIN" "$HOOK") >/dev/null 2>&1
assert_exit 2 "$?" "node不在時はfail-close"
rm -rf "$NOJQ_BIN"

# ── 既知の限界: nodeはあるが不正JSON入力の場合はfail-open(TOOLが空文字になり素通し) ──
printf 'not-json' | (cd "$REPO" && CLAUDE_CONFIG_DIR="$FAKE_CLAUDE_HOME" bash "$HOOK") >/dev/null 2>&1
assert_exit 0 "$?" "既知の限界: 不正JSON入力はfail-open"

echo "----"
if [ "$FAIL" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "SOME TESTS FAILED"
fi
exit "$FAIL"
