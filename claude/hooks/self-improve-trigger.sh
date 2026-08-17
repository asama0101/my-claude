#!/bin/bash
# self-improve-trigger.sh — Stop hook（Tier1: 決定論的シグナル検査）
#
# セッション終了時に以下のシグナルを検査し、該当があれば exit 2 で終了をブロックし、
# self-improvement-loop スキル（Tier2、LLM駆動）の起動を促す。
# - インシデント: transcript に is_error:true が出現
# - モデルバージョン不一致: 直近セッションのモデルIDと state.json の記録が異なる
# - feedback/project メモリ更新: プロジェクト別 memory/ 配下のファイルが前回チェック以降に更新された
# - 累積傾向: session_count_since_full_audit が閾値に到達
#
# ループガード（2層）:
# 1. stop_hook_active が true の場合（＝このStop hook自身のブロックで継続させたターン）は無条件で exit 0。
# 2. state.json.last_handled_session_id が今回の session_id と一致する場合、
#    既に Tier2 が処理済みなのでシグナルがあっても再ブロックしない。
#
# 排他制御: state.json はマシン上の全セッションが共有するグローバルファイルであり、
# 複数セッションが同時にStopするとread-modify-writeが競合してロストアップデートが起きる
# （カウント誤差・last_handled_session_idの巻き戻り等）。flockでSTATE_FILEへの読み書き区間
# 全体を排他化し、同時実行時もアトミックに更新されるようにする。

set -uo pipefail

SESSION_THRESHOLD=10

command -v jq >/dev/null 2>&1 || exit 0   # jq不在時は fail-open（自己改善は必須機能ではない）

STATE_FILE="$HOME/.claude/state/self-improvement.json"
[ -f "$STATE_FILE" ] || exit 0            # 未初期化なら何もしない

LOCK_FILE="$STATE_FILE.lock"
exec 9>"$LOCK_FILE"
flock -w 5 9 || exit 0                    # 5秒待っても取得できなければ fail-open

INPUT=$(cat)
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty')
TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty')
STOP_HOOK_ACTIVE=$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false')

# stop_hook_active=true は「このStop hook自身のブロックで継続させたターン」であることを示す。
# ここで再度exit 2すると無限ループになるため、ハーネスの規約どおり常にexit 0で終了する。
[ "$STOP_HOOK_ACTIVE" = "true" ] && exit 0

[ -z "$SESSION_ID" ] && exit 0

# 累積セッションカウント（session_idごとに1回だけ計上）:
# Stop hookはセッション終了時ではなくターンごとに発火するため、
# 同一セッション内での二重計上を last_counted_session_id で防ぐ。
LAST_COUNTED=$(jq -r '.last_counted_session_id // empty' "$STATE_FILE")
if [ "$LAST_COUNTED" != "$SESSION_ID" ]; then
  tmp_count=$(mktemp)
  jq --arg sid "$SESSION_ID" \
    '.session_count_since_full_audit += 1 | .last_counted_session_id = $sid' \
    "$STATE_FILE" > "$tmp_count" && mv "$tmp_count" "$STATE_FILE"
fi

LAST_HANDLED=$(jq -r '.last_handled_session_id // empty' "$STATE_FILE")
NOW=$(date +%s)

# last_checked_at 更新はどの分岐でも最後に行う
update_checked_at() {
  local tmp
  tmp=$(mktemp)
  jq --argjson t "$NOW" '.last_checked_at = $t' "$STATE_FILE" > "$tmp" && mv "$tmp" "$STATE_FILE"
}

if [ "$LAST_HANDLED" = "$SESSION_ID" ]; then
  update_checked_at
  exit 0
fi

REASONS=()
LAST_CHECKED=$(jq -r '.last_checked_at // 0' "$STATE_FILE")

if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  if grep -q '"is_error":true' "$TRANSCRIPT" 2>/dev/null; then
    REASONS+=("インシデント検知: transcriptにis_error:trueが存在")
  fi

  CURRENT_MODEL=$(grep -o '"model":"[^"]*"' "$TRANSCRIPT" 2>/dev/null | tail -1 | sed -E 's/.*:"([^"]*)"/\1/')
  LAST_MODEL=$(jq -r '.last_reviewed_model // empty' "$STATE_FILE")
  if [ -n "$CURRENT_MODEL" ] && [ "$CURRENT_MODEL" != "$LAST_MODEL" ]; then
    REASONS+=("モデルバージョン不一致: 記録=${LAST_MODEL:-なし} 現在=${CURRENT_MODEL}")
  fi
fi

if [ -n "$CWD" ]; then
  SLUG=$(printf '%s' "$CWD" | sed 's/\//-/g')
  MEMORY_DIR="$HOME/.claude/projects/$SLUG/memory"
  if [ -d "$MEMORY_DIR" ]; then
    for f in "$MEMORY_DIR"/*; do
      [ -f "$f" ] || continue
      MTIME=$(stat -c %Y "$f" 2>/dev/null || echo 0)
      if [ "$MTIME" -gt "$LAST_CHECKED" ]; then
        REASONS+=("feedback/projectメモリ更新を検知: $f")
        break
      fi
    done
  fi
fi

SESSION_COUNT=$(jq -r '.session_count_since_full_audit // 0' "$STATE_FILE")
if [ "$SESSION_COUNT" -ge "$SESSION_THRESHOLD" ]; then
  REASONS+=("累積セッション数が閾値(${SESSION_THRESHOLD})に到達: ${SESSION_COUNT}")
fi

update_checked_at

if [ "${#REASONS[@]}" -gt 0 ]; then
  {
    echo "self-improvement-loop スキルを起動してください。以下のシグナルを検知しました:"
    printf ' - %s\n' "${REASONS[@]}"
  } >&2
  exit 2
fi

exit 0
