# hooks 再設計 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `~/.claude/hooks/` 配下の既存4フック（bash-guard.sh / workspace-guard.sh / main-branch-guard.sh / venv-guard.sh）を削除し、責務軸を「場所」「Gitブランチ状態」「コマンドの絶対破壊性」「Python環境」に直交させた新4構成（workspace-guard.sh(縮小) / branch-guard.sh / system-guard.sh / venv-guard.sh）へ置換する。

**Architecture:** 各フックはPreToolUseフックとして独立したbashスクリプトのまま維持する。workspace-guard.shはBash側のゾーン判定を全廃してWrite/Edit/MultiEdit/NotebookEdit専用に縮小。main-branch-guard.shはbranch-guard.shへ改名し、環境変数バイパスを`.git`書込み権限の自動検知へ置換。bash-guard.shはsystem-guard.shへ改名し、システムパッケージのupdate/upgradeパターンを追加。venv-guard.shは実装を変えずテストのみ新設する。

**Tech Stack:** bash / jq / git（PreToolUseフックスクリプトとその専用テストハーネス、`*.test.sh`形式）

**Spec:** `docs/specs/2026-08-29-hooks-redesign-design.md`

## Global Constraints

- フック本体・テストファイルの実配置先は `$HOME/.claude/hooks/`（このリポジトリの`my-claude`配下ではない）
- `$HOME/.claude/` はgit管理下に無い（`git rev-parse --is-inside-work-tree`で確認済み、`fatal: not a git repository`）。そのため各タスクの実装ステップに「git commit」は含めない。全実装完了後、最終タスク（Task 6）で`sync-config`スキルを使い`linux/claude/`ミラーへ反映し、`my-claude`リポジトリ側で1回だけコミットする
- テスト実行時は実環境`~/.claude/`を汚染しないよう、監査ログ等`$CLAUDE_HOME`配下への書込みが発生するテストは必ず`CLAUDE_CONFIG_DIR`でスクラッチディレクトリへ隔離すること（既存テストの確立された慣習を踏襲）
- 全フックスクリプトは`#!/bin/bash`・`set -uo pipefail`はテストファイル側のみ（フック本体には既存通り付けない）
- 全フックは`jq`不在時fail-close（`exit 2`）を既存通り維持する
- テストの`assert_exit`ヘルパー・`PASS:`/`FAIL:`出力形式は既存の`*.test.sh`の慣習をそのまま踏襲する

---

### Task 1: workspace-guard.sh を縮小する（Write/Edit/MultiEdit/NotebookEdit専用へ）

**Files:**
- Modify: `$HOME/.claude/hooks/workspace-guard.sh`
- Modify（全面書き換え）: `$HOME/.claude/hooks/workspace-guard.test.sh`

**Interfaces:**
- Produces: `workspace-guard.sh`は`is_allowed(path)`関数を保持し、Write/Edit/MultiEdit/NotebookEditの`file_path`/`notebook_path`がプロジェクト配下／`$CLAUDE_HOME`配下／`/tmp/claude-*/`配下のいずれかなら`exit 0`、それ以外なら`exit 2`。Bashツールの`tool_name`が来た場合は無条件`exit 0`（何もしない）

- [ ] **Step 1: 新しいテストファイルを書く（現行の縮小前フックに対しては一部FAILする内容）**

`$HOME/.claude/hooks/workspace-guard.test.sh` を以下の内容で全面上書きする。

```bash
#!/bin/bash
set -uo pipefail

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

# ── jq不在時はfail-close(既存維持) ──
NOJQ_BIN=$(mktemp -d)
BASH_BIN=$(command -v bash)
input='{"tool_name":"Write","tool_input":{"file_path":"x"}}'
printf '%s' "$input" | (cd "$REPO" && PATH="$NOJQ_BIN" "$BASH_BIN" "$HOOK") >/dev/null 2>&1
assert_exit 2 "$?" "jq不在時はfail-close"
rm -rf "$NOJQ_BIN"

# ── 既知の限界: jqはあるが不正JSON入力の場合はfail-open(TOOLが空文字になり素通し) ──
printf 'not-json' | (cd "$REPO" && CLAUDE_CONFIG_DIR="$FAKE_CLAUDE_HOME" bash "$HOOK") >/dev/null 2>&1
assert_exit 0 "$?" "既知の限界: 不正JSON入力はfail-open"

echo "----"
if [ "$FAIL" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "SOME TESTS FAILED"
fi
exit "$FAIL"
```

- [ ] **Step 2: 現行（縮小前）の workspace-guard.sh に対してテストを実行し、Bash側の「縮小」アサーションがFAILすることを確認する（RED）**

Run: `bash "$HOME/.claude/hooks/workspace-guard.test.sh"`
Expected: 「縮小: ...」ラベルの行が軒並み `FAIL`（旧フックはまだBash側ゾーン判定を持っているため `exit 2` を返し、新テストの `assert_exit 0` と食い違う）。「Write/Edit/...」ラベルの行と「jq不在時」「既知の限界」の行は現行実装でも同じ挙動のためPASSしてよい。

- [ ] **Step 3: workspace-guard.sh を縮小実装で上書きする**

`$HOME/.claude/hooks/workspace-guard.sh` を以下の内容で全面上書きする。

