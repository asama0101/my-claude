# Rules/Skills → Agents 完全移行 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `~/.claude/rules/`（11ファイル）と `~/.claude/skills/`（8ディレクトリ）を全廃し、すべての知識をエージェント定義に統合する。

**Architecture:** 新規エージェント3本（python-dev / go-dev / api-designer）を作成し、既存エージェント3本（tdd-guide / code-reviewer / doc-updater）にスキル・ルールの内容をインライン統合する。Hook を改修してサブエージェント使用を自動強制する。

**Tech Stack:** Claude Code agent definitions (.md), bash hooks (.sh), CLAUDE.md

---

## ファイルマップ

| 操作 | ファイル | 内容 |
|------|---------|------|
| 強化 | `~/.claude/agents/tdd-guide.md` | python/go testing スキル・ルールを本文統合 |
| 強化 | `~/.claude/agents/code-reviewer.md` | coding-style ルールを追記 |
| 強化 | `~/.claude/agents/doc-updater.md` | impl-doc-builder スキルを末尾統合 |
| 新規 | `~/.claude/agents/python-dev.md` | Python/FastAPI パターン・コーディングスタイル |
| 新規 | `~/.claude/agents/go-dev.md` | Go/Gin パターン・コーディングスタイル |
| 新規 | `~/.claude/agents/api-designer.md` | REST API 設計パターン |
| 更新 | `~/.claude/CLAUDE.md` | エージェント表に3行追加、スキル欄を簡略化 |
| 更新 | `~/.claude/hooks/tdd-guard.sh` | python-dev 提案を追加 |
| 更新 | `~/.claude/hooks/tdd-guard-go.sh` | go-dev 提案を追加 |
| 削除 | `~/.claude/skills/{api-design,fastapi-patterns,...}/` | 8ディレクトリ削除 |
| 削除 | `~/.claude/rules/{python,go,common}/` | 11ファイル削除 |

---

## Task 1: tdd-guide に Python/Go テスト知識をインライン統合

**Files:**
- Modify: `~/.claude/agents/tdd-guide.md`（末尾の「言語別詳細ルール」セクションを実内容に置換）

- [ ] **Step 1: 現在の tdd-guide 末尾を確認**

```bash
tail -15 ~/.claude/agents/tdd-guide.md
```

Expected: `## 言語別詳細ルール` セクションが参照パスのみの状態（前回追加したもの）

- [ ] **Step 2: 「言語別詳細ルール」セクションを参照パスから実内容に置換**

`~/.claude/agents/tdd-guide.md` の末尾にある下記セクションを **削除** し、代わりに以下の実内容を書く。

削除対象（末尾12行）:
```
## 言語別詳細ルール

プロジェクト言語に応じて以下を Read で読むこと:
- **Python**: `~/.claude/rules/python/testing.md`（pytest・AAA パターン・非同期テスト）
- **FastAPI**: `~/.claude/rules/python/fastapi.md`（DI オーバーライド・AsyncClient）
- **Go**: `~/.claude/rules/go/testing.md`（テーブル駆動・testify・t.Cleanup）
- **Gin**: `~/.claude/rules/go/gin.md`（httptest・モックサービス）
```

置換内容（実ルールをインライン展開）:
```
## Python テスト規約

ソース: rules/python/testing.md
```
その後 `~/.claude/rules/python/testing.md` の **frontmatter を除いた全文** を追記。

続けて:
```
## Go テスト規約

ソース: rules/go/testing.md
```
その後 `~/.claude/rules/go/testing.md` の **frontmatter を除いた全文** を追記。

- [ ] **Step 3: スキル本文も統合（Python テスト詳細パターン）**

`~/.claude/skills/python-testing/SKILL.md` の frontmatter（`---`〜`---`）を除いた本文を、
`## Python テスト詳細パターン（pytest）` というセクションとして tdd-guide.md 末尾に追記。

- [ ] **Step 4: スキル本文も統合（Go テスト詳細パターン）**

