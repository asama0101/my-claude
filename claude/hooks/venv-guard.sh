#!/bin/bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

PROJECT_DIR=$(pwd)

# ── venv パス直接指定の早期許可 ─────────────────────────────────────────────
# /path/to/.venv/bin/pip install や .venv/bin/pip install のように
# venv バイナリを明示指定している場合は venv 内とみなして許可する
if echo "$COMMAND" | grep -qE '([./]venv|\.venv)/bin/pip[0-9.]*\s+(install|uninstall)'; then
  echo "✅ pip: venv バイナリ直接指定のため許可" >&2
  exit 0
fi

# ── pip install チェック（pip / pip3 / python -m pip）──
if echo "$COMMAND" | grep -qE '(^|&&|;)\s*(pip3?\s+install|python[0-9.]*\s+-m\s+pip\s+install)'; then
  if [ -z "$VIRTUAL_ENV" ] && [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "❌ pip install はvenv内でのみ許可されています。" >&2
    echo "   python -m venv .venv && source .venv/bin/activate" >&2
    exit 2
  fi
  if [ -n "$VIRTUAL_ENV" ] && [[ "$VIRTUAL_ENV" != "$PROJECT_DIR"* ]]; then
    echo "❌ venvがプロジェクトフォルダ外です。" >&2
    echo "   現在のvenv: $VIRTUAL_ENV" >&2
    echo "   プロジェクト: $PROJECT_DIR" >&2
    exit 2
  fi
  echo "✅ pip install: venv確認OK" >&2
  exit 0
fi

# ── pip uninstall チェック（pip / pip3 / python -m pip）──
if echo "$COMMAND" | grep -qE '(^|&&|;)\s*(pip3?\s+uninstall|python[0-9.]*\s+-m\s+pip\s+uninstall)'; then
  if [ -z "$VIRTUAL_ENV" ] && [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "❌ pip uninstall はvenv内でのみ許可されています。" >&2
    echo "   python -m venv .venv && source .venv/bin/activate" >&2
    exit 2
  fi
  if [ -n "$VIRTUAL_ENV" ] && [[ "$VIRTUAL_ENV" != "$PROJECT_DIR"* ]]; then
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