```bash
#!/bin/bash
# workspace-guard.sh — PreToolUse フック
# Write/Edit/MultiEdit/NotebookEdit の書込み先が、プロジェクト配下・$CLAUDE_HOME
# 配下・Claude Codeのセッション用一時ディレクトリ(/tmp/claude-*/配下)のいずれでも
# ない場合にブロックする。
#
# 許可ゾーン:
#   1) プロジェクトルート($PROJECT_DIR=pwd)配下
#   2) $CLAUDE_HOME(=${CLAUDE_CONFIG_DIR:-$HOME/.claude})配下（hooks/settings.json含む。
#      設定管理ワークフロー自体がhooks/settingsの編集を要するため自己防御は設けない。
#      settings.json の permissions.ask 側で実行前確認を挟む二重防御に委ねる）
#   3) /tmp/claude-*/配下（Claude Code自身のセッション固有一時ディレクトリ）
#
# 既知の限界:
#   - jqが存在してもINPUTが不正JSONの場合、TOOLが空文字になりどのcase分岐にも
#     一致せず素通しでexit 0になる（fail-closeはjq自体の不在時のみ保証）。
#     Claude Code自身が生成する入力なので通常は整形式JSON。
#   - Bashコマンド経由の書込み・削除（rm/cp/mv等）はこのフックの対象外。
#     場所を問わない絶対破壊コマンドはsystem-guard.shが担当し、それ以外の
#     プロジェクト外への個別ファイル操作は意図的に無防備（設計上の既知のリスク、
#     docs/specs/2026-08-29-hooks-redesign-design.md 参照）。

command -v jq >/dev/null 2>&1 || { echo "❌ workspace-guard: jq not found, failing closed" >&2; exit 2; }

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')
PROJECT_DIR=$(pwd)
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

is_allowed() {
  local path="$1"
  local abs
  abs=$(realpath -m "$path" 2>/dev/null) || abs="$path"
  case "$abs" in
    "$PROJECT_DIR" | "$PROJECT_DIR"/*) return 0 ;;
    "$CLAUDE_HOME" | "$CLAUDE_HOME"/*) return 0 ;;
    /tmp/claude-*/*) return 0 ;;
    *) return 1 ;;
  esac
}

case "$TOOL" in
  Write | Edit | MultiEdit | NotebookEdit)
    FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
    [ -z "$FILE" ] && exit 0
    if ! is_allowed "$FILE"; then
      echo "❌ BLOCKED: プロジェクト外への書き込み: $FILE" >&2
      echo "   許可範囲: プロジェクト配下($PROJECT_DIR) または $CLAUDE_HOME 配下 または /tmp/claude-*/配下" >&2
      exit 2
    fi
    ;;
esac

exit 0
```

- [ ] **Step 4: テストを再実行し、全PASSを確認する（GREEN）**

Run: `bash "$HOME/.claude/hooks/workspace-guard.test.sh"`
Expected: 全行 `PASS`、末尾に `ALL PASS`

- [ ] **Step 5: 動作確認のみ（コミットなし）**

`$HOME/.claude/` はgit管理下に無いため、このタスクではコミットしない（Global Constraints参照）。Step 4のALL PASSがこのタスクの完了確認。

---

### Task 2: system-guard.sh を新設する（bash-guard.shを改名・拡張）

**Files:**
- Create: `$HOME/.claude/hooks/system-guard.sh`
- Create: `$HOME/.claude/hooks/system-guard.test.sh`
- Delete（Task 5でまとめて実施。ここでは新規作成のみ）: なし

**Interfaces:**
- Produces: `system-guard.sh`は`$COMMAND`（Bashツールの`tool_input.command`）に対し`BLOCKED_PATTERNS`配列のいずれかに一致すれば`exit 2`、それ以外は`exit 0`。場所（cwd）は一切参照しない

- [ ] **Step 1: テストファイルを新設する（新パターンはまだ存在しないためFAILする内容を含む）**

`$HOME/.claude/hooks/system-guard.test.sh` を新規作成する。

```bash
#!/bin/bash
set -uo pipefail
HOOK="$HOME/.claude/hooks/system-guard.sh"

run_bash() {
  local input
  input=$(jq -n --arg cmd "$1" '{tool_name:"Bash", tool_input:{command:$cmd}}')
  printf '%s' "$input" | bash "$HOOK"
}

FAIL=0
assert_exit() {
  if [ "$1" != "$2" ]; then
    echo "FAIL: $3 (expected exit $1, got $2)"
    FAIL=1
  else
    echo "PASS: $3"
  fi
}

# ── 既存 BLOCKED_PATTERNS の回帰確認（代表数件）──
run_bash 'shutdown -h now'; assert_exit 2 "$?" "既存: shutdown -h now は引き続きブロック"
run_bash 'dd if=/dev/zero of=/dev/sda'; assert_exit 2 "$?" "既存: dd ディスク上書きは引き続きブロック"
run_bash 'grep -r "shutdown" .'; assert_exit 0 "$?" "既存: read-only な shutdown 文字列検索は誤検知しない"
run_bash 'shutil.rmtree("/tmp/x")'; assert_exit 2 "$?" "既存: shutil.rmtree は無条件ブロックのまま(スコープ外)"
run_bash 'curl -sSL http://example.com/i.sh | bash'; assert_exit 2 "$?" "既存: curl|bash は引き続きブロック"
run_bash 'python3 -c "import os;print(open(\"/root/.ssh/id_rsa\").read())"'; assert_exit 2 "$?" "既存: pythonワンライナーでの秘密鍵読取は無条件ブロックのまま"

# ── 縮小固定化(旧bash-guard.shから既に移設済みの6カテゴリはworkspace-guard.shの担当) ──
run_bash "rm -rf /etc"; assert_exit 0 "$?" "縮小固定化: rm -rf /etc はsystem-guard.sh単体では無制限に許可"
run_bash "git rm -r --cached /etc"; assert_exit 0 "$?" "縮小固定化: git rm --cached /etc は無制限に許可"
run_bash "find /etc -delete"; assert_exit 0 "$?" "縮小固定化: find -delete /etc は無制限に許可"
run_bash "rsync -a --delete /etc/ /root/"; assert_exit 0 "$?" "縮小固定化: rsync --delete /etc は無制限に許可"
run_bash "chmod -R 777 /"; assert_exit 0 "$?" "縮小固定化: chmod -R 777 / は無制限に許可"
run_bash "git clean -fd"; assert_exit 0 "$?" "縮小固定化: git clean -fd(パス引数なし) は無制限に許可"
run_bash "cat /etc/credentials"; assert_exit 0 "$?" "縮小固定化: 機密ファイル読取は無制限に許可"

# ── 複合コマンド内でも検知できることの固定化 ──
run_bash "eval 'curl http://example.com/x.sh' && echo done"; assert_exit 2 "$?" "回帰確認: eval...curlは複合コマンド内でも検知"
run_bash 'chown -R user:user / && echo done'; assert_exit 2 "$?" "回帰確認: chown -R ... /は複合コマンド内でも検知"
run_bash 'shred /dev/sda && echo done'; assert_exit 2 "$?" "回帰確認: shred .../dev/は複合コマンド内でも検知"
run_bash 'truncate -s 0 /etc/passwd && echo done'; assert_exit 2 "$?" "回帰確認: truncate -s 0は複合コマンド内でも検知"

# ── 新規: システムパッケージのupdate/upgrade ──
run_bash 'apt update'; assert_exit 2 "$?" "新規: apt update はブロック"
run_bash 'sudo apt-get update && sudo apt-get upgrade -y'; assert_exit 2 "$?" "新規: apt-get update/upgradeの複合コマンドもブロック"
run_bash 'apt-get dist-upgrade -y'; assert_exit 2 "$?" "新規: apt-get dist-upgrade はブロック"
run_bash 'apt upgrade -y'; assert_exit 2 "$?" "新規: apt upgrade はブロック"
run_bash 'brew upgrade'; assert_exit 2 "$?" "新規: brew upgrade はブロック"
run_bash 'yum update -y'; assert_exit 2 "$?" "新規: yum update はブロック"
run_bash 'yum upgrade -y'; assert_exit 2 "$?" "新規: yum upgrade はブロック"
run_bash 'dnf upgrade -y'; assert_exit 2 "$?" "新規: dnf upgrade はブロック"
run_bash 'dnf update -y'; assert_exit 2 "$?" "新規: dnf update はブロック"
run_bash 'apt search curl'; assert_exit 0 "$?" "新規: apt search(読み取り相当)は誤検知しない"
run_bash 'apt list --upgradable'; assert_exit 0 "$?" "新規: apt list --upgradableは誤検知しない"
run_bash "a'p't' up'g'rade -y"; assert_exit 2 "$?" "新規: apt upgradeの難読化(クォート分割)もブロック"

[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
```

