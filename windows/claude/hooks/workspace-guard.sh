#!/bin/bash
# workspace-guard.sh — PreToolUse フック
# プロジェクト配下・~/.claude 配下・Claude Code のセッション用一時ディレクトリ
# (/tmp/claude-*/配下)以外へのファイル作成・編集をブロックする。
# Write/Edit/MultiEdit/NotebookEdit: 対象 file_path が許可ゾーン外なら exit 2。
# Bash: /var/tmp・および /tmp/claude-*/以外の /tmp 配下へのリダイレクト(> / >>)＋
#       cp/tee/mv/curl/wget のプロジェクト外宛先を保守的にブロック。
#
# 許可ゾーン:
#   1) プロジェクトルート($PROJECT_DIR=pwd)配下
#   2) ~/.claude(=${CLAUDE_CONFIG_DIR:-$HOME/.claude})配下（hooks/settings.json含む。
#      設定管理ワークフロー自体がhooks/settingsの編集を要するため自己防御は設けない。
#      settings.json の permissions.ask 側で実行前確認を挟む二重防御に委ねる）
#   3) /tmp/claude-*/配下（Claude Code自身のセッション固有一時ディレクトリ:
#      スクラッチパッド・サブエージェントのタスク出力等。/tmp 直下や無関係な
#      /tmp配下ディレクトリ、/var/tmp は対象外）
#
# 既知の限界: Bash のファイル書き込み全検出は不可能なため /var/tmp・/tmp(claude-*以外)
# リダイレクト＋ cp/tee/mv/curl/wget の主要経路のみ検査（完全検出ではない）。
# 文字列中に "> /var/tmp/" 等を含むコマンド(grep 等)は誤ブロックされ得る。
# その場合は Read ツールで回避すること（bash-guard.sh / venv-guard.sh と同種の制約）。

# jq 不在時は fail-close（PreToolUse ガードなので判定不能なら安全側に倒して exit 2）。
command -v jq >/dev/null 2>&1 || { echo "❌ workspace-guard: jq not found, failing closed" >&2; exit 2; }

# ── Windows(Git Bash)対応 ──────────────────────────────────────────
# 1) 既定ロケール(CP932等)では grep -P が "supports only unibyte and UTF-8 locales"
#    で失敗し終了ステータス2を返す。if 条件では「不一致」と同じ扱いになるため、
#    ロケールを明示しないと危険パターン判定が黙って fail-open する。
# 2) フックに渡る file_path は Windows 形式(C:\...)だが $(pwd)/$HOME は MSYS 形式(/c/...)。
#    MSYS の realpath は C:\x を C:/x に直すだけで /c/x にはしないため、正規化しないと
#    前方一致比較が必ず失敗し、プロジェクト配下でも「外部」と誤判定される。
case "${OSTYPE:-}" in msys* | cygwin*) export LC_ALL="${LC_ALL:-C.UTF-8}" ;; esac

