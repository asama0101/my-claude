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
