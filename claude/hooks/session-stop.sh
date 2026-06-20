#!/bin/bash
# session-stop.sh — 統合 Stop フック
#   (1) 本プロジェクトの新規フィードバックメモリを検出してパッシブ通知（CLAUDE.md 反映を促す）
#   (2) 最後のユーザー入力に「終了意図」がある時だけ session-close-improve を1回 block で促す
#
# 2026 統合: session-retrospective.sh + session-close-remind.sh を1本に。
#   - 旧 close-remind は「応答終了のたび」毎ターン block していた（無視され機能せず）。
#     → 終了意図（transcript の last-prompt）検出時のみ・1セッション1回 block へ。
#   - 終了意図の判定源は `last-prompt` 型の .lastPrompt（実ユーザー入力。フック注入が混入しない）。
#     `type:user` の string content は "Stop hook feedback" 等の注入を含むため使わない（自己誤発火防止）。

INPUT=$(cat)

# ① 同一 stop チェーン内の再ブロック防止
[ "$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ] && exit 0

# ② transcript / セッションID / memory ディレクトリ
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
{ [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; } && exit 0
SESSION_ID=$(basename "$TRANSCRIPT" .jsonl)
MEMORY_DIR="$(dirname "$TRANSCRIPT")/memory"

LOG_DIR="$HOME/.claude/logs"
RETRO_MARKER="$LOG_DIR/last-retrospective"
REMINDED_DIR="$LOG_DIR/close-reminded"
SKIP_DIR="$LOG_DIR/close-skip"
REMINDED_MARK="$REMINDED_DIR/$SESSION_ID"
SKIP_MARK="$SKIP_DIR/$SESSION_ID"
mkdir -p "$REMINDED_DIR" "$SKIP_DIR"
# per-session マーカーの増殖防止（14日より古いものを掃除）
find "$REMINDED_DIR" "$SKIP_DIR" -type f -mtime +14 -delete 2>/dev/null

# ===== (1) フィードバックメモリのパッシブ通知（常時・非ブロック）=====
if [ -d "$MEMORY_DIR" ]; then
  find_feedback() {
    find "$MEMORY_DIR" -maxdepth 1 -name '*.md' "$@" 2>/dev/null | while IFS= read -r f; do
      grep -qE '^[[:space:]]*type:[[:space:]]*feedback[[:space:]]*$' "$f" 2>/dev/null && echo "$f"
    done
  }
  if [ -f "$RETRO_MARKER" ]; then
    RECENT=$(find_feedback -newer "$RETRO_MARKER")
  else
    RECENT=$(find_feedback)
  fi
  if [ -n "$RECENT" ]; then
    echo ""
    echo "=== 本セッションの学び（フィードバックメモリ更新） ==="
    while IFS= read -r f; do
      NAME=$(grep '^name:' "$f" 2>/dev/null | head -1 | sed 's/^name:[[:space:]]*//')
      DESC=$(grep '^description:' "$f" 2>/dev/null | head -1 | sed 's/^description:[[:space:]]*//')
      echo "  * ${NAME}: ${DESC}"
    done <<< "$RECENT"
    echo ""
    echo "  CLAUDE.md に学びを反映するには:"
    echo "     1) /claude-md-management:revise-claude-md   （学びを取り込む）"
    echo "     2) /claude-md-management:claude-md-improver  （更新をレビュー）"
    echo "====================================================="
    mkdir -p "$(dirname "$RETRO_MARKER")"
    touch "$RETRO_MARKER"
  fi
fi

# ===== (2) close-improve 催促（終了意図検出で1回 block）=====
# このセッションをスキップ指定済み → 何もしない
[ -f "$SKIP_MARK" ] && exit 0
# 既に session-close-improve を起動済み（空白許容）→ 何もしない
grep -qE '"skill"[[:space:]]*:[[:space:]]*"session-close-improve"' "$TRANSCRIPT" 2>/dev/null && exit 0
# 本セッションで既に1回催促済み → 抑制
[ -f "$REMINDED_MARK" ] && exit 0
# 活性判定: 何らかのツールを使ったか（雑談のみは対象外）
grep -q '"type":"tool_use"' "$TRANSCRIPT" 2>/dev/null || exit 0

# 最後の実ユーザー入力（last-prompt が真の入力源・注入混入なし）
LAST=$(jq -r 'select(.type=="last-prompt") | .lastPrompt // empty' "$TRANSCRIPT" 2>/dev/null | tail -1)
[ -z "$LAST" ] && exit 0

# 終了意図キーワード（明確な終了合図に限定。commit/push 等の曖昧語は含めない）
if echo "$LAST" | grep -qiE '終了|終わり|おわり|終わります|お疲れ|おつかれ|さようなら|締め(る)?|クローズ|店じまい|解散|bye|wrap ?up|that'\''?s all|we'\''?re done|good ?night|see you'; then
  touch "$REMINDED_MARK"
  REASON="セッションを終了しようとしています。締める前に session-close-improve を起動し [1]サブエージェント/スキル使用の振り返り [2]superpowers spec/plan の done/ アーカイブ [3]最小更新とメモリ保存 を実施してください。このセッションをスキップするなら: touch $SKIP_MARK"
  jq -nc --arg r "$REASON" '{decision:"block",reason:$r}'
fi
exit 0