- [ ] **Step 2: テストを実行し、「新規」ラベルのテストがFAILすることを確認する（RED）**

Run: `bash "$HOME/.claude/hooks/system-guard.test.sh"`
Expected: `system-guard.sh` がまだ存在しないため、`HOOK` に渡すファイルが無く `bash: .../system-guard.sh: No such file or directory` 等で全件FAILする（あるいは全く実行できない）。これはフック未作成の状態なので想定通り。

- [ ] **Step 3: system-guard.sh を新規作成する**

`$HOME/.claude/hooks/system-guard.sh` を以下の内容で新規作成する。

```bash
#!/bin/bash
# system-guard.sh — PreToolUse フック
# 場所を問わずシステム全体を破壊しうるコマンドのみを無条件ブロックする単純な1層構成。
# ゾーン判定（プロジェクト外かどうか）はworkspace-guard.sh、ブランチ判定は
# branch-guard.shが別途担当する。
#
# ── fail-close: jq 不在なら解析不能として block ──────────────
command -v jq >/dev/null 2>&1 || { echo "❌ system-guard: jq not found, failing closed" >&2; exit 2; }
INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')

BLOCKED_PATTERNS=(
  # ── ディスク・デバイス破壊 ──────────────────────
  'dd\s+if=.*of=/dev/sd'
  'dd\s+if=.*of=/dev/nvme'
  '>\s*/dev/sd'
  'mkfs\.'
  'shred\s+.*(/dev/|/disk)'

  # ── パーミッション破壊 ──────────────────────────
  'chown\s+-R\s+.*\s+/'

  # ── プロセス・システム停止 ──────────────────────
  'kill\s+-9\s+-1'
  ':\(\)\s*\{.*:\|:.*\}'
  '\bshutdown(\s+(-|now|\+|halt)|$)'
  'halt'
  'reboot'
  'poweroff'
  'init\s+0'
  'init\s+6'
  'systemctl\s+(poweroff|reboot|halt)'

  # ── 危険なリモート実行 ──────────────────────────
  'curl\s+.*\|\s*(bash|sh)'
  'wget\s+.*\|\s*(bash|sh)'
  'eval\s+.*curl'

  # ── システムファイル破壊 ────────────────────────
  '>\s*/etc/hosts'
  '>\s*/etc/passwd'
  '>\s*/etc/shadow'
  'unset\s+PATH'

  # ── DB破壊 ─────────────────────────────────────
  'DROP\s+DATABASE'
  'DROP\s+TABLE'

  # ── グローバルパッケージ インストール ────────────
  'npm\s+(install|i)\s+(-g|--global)'
  'yarn\s+global\s+add'
  'pnpm\s+(add|install)\s+(-g|--global)'
  'cargo\s+install'
  'gem\s+install'
  'go\s+install'
  'pipx\s+install'
  'uv\s+tool\s+install'
  'conda\s+install'

  # ── パッケージ アンインストール ──────────────────
  'apt\s+(remove|purge|autoremove)\s+-y'
  'apt-get\s+(remove|purge|autoremove)\s+-y'
  'yum\s+remove\s+-y'
  'dnf\s+remove\s+-y'
  'npm\s+uninstall\s+-g'

  # ── システムパッケージのupdate/upgrade ──────────
  'apt(-get)?\s+update\b'
  'apt(-get)?\s+(upgrade|dist-upgrade)\b'
  'brew\s+upgrade\b'
  'yum\s+(update|upgrade)\b'
  'dnf\s+(update|upgrade)\b'

  # ── ファイル内容消去 ────────────────────────────
  'truncate\s+.*-s\s+0'

  # ── 迂回削除（python経由）──────────────────────
  'shutil\.rmtree'
  'os\.(remove|unlink|rmdir)'
  'truncate\s+.*--size[= ]*0'

  # ── DB 追加破壊 ─────────────────────────────────
  'TRUNCATE\s+TABLE'
  'DROP\s+SCHEMA'

  # ── スケジューラ破壊 ────────────────────────────
  'crontab\s+-r'

  # ── 機密ファイル読取・持ち出し ──────────────────
  # cat/less/head等のファイル読取のゾーン判定はworkspace-guard.shの対象外(Write/Edit系
  # のみに縮小済み)のため、ここでは対象にしない(2026-08-29再設計でスコープ確定)。
  # python/perl等のワンライナー経由（-c/-e）はファイル対象がコード文字列に
  # 埋め込まれ静的に確定できないためゾーン判定になじまず、常時無条件ブロックのまま。
  '(python3?|perl|ruby|node)\s+(-c|-e)\s+.*(\.env(\.|\s|['"'"'")]|$)|\.ssh/|id_rsa|id_ed25519|\.pem(\s|['"'"'")]|$)|\.key(\s|['"'"'")]|$)|authorized_keys|\.netrc|credentials)'
)

# ── 難読化正規化（判定用。実行はしない）──────────────
# クォート分割('r''m')・バックスラッシュエスケープ(r\m)・${IFS}/$IFS空白代替
# (kill${IFS}-9)で BLOCKED_PATTERNS の前提(コマンド名がそのまま文字列に現れる)
# が崩れるのを防ぐため、除去・置換のみ行った正規化版を作る。
normalize() {
  printf '%s' "$1" | tr -d "\"'\\\\" | sed -E 's/\$\{?IFS\}?/ /g'
}

# ── 全体スコープの危険パターン判定（$COMMAND全体へ評価）────────────────
check_whole_command() {
  local pattern COMMAND_NORMALIZED
  COMMAND_NORMALIZED=$(normalize "$COMMAND")

  for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qiP "$pattern"; then
      echo "❌ BLOCKED: $COMMAND" >&2
      echo "   matched pattern: $pattern" >&2
      echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
      exit 2
    fi
  done

  if [ "$COMMAND_NORMALIZED" != "$COMMAND" ]; then
    for pattern in "${BLOCKED_PATTERNS[@]}"; do
      if printf '%s' "$COMMAND_NORMALIZED" | grep -qiP "$pattern" \
         && ! printf '%s' "$COMMAND" | grep -qiP "$pattern"; then
        echo "❌ BLOCKED: $COMMAND" >&2
        echo "   クォート分割/バックスラッシュ/\${IFS}等の難読化を検知し、正規化後に危険パターンへ一致しました: $pattern" >&2
        echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
        exit 2
      fi
    done
  fi
}
check_whole_command
exit 0
```

