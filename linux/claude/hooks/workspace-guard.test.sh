#!/bin/bash
set -uo pipefail

HOOK="$HOME/.claude/hooks/workspace-guard.sh"
# Git Bash(MSYS)は、ネイティブ(非MSYS)実行ファイル(本テストではjq.exe)へ渡す
# 引数が「素のPOSIX絶対パス1語のみ」に見える場合、自動でWindows形式へ書き換える
# (MSYS_NO_PATHCONV)。run_write/run_tool の file_path 引数はまさにこの形なので、
# 無効化しないと jq に渡る前に暗黙変換されテストが意図しない形の値で走ってしまう。
export MSYS_NO_PATHCONV=1
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

# ══════════════════════════════════════════════════════════════════
# ── Windows固有ケース(3件): to_posix()大文字小文字混在・WIN_TEMP_CLAUDEゾーン許可・
#    無アンカー回帰固定化。いずれもWrite(is_allowed経由)で再検証する。
#    Windows絶対パス⇔POSIXパスの相互変換にはドライブレター実体パスが必要なため、
#    MSYS仮想ルートの/tmp配下(上のSCRATCH)ではなく$HOME配下(cygpath -wで一意に
#    往復変換できる)に専用のスクラッチ領域を用意する。
# ══════════════════════════════════════════════════════════════════
WIN_SCRATCH=$(mktemp -d "$HOME/.wg_win_test_XXXXXX")
WIN_CLAUDE_HOME="$WIN_SCRATCH/claude_home"; mkdir -p "$WIN_CLAUDE_HOME/hooks"
trap 'rm -rf "$SCRATCH" "$SESSION_TMP" "$WIN_SCRATCH"' EXIT

run_write_ch() {  # $1=file_path (CLAUDE_CONFIG_DIR=$WIN_CLAUDE_HOME、cwd=$REPO)
  local input; input=$(json_build tool_name=Write tool_input.file_path="$1" tool_input.content=x)
  printf '%s' "$input" | (cd "$REPO" && CLAUDE_CONFIG_DIR="$WIN_CLAUDE_HOME" bash "$HOOK")
}

# (1) to_posix()バグ修正の回帰確認: 大文字小文字混在のWindowsパスでも、
#     ゾーン判定(小文字で計算されるCLAUDE_HOME)と正しく一致して許可される
#     (旧実装はドライブレターのみ小文字化しパス全体を小文字化していなかったため、
#     大文字混在パスが誤ってブロックされ得た)。
command -v cygpath >/dev/null 2>&1 && WIN_CH_BS=$(cygpath -w "$WIN_CLAUDE_HOME/hooks") || WIN_CH_BS=$(printf '%s' "$WIN_CLAUDE_HOME/hooks" | sed -E 's#^/([a-zA-Z])/#\1:\\#; s#/#\\#g')
WIN_CH_SLASH=$(printf '%s' "$WIN_CH_BS" | tr '\\' '/')
WIN_CH_SLASH_UPPER=$(printf '%s' "$WIN_CH_SLASH" | tr 'a-z' 'A-Z')
run_write_ch "$WIN_CH_SLASH/case_target.txt"; assert_exit 0 "$?" "(to_posix bug) 小文字スラッシュ形式Windowsパスは許可"
run_write_ch "$WIN_CH_SLASH_UPPER/case_target2.txt"; assert_exit 0 "$?" "(to_posix bug) 大文字混在スラッシュ形式Windowsパスも同じ許可結果(ドライブレターのみ小文字化する旧バグの回帰確認)"

# (2) WIN_TEMP_CLAUDEゾーン許可: 実$LOCALAPPDATA/Temp/claude配下はWrite(is_allowed)でも許可。
#     $LOCALAPPDATA未設定環境(非Windows)ではスキップする。
LOCALAPPDATA_POSIX=""
if [ -n "${LOCALAPPDATA:-}" ] && command -v cygpath >/dev/null 2>&1; then
  LOCALAPPDATA_POSIX=$(cygpath -u "$LOCALAPPDATA")
fi
if [ -n "$LOCALAPPDATA_POSIX" ]; then
  REAL_TEMP_CLAUDE_DIR="$LOCALAPPDATA_POSIX/Temp/claude/wg-test-$$"; mkdir -p "$REAL_TEMP_CLAUDE_DIR"
  run_write "$REAL_TEMP_CLAUDE_DIR/w.txt"; assert_exit 0 "$?" "(temp-claude-zone) 実\$LOCALAPPDATA/Temp/claude配下はWrite(is_allowed)でも許可"
  rm -rf "$REAL_TEMP_CLAUDE_DIR"
else
  echo "SKIP: LOCALAPPDATA未設定のため実temp/claudeゾーンテストをスキップ"
fi

# (3) 無アンカーcaseパターン(*/[Tt]emp/claude/*)の誤許可バグの回帰固定化テスト。
#    実$LOCALAPPDATA配下ではなく、パスのどこかに"temp/claude"という部分文字列を
#    含むだけの偽パス($WIN_SCRATCH配下、正規のスクラッチパッドとは無関係)を作り、
#    アンカー付き前方一致修正後はこれがWriteでもブロックされる(exit 2)ことを確認する。
FAKE_TEMP_CLAUDE_DIR="$WIN_SCRATCH/fakeproject/nested/temp/claude/evil"; mkdir -p "$FAKE_TEMP_CLAUDE_DIR"
run_write "$FAKE_TEMP_CLAUDE_DIR/w.txt"; assert_exit 2 "$?" "(temp-claude-zone-regression) temp/claudeを部分文字列に含むだけの偽パスはWriteでもブロックされる(無アンカー実装バグの固定化)"

echo "----"
if [ "$FAIL" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "SOME TESTS FAILED"
fi
exit "$FAIL"