to_posix() {
  local p="${1//\\//}"                                                      # \ → /
  case "$p" in
    [A-Za-z]:/*) p="/$(printf '%s' "${p%%:*}" | tr 'A-Z' 'a-z')${p#*:}" ;;  # C:/x → /c/x
  esac
  printf '%s' "$p"
}

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
PROJECT_DIR=$(to_posix "$(pwd)")
CLAUDE_HOME=$(to_posix "${CLAUDE_CONFIG_DIR:-$HOME/.claude}")

is_allowed() {
  local path="$1"
  local abs
  # 未存在ファイルも解決（相対パスは PROJECT_DIR 基準）
  abs=$(realpath -m "$path" 2>/dev/null) || abs="$path"
  abs=$(to_posix "$abs")
  case "$abs" in
    "$PROJECT_DIR" | "$PROJECT_DIR"/*) return 0 ;;
    "$CLAUDE_HOME" | "$CLAUDE_HOME"/*) return 0 ;;
    /tmp/claude-*/*) return 0 ;;  # Claude Code 自身のセッション用ディレクトリのみ許可
    */[Tt]emp/claude/*) return 0 ;;  # Windows: %LOCALAPPDATA%\Temp\claude\<project>\<session>\ 配下
    *) return 1 ;;
  esac
}

# cp/tee/mv/curl/wget 宛先の外部判定（保守的）。
# 絶対パスのみ検査し、相対/判定不能はブロックしない。
is_ext_dest() {
  local path="$1" abs
  case "$path" in
    \~/*) path="$HOME/${path#\~/}" ;;  # ~/... を $HOME 基準の絶対パスへ展開（~はcaseパターン解析時に
    \~) path="$HOME" ;;                # チルダ展開されるため \~ でエスケープ必須）
  esac
  path=$(to_posix "$path")
  case "$path" in
    /*) ;;         # 明確な絶対パスのみを検査対象とする
    *) return 1 ;; # 相対パス等は保守的にスルー（ブロックしない）
  esac
  abs=$(realpath -m "$path" 2>/dev/null) || return 1
  abs=$(to_posix "$abs")
  case "$abs" in
    "$PROJECT_DIR" | "$PROJECT_DIR"/*) return 1 ;; # プロジェクト配下 → 許可
    "$CLAUDE_HOME" | "$CLAUDE_HOME"/*) return 1 ;; # $CLAUDE_HOME 配下 → 許可
    /tmp/claude-*/*) return 1 ;;                   # /tmp/claude-* セッション用ディレクトリのみ許可
    */[Tt]emp/claude/*) return 1 ;;                # Windows: Temp\claude\ 配下(スクラッチパッド)も許可
    *) return 0 ;;                                 # 明確な外部絶対パス → ブロック対象
  esac
}

case "$TOOL" in
  Write | Edit | MultiEdit | NotebookEdit)
    FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
    [ -z "$FILE" ] && exit 0
    if ! is_allowed "$FILE"; then
      echo "❌ BLOCKED: プロジェクト外への書き込み: $FILE" >&2
      echo "   許可範囲: プロジェクト配下($PROJECT_DIR) または $CLAUDE_HOME 配下 または /tmp/claude-*/配下" >&2
      echo "   一時ファイルが必要ならプロジェクト配下、または現在のセッションのスクラッチパッド" >&2
      echo "   ディレクトリ(/tmp/claude-*/配下、システムプロンプトで案内されているパス)に作成してください。" >&2
      exit 2
    fi
    ;;
  Bash)
    CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
    if echo "$CMD" | grep -Eq '>>?[[:space:]]*/var/tmp/'; then
      echo "❌ BLOCKED: /var/tmp へのファイル作成は禁止されています: $CMD" >&2
      echo "   一時ファイルはプロジェクト配下、$CLAUDE_HOME 配下、または /tmp/claude-*/配下に作成してください。" >&2
      echo "   ※読み取りコマンド等の誤検知の場合は Read ツールで回避してください。" >&2
      exit 2
    fi

    # /tmp 配下のうち Claude Code 自身のセッション用ディレクトリ(/tmp/claude-*/配下)
    # 以外へのリダイレクトをブロックする（/tmp直下・無関係な/tmp配下ディレクトリ）。
    # 負の先読み(PCRE)で /tmp/claude-<seed>/ から始まらない /tmp/ 配下のみを検出。
    # ※文字列パターンマッチのため realpath 解決は行わない（既知の限界、上記ヘッダー参照）。
    if echo "$CMD" | grep -Pq '>>?[[:space:]]*/tmp/(?!claude-[^/]+/)'; then
      echo "❌ BLOCKED: /tmp 直下または無関係な /tmp 配下へのファイル作成は禁止されています: $CMD" >&2
      echo "   一時ファイルはプロジェクト配下、$CLAUDE_HOME 配下、または現在のセッションの" >&2
      echo "   スクラッチパッドディレクトリ(/tmp/claude-*/配下、システムプロンプト参照)に作成してください。" >&2
      echo "   ※読み取りコマンド等の誤検知の場合は Read ツールで回避してください。" >&2
      exit 2
    fi

    # ── cp/tee/mv/curl/wget のプロジェクト外書き込みを保守的にブロック ──────────────
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
          target="" prev=""
          for tok in "$@"; do
            case "$prev" in -t) target="$tok" ;; esac
            case "$tok" in --target-directory=*) target="${tok#--target-directory=}" ;; esac
            prev="$tok"
            last="$tok"
          done
          if [ -n "$target" ]; then
            is_ext_dest "$target" && ext_hit="$target"
          else
            is_ext_dest "$last" && ext_hit="$last"  # -t/--target-directory 未指定時は最終引数を宛先とみなす
          fi
          ;;
        tee)
          shift
          for tok in "$@"; do
            case "$tok" in -*) continue ;; esac
            is_ext_dest "$tok" && { ext_hit="$tok"; break; }
          done
          ;;
        curl | wget)
          prev=""
          for tok in "$@"; do
            case "$prev" in
              -o | -O | --output | --output-document) is_ext_dest "$tok" && { ext_hit="$tok"; break; } ;;
            esac
            case "$tok" in
              --output=* | --output-document=*) v="${tok#*=}"; is_ext_dest "$v" && { ext_hit="$v"; break; } ;;
            esac
            prev="$tok"
          done
          ;;
      esac
      [ -n "$ext_hit" ] && break
    done <<EOF
$SEGMENTS
EOF
    set +f
    if [ -n "$ext_hit" ]; then
      echo "❌ BLOCKED: プロジェクト外への cp/tee/mv/curl/wget 書き込み: $ext_hit" >&2
      echo "   宛先がプロジェクト配下・$CLAUDE_HOME 配下・/tmp/claude-*/配下(セッション用ディレクトリ)" >&2
      echo "   のいずれでもありません。" >&2
      echo "   ※主要経路のみの保守的検査です。誤検知時は宛先をプロジェクト配下にするか手動実行してください。" >&2
      exit 2
    fi
    ;;
esac

exit 0