- [ ] **Step 4: テストを再実行し、全PASSを確認する（GREEN）**

Run: `bash "$HOME/.claude/hooks/system-guard.test.sh"`
Expected: 全行 `PASS`、末尾に `ALL PASS`

- [ ] **Step 5: 動作確認のみ（コミットなし）**

---

### Task 3: branch-guard.sh を新設する（main-branch-guard.shを置換）

**Files:**
- Create: `$HOME/.claude/hooks/branch-guard.sh`
- Create: `$HOME/.claude/hooks/branch-guard.test.sh`

**Interfaces:**
- Produces: `branch-guard.sh`は`get_branch(dir)`・`is_protected(branch)`・`can_create_branch(dir)`・`warn_if_stale(dir,branch)`・`bash_targets_outside_project(cmd,project_dir)`・`handle_protected(dir,branch,target)`の各関数を持つ。監査ログは`$CLAUDE_HOME/branch-guard-bypass.log`

- [ ] **Step 1: テストファイルを新設する**

`$HOME/.claude/hooks/branch-guard.test.sh` を新規作成する。

```bash
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

LAST_STDERR=""
run_bash() {  # $1=command $2=repo
  local input repo="$2"
  input=$(jq -n --arg cmd "$1" '{tool_name:"Bash", tool_input:{command:$cmd}}')
  LAST_STDERR=$(printf '%s' "$input" | (cd "$repo" && CLAUDE_CONFIG_DIR="$CLAUDE_HOME_TEST" bash "$HOOK") 2>&1 >/dev/null)
  return $?
}

run_write() {  # $1=file_path $2=repo
  local input repo="$2"
  input=$(jq -n --arg fp "$1" '{tool_name:"Write", tool_input:{file_path:$fp}}')
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
# （非root環境での実行を前提とする、既知の制約）。
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
for bin in jq grep cat; do p=$(command -v "$bin" 2>/dev/null) && ln -sf "$p" "$NOGIT_BIN/$bin"; done
input=$(jq -n --arg cmd 'rm out.txt' '{tool_name:"Bash", tool_input:{command:$cmd}}')
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
```

- [ ] **Step 2: テストを実行し、フック未作成のため全件FAILすることを確認する（RED）**

Run: `bash "$HOME/.claude/hooks/branch-guard.test.sh"`
Expected: `branch-guard.sh` が存在せず実行できないため全件FAILまたはエラー。

- [ ] **Step 3: branch-guard.sh を新規作成する**

`$HOME/.claude/hooks/branch-guard.sh` を以下の内容で新規作成する。

