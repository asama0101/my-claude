#!/bin/bash
# main-branch-guard.sh — PreToolUse フック
# main/masterブランチ上でのファイル作成・削除・編集をブロックする。
#
# Write/Edit/MultiEdit/NotebookEdit: 対象ファイルが git 管理下で現在ブランチが
# main/master なら exit 2。
# Bash: 削除・変更系コマンド（rm/mv/cp/tee/touch/sed -i/リダイレクト/git commit/git rm 等）
# のみを対象に、cwd の git ブランチが main/master なら exit 2。読み取り専用コマンド
# （git status/cat/ls/grep 等）は対象外。
# find -delete/shutil.rmtree/rsync --delete は bash-guard.sh がブランチに関係なく
# 常時無条件ブロックするため、ここには含めない（含めても到達不能な重複ロジックになるため）。
#
# 既知の限界: scripts/sync.sh のようなラッパースクリプトの呼び出し自体は、Bash
# に渡る文字列がスクリプト名のみで内部コマンドが見えないため検知できない。
# リダイレクト検知は `2>/dev/null` 等の破棄リダイレクトは除外済みだが、それ以外の
# 文字列中に "> " を含む read-only コマンド（grep等）は誤検知しうる
# （bash-guard.sh / workspace-guard.sh と同種の制約。回避は Read）。

command -v jq >/dev/null 2>&1 || { echo "❌ main-branch-guard: jq not found, failing closed" >&2; exit 2; }

# ── Windows(Git Bash)対応 ──────────────────────────────────────────
# 1) 既定ロケール(CP932等)では grep -P が "supports only unibyte and UTF-8 locales"
#    で失敗し終了ステータス2を返す。下の MUTATING_PATTERNS 判定は
#    `if ... grep -qiP ...; then` 形式でエラー(2)を「不一致」と同じ扱いにするため、
#    ロケールを明示しないと変更系コマンドの検知が黙って fail-open する。
# 2) フックに渡る file_path は Windows 形式(C:\...)。MSYS の realpath は C:\x を C:/x に
#    直すだけなので、正規化しないと dirname/git -C に渡るパスが壊れる。
case "${OSTYPE:-}" in msys* | cygwin*) export LC_ALL="${LC_ALL:-C.UTF-8}" ;; esac

to_posix() {
  local p="${1//\\//}"                                                      # \ → /
  case "$p" in
    [A-Za-z]:/*) p="/$(printf '%s' "${p%%:*}" | tr 'A-Z' 'a-z')${p#*:}" ;;  # C:/x → /c/x
  esac
  printf '%s' "$p"
}

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')

# git 管理下でなければ空文字を返す。
get_branch() {
  local dir="$1"
  git -C "$dir" rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo ""; return; }
  git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null
}

is_protected() {
  case "$1" in
    main | master) return 0 ;;
    *) return 1 ;;
  esac
}

case "$TOOL" in
  Write | Edit | MultiEdit | NotebookEdit)
    FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
    [ -z "$FILE" ] && exit 0
    ABS=$(realpath -m "$FILE" 2>/dev/null) || ABS="$FILE"
    ABS=$(to_posix "$ABS")
    DIR=$(dirname -- "$ABS")
    BRANCH=$(get_branch "$DIR")
    if is_protected "$BRANCH"; then
      echo "❌ BLOCKED: ${BRANCH}ブランチ上でのファイル変更は禁止されています: $FILE" >&2
      echo "   先に 'git checkout -b <branch-name>' でブランチを作成してから再試行してください。" >&2
      exit 2
    fi
    ;;
  Bash)
    CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
    PROJECT_DIR=$(to_posix "$(pwd)")

    MUTATING_PATTERNS=(
      '\b(rm|rmdir|unlink)\b'                       # 削除
      '\bgit\s+rm\b'                                 # git rm
      '\bgit\s+commit\b'                             # git commit（--amend含む）
      '>>?(?!&)[[:space:]]*(?!/dev/null\b)[^[:space:]]' # リダイレクト書き込み（先頭境界不要。2>&1等のfd複製・/dev/null宛の破棄は除外）
      '\btee\b'
      '\bcp\b'
      '\bmv\b'
      '\btouch\b'
      'sed\s+-i'                                     # sed インプレース編集
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
        echo "❌ BLOCKED: ${BRANCH}ブランチ上でのファイル変更は禁止されています: $CMD" >&2
        echo "   先に 'git checkout -b <branch-name>' でブランチを作成してから再試行してください。" >&2
        exit 2
      fi
    fi
    ;;
esac

exit 0
