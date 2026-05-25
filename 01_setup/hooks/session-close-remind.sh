#!/bin/bash
# session-close-remind.sh
# Stop フック: アクティブなセッション終了時に session-close-improve を自動起動する。
# 2026-05-25 リマインド表示 → decision:block 自動起動へ格上げ。
#
# ロジック:
# - 既に stop フック起因で継続中（stop_hook_active）なら再ブロックしない（ループ防止）
# - 本日既に実施済み / 非活性セッション / 実施済み形跡があればスキップ
# - 活性かつ未実施なら decision:block で session-close-improve を自動起動

INPUT=$(cat)

# ループ防止: 既に stop フック起因で継続中なら再ブロックしない
[ "$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ] && exit 0

LOG_FILE="/home/asama/.claude/logs/session-usage-$(date '+%Y%m%d').log"
MARKER="/home/asama/.claude/logs/session-close-done-$(date '+%Y%m%d')"

# マーカーファイルがあれば今日は既に実行済み → スキップ
[ -f "$MARKER" ] && exit 0

# スキルログがなければ（非活性セッション）→ スキップ
{ [ ! -f "$LOG_FILE" ] || [ ! -s "$LOG_FILE" ]; } && exit 0

# session-close-improve が今日実行された形跡があれば → マーカー作成してスキップ
grep -q "session-close-improve" "$LOG_FILE" 2>/dev/null && touch "$MARKER" && exit 0

# ここに到達 = 活性セッションで session-close-improve 未実施 → 自動起動
cat <<'JSON'
{"decision":"block","reason":"アクティブなセッションを終了しようとしていますが session-close-improve が未実行です。今すぐ session-close-improve skill を起動し、(1) サブエージェント/スキル使用の振り返り、(2) superpowers の spec/plan 完了確認と完了分の done/ への承認付きアーカイブ、(3) 必要最小限の更新とメモリ保存 を実施してください。ユーザーが明示的にスキップを希望する場合のみ、touch コマンドで本日のマーカーファイル（~/.claude/logs/session-close-done-YYYYMMDD）を作成して終了を許可してください。"}
JSON
exit 0