```bash
#!/bin/bash
# branch-guard.sh — PreToolUse フック
# main/masterブランチ上での変更系操作をブロックする。
#
# Write/Edit/MultiEdit/NotebookEdit: 対象ファイルが git 管理下で現在ブランチが
# main/master なら exit 2。
# Bash: 削除・変更系コマンド（rm/mv/cp/tee/touch/sed -i/リダイレクト/git commit/git rm 等）
# のみを対象に、cwd の git ブランチが main/master なら exit 2。読み取り専用コマンド
# （git status/cat/ls/grep 等）は対象外。
#
# 状態ごとの挙動(docs/specs/2026-08-29-hooks-redesign-design.md 決定表):
#   1) gitコマンド自体が無い                       → 何もしない(fail-open。
#      get_branchがgit呼び出し失敗時に空文字を返しis_protectedがfalseになるため
#      保護は効かないが、そもそもgitが無ければ変更操作自体が実行不能なため実害は
#      限定的。jq欠如とは異なりfail-closeにしない)
#   2) gitはあるがこのディレクトリはリポジトリでない   → 無条件許可
#   3) detached HEAD                                → 無条件許可(get_branchが
#      空文字を返しis_protectedがfalseになる。どのブランチにも属さないコミットに
#      なるだけでmainブランチの内容を直接書き換えるわけではないため実害は限定的)
#   4) main/master・かつ.git書込み権限あり            → ブロック
#   5) main/master・かつ.git書込み権限なし            → 警告のみで許容(自動検知。
#      $CLAUDE_HOME配下のログへ毎回記録=監査証跡)
#   6) main/master以外の通常ブランチ                  → 無条件許可
#
# 旧main-branch-guard.shにあったCLAUDE_MAIN_BRANCH_GUARD_BYPASS環境変数バイパスは
# 廃止した(セキュリティレビューで指摘されたCRITICAL: 設定ファイル/シェルRC経由の
# 間接的自己バイパス経路の温床だったため。.git書込み権限の自動検知に置き換えることで
# この経路自体が構造的に無くなる)。
#
# shutil.rmtree は system-guard.sh がブランチに関係なく常時無条件ブロックするため、
# ここには含めない（含めても到達不能な重複ロジックになるため）。find -delete/
# rsync --delete は workspace-guard.sh の対象外(ゾーン判定はWrite/Edit系のみに
# 縮小済み)のため、保護ブランチ上でのプロジェクト内破壊を防ぐにはこちらで対象に
# 含める必要がある。

command -v jq >/dev/null 2>&1 || { echo "❌ branch-guard: jq not found, failing closed" >&2; exit 2; }

CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

log_warn_allow() {  # $1=branch $2=target
  local branch="$1" target="$2" logfile="$CLAUDE_HOME/branch-guard-bypass.log"
  printf '%s\tbranch=%s\ttarget=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$branch" "$target" >>"$logfile" 2>/dev/null
}

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')

# git 管理下でなければ空文字を返す。symbolic-ref ベースなので、同名タグの併存や
# 未出生ブランチ（コミット0件）でも rev-parse --abbrev-ref HEAD のように誤動作しない。
# detached HEAD・gitコマンド不在・非リポジトリのいずれも symbolic-ref/rev-parse の
# 失敗として同じ経路で空文字を返す(状態1/2/3が同一コードパスで安全側に倒れる)。
get_branch() {
  local dir="$1"
  git -C "$dir" rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo ""; return; }
  local ref
  ref=$(git -C "$dir" symbolic-ref -q HEAD 2>/dev/null)
  printf '%s\n' "${ref#refs/heads/}"
}

is_protected() {
  case "$1" in
    main | master) return 0 ;;
    *) return 1 ;;
  esac
}

# .git ディレクトリへの書込み権限を自動検知する(git checkout -b が実際に失敗するか
# どうかの近似判定)。HEADファイルの書換えとgit-dir自体へのref作成の両方が必要になる
# ため、両方が書込み可能であることを要求する。
can_create_branch() {
  local dir="$1" gitdir
  gitdir=$(git -C "$dir" rev-parse --absolute-git-dir 2>/dev/null) || return 1
  [ -w "$gitdir" ] && [ -w "$gitdir/HEAD" ]
}

# ローカル<branch>がorigin/<branch>よりfast-forward可能に遅れている場合のみ警告行を出す。
# ネットワークアクセス（fetch）は行わない。祖先判定はgit merge-base --is-ancestorの終了コードのみで行い、
# git log等のテキスト解析はしない。
warn_if_stale() {
  local dir="$1" branch="$2"
  local remote_ref="origin/${branch}"
  git -C "$dir" rev-parse --verify -q "$remote_ref" >/dev/null 2>&1 || return 0
  local local_sha remote_sha
  local_sha=$(git -C "$dir" rev-parse "refs/heads/$branch" 2>/dev/null) || return 0
  remote_sha=$(git -C "$dir" rev-parse "$remote_ref" 2>/dev/null) || return 0
  [ "$local_sha" = "$remote_sha" ] && return 0
  git -C "$dir" merge-base --is-ancestor "refs/heads/$branch" "$remote_ref" 2>/dev/null || return 0
  echo "⚠️  ローカルの${branch}が${remote_ref}より遅れています。先に 'git pull' を実行してから上記のブランチ作成をしてください。" >&2
}

# 単一コマンド（rm/rmdir/unlink・mv・cp・touch・sed -i）が、全対象パスを
# プロジェクト外かつ $CLAUDE_HOME 外に持つ場合のみ真を返す。パイプ・リダイレクト・
# 複合コマンド・改行・cd・安全文字集合外の文字を含む場合や sed に -i が無い場合は
# 偽（従来通りブロック）。$CLAUDE_HOME を除外しないと、cp/mv/touch/sed -i でフック
# 自身（branch-guard.sh等）を保護ブランチ上から書き換えられてしまうため必須。
bash_targets_outside_project() {
  local cmd="$1" project_dir="$2" claude_home="$CLAUDE_HOME" first tok abs had_target=0 idx=0
  first=$(printf '%s' "$cmd" | awk 'NR==1{print $1}')
  case "$first" in
    rm | rmdir | unlink | mv | cp | touch | sed) ;;
    *) return 1 ;;
  esac
  if [ "$first" = "sed" ]; then
    printf '%s' "$cmd" | grep -qP -- '-i\b' || return 1
  fi
  printf '%s' "$cmd" | tr '\n' '\v' | grep -qP '[^A-Za-z0-9 \t_./-]' && return 1
  printf '%s' "$cmd" | grep -qiP '\bcd\b' && return 1
  set -f
  for tok in $cmd; do
    idx=$((idx + 1))
    if [ "$idx" -eq 1 ]; then continue; fi
    case "$tok" in
      -*) continue ;;
    esac
    had_target=1
    abs=$(realpath -m "$tok" 2>/dev/null)
    if [ -z "$abs" ]; then set +f; return 1; fi
    case "$abs" in
      "$project_dir" | "$project_dir"/*) set +f; return 1 ;;
      "$claude_home" | "$claude_home"/*) set +f; return 1 ;;
    esac
  done
  set +f
  [ "$had_target" -eq 1 ]
}

# main/master保護時の共通処理: .git書込み権限があればブロック、無ければ
# 警告のみで許容(自動検知)し監査ログへ記録する。
handle_protected() {  # $1=dir $2=branch $3=target(表示用)
  local dir="$1" branch="$2" target="$3"
  if can_create_branch "$dir"; then
    echo "❌ BLOCKED: ${branch}ブランチ上でのファイル変更は禁止されています: $target" >&2
    echo "   先に 'git checkout -b <branch-name>' でブランチを作成してから再試行してください。" >&2
    warn_if_stale "$dir" "$branch"
    exit 2
  fi
  echo "⚠️  branch-guard: .git への書込み権限が無くブランチを作成できないため、${branch}ブランチ上での変更を警告のみで許容します: $target" >&2
  log_warn_allow "$branch" "$target"
  exit 0
}

case "$TOOL" in
  Write | Edit | MultiEdit | NotebookEdit)
    FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
    [ -z "$FILE" ] && exit 0
    ABS=$(realpath -m "$FILE" 2>/dev/null) || ABS="$FILE"
    DIR=$(dirname -- "$ABS")
    BRANCH=$(get_branch "$DIR")
    if is_protected "$BRANCH"; then
      handle_protected "$DIR" "$BRANCH" "$FILE"
    fi
    ;;
  Bash)
    CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
    PROJECT_DIR=$(pwd)

    MUTATING_PATTERNS=(
      '\b(rm|rmdir|unlink)\b'
      '\bgit\s+rm\b'
      '\bgit\s+commit\b'
      '>>?(?!&)[[:space:]]*(?!/dev/null\b)[^[:space:]]'
      '\btee\b'
      '\bcp\b'
      '\bmv\b'
      '\btouch\b'
      'sed\s+-i'
      '\bfind\b.*-delete\b'
      '\brsync\b.*--del(ete)?\b'
    )

    is_mutating=0
    for pattern in "${MUTATING_PATTERNS[@]}"; do
      if printf '%s' "$CMD" | grep -qiP "$pattern"; then
        is_mutating=1
        break
      fi
    done

    if [ "$is_mutating" -eq 1 ]; then
      BRANCH=$(get_branch "$PROJECT_DIR")
      if is_protected "$BRANCH"; then
        if bash_targets_outside_project "$CMD" "$PROJECT_DIR"; then
          exit 0
        fi
        handle_protected "$PROJECT_DIR" "$BRANCH" "$CMD"
      fi
    fi
    ;;
esac

exit 0
```

