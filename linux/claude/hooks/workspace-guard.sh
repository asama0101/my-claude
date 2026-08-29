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
