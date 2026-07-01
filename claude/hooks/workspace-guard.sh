#!/bin/bash
# workspace-guard.sh — PreToolUse フック
# プロジェクト配下と ~/.claude 配下以外へのファイル作成・編集をブロックする。
# Write/Edit/MultiEdit/NotebookEdit: 対象 file_path が許可ゾーン外なら exit 2。
# Bash: /tmp・/var/tmp へのリダイレクト(> / >>)のみ保守的にブロック。
#
# 許可ゾーン:
#   1) プロジェクトルート($PROJECT_DIR=pwd)配下
#   2) ~/.claude(=${CLAUDE_CONFIG_DIR:-$HOME/.claude})配下
#      （plan ファイル・メモリ・設定管理ワークフローを壊さないための例外）
#   3) ハーネスのセッション scratchpad(/tmp/claude-*/.../scratchpad)配下
#      （ハーネスが一時領域として提供。サブエージェントのレポート受け渡し等に使う）
#
# 既知の限界: Bash のファイル書き込み全検出は不可能なため /tmp リダイレクトのみ検査。
# 文字列中に "> /tmp/" 等を含むコマンド(grep 等)は誤ブロックされ得る。
# その場合は Read ツールで回避すること（bash-guard.sh / venv-guard.sh と同種の制約）。

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
    "$PROJECT_DIR" | "$PROJECT_DIR"/*) return 0 ;;
    "$CLAUDE_HOME" | "$CLAUDE_HOME"/*) return 0 ;;
    # ハーネスのセッション scratchpad（サンクションされた一時領域）は許可。
    # case の '*' はスラッシュも跨ぐため uid/project/session の各セグメントに一致する。
    /tmp/claude-*/scratchpad | /tmp/claude-*/scratchpad/*) return 0 ;;
    *) return 1 ;;
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
    ;;
esac

exit 0