- [ ] **Step 4: テストを再実行し、全PASSを確認する（GREEN）**

Run: `bash "$HOME/.claude/hooks/branch-guard.test.sh"`
Expected: 全行 `PASS`、末尾に `ALL PASS`（非root環境で実行すること。root権限下ではStep(5)の権限テストが無効化される既知の制約がある）

- [ ] **Step 5: 動作確認のみ（コミットなし）**

---

### Task 4: venv-guard.sh のテストを新設する（本体は変更なし）

**Files:**
- Create: `$HOME/.claude/hooks/venv-guard.test.sh`
- （`$HOME/.claude/hooks/venv-guard.sh` は変更しない）

**Interfaces:**
- Consumes: `venv-guard.sh`の既存の`VIRTUAL_ENV`環境変数ベースの判定ロジック（変更なし）

- [ ] **Step 1: テストファイルを新規作成する**

`$HOME/.claude/hooks/venv-guard.test.sh` を以下の内容で新規作成する。

```bash
#!/bin/bash
set -uo pipefail
HOOK="$HOME/.claude/hooks/venv-guard.sh"
SCRATCH=$(mktemp -d)
REPO="$SCRATCH/repo"; mkdir -p "$REPO/.venv/bin"
trap 'rm -rf "$SCRATCH"' EXIT

run_bash() {  # $1=command $2=VIRTUAL_ENV値(省略時は未設定)
  local input cmd="$1" venv="${2:-}"
  input=$(jq -n --arg cmd "$cmd" '{tool_name:"Bash", tool_input:{command:$cmd}}')
  if [ -n "$venv" ]; then
    printf '%s' "$input" | (cd "$REPO" && VIRTUAL_ENV="$venv" bash "$HOOK")
  else
    printf '%s' "$input" | (cd "$REPO" && env -u VIRTUAL_ENV bash "$HOOK")
  fi
}

FAIL=0
assert_exit() {
  if [ "$1" != "$2" ]; then
    echo "FAIL: $3 (expected exit $1, got $2)"
    FAIL=1
  else
    echo "PASS: $3"
  fi
}

# ── pip install ──
run_bash 'pip install requests'; assert_exit 2 "$?" "pip install: VIRTUAL_ENV未設定はブロック"
run_bash 'pip install requests' "$REPO/.venv"; assert_exit 0 "$?" "pip install: VIRTUAL_ENVがプロジェクト配下なら許可"
run_bash 'pip install requests' "/tmp/other-venv"; assert_exit 2 "$?" "pip install: VIRTUAL_ENVがプロジェクト外はブロック"
run_bash 'pip3 install requests' "$REPO/.venv"; assert_exit 0 "$?" "pip3 install も同様に許可"
run_bash 'python3 -m pip install requests' "$REPO/.venv"; assert_exit 0 "$?" "python -m pip install も同様に許可"
run_bash 'echo start && pip install requests' "$REPO/.venv"; assert_exit 0 "$?" "複合コマンド内(&&)のpip installも検知される"

# ── pip uninstall ──
run_bash 'pip uninstall requests'; assert_exit 2 "$?" "pip uninstall: VIRTUAL_ENV未設定はブロック"
run_bash 'pip uninstall requests' "$REPO/.venv"; assert_exit 0 "$?" "pip uninstall: VIRTUAL_ENVがプロジェクト配下なら許可"

# ── venvバイナリ直接指定の早期許可 ──
run_bash '.venv/bin/pip install requests'; assert_exit 0 "$?" "venvバイナリ直接指定(.venv/bin/pip)は許可"
run_bash "$REPO/.venv/bin/pip3 install requests"; assert_exit 0 "$?" "venvバイナリ直接指定(絶対パス)は許可"

# ── uv add / uv pip install ──
run_bash 'uv add requests'; assert_exit 0 "$?" "uv add: プロジェクト配下に.venvがあれば許可"
NOVENV="$SCRATCH/novenv"; mkdir -p "$NOVENV"
input=$(jq -n --arg cmd 'uv add requests' '{tool_name:"Bash", tool_input:{command:$cmd}}')
printf '%s' "$input" | (cd "$NOVENV" && bash "$HOOK")
assert_exit 2 "$?" "uv add: プロジェクト配下に.venvが無ければブロック"

# ── 例外なし方針: VIRTUAL_ENVがプロジェクトのプレフィックスと無関係でもブロック ──
run_bash 'pip install requests' "/some/unrelated/path"; assert_exit 2 "$?" "誤検知しても機械的にブロック(回避経路は用意しない方針)"

echo "----"
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
```

