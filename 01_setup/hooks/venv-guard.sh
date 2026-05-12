#!/bin/bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

PROJECT_DIR=$(pwd)

# ── pip install チェック（pip / pip3 / python -m pip）──
if echo "$COMMAND" | grep -qE '(^|&&|\|)\s*(pip3?\s+install|python[0-9.]*\s+-m\s+pip\s+install)'; then
  if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ pip install はvenv内でのみ許可されています。" >&2
    echo "   python -m venv .venv && source .venv/bin/activate" >&2
    exit 2
  fi
  if [[ "$VIRTUAL_ENV" != "$PROJECT_DIR"* ]]; then
    echo "❌ venvがプロジェクトフォルダ外です。" >&2
    echo "   現在のvenv: $VIRTUAL_ENV" >&2
    echo "   プロジェクト: $PROJECT_DIR" >&2
    exit 2
  fi
  echo "✅ pip: venv確認OK: $VIRTUAL_ENV" >&2
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
