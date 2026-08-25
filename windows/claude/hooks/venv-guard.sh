#!/bin/bash
command -v jq >/dev/null 2>&1 || { echo "❌ venv-guard: jq not found, failing closed" >&2; exit 2; }
# ── Windows(Git Bash)対応 ──────────────────────────────────────────
# Windows では $VIRTUAL_ENV が C:\... 形式で渡る一方 $(pwd) は MSYS 形式(/c/...)。
# 正規化しないと前方一致が必ず失敗し、プロジェクト直下の正しい venv であっても
# 「venvがプロジェクトフォルダ外です」で誤ブロックされる。
case "${OSTYPE:-}" in msys* | cygwin*) export LC_ALL="${LC_ALL:-C.UTF-8}" ;; esac

to_posix() {
  local p="${1//\\//}"                                                      # \ → /
  case "$p" in
    [A-Za-z]:/*) p="/$(printf '%s' "${p%%:*}" | tr 'A-Z' 'a-z')${p#*:}" ;;  # C:/x → /c/x
  esac
  printf '%s' "$p"
}

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

PROJECT_DIR=$(to_posix "$(pwd)")
VENV_DIR=$(to_posix "${VIRTUAL_ENV:-}")

# ── venv パス直接指定の早期許可 ─────────────────────────────────────────────
# /path/to/.venv/bin/pip install や .venv/bin/pip install のように
# venv バイナリを明示指定している場合は venv 内とみなして許可する
if echo "$COMMAND" | grep -qE '([./]venv|\.venv)[/\\](bin|Scripts)[/\\]pip[0-9.]*(\.exe)?\s+(install|uninstall)'; then
  echo "✅ pip: venv バイナリ直接指定のため許可" >&2
  exit 0
fi

# ── pip install チェック（pip / pip3 / python -m pip）──
# VIRTUAL_ENV が実際にセットされている場合のみ許可する。
# .venv ディレクトリが存在するだけでは system pip を許可しない（未 activate のため）。
if echo "$COMMAND" | grep -qE '(^|&&|;)\s*(pip3?\s+install|python[0-9.]*\s+-m\s+pip\s+install)'; then
  if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ pip install はvenv内でのみ許可されています（VIRTUAL_ENV 未設定）。" >&2
    echo "   venv を有効化するか、venv 内 pip を明示してください:" >&2
    echo "   Linux/macOS: source .venv/bin/activate && pip install ...   /   .venv/bin/pip install ..." >&2
    echo "   Windows:     source .venv/Scripts/activate && pip install ...   /   .venv/Scripts/pip install ..." >&2
    exit 2
  fi
  if [[ "$VENV_DIR" != "$PROJECT_DIR"* ]]; then
    echo "❌ venvがプロジェクトフォルダ外です。" >&2
    echo "   現在のvenv: $VIRTUAL_ENV" >&2
    echo "   プロジェクト: $PROJECT_DIR" >&2
    exit 2
  fi
  echo "✅ pip install: venv確認OK" >&2
  exit 0
fi

# ── pip uninstall チェック（pip / pip3 / python -m pip）──
# VIRTUAL_ENV が実際にセットされている場合のみ許可する。
if echo "$COMMAND" | grep -qE '(^|&&|;)\s*(pip3?\s+uninstall|python[0-9.]*\s+-m\s+pip\s+uninstall)'; then
  if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ pip uninstall はvenv内でのみ許可されています（VIRTUAL_ENV 未設定）。" >&2
    echo "   venv を有効化するか、venv 内 pip を明示してください:" >&2
    echo "   Linux/macOS: source .venv/bin/activate && pip uninstall ...   /   .venv/bin/pip uninstall ..." >&2
    echo "   Windows:     source .venv/Scripts/activate && pip uninstall ...   /   .venv/Scripts/pip uninstall ..." >&2
    exit 2
  fi
  if [[ "$VENV_DIR" != "$PROJECT_DIR"* ]]; then
    echo "❌ venvがプロジェクトフォルダ外です。" >&2
    echo "   現在のvenv: $VIRTUAL_ENV" >&2
    echo "   プロジェクト: $PROJECT_DIR" >&2
    exit 2
  fi
  echo "✅ pip uninstall: venv確認OK" >&2
  exit 0
fi

# ── uv add / uv pip install チェック ───────────────
if echo "$COMMAND" | grep -qE '(^|&&|\|)\s*uv\s+(add|pip\s+install)'; then
  # プロジェクト配下に .venv があるかチェック
  if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "❌ uv: プロジェクト配下に .venv が見つかりません。" >&2
    echo "   先に: uv venv または uv init を実行してください" >&2
    exit 2
  fi
  echo "✅ uv: .venv確認OK: $PROJECT_DIR/.venv" >&2
  exit 0
fi

exit 0
