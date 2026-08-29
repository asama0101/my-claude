#!/bin/bash
set -euo pipefail

# show-ledger.sh — ledger.json（許容差分の台帳）をMarkdown表に整形して表示する。
# 同じファイルに複数エントリ（履歴）があれば記録日順に並ぶため、そのまま履歴として読める。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LEDGER="$SKILL_DIR/ledger.json"

command -v jq >/dev/null 2>&1 || { echo "jq が見つかりません。" >&2; exit 1; }

if [ ! -f "$LEDGER" ] || [ "$(jq 'length' "$LEDGER")" -eq 0 ]; then
  echo "台帳(ledger.json)はまだ空です。許容済みの差分はありません。"
  exit 0
fi

jq -r '
  "| ファイル | 記録日 | 理由 |",
  "|---|---|---|",
  (sort_by(.file, .recorded_at)[] | "| \(.file) | \(.recorded_at) | \(.reason) |")
' "$LEDGER"
