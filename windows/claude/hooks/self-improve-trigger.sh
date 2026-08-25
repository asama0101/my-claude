#!/bin/bash
# self-improve-trigger.sh — Stop hook（Tier1: 決定論的シグナル検査）
#
# セッション終了時に以下のシグナルを検査し、該当があれば exit 2 で終了をブロックし、
# self-improvement-loop スキル（Tier2、LLM駆動）の起動を促す。
# - インシデント: transcript に is_error:true が出現
# - モデルバージョン不一致: 直近セッションのモデルIDと state.json の記録が異なる
# - feedback/project メモリ更新: プロジェクト別 memory/ 配下のファイルが前回チェック以降に更新された
# - 累積傾向: session_count_since_full_audit が閾値に到達
# - レビュー指摘の可能性: transcript の prompt 文字列にレビュー関連キーワードが出現
#
# ループガード（2層）:
# 1. stop_hook_active が true の場合（＝このStop hook自身のブロックで継続させたターン）は無条件で exit 0。
# 2. state.json.handled_session_ids（配列、直近20件）に今回の session_id が含まれる場合、
#    既に Tier2 が処理済みなのでシグナルがあっても再ブロックしない。
#    単一値（last_handled_session_id）ではなく配列にしているのは、マシン上で複数の
#    Main セッションが同時に稼働するケースに対応するため。単一値だと片方の Tier2 完了が
#    もう片方の「処理済み」記録を上書きしてしまい、セッション同士が互いを再ブロックし合う
#    （flock だけでは解決しない設計上の問題だった）。
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
if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  flock -w 5 9 || exit 0                  # 5秒待っても取得できなければ fail-open
else
  # Windows(Git Bash)には flock が無い。従来はここで `|| exit 0` に落ち、本フックが
  # 黙って無効化されていた（自己改善ループが一度も起動しない）。mkdir のアトミック性を
  # 使ったロックで代替し、Linux 側の挙動（5秒待って取れなければ fail-open）を揃える。
  LOCK_DIR="$STATE_FILE.lockdir"
  lock_acquired=0
  i=0
  while [ "$i" -lt 50 ]; do
    if mkdir "$LOCK_DIR" 2>/dev/null; then lock_acquired=1; break; fi
    # 異常終了で残った 60 秒より古いロックは無効とみなして掃除する（恒久 fail-open を防ぐ）
    if [ -d "$LOCK_DIR" ] && [ -z "$(find "$LOCK_DIR" -maxdepth 0 -newermt '-60 seconds' 2>/dev/null)" ]; then
      rmdir "$LOCK_DIR" 2>/dev/null
    fi
    sleep 0.1
    i=$((i + 1))
  done
  [ "$lock_acquired" -eq 1 ] || exit 0    # 5秒待っても取得できなければ fail-open
  trap 'rmdir "$LOCK_DIR" 2>/dev/null' EXIT
fi

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

ALREADY_HANDLED=$(jq --arg sid "$SESSION_ID" \
  '[(.handled_session_ids // [])[] | select(. == $sid)] | length > 0' "$STATE_FILE")
NOW=$(date +%s)

# last_checked_at 更新はどの分岐でも最後に行う
update_checked_at() {
  local tmp
  tmp=$(mktemp)
  jq --argjson t "$NOW" '.last_checked_at = $t' "$STATE_FILE" > "$tmp" && mv "$tmp" "$STATE_FILE"
}

if [ "$ALREADY_HANDLED" = "true" ]; then
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

  # レビュー系サブエージェント起動の形跡: subagent_type（エージェント名）ではなく
  # transcript中のprompt文字列（現状はAgentツール呼び出しでのみ出現）の内容で判定する。
  # 専用review-*/tdd-evaluatorに限らず、汎用エージェント(general-purpose等)への
  # アドホックなレビュー依頼もエージェント名の命名規約に依存せず拾えるようにするため。
  # 粗い検知のため "preview"/"interview" 等 review を部分文字列に含む語も誤って
  # ヒットしうるが、Tier1は粗くてよい設計（裏取りはTier2が担う）ため許容する。
  if grep -qE '"prompt":"([^"\\]|\\.)*(review|レビュー|指摘|査読)' "$TRANSCRIPT" 2>/dev/null; then
    REASONS+=("レビュー指摘の可能性: transcriptにレビュー関連のサブエージェント起動の形跡")
  fi
fi

if [ -n "$CWD" ]; then
  # Claude Code のプロジェクトディレクトリ名は cwd の区切り文字を "-" に潰したもの。
  # Windows では cwd が C:\Users\... 形式で渡るため ":" と "\" も対象に含める
  # (C:\Users\u\proj → C--Users-u-proj)。Linux の /home/u/proj → -home-u-proj は不変。
  SLUG=$(printf '%s' "$CWD" | sed 's|[/\:]|-|g')
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