`~/.claude/skills/go-testing/SKILL.md` の frontmatter を除いた本文を、
`## Go テスト詳細パターン（testify）` というセクションとして tdd-guide.md 末尾に追記。

- [ ] **Step 5: 検証**

```bash
grep -n "## Python テスト規約\|## Go テスト規約\|## Python テスト詳細\|## Go テスト詳細" \
  ~/.claude/agents/tdd-guide.md
```

Expected: 4行ヒット（それぞれのセクション見出し）

- [ ] **Step 6: commit**

```bash
cd ~/my-claude && bash sync_file.sh
```

Expected: `Done: agents` が出力され、git push 完了

---

## Task 2: code-reviewer に coding-style ルールを追記

**Files:**
- Modify: `~/.claude/agents/code-reviewer.md`（末尾にコーディングスタイルセクション追加）

- [ ] **Step 1: 現在の code-reviewer 末尾確認**

```bash
tail -10 ~/.claude/agents/code-reviewer.md
```

Expected: `## v1.8 AI 生成コードレビュー補足` で終わっていること

- [ ] **Step 2: Python コーディングスタイルルールを追記**

`~/.claude/agents/code-reviewer.md` 末尾に以下を追記:

```markdown

## Python コーディングスタイル規約
```

続けて `~/.claude/rules/python/coding-style.md` の frontmatter を除いた全文を追記。

- [ ] **Step 3: Go コーディングスタイルルールを追記**

続けて末尾に:

```markdown

## Go コーディングスタイル規約
```

続けて `~/.claude/rules/go/coding-style.md` の frontmatter を除いた全文を追記。

- [ ] **Step 4: 検証**

```bash
grep -n "## Python コーディングスタイル規約\|## Go コーディングスタイル規約" \
  ~/.claude/agents/code-reviewer.md
```

Expected: 2行ヒット

- [ ] **Step 5: commit**

```bash
cd ~/my-claude && bash sync_file.sh
```

---

## Task 3: doc-updater に impl-doc-builder スキルを統合

**Files:**
- Modify: `~/.claude/agents/doc-updater.md`

- [ ] **Step 1: 現在の doc-updater 末尾確認**

```bash
tail -5 ~/.claude/agents/doc-updater.md
```

- [ ] **Step 2: impl-doc-builder 本文を追記**

`~/.claude/agents/doc-updater.md` 末尾に以下を追記:

```markdown

## ドキュメント整備ワークフロー（impl-doc-builder）
```

続けて `~/.claude/skills/impl-doc-builder/SKILL.md` の frontmatter を除いた全文を追記。

- [ ] **Step 3: 検証**

```bash
grep -n "ドキュメント整備ワークフロー" ~/.claude/agents/doc-updater.md
```

Expected: 1行ヒット

- [ ] **Step 4: commit**

```bash
cd ~/my-claude && bash sync_file.sh
```

---

## Task 4: python-dev エージェント新規作成

**Files:**
- Create: `~/.claude/agents/python-dev.md`

- [ ] **Step 1: python-dev.md を新規作成（frontmatter + 呼び出しタイミング）**

`~/.claude/agents/python-dev.md` を以下の内容で作成:

```markdown
---
name: python-dev
description: Python/FastAPI 開発の専門家。コーディングスタイル・設計パターン・FastAPI 実装を担当。Python/FastAPI コードを書くときに積極的に活用。
tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
model: sonnet
---

## 呼び出しタイミング

以下の場合に使用すること:
- Python / FastAPI のコードを新規実装するとき
- 既存 Python コードをリファクタリングするとき
- FastAPI エンドポイント・スキーマ・DI を設計・実装するとき

汎用 `claude` エージェントで代替しないこと。
```

- [ ] **Step 2: Python コーディングスタイルを追記**

`## Python コーディングスタイル` というセクション見出しを追加した後、
`~/.claude/rules/python/coding-style.md` の frontmatter を除いた全文を追記。

