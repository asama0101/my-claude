#!/bin/bash
# PostToolUse: Write/Edit で tests/ 外の実装ファイルを編集したとき tdd-gates オーケストレータの使用を促す（非ブロッキング）
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[[ -z "$FILE" ]] && exit 0

BASENAME="$(basename "$FILE")"

# 実装ファイルの拡張子だけ対象。言語プロファイル（profiles/*.md）がある言語のみ nudge する。
# Go 等を足すときは、対応する profiles/<runner>.md を用意してからここに拡張子とテスト命名を追加する。
case "$FILE" in
  *.py) ;;
  *) exit 0 ;;
esac

# テストコードならスキップ
[[ "$FILE" == */tests/* ]] && exit 0
[[ "$BASENAME" == test_*.py ]] && exit 0     # pytest

# 促し文を JSON(additionalContext)で stdout に出し、model に確実に届くようにする（非ブロック・exit 0）。
MSG="⚠️  [tdd-gates] 実装ファイルを編集しました: $BASENAME
   substantial な変更なら tdd-gates スキル（9品質ゲート）で回しましたか？
   RED は実際の失敗ログを証拠に、採点は gate-evaluator（実装者とは別コンテキスト）で。
   trivial（数行・設定/ドキュメント）は比例ルールによりゲート不要（CLAUDE.md 参照）。"
jq -nc --arg m "$MSG" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$m}}'
exit 0
