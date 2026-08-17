#!/bin/bash
set -uo pipefail
HOOK="$HOME/.claude/hooks/self-improve-trigger.sh"
SCRATCH=$(mktemp -d)
FAKE_HOME="$SCRATCH/home"
PROJECT_DIR="$FAKE_HOME/proj"
STATE_DIR="$FAKE_HOME/.claude/state"
# フック本体と同じスラッグ化ロジック（cwdの "/" を "-" に置換）でMEMORY_DIRを算出する。
# ハードコードすると mktemp -d が生成する実パスとズレて偽陰性になるため必ず動的に計算すること。
SLUG=$(printf '%s' "$PROJECT_DIR" | sed 's/\//-/g')
MEMORY_DIR="$FAKE_HOME/.claude/projects/$SLUG/memory"
mkdir -p "$STATE_DIR" "$MEMORY_DIR" "$PROJECT_DIR"

reset_state() {
  cat > "$STATE_DIR/self-improvement.json" <<'EOF'
{
  "last_reviewed_model": "claude-sonnet-5",
  "session_count_since_full_audit": 0,
  "last_full_audit_at": 0,
  "last_checked_at": 0,
  "last_handled_session_id": "",
  "last_counted_session_id": "",
  "pending_improver_suggestions": []
}
EOF
}

run_hook() {  # $1=session_id $2=transcript_path
  local input
  input=$(jq -n --arg sid "$1" --arg tp "$2" --arg cwd "$PROJECT_DIR" \
    '{session_id:$sid, transcript_path:$tp, cwd:$cwd, hook_event_name:"Stop"}')
  printf '%s' "$input" | HOME="$FAKE_HOME" bash "$HOOK"
}

run_hook_stop_active() {  # $1=session_id $2=transcript_path
  local input
  input=$(jq -n --arg sid "$1" --arg tp "$2" --arg cwd "$PROJECT_DIR" \
    '{session_id:$sid, transcript_path:$tp, cwd:$cwd, hook_event_name:"Stop", stop_hook_active:true}')
  printf '%s' "$input" | HOME="$FAKE_HOME" bash "$HOOK"
}

FAIL=0
assert_exit() {  # $1=expected $2=actual $3=label
  if [ "$1" != "$2" ]; then
    echo "FAIL: $3 (expected exit $1, got $2)"
    FAIL=1
  else
    echo "PASS: $3"
  fi
}

# 1. クリーンなtranscript → シグナルなし → exit 0
reset_state
echo '{"model":"claude-sonnet-5","is_error":false}' > "$PROJECT_DIR/clean.jsonl"
run_hook "s1" "$PROJECT_DIR/clean.jsonl"; assert_exit 0 "$?" "クリーン transcript"

# 2. is_error:true を含む → インシデント検知 → exit 2
reset_state
echo '{"model":"claude-sonnet-5","is_error":true}' > "$PROJECT_DIR/incident.jsonl"
run_hook "s2" "$PROJECT_DIR/incident.jsonl"; assert_exit 2 "$?" "インシデント検知"

# 3. モデル不一致 → exit 2
reset_state
echo '{"model":"claude-sonnet-6","is_error":false}' > "$PROJECT_DIR/version.jsonl"
run_hook "s3" "$PROJECT_DIR/version.jsonl"; assert_exit 2 "$?" "モデルバージョン不一致"

# 4. 累積閾値到達 → exit 2
reset_state
jq '.session_count_since_full_audit = 10' "$STATE_DIR/self-improvement.json" > "$STATE_DIR/tmp.json" && mv "$STATE_DIR/tmp.json" "$STATE_DIR/self-improvement.json"
run_hook "s4" "$PROJECT_DIR/clean.jsonl"; assert_exit 2 "$?" "累積閾値到達"

# 5. memoryファイル更新 → exit 2
reset_state
touch "$MEMORY_DIR/feedback-example.md"
run_hook "s5" "$PROJECT_DIR/clean.jsonl"; assert_exit 2 "$?" "memory更新検知"

# 6. 同一セッションで既にTier2処理済み（last_handled_session_id一致）→ シグナルがあっても exit 0
reset_state
jq '.last_handled_session_id = "s6"' "$STATE_DIR/self-improvement.json" > "$STATE_DIR/tmp.json" && mv "$STATE_DIR/tmp.json" "$STATE_DIR/self-improvement.json"
run_hook "s6" "$PROJECT_DIR/incident.jsonl"; assert_exit 0 "$?" "ループガード（処理済みセッション）"

# 7. 新規セッションIDで初回実行 → session_count_since_full_audit が1増える
reset_state
run_hook "s7" "$PROJECT_DIR/clean.jsonl" > /dev/null
COUNT_AFTER_1ST=$(jq -r '.session_count_since_full_audit' "$STATE_DIR/self-improvement.json")
if [ "$COUNT_AFTER_1ST" = "1" ]; then
  echo "PASS: 新規セッション初回実行でカウント+1"
else
  echo "FAIL: 新規セッション初回実行でカウント+1 (expected 1, got $COUNT_AFTER_1ST)"
  FAIL=1
fi

# 8. 同じセッションIDで2回目実行（state.jsonの状態を引き継いだまま）→ カウントは増えない
run_hook "s7" "$PROJECT_DIR/clean.jsonl" > /dev/null
COUNT_AFTER_2ND=$(jq -r '.session_count_since_full_audit' "$STATE_DIR/self-improvement.json")
if [ "$COUNT_AFTER_2ND" = "1" ]; then
  echo "PASS: 同一セッション2回目実行でカウントは増えない"
else
  echo "FAIL: 同一セッション2回目実行でカウントは増えない (expected 1, got $COUNT_AFTER_2ND)"
  FAIL=1
fi

# 9. stop_hook_active:true → シグナルが検知されても再ブロックしない（無限ループ防止） → exit 0
reset_state
run_hook_stop_active "s9" "$PROJECT_DIR/incident.jsonl"; assert_exit 0 "$?" "stop_hook_active時は再ブロックしない"

# 10. 複数セッションが同時にstate.jsonを読み書きしてもロストアップデートが起きない（競合状態の回帰防止）
#     ロック無しだと read-modify-write が競合し、カウントが起動数より少なくなる／last_counted_session_idが
#     他セッションの書き込みで上書きされ続ける（実運用で観測された不具合）。
reset_state
CONCURRENCY=8
for i in $(seq 1 "$CONCURRENCY"); do
  run_hook "race-$i" "$PROJECT_DIR/clean.jsonl" > /dev/null &
done
wait
COUNT_AFTER_RACE=$(jq -r '.session_count_since_full_audit' "$STATE_DIR/self-improvement.json")
if [ "$COUNT_AFTER_RACE" = "$CONCURRENCY" ]; then
  echo "PASS: 同時実行でもカウントがロストしない（$CONCURRENCY並列 → $COUNT_AFTER_RACE）"
else
  echo "FAIL: 同時実行でもカウントがロストしない (expected $CONCURRENCY, got $COUNT_AFTER_RACE)"
  FAIL=1
fi

rm -rf "$SCRATCH"
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
