# ~/.claude MD 統廃合・命名統一 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans でタスク単位に実行する。チェックボックス（`- [ ]`）で進捗管理。
> **重要な実行制約:** `~/.claude/agents/` はフックによりサブエージェントの編集がブロックされるため、**本計画は Main がインライン実行する**（subagent-driven-development は使用不可）。

**Goal:** `~/.claude/` の MD を統廃合（plans/ 約50件削除）し、agents/（対象→役割）・references/（裸名詞）の命名規約へ12ファイルをリネームし、全参照を追随更新する。

**Architecture:** フックの制約（`~/.claude` 配下の mv/rm 不可・agents/ のサブエージェント編集不可）に合わせ、①削除・リネームはプロジェクト配下スクリプトに集約してユーザーが `! bash` で1回実行、②参照更新は Main が Edit で直接実施、③検証は旧名の全文 grep ゼロ、④最後に `scripts/sync.sh`（rsync --delete）でミラーへ反映する。

**Tech Stack:** bash（mv / find）・Edit ツール・grep 検証。テストコードは無し（設定資産のため、検証＝grep 残存ゼロ＋ls 実在確認）。

## Global Constraints

- 仕様の正典: `docs/2026-07-02-md-consolidation-naming-design.md`
- 命名規約: agents = `<対象・領域>-<役割>`（汎用役割は裸名可）／references/ = 裸名詞（`_template.md` は雛形慣習として例外）
- plans/ 削除基準: mtime が 2026-06-26 より古いもののみ削除（06-26 以降は保持）
- `~/.claude/hooks/`・`settings.json` は編集しない（旧名参照なしを確認済み・ロック領域）
- `cache/changelog.md` は触らない（製品キャッシュ）
- グループ表記 `reviewer-*` は全て `*-reviewer` に置換する
- コミット・push は最後の `scripts/sync.sh`（auto commit+push）に集約。途中コミットはしない

### リネーム対応表（全タスク共通・正典）

| 旧 | 新 |
|----|----|
| agents/reviewer-correctness.md | agents/correctness-reviewer.md |
| agents/reviewer-maintainability.md | agents/maintainability-reviewer.md |
| agents/reviewer-performance.md | agents/performance-reviewer.md |
| agents/reviewer-security.md | agents/security-reviewer.md |
| agents/reviewer-test.md | agents/test-reviewer.md |
| agents/references/api-design-patterns.md | agents/references/api-design.md |
| agents/references/doc-building-patterns.md | agents/references/doc-building.md |
| agents/references/fastapi-patterns.md | agents/references/fastapi.md |
| agents/references/pytest-patterns.md | agents/references/pytest.md |
| agents/references/python-patterns.md | agents/references/python.md |
| agents/references/planner-examples.md | agents/references/planner.md |
| agents/references/review-protocol.md | agents/references/review.md |

---

### Task 1: リネーム＆plans掃除スクリプトの作成とユーザー実行

**Files:**
- Create: `scripts/cleanup-md-restructure.sh`

**Interfaces:**
- Produces: 新パスのファイル実体（Task 2 以降の Edit 対象）。plans/ は直近7日分のみ残存。

- [ ] **Step 1: スクリプトを書く**

