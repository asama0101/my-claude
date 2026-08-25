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

CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

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

# upstream追跡ブランチに対しfast-forward可能な祖先（かつ差分あり）なら
# git pull を促すヒント行を stderr に出す。upstream未設定・diverged等は何もしない。
print_pull_hint_if_ff() {
  local dir="$1" upstream local_rev remote_rev
  upstream=$(git -C "$dir" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null) || return 0
  [ -z "$upstream" ] && return 0
  local_rev=$(git -C "$dir" rev-parse HEAD 2>/dev/null)
  remote_rev=$(git -C "$dir" rev-parse "$upstream" 2>/dev/null)
  [ -z "$local_rev" ] && return 0
  [ -z "$remote_rev" ] && return 0
  [ "$local_rev" = "$remote_rev" ] && return 0
  if git -C "$dir" merge-base --is-ancestor HEAD "$upstream" 2>/dev/null; then
    echo "   ヒント: ローカルは ${upstream} に対して fast-forward 可能です。'git pull' で追従してから再試行してください。" >&2
  fi
}

# 単一コマンド（rm/rmdir/unlink・mv・cp・touch・sed -i）が、全対象パスを
# プロジェクト外かつ $CLAUDE_HOME 外に持つ場合のみ真を返す。パイプ・リダイレクト・
# 複合コマンド・改行・cd・安全文字集合外の文字を含む場合や sed に -i が無い場合は
# 偽（従来通りブロック）。$CLAUDE_HOME を除外しないと、cp/mv/touch/sed -i でフック
# 自身（main-branch-guard.sh等）を保護ブランチ上から書き換えられてしまうため必須。
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
  # 改行は tr で許可集合外の \v に変換してから判定する（grep は行単位評価のため
  # 生の改行は素通りし、複数行コマンドの2行目以降が無検査になる穴を防ぐ）。
  printf '%s' "$cmd" | tr '\n' '\v' | grep -qP '[^A-Za-z0-9 \t_./*?-]' && return 1
  printf '%s' "$cmd" | grep -qiP '\bcd\b' && return 1
  set -f
  for tok in $cmd; do
    idx=$((idx + 1))
    if [ "$idx" -eq 1 ]; then continue; fi   # コマンド名は先頭トークン(位置)でスキップ。
                                              # 値一致だと「コマンド名と同名の引数」
                                              # (例: cp /tmp/x cp)を誤ってスキップする。
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

case "$TOOL" in
  Write | Edit | MultiEdit | NotebookEdit)
    FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
    [ -z "$FILE" ] && exit 0
    ABS=$(realpath -m "$FILE" 2>/dev/null) || ABS="$FILE"
    DIR=$(dirname -- "$ABS")
    BRANCH=$(get_branch "$DIR")
    if is_protected "$BRANCH"; then
      echo "❌ BLOCKED: ${BRANCH}ブランチ上でのファイル変更は禁止されています: $FILE" >&2
      echo "   先に 'git checkout -b <branch-name>' でブランチを作成してから再試行してください。" >&2
      print_pull_hint_if_ff "$DIR"
      exit 2
    fi
    ;;
  Bash)
    CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
    PROJECT_DIR=$(pwd)

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
        if bash_targets_outside_project "$CMD" "$PROJECT_DIR"; then
          exit 0
        fi
        echo "❌ BLOCKED: ${BRANCH}ブランチ上でのファイル変更は禁止されています: $CMD" >&2
        echo "   先に 'git checkout -b <branch-name>' でブランチを作成してから再試行してください。" >&2
        print_pull_hint_if_ff "$PROJECT_DIR"
        exit 2
      fi
    fi
    ;;
esac

exit 0