- [ ] **Step 2: テストを実行し、全PASSを確認する**

Run: `bash "$HOME/.claude/hooks/venv-guard.test.sh"`
Expected: 全行 `PASS`、末尾に `ALL PASS`（`venv-guard.sh`は無変更のため、このタスクにRED状態は無い。テスト新設が目的）

- [ ] **Step 3: 動作確認のみ（コミットなし）**

---

### Task 5: settings.json・hooks.md の更新と旧ファイルの削除

**Files:**
- Modify: `$HOME/.claude/settings.json`
- Modify: `$HOME/.claude/rules/hooks.md`
- Delete: `$HOME/.claude/hooks/bash-guard.sh`
- Delete: `$HOME/.claude/hooks/bash-guard.test.sh`
- Delete: `$HOME/.claude/hooks/main-branch-guard.sh`
- Delete: `$HOME/.claude/hooks/main-branch-guard.test.sh`

**Interfaces:**
- Consumes: Task 1〜4で作成した `workspace-guard.sh` / `system-guard.sh` / `branch-guard.sh` / `venv-guard.sh` の絶対パス（いずれも `$HOME/.claude/hooks/` 配下）

- [ ] **Step 1: settings.json の `hooks.PreToolUse` を新構成に書き換える**

`$HOME/.claude/settings.json` の `"hooks"` キー全体を以下に置き換える（他のキーは変更しない）。3グループに分割し、各フックが実際に必要とするツール種別のみを`matcher`に列挙する（workspace-guard.shはWrite/Edit/MultiEdit/NotebookEditのみ必要になったため、旧来Bashも含む共有matcherから分離する）。

```json
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/home/asama/.claude/hooks/system-guard.sh"
          },
          {
            "type": "command",
            "command": "/home/asama/.claude/hooks/venv-guard.sh"
          }
        ]
      },
      {
        "matcher": "Write|Edit|MultiEdit|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "/home/asama/.claude/hooks/workspace-guard.sh"
          }
        ]
      },
      {
        "matcher": "Write|Edit|MultiEdit|NotebookEdit|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/home/asama/.claude/hooks/branch-guard.sh"
          }
        ]
      }
    ]
  },
```

- [ ] **Step 2: hooks.md（正典ドキュメント）を新構成に合わせて書き換える**

`$HOME/.claude/rules/hooks.md` を以下の内容で全面上書きする。

```markdown
# Hooks（enforcement の正典）

| Hook | 効果 |
|------|------|
| system-guard.sh | 場所を問わずシステム全体を破壊しうるコマンドのみを無条件ブロックする単純な1層構成。<br>カテゴリ: ディスク・デバイス破壊（`dd`/`mkfs`/`shred`の`/dev/`対象）・パーミッション破壊（`chown -R .../`）・プロセス/システム停止（`kill -9 -1`・フォーク爆弾・`shutdown`/`halt`/`reboot`/`poweroff`/`init 0`/`init 6`/`systemctl poweroff`等）・危険なリモート実行（`curl\|bash`等）・システムファイル破壊（`/etc/hosts`等への書込・`PATH`破壊）・DB破壊（`DROP DATABASE`/`TABLE`/`SCHEMA`・`TRUNCATE TABLE`）・グローバルパッケージ導入（`npm -g`等）/削除（`apt purge -y`等）・**システムパッケージのupdate/upgrade**（`apt update`/`apt upgrade`/`apt dist-upgrade`・`brew upgrade`・`yum update`/`upgrade`・`dnf update`/`upgrade`等）・ファイル内容消去（`truncate -s 0`）・スケジューラ破壊（`crontab -r`）。<br>Python経由の削除（`shutil.rmtree`/`os.remove`/`os.unlink`/`os.rmdir`）、および`python`/`perl`/`ruby`/`node`の`-c`/`-e`ワンライナー経由での機密ファイル読取は、静的にゾーン判定できないため無条件ブロックのまま維持。<br>クォート分割/バックスラッシュ/`${IFS}`等の難読化は正規化後に再判定してブロックする。<br>jq 不在時 fail-close。ブロック時は `! <コマンド>` 形式で依頼せよ |
| workspace-guard.sh | Write/Edit/MultiEdit/NotebookEdit: プロジェクト配下／`$CLAUDE_HOME`配下／`/tmp/claude-*/`配下（セッション用）以外への書き込みをブロック。<br>Bashコマンド経由の書込み・削除（`rm`/`cp`/`mv`等）はこのフックの対象外（2026-08-29再設計でスコープを縮小。プロジェクト外への個別ファイル操作は意図的に無防備。詳細は`docs/specs/2026-08-29-hooks-redesign-design.md`参照）。<br>誤検知時は Read で回避せよ |
| venv-guard.sh | venv 外への `pip install`/`pip uninstall`/`uv add` 等をブロック。`VIRTUAL_ENV`環境変数ベースの文字列一致で誤検知しうるが、例外は認めない方針（誤検知時の回避経路は用意しない）。回避が必要な場合は Read で内容確認の上、判断せよ |
| branch-guard.sh | main/master ブランチ上での Write/Edit/MultiEdit/NotebookEdit、および Bash の削除・変更系コマンド（`rm`/`mv`/`cp`/`tee`/`touch`/リダイレクト/`sed -i`/`git commit`/`git rm`等）をブロック。<br>読み取り専用コマンド、および対象パスが全てプロジェクト外かつ`$CLAUDE_HOME`外の単純な rm/rmdir/unlink/mv/cp/touch/sed -i は対象外。<br>`.git`ディレクトリへの書込み権限が無い場合（ブランチ作成が実行不能な環境）は自動検知し、警告のみで許容する（`$CLAUDE_HOME`配下の`branch-guard-bypass.log`へ毎回記録=監査証跡）。<br>ローカルの当該ブランチが `origin/<branch>` の祖先で、かつ異なるコミットの場合のみ、ネットワークアクセスなしで `warn_if_stale()` が警告を追加する（`origin/<branch>` 参照が無い場合は対象外）。<br>ブロック時は `git checkout -b <branch>` でブランチを作成してから再試行せよ |
```