```bash
#!/usr/bin/env bash
# ~/.claude MD 統廃合・命名統一（2026-07-02 設計書準拠）
# 実行はユーザーが `! bash scripts/cleanup-md-restructure.sh` で行う（フック回避のため）
set -euo pipefail

C="$HOME/.claude"

# 1) agents/ リネーム（対象→役割）
mv "$C/agents/reviewer-correctness.md"     "$C/agents/correctness-reviewer.md"
mv "$C/agents/reviewer-maintainability.md" "$C/agents/maintainability-reviewer.md"
mv "$C/agents/reviewer-performance.md"     "$C/agents/performance-reviewer.md"
mv "$C/agents/reviewer-security.md"        "$C/agents/security-reviewer.md"
mv "$C/agents/reviewer-test.md"            "$C/agents/test-reviewer.md"

# 2) agents/references/ リネーム（裸名詞）
mv "$C/agents/references/api-design-patterns.md"   "$C/agents/references/api-design.md"
mv "$C/agents/references/doc-building-patterns.md" "$C/agents/references/doc-building.md"
mv "$C/agents/references/fastapi-patterns.md"      "$C/agents/references/fastapi.md"
mv "$C/agents/references/pytest-patterns.md"       "$C/agents/references/pytest.md"
mv "$C/agents/references/python-patterns.md"       "$C/agents/references/python.md"
mv "$C/agents/references/planner-examples.md"      "$C/agents/references/planner.md"
mv "$C/agents/references/review-protocol.md"       "$C/agents/references/review.md"

# 3) plans/ 掃除: mtime 2026-06-26 より古い .md を削除（06-26 以降は保持）
echo "--- plans/ 削除対象 ---"
find "$C/plans" -maxdepth 1 -name '*.md' ! -newermt 2026-06-26 -print -delete

echo "--- 完了。残存 plans: $(find "$C/plans" -maxdepth 1 -name '*.md' | wc -l) 件 ---"
```

- [ ] **Step 2: ユーザーに実行を依頼**

依頼文: 「`! bash scripts/cleanup-md-restructure.sh` を実行してください（12ファイルのリネームと plans/ 約50件の削除）」

- [ ] **Step 3: 実行結果を検証**

Run: `ls ~/.claude/agents/ ~/.claude/agents/references/ && find ~/.claude/plans -maxdepth 1 -name '*.md' | wc -l`
Expected: 新名12ファイルが存在・旧名が不在・plans が約29件

---

### Task 2: agents/ 配下の参照・frontmatter 更新（Main が直接 Edit）

**Files:**
- Modify: 下表の13ファイル（すべて `~/.claude/agents/` 配下・新名パス）

**Interfaces:**
- Consumes: Task 1 のリネーム済みファイル実体
- Produces: agents/ 配下から旧名参照ゼロ

- [ ] **Step 1: reviewer 5本の frontmatter `name:` と共通参照を更新**

各ファイルの置換（5本とも同型）:

| ファイル | 置換 |
|---------|------|
| correctness-reviewer.md:2 | `name: reviewer-correctness` → `name: correctness-reviewer` |
| maintainability-reviewer.md:2 | `name: reviewer-maintainability` → `name: maintainability-reviewer` |
| performance-reviewer.md:2 | `name: reviewer-performance` → `name: performance-reviewer` |
| security-reviewer.md:2 | `name: reviewer-security` → `name: security-reviewer` |
| test-reviewer.md:2 | `name: reviewer-test` → `name: test-reviewer` |
| 上記5本の :10 | `references/review-protocol.md` → `references/review.md` |
| test-reviewer.md:62 | `reviewer-maintainability` → `maintainability-reviewer` |

- [ ] **Step 2: その他 agents 本体の参照を更新**

| ファイル | 置換 |
|---------|------|
| planner.md:62, :121 | `references/planner-examples.md` → `references/planner.md` |
| planner.md:144 | `reviewer-maintainability` → `maintainability-reviewer` |
| python-dev.md:70, :128 | `reviewer-maintainability` → `maintainability-reviewer` |
| python-dev.md:167 | `references/python-patterns.md` → `references/python.md` |
| python-dev.md:168 | `references/fastapi-patterns.md` → `references/fastapi.md` |
| python-dev.md:169 | `references/api-design-patterns.md` → `references/api-design.md` |
| python-dev.md:170 | `references/pytest-patterns.md` → `references/pytest.md` |
| doc-updater.md:126 | `references/doc-building-patterns.md` → `references/doc-building.md` |
| gate-generator.md:19 | `references/pytest-patterns.md` → `references/pytest.md` |
| gate-evaluator.md:3, :24 | `reviewer-*` → `*-reviewer` |

- [ ] **Step 3: references/ 内の相互参照・自己申告コメントを更新**

