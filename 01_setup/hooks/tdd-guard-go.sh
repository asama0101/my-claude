#!/bin/bash
# PostToolUse: Write/Edit で *_test.go 以外の *.go ファイルを編集したとき tdd-guide 使用を促す
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# .go ファイルでなければスキップ
[[ "$FILE" != *.go ]] && exit 0

# *_test.go はスキップ
[[ "$FILE" == *_test.go ]] && exit 0

echo "⚠️  [tdd-guard-go] Go 実装ファイルを編集しました: $(basename "$FILE")" >&2
echo "   go-dev エージェント（実装）または tdd-guide エージェント（TDD）を使いましたか？" >&2
echo "   汎用 claude エージェントで代替しないこと（CLAUDE.md 参照）" >&2
exit 0
