# session-close-improve STEP 再構成 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `~/.claude/skills/session-close-improve/SKILL.md` の STEP 番号を線形 1–5 に振り直し、あわせて高2件・中3件のロジック修正を施す。

**Architecture:** 単一の markdown スキル定義（SKILL.md）の構成編集。コードテストは存在しないため、各タスクの検証は grep ベースの構造チェックと目視で行う。編集後 `scripts/sync.sh` で `claude/` ミラーへ反映（commit + push 自動）。

**Tech Stack:** Markdown / bash（grep, git） / `scripts/sync.sh`

## Global Constraints

- 対象は `~/.claude/skills/session-close-improve/SKILL.md` のみ（＋波及で `~/.claude/hooks/session-stop.sh` の要約列挙1箇所）。
- **不変対象に触れない**: 振り返り本体・ゲート定義群（実害3条件/先回り3条件）・クローズ/メモリ保存・各種閉ループ（完了＝行削除・未実行同期）。
- 編集は必ず対象ファイルを Read してから行う（行番号は設計時点の目安。実テキストは Read で確認）。
- スコープ外: バックログ機構そのものの再設計、ラダーのゲート条件変更、振り返りの質評価二段ゲートのロジック変更。
- 設計の正本: `docs/2026-06-20-session-close-step-restructure-design.md`。
- **コミット運用（重要）**: `~/.claude/` は **git 管理ではない**（確認済み: `git -C ~/.claude rev-parse --git-dir` が fatal）。編集は `~/.claude/...` に対して行い、バージョン管理は my-claude repo の `claude/` ミラーで行う。**タスクごとの個別コミットは行わず**、全編集（Task 1–4）完了後に Task 5 で `scripts/sync.sh` を1回実行して `~/.claude/` → `claude/` をミラー反映＋ commit + push する。各タスクのレビューゲートは末尾の grep 検証で代替する。

---

### Task 1: STEP 番号の線形化＋アーカイブ末尾移動（構造変更・H1）

**Files:**
- Modify: `~/.claude/skills/session-close-improve/SKILL.md`（全 STEP 見出し・現 Step 1.5 ブロックの移動・Step 1 末尾の制御ノート移設）

**Interfaces:**
- Produces: 新しい STEP 見出し体系（`## Step 1`〜`## Step 5`）。後続タスクはこの見出し名で各 STEP を参照する。
  - Step 1 = 振り返り（旧 Step 1）
  - Step 2 = 改善バックログ 取込・提示・選択（旧 Step 2.0）
  - Step 3 = 最小更新（旧 Step 2）
  - Step 4 = spec/plan アーカイブ・条件付（旧 Step 1.5・末尾へ移動）
  - Step 5 = クローズ／メモリ保存（旧 Step 3）

- [ ] **Step 1: SKILL.md 全体を Read して現状の STEP 見出し・行範囲を確認**

対象: `~/.claude/skills/session-close-improve/SKILL.md`。現 Step 1 / 1.5 / 2.0 / 2 / 3 の見出し行と各ブロックの開始・終了行を特定する。

- [ ] **Step 2: 現状の小数番号を検証（変更前ベースライン）**

Run: `grep -nE '^#+ *Step (1\.5|2\.0)' ~/.claude/skills/session-close-improve/SKILL.md`
Expected: 2行ヒット（`Step 1.5` と `Step 2.0` が存在する）

- [ ] **Step 3: 現 Step 1.5（spec/plan アーカイブ）ブロックを切り出し、現 Step 2（最小更新）の直後・現 Step 3（クローズ）の直前へ移動**

旧 Step 1.5 のブロック全体（見出し＋本文＋スキップ条件）を、新 Step 3（最小更新）の末尾の後、Step 5（クローズ）の前に移す。移動先での見出しを `## Step 4: spec/plan アーカイブ（docs/superpowers/ がある時のみ）` とする。

- [ ] **Step 4: Step 1 末尾の制御ノートを Step 4 冒頭へ移設**

旧 Step 1 末尾にある「`docs/superpowers/` がある時のみ実施／Step 2 の有無と独立」の制御ノート一文を Step 1 から削除し、新 Step 4 の冒頭スキップ条件として配置する（例: 「**スキップ条件**: `docs/superpowers/` が無ければ本 STEP 全体をスキップ。本 STEP は他 STEP と独立した housekeeping。」）。

- [ ] **Step 5: 残る見出しを線形 1–5 に振り直す**

- 旧 `## Step 2.0`（バックログ）→ `## Step 2`
- 旧 `## Step 2`（最小更新）→ `## Step 3`
- 旧 `## Step 3`（クローズ）→ `## Step 5`
- （Step 1 は据え置き、アーカイブは Step 4）

本文中に STEP 番号への相互参照（例: 「Step 2.0 で」「Step 2 のゲート」）があれば、新番号へ全て追従修正する。

- [ ] **Step 6: 小数番号が消えたことを検証**