| ファイル | 置換 |
|---------|------|
| review.md:1 | `reviewer-* 共通リファレンス` → `*-reviewer 共通リファレンス` |
| review.md:3 | `reviewer-correctness / reviewer-security / reviewer-performance / reviewer-test / reviewer-maintainability` → `correctness-reviewer / security-reviewer / performance-reviewer / test-reviewer / maintainability-reviewer` |
| api-design.md:412 | `references/fastapi-patterns.md` → `references/fastapi.md` |
| api-design.md:413 | `references/pytest-patterns.md` → `references/pytest.md` |
| fastapi.md:218 | `python-patterns.md` を含む参照 → `python.md` |
| fastapi.md:266 | `pytest-patterns.md` を含む参照 → `pytest.md` |
| fastapi.md:353〜355 | `python-patterns.md`/`pytest-patterns.md`/`api-design-patterns.md` → `python.md`/`pytest.md`/`api-design.md` |

（fastapi.md:1/6・python.md:1/6 のタイトル二重掲載はヘッダ冗長のみで本計画のスコープ外。触らない）

- [ ] **Step 4: agents/ 配下の残存検証**

Run: `grep -rnE 'reviewer-(correctness|maintainability|performance|security|test)|(-patterns|planner-examples|review-protocol)\.md|reviewer-\*' ~/.claude/agents/`
Expected: マッチ 0 件

---

### Task 3: skills/ と ~/.claude/CLAUDE.md の参照更新

**Files:**
- Modify: `~/.claude/skills/tdd-gates/SKILL.md`, `~/.claude/skills/tdd-gates/references/gates.md`, `~/.claude/skills/tdd-gates/references/profiles/pytest.md`, `~/.claude/CLAUDE.md`, `~/.claude/skills/session-close-improve/SKILL.md`（:22 に `reviewer-*` があれば）

**Interfaces:**
- Consumes: リネーム対応表
- Produces: skills/・CLAUDE.md から旧名参照ゼロ

- [ ] **Step 1: tdd-gates スキルの更新**

| ファイル | 置換 |
|---------|------|
| SKILL.md:47, :50, :53 | `reviewer-*` → `*-reviewer` |
| SKILL.md:72 | `pytest-patterns.md`（深い作法の参照） → `pytest.md`（`agents/references/` 側のパスであることに注意。profiles/pytest.md と混同しない） |
| gates.md:33, :36, :71, :74 | `reviewer-*` → `*-reviewer` |
| gates.md:32 | 行内に旧 reviewer 名があれば新名へ（実行時に grep で確認） |
| profiles/pytest.md:4, :50 | `agents/references/pytest-patterns.md` → `agents/references/pytest.md` |
| profiles/pytest.md:51 | `agents/references/python-patterns.md` → `agents/references/python.md` |

- [ ] **Step 2: ~/.claude/CLAUDE.md の更新**

| 箇所 | 置換 |
|------|------|
| :28（レビュー単独ルート） | `reviewer-*` → `*-reviewer` |
| :49（並列実行） | `reviewer-*` → `*-reviewer` |
| :57（gate-evaluator 行） | `reviewer-*` → `*-reviewer` |
| :58 | `reviewer-correctness / -performance / -security / -maintainability` → `correctness- / performance- / security- / maintainability-reviewer` |
| :59 | `reviewer-test` → `test-reviewer` |

- [ ] **Step 3: session-close-improve/SKILL.md:22 を確認・必要なら更新**

Run: `grep -n 'reviewer' ~/.claude/skills/session-close-improve/SKILL.md`
`reviewer-*` 表記があれば `*-reviewer` へ置換。

- [ ] **Step 4: skills/・CLAUDE.md の残存検証**

Run: `grep -rnE 'reviewer-(correctness|maintainability|performance|security|test)|(-patterns|planner-examples|review-protocol)\.md|reviewer-\*' ~/.claude/skills/ ~/.claude/CLAUDE.md`
Expected: マッチ 0 件

---

### Task 4: メモリの更新（旧名言及の修正＋命名規約の記録）