- [ ] **Step 3: Python 設計パターンを追記**

`## Python 設計パターン` というセクション見出しを追加した後、
`~/.claude/rules/python/patterns.md` の frontmatter を除いた全文を追記。

- [ ] **Step 4: FastAPI ルールを追記**

`## FastAPI 規約` というセクション見出しを追加した後、
`~/.claude/rules/python/fastapi.md` の frontmatter を除いた全文を追記。

- [ ] **Step 5: Python パターンスキルを追記**

`## Python 実装パターン（詳細）` というセクション見出しを追加した後、
`~/.claude/skills/python-patterns/SKILL.md` の frontmatter を除いた全文を追記。

- [ ] **Step 6: FastAPI パターンスキルを追記**

`## FastAPI 実装パターン（詳細）` というセクション見出しを追加した後、
`~/.claude/skills/fastapi-patterns/SKILL.md` の frontmatter を除いた全文を追記。

- [ ] **Step 7: 検証**

```bash
grep -n "^## " ~/.claude/agents/python-dev.md
```

Expected（順番に）:
```
## 呼び出しタイミング
## Python コーディングスタイル
## Python 設計パターン
## FastAPI 規約
## Python 実装パターン（詳細）
## FastAPI 実装パターン（詳細）
```

```bash
wc -l ~/.claude/agents/python-dev.md
```

Expected: 1000行以上（ソース合計 ~1384行 + 見出し）

- [ ] **Step 8: commit**

```bash
cd ~/my-claude && bash sync_file.sh
```

---

## Task 5: go-dev エージェント新規作成

**Files:**
- Create: `~/.claude/agents/go-dev.md`

- [ ] **Step 1: go-dev.md を新規作成（frontmatter + 呼び出しタイミング）**

`~/.claude/agents/go-dev.md` を以下の内容で作成:

```markdown
---
name: go-dev
description: Go/Gin 開発の専門家。コーディングスタイル・設計パターン・Gin 実装を担当。Go/Gin コードを書くときに積極的に活用。
tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
model: sonnet
---

## 呼び出しタイミング

以下の場合に使用すること:
- Go / Gin のコードを新規実装するとき
- 既存 Go コードをリファクタリングするとき
- Gin ルーター・ハンドラー・ミドルウェアを設計・実装するとき

汎用 `claude` エージェントで代替しないこと。
```

- [ ] **Step 2: Go コーディングスタイルを追記**

`## Go コーディングスタイル` 見出し後に `~/.claude/rules/go/coding-style.md` の本文を追記。

- [ ] **Step 3: Go 設計パターンを追記**

`## Go 設計パターン` 見出し後に `~/.claude/rules/go/patterns.md` の本文を追記。

- [ ] **Step 4: Gin ルールを追記**

`## Gin 規約` 見出し後に `~/.claude/rules/go/gin.md` の本文を追記。

- [ ] **Step 5: Go パターンスキルを追記**

`## Go 実装パターン（詳細）` 見出し後に `~/.claude/skills/go-patterns/SKILL.md` の本文を追記。

- [ ] **Step 6: Gin パターンスキルを追記**

`## Gin 実装パターン（詳細）` 見出し後に `~/.claude/skills/gin-patterns/SKILL.md` の本文を追記。

- [ ] **Step 7: 検証**

```bash
grep -n "^## " ~/.claude/agents/go-dev.md
```

Expected:
```
## 呼び出しタイミング
## Go コーディングスタイル
## Go 設計パターン
## Gin 規約
## Go 実装パターン（詳細）
## Gin 実装パターン（詳細）
```

```bash
wc -l ~/.claude/agents/go-dev.md
```

Expected: 1000行以上

- [ ] **Step 8: commit**

```bash
cd ~/my-claude && bash sync_file.sh
```

---

## Task 6: api-designer エージェント新規作成

**Files:**
- Create: `~/.claude/agents/api-designer.md`

