#!/bin/bash
# session-retrospective.sh
# Stop フック: 本プロジェクトの新規フィードバックメモリを検出して CLAUDE.md 改善を促す。
# 2026-05-25 検出方式を現行メモリ形式（スラッグ名 + frontmatter type: feedback）に修正。
#            対象を transcript パスから導出した「本プロジェクトの memory/」に限定（全プロジェクト横断をやめる）。

INPUT=$(cat)
MARKER="/home/asama/.claude/logs/last-retrospective"

# 本プロジェクトの memory ディレクトリを transcript パスから導出
# transcript: ~/.claude/projects/<sanitized-cwd>/<session>.jsonl → 同階層の memory/
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[ -z "$TRANSCRIPT" ] && exit 0
MEMORY_DIR="$(dirname "$TRANSCRIPT")/memory"
[ -d "$MEMORY_DIR" ] || exit 0

# frontmatter に type: feedback を持つ *.md を抽出（任意で -newer フィルタを適用）
find_feedback() {
  find "$MEMORY_DIR" -maxdepth 1 -name '*.md' "$@" 2>/dev/null | while IFS= read -r f; do
    grep -qE '^[[:space:]]*type:[[:space:]]*feedback[[:space:]]*$' "$f" 2>/dev/null && echo "$f"
  done
}

if [ -f "$MARKER" ]; then
  RECENT=$(find_feedback -newer "$MARKER")
else
  RECENT=$(find_feedback)
fi

if [ -n "$RECENT" ]; then
  echo ""
  echo "=== 本セッションの学び（フィードバックメモリ更新） ==="
  while IFS= read -r f; do
    NAME=$(grep '^name:' "$f" 2>/dev/null | head -1 | sed 's/^name:[[:space:]]*//')
    DESC=$(grep '^description:' "$f" 2>/dev/null | head -1 | sed 's/^description:[[:space:]]*//')
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