**Files:**
- Modify: `~/.claude/projects/-home-asama-my-claude/memory/` 配下の `MEMORY.md`, `project-agents-restructure.md`, `project-claude-config-inventory.md`, `project-tdd-gates-harness.md`, `feedback-cross-review-html.md`（要確認）

**Interfaces:**
- Produces: メモリの現状記述が新名と一致。命名規約が `project-claude-config-inventory.md` に記録され将来セッションから参照可能。

- [ ] **Step 1: 旧名言及を新名へ更新**

対象を確定するため実行: `grep -rnE 'reviewer-(correctness|maintainability|performance|security|test)|(-patterns|planner-examples|review-protocol)\.md|reviewer-\*' ~/.claude/projects/-home-asama-my-claude/memory/`

判明済みの置換:

| ファイル | 置換 |
|---------|------|
| project-agents-restructure.md:15 | `references/review-protocol.md` → `references/review.md`、`reviewer-maintainability` → `maintainability-reviewer`、`reviewer-test` → `test-reviewer` |
| project-agents-restructure.md:16 | `references/planner-examples.md` → `references/planner.md`、`references/api-design-patterns.md` → `references/api-design.md` |
| project-claude-config-inventory.md:21 | `python-patterns.md` → `python.md` |
| project-tdd-gates-harness.md:14 と MEMORY.md:14 | `reviewer-*温存` → `*-reviewer温存（2026-07-02 対象→役割へ改名）`（歴史記述のため注記形式で） |
| feedback-cross-review-html.md:14 | `reviewer-*` 表記があれば `*-reviewer` へ |

- [ ] **Step 2: 命名規約を project-claude-config-inventory.md に追記**

本文末尾に追記する内容（そのまま使用）:

```markdown
**命名規約（2026-07-02 統一）:** agents/ は `<対象・領域>-<役割>`（例: correctness-reviewer・python-dev。汎用役割は裸名可: planner）。references/ 配下は裸名詞（サフィックス禁止・種別は冒頭の自己申告コメントで表す。`_template.md` は雛形慣習として例外）。旧 reviewer-* / *-patterns.md / planner-examples.md / review-protocol.md は 2026-07-02 に一括改名済み。
```

MEMORY.md の該当索引行（project-claude-config-inventory）の末尾に「・命名規約（agents=対象→役割/references=裸名詞）も本ファイルが正」を追記。

---

### Task 5: 全体検証と同期

**Files:**
- 変更なし（検証と `scripts/sync.sh` 実行依頼のみ）

- [ ] **Step 1: 旧名の全文 grep（最終検証）**

Run:
```bash
grep -rnE 'reviewer-(correctness|maintainability|performance|security|test)|(api-design|doc-building|fastapi|pytest|python)-patterns\.md|planner-examples\.md|review-protocol\.md|reviewer-\*' \
  ~/.claude/CLAUDE.md ~/.claude/agents/ ~/.claude/skills/ ~/.claude/settings.json \
  ~/.claude/projects/-home-asama-my-claude/memory/
```
Expected: マッチ 0 件（`~/.claude/plans/`・`cache/`・リポジトリ側 `docs/` の設計書・本計画は歴史記録なので対象外）

- [ ] **Step 2: リポジトリの差分確認**

Run: `git -C ~/my-claude status --short`
Expected: `docs/` の設計書・本計画・`scripts/cleanup-md-restructure.sh` のみが未追跡/変更（想定外の差分があれば sync 前にユーザーへ報告）

- [ ] **Step 3: ユーザーに sync 実行を依頼**

依頼文: 「`! bash scripts/sync.sh` を実行してください（`~/.claude` → `claude/` ミラー同期＋auto commit/push。旧名ファイルは rsync --delete でミラーから消えます）」
（エージェントの push はフック分類器にブロックされるため Main からは実行しない）

- [ ] **Step 4: ミラーの事後確認**

Run: `ls ~/my-claude/claude/agents/ ~/my-claude/claude/agents/references/ && git -C ~/my-claude log --oneline -1`
Expected: ミラーに新名のみ存在・同期コミットが積まれている
