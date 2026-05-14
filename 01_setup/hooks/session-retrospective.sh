#!/bin/bash
# セッション終了時に新規フィードバックメモリを検出して CLAUDE.md 改善を促す Stop フック
MARKER="/home/asama/.claude/logs/last-retrospective"
FEEDBACK_DIR="/home/asama/.claude/projects"

if [ -f "$MARKER" ]; then
  RECENT=$(find "$FEEDBACK_DIR" -name "feedback_*.md" -newer "$MARKER" 2>/dev/null)
else
  RECENT=$(find "$FEEDBACK_DIR" -name "feedback_*.md" 2>/dev/null)
fi

if [ -n "$RECENT" ]; then
  echo ""
  echo "=== 本セッションの学び（フィードバックメモリ更新） ==="
  while IFS= read -r f; do
    NAME=$(grep '^name:' "$f" 2>/dev/null | head -1 | sed 's/^name: //')
    DESC=$(grep '^description:' "$f" 2>/dev/null | head -1 | sed 's/^description: //')
    echo "  * ${NAME}: ${DESC}"
  done <<< "$RECENT"
  echo ""
  echo "  CLAUDE.md / Skills を改善するには:"
  echo "     /claude-md-management:claude-md-improver"
  echo "====================================================="
fi

mkdir -p "$(dirname "$MARKER")"
touch "$MARKER"
exit 0