Run: `grep -nE 'Step *[0-9]+\.[0-9]' ~/.claude/skills/session-close-improve/SKILL.md`
Expected: ヒット0件（小数番号が残っていない）

- [ ] **Step 7: 連番 1–5 が揃ったことを検証**

Run: `grep -nE '^#+ *Step [1-9]' ~/.claude/skills/session-close-improve/SKILL.md`
Expected: `Step 1`〜`Step 5` が各1回、この順で出現。Step 4 が「アーカイブ」、Step 5 が「クローズ」であること。

- [ ] **Step 8: レビューゲート（コミットは Task 5 に集約）**

`~/.claude` は git 非管理のため個別コミットは行わない。Step 6–7 の grep 検証が green であることをもって本タスクのレビューゲートとし、次タスクへ進む。

---

### Task 2: ルーティング二重定義の解消（H2）

**Files:**
- Modify: `~/.claude/skills/session-close-improve/SKILL.md`（Step 2 の (c) ルーティング、Step 3 の type→機構 対応表）

**Interfaces:**
- Consumes: Task 1 の新 STEP 見出し（Step 2 = バックログ、Step 3 = 最小更新）。
- Produces: type→機構（ラダー②〜⑥／revise→improver／sync）の対応表が **Step 3 のみ** に存在する状態。

- [ ] **Step 1: Step 2 と Step 3 の該当箇所を Read**

Step 2 内の「(c) type 別ルーティング」記述と、Step 3 内の「反・増殖ラダー②〜⑥／更新表」を読み、両者が同じ type→機構の振り分けを二重記述していることを確認する。

- [ ] **Step 2: Step 2 の (c) を一文へ縮約**

Step 2 の (c) ルーティング記述を、type 別の振り分け詳細を削除し「(c) 選択された項目を Step 3 の更新機構（ラダー②〜⑥）へ渡す」という一文へ置き換える。type→機構の対応詳細は Step 2 からは消す。

- [ ] **Step 3: type→機構の対応表を Step 3 に一本化**

Step 3 側にラダー②〜⑥／revise→improver／sync への対応表が完全な形で存在することを確認し、不足があれば Step 2 から移した内容で補完する（重複ではなく移設）。

- [ ] **Step 4: 対応表が Step 3 のみに存在することを検証**

Run: `grep -nE 'ラダー|revise→improver|→improver' ~/.claude/skills/session-close-improve/SKILL.md`
Expected: type→機構の対応表に相当する記述が Step 3 のブロック行範囲にのみ出現し、Step 2 ブロックには振り分け詳細が残っていない（目視確認）。

- [ ] **Step 5: レビューゲート（コミットは Task 5 に集約）**

Step 4 の検証が green であることをもってレビューゲートとし、次タスクへ進む。

---

### Task 3: 中重大度の文言修正（M1/M2/M3）

**Files:**
- Modify: `~/.claude/skills/session-close-improve/SKILL.md`（Step 1 の今やる判定、Step 3 のラダー①、Step 2 の空スキップ）

**Interfaces:**
- Consumes: Task 1 の新 STEP 見出し、Task 2 の縮約後 Step 2。

- [ ] **Step 1: 3箇所を Read**

Step 1 の「今やる/寝かせる」判定文、Step 3 のラダー①記述、Step 2 の「バックログ空＝スキップ」記述を読む。

- [ ] **Step 2: M1 — Step 1 の「今やる」にゲート前方参照を追加**

Step 1 の「今やる」判定文に、後段ゲートを前方参照する語を加える。例: 「**今やる**（Step 3 の実害3条件／先回り3条件のいずれかを満たす見込みのもの）／**寝かせる**（満たさない・判断保留）」。

- [ ] **Step 3: M2 — Step 3 ラダー①を一方向化**

Step 3 のラダー①「バックログへ append」を「① ゲート不充足なら Step 2 のバックログへ送る（後退は一方向。本 STEP の実効選択肢は②〜⑥）」と書き換え、実行 STEP 内で前段へ戻るループに読めない表現にする。

- [ ] **Step 4: M3 — Step 2 の空スキップを明確化**

Step 2 の「バックログ空＝スキップ」を「バックログが空ならこの提示・選択を飛ばす（Step 1 の『今やる』項目があれば Step 3 の更新は実行する）」と書き換え、更新 STEP 全体のスキップと誤読されないようにする。

- [ ] **Step 5: 3文言の反映を検証**

Run: `grep -nE '実効選択肢|提示・選択を飛ばす|満たす見込み|前方|Step 3 の(実害|更新)' ~/.claude/skills/session-close-improve/SKILL.md`
Expected: M1/M2/M3 に対応する新文言がそれぞれヒットする（目視で3箇所反映を確認）。

- [ ] **Step 6: レビューゲート（コミットは Task 5 に集約）**

Step 5 の検証が green であることをもってレビューゲートとし、次タスクへ進む。

