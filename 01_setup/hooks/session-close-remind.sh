#!/bin/bash
# session-close-remind.sh
# Stop フック: session-close-improve が未実施の場合にリマインドを表示する
#
# ロジック:
# - 本日のスキルログが存在し（セッションが活発）
# - かつ session-close-improve の実行ログがない場合にリマインドを出す
# - これにより毎ターン後に表示されるのを防ぐ

LOG_FILE="/home/asama/.claude/logs/session-usage-$(date '+%Y%m%d').log"
MARKER="/home/asama/.claude/logs/session-close-done-$(date '+%Y%m%d')"

# マーカーファイルがあれば今日は既に実行済み → スキップ
[ -f "$MARKER" ] && exit 0

# スキルログがなければ（非活性セッション）→ スキップ
[ ! -f "$LOG_FILE" ] || [ ! -s "$LOG_FILE" ] && exit 0

# session-close-improve が今日実行された形跡があれば → スキップ
grep -q "session-close-improve" "$LOG_FILE" 2>/dev/null && touch "$MARKER" && exit 0

# ここに到達 = 活性セッションで session-close-improve 未実施
echo ""
echo "=== セッション終了前チェック ==="
echo "  session-close-improve が未実行です。"
echo "  振り返り・CLAUDE.md更新・メモリ保存を行うには:"
echo "     「終了します」または「振り返りをしたい」と入力"
echo "================================"