- [ ] **Step 1: api-designer.md を新規作成**

`~/.claude/agents/api-designer.md` を以下の内容で作成:

```markdown
---
name: api-designer
description: REST API 設計の専門家。リソース命名・ステータスコード・ページネーション・エラーレスポンス・バージョニングを担当。エンドポイント・スキーマ設計時に積極的に活用。
tools: ["Read", "Grep", "Glob"]
model: sonnet
---

## 呼び出しタイミング

以下の場合に使用すること:
- 新規 API エンドポイントを設計するとき
- 既存の API 契約をレビューするとき
- ページネーション・フィルタリング・ソートを追加するとき
- API のエラーハンドリングを設計するとき
- API バージョニング戦略を検討するとき
```

- [ ] **Step 2: API 設計パターン本文を追記**

`## REST API 設計パターン` 見出し後に `~/.claude/skills/api-design/SKILL.md` の frontmatter を除いた全文を追記。

- [ ] **Step 3: 検証**

```bash
grep -n "^## " ~/.claude/agents/api-designer.md
wc -l ~/.claude/agents/api-designer.md
```

Expected: セクション2本以上、400行以上

- [ ] **Step 4: commit**

```bash
cd ~/my-claude && bash sync_file.sh
```

---

## Task 7: CLAUDE.md のエージェント表・スキル欄を更新

**Files:**
- Modify: `~/.claude/CLAUDE.md`

- [ ] **Step 1: 現在のエージェント表を確認**

```bash
grep -n "python-dev\|go-dev\|api-designer\|e2e-runner" ~/.claude/CLAUDE.md
```

Expected: python-dev/go-dev/api-designer はヒットしない（まだ追加されていない）

- [ ] **Step 2: エージェント表に3行追加**

`~/.claude/CLAUDE.md` の `| e2e-runner |` 行の **直前** に以下3行を挿入:

```markdown
| python-dev | Python/FastAPI実装 | Python/FastAPI コードを書くとき |
| go-dev | Go/Gin実装 | Go/Gin コードを書くとき |
| api-designer | REST API設計 | エンドポイント・スキーマ設計時 |
```

- [ ] **Step 3: スキル欄を更新**

現在の `## スキル` セクション（2行）を以下に置換:

```markdown
## スキル

ローカル: `~/.claude/skills/session-close-improve`（セッション終了時の改善ワークフロー専用）。プラグイン（superpowers / context7）は `enabledPlugins` で有効化済み。  
context7 はライブラリ・SDK・API 質問で**必ず**使用（SessionStart フック参照）。`resolve-library-id` → `query-docs` の順。
```

- [ ] **Step 4: 検証**

```bash
grep -n "python-dev\|go-dev\|api-designer" ~/.claude/CLAUDE.md
grep -A3 "^## スキル" ~/.claude/CLAUDE.md
```

Expected: エージェント3行ヒット、スキル欄が session-close-improve のみ言及

- [ ] **Step 5: commit（CLAUDE.md は Bash 経由で sync）**

```bash
cd ~/my-claude && bash sync_file.sh
```

---

## Task 8: Hook 改修（tdd-guard.sh / tdd-guard-go.sh）

**Files:**
- Modify: `~/.claude/hooks/tdd-guard.sh`
- Modify: `~/.claude/hooks/tdd-guard-go.sh`

- [ ] **Step 1: tdd-guard.sh を改修**

`~/.claude/hooks/tdd-guard.sh` の出力メッセージを以下に変更:

変更前:
```bash
echo "⚠️  [tdd-guard] 実装ファイルを編集しました: $(basename "$FILE")" >&2
echo "   tdd-guide エージェントを使って TDD（テストファースト）で開発しましたか？" >&2
echo "   汎用 claude エージェントで代替しないこと（CLAUDE.md 参照）" >&2
```

