# self-improvement-loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** セッション終了時に決定論的シグナル（インシデント・モデルバージョン不一致・feedbackメモリ更新・累積セッション数）を検知し、軽微な改善は `~/.claude/` へ自動適用、構造的な改善は提案のみに留める自己改善ループを実装する。

**Architecture:** Stop hook（`self-improve-trigger.sh`、決定論的・LLM不使用）が毎セッション終了時にシグナルを検査し、該当があれば exit code 2 でセッション終了をブロックして `self-improvement-loop` スキル（LLM駆動）の起動を促す。スキル側が信号を裏取りし、比例ルールで trivial/small/substantial に分類、trivial のみ `~/.claude/` の実ファイルを直接編集して構造検証（jq/bash -n/frontmatter parse）を通す。git 操作は一切行わない。

**Tech Stack:** bash（フック・テスト）、jq（JSON操作）、Claude Code Skill（Markdown + YAMLフロントマター）

**Spec:** `docs/specs/2026-08-17-self-improvement-loop-design.md`

## Global Constraints

- 実ファイルは `~/.claude/` 配下を直接編集する（`<repo>/claude/` はミラーであり直接編集しない）
- ループ本体（Tier1/Tier2）は `git commit`/`push`/`sync.sh` を一切実行しない
- hooks/settings.json への変更は行数によらず常に small/substantial 扱い固定（trivial 自動適用の対象外）
- スクリプトは `$HOME` を直書きする（絶対パス `/home/<user>/` を書かない）。既存フック（`bash-guard.sh` 等）と同じ規約
- jq 不在時は fail-close ではなく **fail-open**（自己改善は必須機能ではないため、jq が無ければ何もせず exit 0 で通常終了する。既存の PreToolUse ガード群とは exit 方針が異なる点に注意）
- `~/.claude/state/` は `scripts/sync.sh`/`scripts/install.sh` のホワイトリストに含まれておらず、追加実装なしで自動的に同期対象外になる（設計doc「確認済み事項」節で検証済み）

---

## 事前に確定した技術事実（実機検証済み）

- Stop hook の stdin JSON には `session_id`（string）、`transcript_path`（string, JSONL）、`cwd`（string）、`hook_event_name`（"Stop"）が含まれる
- Stop hook が exit code 2 を返すと、JSON出力なしでセッション終了をブロックできる（stderr の内容が Claude への継続指示として使われる）
- transcript の各行（JSONL）には `"model":"<model-id>"` と `"is_error":true|false` が文字列として出現する（本セッションの実transcriptで実測確認済み）
- `claude doctor` は設定ファイルの構文・整合性を検証しない（installation health のみ）ため、構造検証には使わない
- プロジェクト別メモリディレクトリのパスは `~/.claude/projects/<cwdのスラッシュをハイフンに置換したスラッグ>/memory/`（例: `/home/asama/my-claude` → `-home-asama-my-claude`）

---

### Task 1: state.json の初期化

**Files:**
- Create: `$HOME/.claude/state/self-improvement.json`

**Interfaces:**
- Produces: state.json のスキーマ（後続タスクが読み書きするキー）:
  - `last_reviewed_model` (string): 最後に監査したモデルID
  - `session_count_since_full_audit` (number): 累積セッション監査カウンタ
  - `last_full_audit_at` (number, epoch秒): 最後の累積監査実施時刻
  - `last_checked_at` (number, epoch秒): Tier1が最後にチェックした時刻（Tier1が毎回更新）
  - `last_handled_session_id` (string): Tier2が最後に処理を完了したセッションID（ループガード）
  - `pending_improver_suggestions` (array of string): claude-md-improver が出した未反映の改善提案

- [ ] **Step 1: ディレクトリと初期ファイルを作成**

```bash
mkdir -p "$HOME/.claude/state"
cat > "$HOME/.claude/state/self-improvement.json" <<'EOF'
{
  "last_reviewed_model": "claude-sonnet-5",
  "session_count_since_full_audit": 0,
  "last_full_audit_at": 0,
  "last_checked_at": 0,
  "last_handled_session_id": "",
  "pending_improver_suggestions": []
}
EOF
```

- [ ] **Step 2: JSON構文を検証**

Run: `jq empty "$HOME/.claude/state/self-improvement.json" && echo OK`
Expected: `OK`

