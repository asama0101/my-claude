#!/bin/bash
# workspace-guard.sh — PreToolUse フック
# Write/Edit/MultiEdit/NotebookEdit の書込み先が、プロジェクト配下・$CLAUDE_HOME
# 配下・Claude Codeのセッション用一時ディレクトリ(/tmp/claude-*/配下、Windowsでは
# $LOCALAPPDATA/Temp/claude/配下)のいずれでもない場合にブロックする。
#
# 許可ゾーン:
#   1) プロジェクトルート($PROJECT_DIR=pwd)配下
#   2) $CLAUDE_HOME(=${CLAUDE_CONFIG_DIR:-$HOME/.claude})配下（hooks/settings.json含む。
#      設定管理ワークフロー自体がhooks/settingsの編集を要するため自己防御は設けない。
#      settings.json の permissions.ask 側で実行前確認を挟む二重防御に委ねる）
#   3) /tmp/claude-*/配下（Claude Code自身のセッション固有一時ディレクトリ）
#   4) $LOCALAPPDATA/Temp/claude/配下（Windows版セッション用スクラッチパッド。3)のWindows版）
#
# 既知の限界:
#   - nodeが存在してもINPUTが不正JSONの場合、TOOLが空文字になりどのcase分岐にも
#     一致せず素通しでexit 0になる（fail-closeはnode自体の不在時のみ保証）。
#     Claude Code自身が生成する入力なので通常は整形式JSON。
#   - Bashコマンド経由の書込み・削除（rm/cp/mv等）はこのフックの対象外。
#     場所を問わない絶対破壊コマンドはsystem-guard.shが担当し、それ以外の
#     プロジェクト外への個別ファイル操作は意図的に無防備（設計上の既知のリスク、
#     docs/specs/2026-08-29-hooks-redesign-design.md 参照）。

source "${BASH_SOURCE[0]%/*}/lib/json-field.sh"
has_json_backend || { echo "❌ workspace-guard: node not found, failing closed" >&2; exit 2; }

# ── Windows(Git Bash)対応 ──────────────────────────────────────────
# 1) 既定ロケール(CP932等)では grep -P が "supports only unibyte and UTF-8 locales"
#    で失敗し終了ステータス2を返す(本ファイル自体はgrepを使わないが、他フックとの
#    一貫性のため踏襲する)。
# 2) フックに渡る file_path は Windows 形式(C:\...)になり得るが $(pwd)/$HOME は
#    MSYS 形式(/c/...)。MSYS の realpath は C:\x を C:/x に直すだけで /c/x にはしない
#    ため、正規化しないと前方一致比較が必ず失敗する。
case "${OSTYPE:-}" in msys* | cygwin*) export LC_ALL="${LC_ALL:-C.UTF-8}" ;; esac

to_posix() {
  local p="${1//\\//}"                                                      # \ → /
  case "$p" in
    [A-Za-z]:/*) p="/$(printf '%s' "${p%%:*}" | tr 'A-Z' 'a-z')${p#*:}" ;;  # C:/x → /c/x
  esac
  # NTFS はパスの大文字小文字を区別しないため、ゾーン前方一致比較
  # （"$PROJECT_DIR"/* 等）が大文字小文字違いだけで誤って不一致判定
  # されないよう、Windows(msys/cygwin)上でのみ全体を小文字化する。
  case "${OSTYPE:-}" in msys* | cygwin*) p=$(printf '%s' "$p" | tr 'A-Z' 'a-z') ;; esac
  printf '%s' "$p"
}

INPUT=$(cat)
TOOL=$(json_field "$INPUT" tool_name)
PROJECT_DIR=$(to_posix "$(pwd)")
CLAUDE_HOME=$(to_posix "${CLAUDE_CONFIG_DIR:-$HOME/.claude}")

# Windows版セッション用スクラッチパッドのアンカー基点。$LOCALAPPDATA未設定時は
# 空文字列のままにする(""/* が /* に展開され任意の絶対パスに誤マッチするcase文の
# 罠を避けるため)。以降はこの変数を直接case文で参照せず、必ず_wg_in_win_temp_claude
# ヘルパー経由で参照すること(実装上の必須要件)。
WIN_TEMP_CLAUDE=""
[ -n "${LOCALAPPDATA:-}" ] && WIN_TEMP_CLAUDE=$(to_posix "${LOCALAPPDATA}/Temp/claude")

# ルート自体を含めた前方一致判定。
_wg_in_win_temp_claude() {
  [ -n "$WIN_TEMP_CLAUDE" ] || return 1
  case "$1" in
    "$WIN_TEMP_CLAUDE" | "$WIN_TEMP_CLAUDE"/*) return 0 ;;
    *) return 1 ;;
  esac
}

is_allowed() {
  local path="$1"
  local abs
  # 未存在ファイルも解決（相対パスは PROJECT_DIR 基準）
  abs=$(realpath -m "$path" 2>/dev/null) || abs="$path"
  abs=$(to_posix "$abs")
  case "$abs" in
    "$PROJECT_DIR" | "$PROJECT_DIR"/*) return 0 ;;
    "$CLAUDE_HOME" | "$CLAUDE_HOME"/*) return 0 ;;
    /tmp/claude-*/*) return 0 ;;
  esac
  # Windows: $LOCALAPPDATA/Temp/claude/<project>/<session>/ 配下(アンカー付き前方一致。
  # 無アンカーcaseパターンだと "temp/claude" を部分文字列に含むだけの任意パスが
  # 誤って許可されてしまうため、_wg_in_win_temp_claude() 経由でのみ判定する)。
  _wg_in_win_temp_claude "$abs"
}

case "$TOOL" in
  Write | Edit | MultiEdit | NotebookEdit)
    FILE=$(json_field "$INPUT" tool_input.file_path tool_input.notebook_path)
    [ -z "$FILE" ] && exit 0
    if ! is_allowed "$FILE"; then
      echo "❌ BLOCKED: プロジェクト外への書き込み: $FILE" >&2
      echo "   許可範囲: プロジェクト配下($PROJECT_DIR) または $CLAUDE_HOME 配下 または /tmp/claude-*/配下 または $LOCALAPPDATA/Temp/claude/配下" >&2
      exit 2
    fi
    ;;
esac

exit 0
