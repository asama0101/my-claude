#!/bin/bash
# workspace-guard.sh — PreToolUse フック
# プロジェクト配下と ~/.claude 配下以外へのファイル作成・編集をブロックする。
# Write/Edit/MultiEdit/NotebookEdit: 対象 file_path が許可ゾーン外なら exit 2。
# Bash: /tmp・/var/tmp へのリダイレクト(> / >>)＋ cp/tee/mv のプロジェクト外宛先を保守的にブロック。
#
# 許可ゾーン:
#   1) プロジェクトルート($PROJECT_DIR=pwd)配下
#   2) ~/.claude(=${CLAUDE_CONFIG_DIR:-$HOME/.claude})配下
#      （plan ファイル・メモリ・設定管理ワークフローを壊さないための例外）
#   3) ハーネスのセッション scratchpad(/tmp/claude-*/.../scratchpad)配下
#      （ハーネスが一時領域として提供。サブエージェントのレポート受け渡し等に使う）
#
# 既知の限界: Bash のファイル書き込み全検出は不可能なため /tmp リダイレクト＋
# cp/tee/mv の主要経路のみ検査（完全検出ではない）。
# 文字列中に "> /tmp/" 等を含むコマンド(grep 等)は誤ブロックされ得る。
# その場合は Read ツールで回避すること（bash-guard.sh / venv-guard.sh と同種の制約）。

# jq 不在時は fail-close（PreToolUse ガードなので判定不能なら安全側に倒して exit 2）。
command -v jq >/dev/null 2>&1 || { echo "❌ workspace-guard: jq not found, failing closed" >&2; exit 2; }

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
PROJECT_DIR=$(pwd)
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

is_allowed() {
  local path="$1"
  local abs
  # 未存在ファイルも解決（相対パスは PROJECT_DIR 基準）
  abs=$(realpath -m "$path" 2>/dev/null) || abs="$path"
  case "$abs" in
    # ガード実体($CLAUDE_HOME/hooks/)とハーネス設定(settings.json/settings.local.json)は
    # $CLAUDE_HOME 配下でも自己書換を防ぐため先にブロックする（settings.json 側 deny と二重防御）。
    "$CLAUDE_HOME"/hooks/* | "$CLAUDE_HOME"/settings.json | "$CLAUDE_HOME"/settings.local.json) return 1 ;;
    "$PROJECT_DIR" | "$PROJECT_DIR"/*) return 0 ;;
    "$CLAUDE_HOME" | "$CLAUDE_HOME"/*) return 0 ;;
    # ハーネスのセッション scratchpad（サンクションされた一時領域）は許可。
    # case の '*' はスラッシュも跨ぐため uid/project/session の各セグメントに一致する。
    /tmp/claude-*/scratchpad | /tmp/claude-*/scratchpad/*) return 0 ;;
    *) return 1 ;;
  esac
}

# cp/tee/mv 宛先の外部判定（保守的）。
# is_allowed の hooks 自己ブロックは適用しない：$CLAUDE_HOME 配下は許可扱いとし
# 正当な設定反映 cp を妨げない。絶対パスのみ検査し、相対/判定不能はブロックしない。
is_ext_dest() {
  local path="$1" abs
  case "$path" in
    /*) ;;         # 明確な絶対パスのみを検査対象とする
    *) return 1 ;; # 相対パス等は保守的にスルー（ブロックしない）
  esac
  abs=$(realpath -m "$path" 2>/dev/null) || return 1
  case "$abs" in
    "$PROJECT_DIR" | "$PROJECT_DIR"/*) return 1 ;;                     # プロジェクト配下 → 許可
    "$CLAUDE_HOME" | "$CLAUDE_HOME"/*) return 1 ;;                     # $CLAUDE_HOME 配下 → 許可（設定反映 cp を許す）
    /tmp/claude-*/scratchpad | /tmp/claude-*/scratchpad/*) return 1 ;; # scratchpad → 許可
    *) return 0 ;;                                                     # 明確な外部絶対パス → ブロック対象
  esac
}

case "$TOOL" in
  Write | Edit | MultiEdit | NotebookEdit)
    FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
    [ -z "$FILE" ] && exit 0
    if ! is_allowed "$FILE"; then
      echo "❌ BLOCKED: プロジェクト外への書き込み: $FILE" >&2
      echo "   許可範囲: プロジェクト配下($PROJECT_DIR) または $CLAUDE_HOME 配下" >&2
      echo "   一時ファイルが必要ならプロジェクト配下に作成してください。" >&2
      exit 2
    fi
    ;;
  Bash)
    CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
    if echo "$CMD" | grep -Eq '>>?[[:space:]]*/(var/)?tmp/'; then
      # scratchpad(/tmp/claude-*/.../scratchpad/) へのリダイレクトは許可。
      # 該当リダイレクト先を除去してから、残る /tmp リダイレクトの有無で判定する。
      REST=$(echo "$CMD" | sed -E 's#>>?[[:space:]]*/tmp/claude-[^[:space:]]*/scratchpad/[^[:space:]]*##g')
      if echo "$REST" | grep -Eq '>>?[[:space:]]*/(var/)?tmp/'; then
        echo "❌ BLOCKED: /tmp へのファイル作成は禁止されています: $CMD" >&2
        echo "   一時ファイルはプロジェクト配下、または scratchpad(/tmp/claude-*/.../scratchpad/) に作成してください。" >&2
        echo "   ※読み取りコマンド等の誤検知の場合は Read ツールで回避してください。" >&2
        exit 2
      fi
    fi

    # ── cp/tee/mv のプロジェクト外書き込みを保守的にブロック ──────────────
    # 主要経路のみ・完全検出ではない（複雑な引数・エイリアス等は検出外）。
    # 明確な外部絶対パス宛先($HOME 直下や許可ゾーン外の絶対パス)のみを対象とする。
    # コマンド置換を含むセグメントは宛先を確定できないため保守的にスルーする。
    SEGMENTS=$(printf '%s' "$CMD" | sed -E 's/\|\||&&|;|\|/\n/g')
    ext_hit=""
    set -f
    while IFS= read -r seg; do
      printf '%s' "$seg" | grep -qE '`|\$\(' && continue   # コマンド置換 → スルー
      set -- $seg
      [ $# -eq 0 ] && continue
      c="$1"
      case "$c" in
        cp | mv)
          for last in "$@"; do :; done   # 最終引数を宛先とみなす
          is_ext_dest "$last" && ext_hit="$last"
          ;;
        tee)
          shift
          for tok in "$@"; do
            case "$tok" in -*) continue ;; esac
            is_ext_dest "$tok" && { ext_hit="$tok"; break; }
          done
          ;;
      esac
      [ -n "$ext_hit" ] && break
    done <<EOF
$SEGMENTS
EOF
    set +f
    if [ -n "$ext_hit" ]; then
      echo "❌ BLOCKED: プロジェクト外への cp/tee/mv 書き込み: $ext_hit" >&2
      echo "   宛先がプロジェクト配下・$CLAUDE_HOME 配下・scratchpad のいずれでもありません。" >&2
      echo "   ※主要経路のみの保守的検査です。誤検知時は宛先をプロジェクト配下にするか手動実行してください。" >&2
      exit 2
    fi
    ;;
esac

exit 0
