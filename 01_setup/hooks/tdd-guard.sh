#!/bin/bash
# PostToolUse: Write/Edit で tests/ 外の *.py ファイルを編集したとき tdd-guide 使用を促す
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# .py ファイルでなければスキップ
[[ "$FILE" != *.py ]] && exit 0

# tests/ 配下 または test_*.py ならスキップ
[[ "$FILE" == */tests/* ]] && exit 0
[[ "$FILE" == */test_*.py ]] && exit 0
[[ "$(basename "$FILE")" == test_*.py ]] && exit 0

echo "⚠️  [tdd-guard] 実装ファイルを編集しました: $(basename "$FILE")" >&2
echo "   tdd-guide エージェントを使って TDD（テストファースト）で開発しましたか？" >&2
echo "   汎用 claude エージェントで代替しないこと（CLAUDE.md 参照）" >&2
exit 0