---

### Task 4: session-stop.sh フックメッセージの整合

**Files:**
- Modify: `~/.claude/hooks/session-stop.sh`（決定ブロック時の要約列挙メッセージ1箇所）

**Interfaces:**
- Consumes: Task 1 の新 STEP 順序。

- [ ] **Step 1: 該当メッセージを Read**

Run: `grep -nE '\[1\]|\[2\]|\[3\]|アーカイブ|振り返り' ~/.claude/hooks/session-stop.sh`
Expected: 「[1]サブエージェント/スキル使用の振り返り [2]superpowers spec/plan の done/ アーカイブ [3]最小更新とメモリ保存」相当の要約列挙行を特定。

- [ ] **Step 2: 要約列挙を新順序へ整える**

要約を新 STEP 順序（振り返り → バックログ → 最小更新 → アーカイブ → クローズ）に合わせて並べ替える。例: 「[1]振り返り [2]改善バックログ取込 [3]最小更新 [4]spec/plan アーカイブ [5]メモリ保存」。番号厳密化は必須ではないが、アーカイブが更新より後に来る並びにすること。

- [ ] **Step 3: 構文チェック**

Run: `bash -n ~/.claude/hooks/session-stop.sh`
Expected: 構文エラーなし（出力なし・終了コード0）

- [ ] **Step 4: レビューゲート（コミットは Task 5 に集約）**

Step 3 の構文チェックが green であることをもってレビューゲートとし、Task 5 のミラー同期へ進む。

---

### Task 5: ミラー同期と受け入れ検証

**Files:**
- Modify: `claude/skills/session-close-improve/SKILL.md`・`claude/hooks/session-stop.sh`（`scripts/sync.sh` が `~/.claude/` から自動反映）

**Interfaces:**
- Consumes: Task 1〜4 の編集済み `~/.claude/` 配下ファイル。

- [ ] **Step 1: 受け入れ基準を一括検証（編集元）**

Run: `grep -cE 'Step *[0-9]+\.[0-9]' ~/.claude/skills/session-close-improve/SKILL.md; grep -nE '^#+ *Step [1-9]' ~/.claude/skills/session-close-improve/SKILL.md`
Expected: 1行目（小数番号カウント）= `0`。2行目で Step 1〜5 が順に出現し、Step 4=アーカイブ・Step 5=クローズ。

- [ ] **Step 2: 不変対象が壊れていないことを確認**

`git -C ~/.claude diff` で振り返り本体・ゲート定義（実害3条件/先回り3条件）・クローズ/メモリ保存・閉ループ（完了＝行削除・未実行同期）に意図しない変更が入っていないことを目視確認する。

- [ ] **Step 3: ミラー同期を実行**

`scripts/sync.sh` 実行前に余計な差分が無いことを確認（リポジトリ規約）。

Run: `cd /home/asama/my-claude && git status --short`
Expected: 想定外の未追跡・変更ファイルが無い。問題なければ `bash scripts/sync.sh` を実行（`~/.claude/` → `claude/` 反映＋ commit + push 自動）。

- [ ] **Step 4: ミラー反映を検証**

Run: `grep -cE 'Step *[0-9]+\.[0-9]' /home/asama/my-claude/claude/skills/session-close-improve/SKILL.md`
Expected: `0`（ミラー側にも小数番号が残っていない＝同期成功）。

---

## Self-Review

**Spec coverage:**
- 線形番号化 → Task 1。
- H1 アーカイブ末尾移動＋制御ノート移設 → Task 1 Step 3–4。
- H2 ルーティング一本化 → Task 2。
- M1/M2/M3 → Task 3。
- 波及 session-stop.sh → Task 4。
- 波及 sync ミラー → Task 5。
- 受け入れ基準（小数番号ゼロ・順序・対応表一本化・不変対象保護）→ Task 1 Step 6–7・Task 2 Step 4・Task 5 Step 1–2。全項目に対応タスクあり。

**Placeholder scan:** 各 Step に具体的な grep コマンドと期待値、編集の意図と新文言例を記載。markdown 編集のため verbatim old_string は実装時 Read で確定する旨を Global Constraints に明記済み。

**Type consistency:** STEP 見出し名（Step 1=振り返り / 2=バックログ / 3=最小更新 / 4=アーカイブ / 5=クローズ）を全タスクで統一。Task 2 以降は Task 1 の新見出しを Consumes として参照。

**コミット運用（確定済み）:** `~/.claude/` は git 非管理（確認済み）。Task 1–4 は `~/.claude/...` を編集するのみで個別コミットせず、各タスクは末尾 grep 検証をレビューゲートとする。コミット＋push は Task 5 の `scripts/sync.sh` 1回に集約（ミラー `claude/` 側で実行）。1コミットに全変更が入るため、Task 5 Step 3 の事前 `git status` 確認で想定外差分が混ざらないことを必ずチェックする。
