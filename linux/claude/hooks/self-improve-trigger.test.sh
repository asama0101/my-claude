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
  rm -f "$MEMORY_DIR"/*
  cat > "$STATE_DIR/self-improvement.json" <<'EOF'
{
  "last_reviewed_model": "claude-sonnet-5",
  "session_count_since_full_audit": 0,
  "last_full_audit_at": 0,
  "last_checked_at": 0,
  "handled_session_ids": [],
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

# 6. 同一セッションで既にTier2処理済み（handled_session_idsに含まれる）→ シグナルがあっても exit 0
reset_state
jq '.handled_session_ids = ["s6"]' "$STATE_DIR/self-improvement.json" > "$STATE_DIR/tmp.json" && mv "$STATE_DIR/tmp.json" "$STATE_DIR/self-improvement.json"
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

# 11. 複数セッションのTier2完了記録が互いを上書きしない（handled_session_idsが単一値でなく集合であること）
#     旧実装（last_handled_session_id単一値）だと、セッションBのTier2完了でセッションAの
#     「処理済み」記録が消え、Aが再ブロックされてしまっていた（実運用で観測された不具合）。
reset_state
jq '.handled_session_ids = ["sA"]' "$STATE_DIR/self-improvement.json" > "$STATE_DIR/tmp.json" && mv "$STATE_DIR/tmp.json" "$STATE_DIR/self-improvement.json"
# セッションBのTier2完了を模擬（sAを消さずsBを追記）
jq '.handled_session_ids = ((.handled_session_ids // []) - ["sB"] + ["sB"] | .[-20:])' "$STATE_DIR/self-improvement.json" > "$STATE_DIR/tmp.json" && mv "$STATE_DIR/tmp.json" "$STATE_DIR/self-improvement.json"
run_hook "sA" "$PROJECT_DIR/incident.jsonl"; assert_exit 0 "$?" "セッションBのTier2完了後もセッションAの処理済み記録が残る"

# 12. Agentツール呼び出しのprompt内にレビュー関連キーワードがある → シグナル検知 → exit 2
#     エージェント名(subagent_type)ではなくprompt内容で判定するため、専用reviewエージェントに
#     限らず汎用エージェント(general-purpose等)へのアドホックなレビュー依頼も拾える。
reset_state
echo '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose","prompt":"このコードをreviewして問題点を指摘して"}}' > "$PROJECT_DIR/review_prompt.jsonl"
run_hook "s12" "$PROJECT_DIR/review_prompt.jsonl"; assert_exit 2 "$?" "レビュー関連キーワードを含むprompt(汎用エージェント)を検知"

# 13. 専用review-*エージェントの起動もprompt内容経由で検知される
reset_state
echo '{"tool_name":"Agent","tool_input":{"subagent_type":"review-security","prompt":"セキュリティレビューを実施し指摘事項を報告して"}}' > "$PROJECT_DIR/review_security.jsonl"
run_hook "s13" "$PROJECT_DIR/review_security.jsonl"; assert_exit 2 "$?" "review-*エージェントのprompt内容も検知"

# 14. レビュー関連キーワードを含まないAgent呼び出し → シグナルなし → exit 0（回帰確認）
reset_state
echo '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose","prompt":"このファイルの内容を要約して"}}' > "$PROJECT_DIR/non_review.jsonl"
run_hook "s14" "$PROJECT_DIR/non_review.jsonl"; assert_exit 0 "$?" "レビュー無関係のAgent呼び出しは誤検知しない"

# 15. セキュリティレビュー指摘の修正確認: promptにエスケープされた引用符(\")を含むコード
#     スニペットがキーワードより手前にあっても検知漏れしない（旧パターン[^"]*は\"で
#     停止してしまい、レビュー依頼の典型例で検知漏れが起きていた）。
reset_state
printf '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose","prompt":"このコードの \\"review\\" をお願いします。指摘してください"}}\n' > "$PROJECT_DIR/escaped_quote.jsonl"
run_hook "s15" "$PROJECT_DIR/escaped_quote.jsonl"; assert_exit 2 "$?" "セキュリティレビュー修正: エスケープされた引用符を含むpromptでも検知漏れしない"

# 16. 正確性レビュー指摘の修正確認: 判定は"prompt"文字列の有無だけで行われ、tool_nameフィールドの
#     値には一切依存しない（実装がドキュメント記述通り「Agentツールに限定」されていないことを明示する）。
reset_state
echo '{"prompt":"このコードをreviewして"}' > "$PROJECT_DIR/no_toolname.jsonl"
run_hook "s16" "$PROJECT_DIR/no_toolname.jsonl"; assert_exit 2 "$?" "正確性レビュー修正: tool_nameフィールドが無くてもprompt文字列だけで検知される"

rm -rf "$SCRATCH"
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
