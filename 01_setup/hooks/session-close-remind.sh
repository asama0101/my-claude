#!/bin/bash
# session-close-remind.sh
# Stop フック: アクティブなセッション終了時に session-close-improve を自動起動する。
# 2026-05-25 ログ依存（skill-logger / 日次マーカー）を撤廃し、
#            transcript ベースの「セッション単位で1回」制御へ移行。
#
# ロジック:
# - stop_hook_active 継続中なら再ブロックしない（同一 stop チェーンのループ防止）
# - 本日スキップ指定マーカー（手動エスケープ）があればスキップ
# - transcript に session-close-improve 起動痕跡があれば「本セッション実施済み」→スキップ
# - transcript に tool_use が無い（雑談のみ）セッションは対象外
# - 上記を通過した活性セッションでのみ decision:block で自動起動

INPUT=$(cat)

# ① 同一 stop チェーン内の再ブロック防止
[ "$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ] && exit 0

# ② 本日スキップ指定（ユーザーが明示スキップした場合の手動エスケープ）
DAY_MARKER="/home/asama/.claude/logs/session-close-done-$(date '+%Y%m%d')"
[ -f "$DAY_MARKER" ] && exit 0

# ③ transcript を取得（無ければ判定不能 → スキップ）
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
{ [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; } && exit 0

# ④ 本セッションで既に session-close-improve を起動済み → セッション単位で1回に抑制
#    Skill ツールの入力 "skill":"session-close-improve" のみに一致（散文/Bash 文字列は誤検知しない）
grep -q '"skill":"session-close-improve"' "$TRANSCRIPT" 2>/dev/null && exit 0

# ⑤ 活性判定: 本セッションで何らかのツールを使ったか（雑談のみセッションは対象外）
grep -q '"type":"tool_use"' "$TRANSCRIPT" 2>/dev/null || exit 0

# ⑥ 活性かつ未実施 → decision:block で自動起動
cat <<'JSON'
{"decision":"block","reason":"アクティブなセッションを終了しようとしていますが session-close-improve が未実行です。今すぐ session-close-improve skill を起動し、(1) サブエージェント/スキル使用の振り返り、(2) superpowers の spec/plan 完了確認と完了分の done/ への承認付きアーカイブ、(3) 必要最小限の更新とメモリ保存 を実施してください。ユーザーが明示的にスキップを希望する場合のみ、touch コマンドで本日のスキップマーカー（~/.claude/logs/session-close-done-YYYYMMDD、YYYYMMDD は本日の日付）を作成して終了を許可してください。"}
JSON
exit 0