- [ ] **Step 3: 内容を確認**

Run: `jq . "$HOME/.claude/state/self-improvement.json"`
Expected: Step 1 で書いた6キーがすべて表示される

このタスクはリポジトリへのコミット対象外（`~/.claude/state/` は git 管理下の `claude/` ミラーに含まれないため）。commit不要。

---

### Task 2: self-improve-trigger.sh の実装（Tier1）

**Files:**
- Create: `$HOME/.claude/hooks/self-improve-trigger.sh`
- Test: `$HOME/.claude/hooks/self-improve-trigger.test.sh`

**Interfaces:**
- Consumes: Task 1 の `$HOME/.claude/state/self-improvement.json`
- Produces: exit code 0（シグナルなし・通常終了）または 2（シグナルあり・stderr に理由と `self-improvement-loop` スキル起動指示）。stdin として Stop hook JSON（`session_id`, `transcript_path`, `cwd`）を受け取る

- [ ] **Step 1: テストスクリプトを書く（フィクスチャ含む）**

```bash
cat > "$HOME/.claude/hooks/self-improve-trigger.test.sh" <<'TESTEOF'
#!/bin/bash
set -uo pipefail
HOOK="$HOME/.claude/hooks/self-improve-trigger.sh"
SCRATCH=$(mktemp -d)
FAKE_HOME="$SCRATCH/home"
PROJECT_DIR="$FAKE_HOME/proj"
STATE_DIR="$FAKE_HOME/.claude/state"
MEMORY_DIR="$FAKE_HOME/.claude/projects/-scratch-home-proj/memory"
mkdir -p "$STATE_DIR" "$MEMORY_DIR" "$PROJECT_DIR"

reset_state() {
  cat > "$STATE_DIR/self-improvement.json" <<'EOF'
{
  "last_reviewed_model": "claude-sonnet-5",
  "session_count_since_full_audit": 0,
  "last_full_audit_at": 0,
  "last_checked_at": 0,
  "last_handled_session_id": "",
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

rm -rf "$SCRATCH"
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
TESTEOF
chmod +x "$HOME/.claude/hooks/self-improve-trigger.test.sh"
```

- [ ] **Step 2: テストを実行して失敗することを確認（RED）**

Run: `bash "$HOME/.claude/hooks/self-improve-trigger.test.sh"`
Expected: `self-improve-trigger.sh` がまだ存在しないため `No such file or directory` 等のエラーで失敗する

- [ ] **Step 3: self-improve-trigger.sh を実装**

```bash
cat > "$HOME/.claude/hooks/self-improve-trigger.sh" <<'HOOKEOF'
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
# ループガード: state.json.last_handled_session_id が今回の session_id と一致する場合、
# 既に Tier2 が処理済みなのでシグナルがあっても再ブロックしない。

set -uo pipefail

SESSION_THRESHOLD=10

command -v jq >/dev/null 2>&1 || exit 0   # jq不在時は fail-open（自己改善は必須機能ではない）

STATE_FILE="$HOME/.claude/state/self-improvement.json"
[ -f "$STATE_FILE" ] || exit 0            # 未初期化なら何もしない

INPUT=$(cat)
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty')
TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty')

[ -z "$SESSION_ID" ] && exit 0

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
HOOKEOF
chmod +x "$HOME/.claude/hooks/self-improve-trigger.sh"
```

- [ ] **Step 4: テストを実行して成功することを確認（GREEN）**

Run: `bash "$HOME/.claude/hooks/self-improve-trigger.test.sh"`
Expected: 6件すべて `PASS`、最終行 `ALL PASS`

- [ ] **Step 5: シェル構文検証**

Run: `bash -n "$HOME/.claude/hooks/self-improve-trigger.sh" && echo SYNTAX_OK`
Expected: `SYNTAX_OK`

---

### Task 3: Stop hook を settings.json に登録

**Files:**
- Modify: `$HOME/.claude/settings.json`

**Interfaces:**
- Consumes: Task 2 の `$HOME/.claude/hooks/self-improve-trigger.sh`

- [ ] **Step 1: 現在の hooks セクションを確認**

Run: `jq '.hooks' "$HOME/.claude/settings.json"`
Expected: `PreToolUse` のみが存在し `Stop` キーは無い

- [ ] **Step 2: Stop hook を追加**