- [ ] **Step 3: 旧ファイルを削除する**

Run:
```bash
rm "$HOME/.claude/hooks/bash-guard.sh"
rm "$HOME/.claude/hooks/bash-guard.test.sh"
rm "$HOME/.claude/hooks/main-branch-guard.sh"
rm "$HOME/.claude/hooks/main-branch-guard.test.sh"
```

- [ ] **Step 4: 新4フックのテストを一括実行し、全てALL PASSであることを確認する**

Run:
```bash
for t in workspace-guard branch-guard system-guard venv-guard; do
  echo "=== $t ==="
  bash "$HOME/.claude/hooks/$t.test.sh" | tail -3
done
```
Expected: 4つとも末尾が `ALL PASS`

- [ ] **Step 5: 動作確認のみ（コミットなし）**

`$HOME/.claude/` はgit管理下に無いため、このタスクではコミットしない。Step 4の4件ALL PASSがこのタスクの完了確認。

---

### Task 6: sync-config スキルで my-claude リポジトリへ反映し、コミットする

**Files:**
- Modify（`sync-config`スキル経由で自動生成）: `linux/claude/hooks/workspace-guard.sh` / `linux/claude/hooks/workspace-guard.test.sh` / `linux/claude/hooks/system-guard.sh`（新規） / `linux/claude/hooks/system-guard.test.sh`（新規） / `linux/claude/hooks/branch-guard.sh`（新規） / `linux/claude/hooks/branch-guard.test.sh`（新規） / `linux/claude/hooks/venv-guard.test.sh`（新規） / `linux/claude/settings.json` / `linux/claude/rules/hooks.md`
- Delete（`sync-config`スキル経由で自動生成）: `linux/claude/hooks/bash-guard.sh` / `linux/claude/hooks/bash-guard.test.sh` / `linux/claude/hooks/main-branch-guard.sh` / `linux/claude/hooks/main-branch-guard.test.sh`

**Interfaces:**
- Consumes: Task 1〜5で `$HOME/.claude/` に反映済みの新4フック・settings.json・hooks.md

- [ ] **Step 1: `sync-config` スキルを実行し、`~/.claude/` の内容を `linux/claude/` ミラーへコピーする**

`sync-config` スキルを起動する（コピーのみ、commit・pushは行わない）。

- [ ] **Step 2: 反映内容を確認する**

Run: `git -C /home/asama/my-claude status --short`
Expected: 以下のファイルが変更・新規・削除として現れる（他の意図しない差分が無いことを確認する）:
- `M  linux/claude/hooks/workspace-guard.sh`
- `M  linux/claude/hooks/workspace-guard.test.sh`
- `A  linux/claude/hooks/system-guard.sh`
- `A  linux/claude/hooks/system-guard.test.sh`
- `A  linux/claude/hooks/branch-guard.sh`
- `A  linux/claude/hooks/branch-guard.test.sh`
- `A  linux/claude/hooks/venv-guard.test.sh`
- `D  linux/claude/hooks/bash-guard.sh`
- `D  linux/claude/hooks/bash-guard.test.sh`
- `D  linux/claude/hooks/main-branch-guard.sh`
- `D  linux/claude/hooks/main-branch-guard.test.sh`
- `M  linux/claude/settings.json`
- `M  linux/claude/rules/hooks.md`

- [ ] **Step 3: ユーザーに差分を提示し、コミットしてよいか確認する**

このステップはユーザー承認が必要（CLAUDE.mdの方針により、コミットは明示的な依頼があった場合のみ実施する）。承認が得られたら以下でコミットする。

Run:
```bash
git -C /home/asama/my-claude add linux/claude/hooks linux/claude/settings.json linux/claude/rules/hooks.md
git -C /home/asama/my-claude commit -m "$(cat <<'EOF'
refactor: hooksを4本構成へ再設計(場所/ブランチ/絶対破壊性/Python環境で責務分離)

bash-guard.sh/workspace-guard.sh/main-branch-guard.sh/venv-guard.shを
削除し、責務軸を直交させたworkspace-guard.sh(縮小)/branch-guard.sh/
system-guard.sh/venv-guard.shの新4構成へ置換した。

- workspace-guard.sh: Bash側ゾーン判定を全廃、Write/Edit系専用に縮小
- branch-guard.sh: main-branch-guard.shの環境変数バイパスを.git書込み
  権限の自動検知に置換(CRITICAL指摘だった間接的自己バイパス経路を解消)
- system-guard.sh: bash-guard.shを改名、システムパッケージの
  update/upgradeパターンを追加
- venv-guard.sh: 実装は変更なし、テストを新設

詳細: docs/specs/2026-08-29-hooks-redesign-design.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JBc1zL3cYiui33CP47Rj9v
EOF
)"
```

- [ ] **Step 4: コミット結果を確認する**

Run: `git -C /home/asama/my-claude log --oneline -1 && git -C /home/asama/my-claude status --short`
Expected: 直前のコミットが新規に追加され、`git status --short`が空（未コミット差分なし）