変更後:
```bash
echo "⚠️  [tdd-guard] Python 実装ファイルを編集しました: $(basename "$FILE")" >&2
echo "   python-dev エージェント（実装）または tdd-guide エージェント（TDD）を使いましたか？" >&2
echo "   汎用 claude エージェントで代替しないこと（CLAUDE.md 参照）" >&2
```

- [ ] **Step 2: tdd-guard-go.sh を改修**

`~/.claude/hooks/tdd-guard-go.sh` の出力メッセージを以下に変更:

変更前:
```bash
echo "⚠️  [tdd-guard-go] 実装ファイルを編集しました: $(basename "$FILE")" >&2
echo "   tdd-guide エージェントを使って TDD（テストファースト）で開発しましたか？" >&2
echo "   汎用 claude エージェントで代替しないこと（CLAUDE.md 参照）" >&2
```

変更後:
```bash
echo "⚠️  [tdd-guard-go] Go 実装ファイルを編集しました: $(basename "$FILE")" >&2
echo "   go-dev エージェント（実装）または tdd-guide エージェント（TDD）を使いましたか？" >&2
echo "   汎用 claude エージェントで代替しないこと（CLAUDE.md 参照）" >&2
```

- [ ] **Step 3: 検証**

```bash
grep "python-dev\|go-dev" ~/.claude/hooks/tdd-guard.sh ~/.claude/hooks/tdd-guard-go.sh
```

Expected: 各ファイルで1行ヒット

- [ ] **Step 4: commit**

```bash
cd ~/my-claude && bash sync_file.sh
```

---

## Task 9: 旧ファイル削除（skills/ 8本・rules/ 11ファイル）

**⚠️ bash-guard.sh が rm をブロックするため、ユーザーが `! <コマンド>` で実行する必要がある。**  
各削除コマンドを提示し、ユーザーに実行を依頼すること。

- [ ] **Step 1: 削除対象の確認**

```bash
ls ~/.claude/skills/
find ~/.claude/rules -name "*.md" | sort
```

Expected:
- skills/: api-design, fastapi-patterns, gin-patterns, go-patterns, go-testing, impl-doc-builder, python-patterns, python-testing（8ディレクトリ）※ session-close-improve は残す
- rules/: 11ファイル

- [ ] **Step 2: ユーザーに skills 削除を依頼**

以下のコマンドをユーザーに提示し `! <コマンド>` で実行してもらう:

```bash
rm -rf ~/.claude/skills/api-design \
       ~/.claude/skills/fastapi-patterns \
       ~/.claude/skills/gin-patterns \
       ~/.claude/skills/go-patterns \
       ~/.claude/skills/go-testing \
       ~/.claude/skills/impl-doc-builder \
       ~/.claude/skills/python-patterns \
       ~/.claude/skills/python-testing
```

- [ ] **Step 3: ユーザーに rules 削除を依頼**

```bash
rm -rf ~/.claude/rules/python \
       ~/.claude/rules/go \
       ~/.claude/rules/common
```

- [ ] **Step 4: 削除後の状態確認**

```bash
ls ~/.claude/skills/
ls ~/.claude/rules/ 2>/dev/null || echo "rules/ is empty or gone"
```

Expected:
- skills/: `session-close-improve` のみ
- rules/: 空またはディレクトリなし

- [ ] **Step 5: 最終 commit**

```bash
cd ~/my-claude && bash sync_file.sh
```

---

## 最終検証

```bash
# エージェント数（10本）
echo "=== agents ===" && ls ~/.claude/agents/

# スキル残存（session-close-improve のみ）
echo "=== skills ===" && ls ~/.claude/skills/

# rules 全廃
echo "=== rules ===" && ls ~/.claude/rules/ 2>/dev/null || echo "(空)"

# CLAUDE.md に新エージェント3本
echo "=== CLAUDE.md ===" && grep -E "python-dev|go-dev|api-designer" ~/.claude/CLAUDE.md

# Hook 改修確認
echo "=== hooks ===" && grep "python-dev\|go-dev" ~/.claude/hooks/tdd-guard*.sh
```
