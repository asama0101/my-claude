#!/bin/bash
set -euo pipefail

# show-ledger.sh — ledger.json（許容差分の台帳）をMarkdown表に整形して表示する。
# 同じファイルに複数エントリ（履歴）があれば記録日順に並ぶため、そのまま履歴として読める。
#
# 実装はnode(lib/show-ledger.js)。jqには依存しない(jqがPATH上から消失する事故が実際に発生したため。#37参照)。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LEDGER="$SKILL_DIR/ledger.json"

command -v node >/dev/null 2>&1 || { echo "node が見つかりません。" >&2; exit 1; }

node "$SCRIPT_DIR/lib/show-ledger.js" "$LEDGER"