```bash
TMP=$(mktemp)
jq '.hooks.Stop = [{"hooks": [{"type": "command", "command": "$HOME/.claude/hooks/self-improve-trigger.sh"}]}]' \
  "$HOME/.claude/settings.json" > "$TMP" && mv "$TMP" "$HOME/.claude/settings.json"
```

- [ ] **Step 3: JSON構文検証**

Run: `jq empty "$HOME/.claude/settings.json" && echo OK`
Expected: `OK`

- [ ] **Step 4: 追加内容を確認**

Run: `jq '.hooks.Stop' "$HOME/.claude/settings.json"`
Expected: `self-improve-trigger.sh` を command に持つエントリが1件表示される

---

### Task 4: Tier1 の結線確認（実データでの手動ドライラン）

**Files:**
- なし（検証のみ、コード変更なし）

**Interfaces:**
- Consumes: Task 2/3 の成果物すべて

- [ ] **Step 1: 実際の Stop hook JSON 形式を模した入力で、jq不在時のfail-open動作を確認しない（jqは常在のため対象外）。実transcriptに対してシグナルなしパスを確認**

Run:
```bash
echo '{"session_id":"manual-check-1","transcript_path":"/dev/null","cwd":"'"$HOME"'"}' | bash "$HOME/.claude/hooks/self-improve-trigger.sh"; echo "EXIT:$?"
```
Expected: `state.json` が初期値（`last_reviewed_model: claude-sonnet-5`）のままなら、transcript が `/dev/null`（空）でシグナルなしのため `EXIT:0`

- [ ] **Step 2: state.json の last_checked_at が更新されたことを確認**

Run: `jq '.last_checked_at' "$HOME/.claude/state/self-improvement.json"`
Expected: Step 1 実行直前より新しい epoch 秒が入っている（0 ではない）

- [ ] **Step 3: state.json を初期値に戻す**

Run:
```bash
cat > "$HOME/.claude/state/self-improvement.json" <<'EOF'
{
  "last_reviewed_model": "claude-sonnet-5",
  "session_count_since_full_audit": 0,
  "last_full_audit_at": 0,
  "last_checked_at": 0,
  "last_handled_session_id": "",
  "pending_improver_suggestions": []
}
EOF
```
Expected: Task 1 Step 3 と同じ内容に戻る（次回の実セッションが正しく検知できるようにするため）

---

### Task 5: self-improvement-loop スキルの作成（Tier2）

**Files:**
- Create: `$HOME/.claude/skills/self-improvement-loop/SKILL.md`

**Interfaces:**
- Consumes: `$HOME/.claude/state/self-improvement.json`（Task 1）、Stop hook が stderr に出したシグナル理由（Task 2）
- Produces: `~/.claude/` 実ファイルへの trivial 編集、または提案テキストのみ。終了時に必ず `state.json` の `last_reviewed_model` / `session_count_since_full_audit` / `last_full_audit_at` / `last_handled_session_id` を更新する

- [ ] **Step 1: SKILL.md を作成**

```bash
mkdir -p "$HOME/.claude/skills/self-improvement-loop"
cat > "$HOME/.claude/skills/self-improvement-loop/SKILL.md" <<'SKILLEOF'
---
name: self-improvement-loop
description: |
  セッション終了時に self-improve-trigger.sh（Stop hook）が検知したシグナル（インシデント・モデルバージョン不一致・feedback/projectメモリ更新・累積セッション数閾値到達）を受けて、~/.claude/ 配下（CLAUDE.md・skills・agents・hooks・settings.json）の改善要否を判定し、低リスクな修正は自動適用、構造変更は提案に留める。

  Stop hook が exit 2 で終了をブロックし、stderr に「self-improvement-loop スキルを起動してください」という指示とシグナル理由を出した直後に、その指示に従って起動すること。ユーザーが明示的に「自己改善ループを回して」と言った場合も起動する。
---

# self-improvement-loop

あなた（Main）は、Stop hook（`~/.claude/hooks/self-improve-trigger.sh`）が検知したシグナルを受けて、`~/.claude/` の設定を点検・改善する。**司令塔に徹し、シグナルの裏取りと実際の編集はサブエージェントに委任する**。

## 手順

1. **シグナルの裏取り**: stderr に出力されたシグナル理由（インシデント/モデル不一致/メモリ更新/累積閾値）を general-purpose サブエージェントに渡し、以下を確認させる。grep結果を鵜呑みにせず、実際にファイルを読ませて裏取りすること。
   - インシデント: `~/.claude/hooks/bash-guard.sh` 等のブロックが実際に発生したか、なぜブロックされたか、指示不足が原因ならどの記述を直すべきか
   - モデルバージョン不一致: 現在のモデル世代で CLAUDE.md/skills/agents の記述が前提として古くないか
   - メモリ更新: 新規/更新された feedback・project メモリの内容と、現行の CLAUDE.md/skills/agents の記述に反映漏れがないか
   - 累積閾値到達: 直近の feedback/project メモリ群を俯瞰し、単発では気づけない繰り返しパターンがないか

2. **分類**: 見つかった各改善項目を、プロジェクトCLAUDE.mdの比例ルール表（trivial/small/substantial）で分類する。**`hooks/*.sh` または `settings.json` に関わる変更は、行数によらず常に small/substantial 扱いに固定する**（trivial 自動適用の対象外）。

3. **trivial 項目の適用**（CLAUDE.md / `skills/*/SKILL.md` / `agents/*.md` の記述修正のみが対象）:
   a. 編集前に対象ファイルの内容をバックアップ変数として保持する（ロールバック用）
   b. `~/.claude/` の実ファイルを直接編集する
   c. 構造検証を実行する:
      - 対象が `skills/*/SKILL.md` または `agents/*.md`（YAMLフロントマター付き）の場合: フロントマターを抽出し、`name`・`description` キーが存在し YAML として parse できるか確認する
      - 対象が `CLAUDE.md`（プレーンMarkdown）の場合: ファイルが非空であることのみ確認する
   d. 検証NG（フロントマター破壊・ファイル空文字化等）→ 直前のバックアップ内容へ書き戻し、「適用したが構造検証で問題検出、ロールバックした」と報告してこの項目の処理を終える
   e. 検証OK → 継続
   f. 編集対象に CLAUDE.md が含まれる場合、`claude-md-management:claude-md-improver` スキルを起動してスコア・追加改善提案を取得する（ブロッキングしない。追加提案は state.json の `pending_improver_suggestions` に文字列として追記する）

4. **small/substantial 項目**: 編集しない。チャットで簡潔に提案を提示し、ユーザーが望めば `superpowers:brainstorming` へ引き継ぐ旨を伝える。

5. **state.json の更新**（必ず最後に実行、jq で patch）:
   - `last_reviewed_model` を今回のモデルIDへ更新
   - `session_count_since_full_audit`: 累積閾値到達シグナルで起動した場合は `0` にリセットし `last_full_audit_at` を現在epoch秒に更新。それ以外の理由で起動した場合は `+1` する
   - `last_handled_session_id` を今回の `session_id` に更新（Tier1のループガード用）

6. **報告**: 「適用した内容」「ロールバックした内容（あれば）」「提案のみに留めた内容（あれば）」「claude-md-improver のスコア（CLAUDE.mdを触った場合）」を簡潔にユーザーへ報告する。git操作は一切行わないことを明記する。
SKILLEOF
```

- [ ] **Step 2: フロントマターのYAML妥当性を確認**

Run:
```bash
sed -n '/^---$/,/^---$/p' "$HOME/.claude/skills/self-improvement-loop/SKILL.md" | sed '1d;$d' | python3 -c "import sys,yaml; d=yaml.safe_load(sys.stdin); assert 'name' in d and 'description' in d; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: ファイル非空確認**

Run: `[ -s "$HOME/.claude/skills/self-improvement-loop/SKILL.md" ] && echo OK`
Expected: `OK`

---

## 完了後（このplanの範囲外・Mainが実施）

- `bash scripts/sync.sh` の実行は **ユーザーへの確認を経てから** Main が実施する（Global Constraints の「ループ本体は push しない」は実行時の話であり、実装物をリポジトリへ反映するこの一回限りの作業には適用されない。ただし sync.sh は commit+push まで自動実行するため、実行前に `git status`/diff を見せて確認を取ること）
- 次回以降の実セッションで Stop hook が実際に起動しシグナルを検知するかは、本plan内のドライランでは確認できない（Task 4 は手動での擬似実行に留まる）。初回の実発火は今後の通常セッションで観察する
