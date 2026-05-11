# rules/ ファイル一括修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** レビューで発見した7件の問題（frontmatter 欠落・paths 不整合・重複・内容不足・言語指定欠落）をすべて修正する

**Architecture:** ドキュメントのみの変更。各タスクは独立したファイルを対象とし、依存関係なし。すべてのタスクを任意の順序で実行できる。

**Tech Stack:** Markdown のみ

---

## ファイル構成

```
rules/
  github.md        ← Task 1（Fix 1: frontmatter 追加 / Fix 7: 言語指定追加）
  design-review.md ← Task 2（Fix 2: paths 追加 / Fix 6: 重要度ラベル追加）
  code-review.md   ← Task 3（Fix 3: N+1 参照追記）
  container.md     ← Task 4（Fix 4: シークレット参照追記）
  testing.md       ← Task 5（Fix 5: 2セクション追加）
```

---

## Task 1: github.md — frontmatter 追加 + コードブロック言語指定追加

**Files:**
- Modify: `rules/github.md`

**修正理由:**
- frontmatter がないため、Claude がどのファイルを編集しているときも github.md が自動ロードされない。コミット規約・gitignore 必須エントリが参照されず、誤コミットや規約外コミットが起きるリスクがある
- `docs.md` が「コードブロック: 言語指定必須」と規定しているのに、自ファイルの `.gitignore` ブロックが無指定で自己矛盾している

- [ ] **Step 1: `rules/github.md` を読んで現在の冒頭と `.gitignore` コードブロック位置を確認する**

- [ ] **Step 2: ファイル先頭に frontmatter を追加する**

`rules/github.md` の先頭（`# GitHub運用` の前）に以下を挿入する:

```
---
paths:
  - "**"
---
```

- [ ] **Step 3: `.gitignore` コードブロックの言語指定を追加する**

現在の `.gitignore` ブロック（` ``` ` のみで始まる行）を ` ```gitignore ` に変更する。

- [ ] **Step 4: 目視確認**

- ファイル先頭が `---\npaths:\n  - "**"\n---\n# GitHub運用` になっていること
- `.gitignore` ブロックが ` ```gitignore ` で始まっていること

- [ ] **Step 5: コミット**

```bash
git add rules/github.md
git commit -m "fix(rules): github.md に frontmatter を追加し .gitignore ブロックに言語指定を追加"
```

---

## Task 2: design-review.md — paths 追加 + 重要度ラベル追加

**Files:**
- Modify: `rules/design-review.md`

**修正理由:**
- CLAUDE.md の索引には `docs/**`, `**/*.html`, `**/*.md` と記載されているが frontmatter は `docs/**` のみ。HTML 設計書・ADR・外部仕様書（`.md`）の編集時にレビュー観点がロードされない
- 約30項目がフラットに並んでいて優先度が不明。Claude がレビューする際に何を必ず確認すべきかわからないため、重要度ラベルを追加して「必ず確認」と「余裕があれば確認」を区別する

- [ ] **Step 1: `rules/design-review.md` を読んで現在の frontmatter と全セクション見出しを確認する**

- [ ] **Step 2: frontmatter に paths を2行追加する**

現在:
```yaml
---
paths:
  - "docs/**"
---
```

修正後:
```yaml
---
paths:
  - "docs/**"
  - "**/*.html"
  - "**/*.md"
---
```

- [ ] **Step 3: 各観点の見出しに重要度ラベルを追加する**

以下の対応で見出しを変更する:

| 変更前 | 変更後 |
|---|---|
| `**要件の完全性**` | `**【必須】要件の完全性**` |
| `**ルーティング・データ整合性**` | `**【必須】ルーティング・データ整合性**` |
| `**実行モデル・並列処理**` | `**【推奨】実行モデル・並列処理**` |
| `**外部I/F**` | `**【必須】外部I/F**` |
| `**運用ライフサイクル**` | `**【推奨】運用ライフサイクル**` |
| `**セキュリティ**` | `**【必須】セキュリティ**` |
| `**観測性**` | `**【推奨】観測性**` |
| `**テスト可能性**` | `**【推奨】テスト可能性**` |
| `**ドキュメント完全性**` | `**【推奨】ドキュメント完全性**` |

- [ ] **Step 4: 目視確認**

- frontmatter の paths に `"**/*.html"` と `"**/*.md"` が追加されていること
- 【必須】が4つ（要件の完全性・ルーティング・外部I/F・セキュリティ）、【推奨】が5つであること

- [ ] **Step 5: コミット**

```bash
git add rules/design-review.md
git commit -m "fix(rules): design-review.md の paths を修正し観点に重要度ラベルを追加"
```

---

## Task 3: code-review.md — N+1 項目に database.md への参照を追記

**Files:**
- Modify: `rules/code-review.md`

**修正理由:** `database.md` に N+1 の詳細（NG/OK コード例・selectin_load と joinedload の使い分け）が既にある。`code-review.md` の同じ趣旨の項目は重複であり、片方だけ更新されたときに乖離する。`code-review.md` はチェックポイント、詳細は `database.md` に集約する。

- [ ] **Step 1: `rules/code-review.md` を読み、「パフォーマンス」の行を確認する**

現在の行:
```
- **パフォーマンス**: N+1 クエリ・ループ内 DB アクセス・不必要な全件取得がないか
```

- [ ] **Step 2: 「パフォーマンス」行を以下に変更する**

```
- **パフォーマンス**: N+1 クエリ・ループ内 DB アクセス・不必要な全件取得がないか（詳細は `rules/database.md` 参照）
```

- [ ] **Step 3: 目視確認**

変更後の行に `（詳細は \`rules/database.md\` 参照）` が含まれていること。

- [ ] **Step 4: コミット**

```bash
git add rules/code-review.md
git commit -m "fix(rules): code-review.md のパフォーマンス項目に database.md への参照を追記"
```

---

## Task 4: container.md — シークレット節に security.md への参照を追記

**Files:**
- Modify: `rules/container.md`

**修正理由:** `container.md` の「ARG と ENV の使い分け」でシークレットの扱いに触れているが、本番環境での Secrets Manager 利用・ローテーション・ログマスクの詳細は `security.md` にある。`container.md` は「Dockerfile に書くな」に留め、全体ポリシーは `security.md` に委ねることで重複を排除する。

- [ ] **Step 1: `rules/container.md` を読み、「ARG と ENV の使い分け」セクションの末尾行を確認する**

セクション末尾は以下の行:
```
ENV DATABASE_URL=""
```
の後の ` ``` ` 閉じタグ行。

- [ ] **Step 2: 「ARG と ENV の使い分け」セクションのコードブロック終了後に1行追加する**

コードブロック（` ``` `）の直後の空行の後ろに以下を追加する:

```
シークレットの保管・ローテーション方針は `rules/security.md` のシークレット管理を参照する。
```

- [ ] **Step 3: 目視確認**

「ARG と ENV の使い分け」セクションの末尾（コードブロックの後）に参照行が存在すること。次のセクション（`## レイヤーキャッシュ最適化`）の前であること。

- [ ] **Step 4: コミット**

```bash
git add rules/container.md
git commit -m "fix(rules): container.md のシークレット節に security.md への参照を追記"
```

---

## Task 5: testing.md — テスト粒度・命名と CI 種別の定義を追加

**Files:**
- Modify: `rules/testing.md`

**修正理由:** 現状22行で TDD の方針のみ。Claude がテストを書く際の基準（命名規則・1テスト1アサーション・Arrange-Act-Assert）がなく、CI 種別（Unit/Integration/E2E/Smoke/Load）の定義・境界・実行タイミングも不明。他ファイルと比べて情報密度が低く、テストの品質が属人化する。

- [ ] **Step 1: `rules/testing.md` を読み、現在の末尾行を確認する**

現在の末尾:
```
- 自動化（CI）: Unit / Integration / E2E / Smoke / Load・Stress（例: Locust）
- 手動: Scenario（Acceptance）。手順書は `docs/testing/scenario/` に配置
```

- [ ] **Step 2: ファイル末尾に「テスト粒度と命名」セクションを追加する**

現在の末尾行の後に以下を追加する:

```markdown
## テスト粒度と命名

- テスト関数名は `test_<状況>_<期待結果>` 形式: `test_create_order_returns_201`
- 1テスト関数で1つのアサーション（複数を検証する場合は `pytest.approx` 等でまとめる）
- テストは Arrange（準備）→ Act（実行）→ Assert（検証）の3段階で書く
```

- [ ] **Step 3: 「テスト粒度と命名」セクションの後に「CI 種別と定義」セクションを追加する**

```markdown
## CI 種別と定義

| 種別 | 定義 | 実行タイミング |
|---|---|---|
| Unit | 外部依存を排除した単一関数・クラスのテスト | PR ごと |
| Integration | 実 DB・実キューを使った複数コンポーネントの結合テスト | PR ごと |
| E2E | 実際の HTTP クライアントからエンドポイントを叩く | PR ごと |
| Smoke | 本番/ステージングで最小限の疎通確認 | デプロイ後 |
| Load/Stress | Locust 等で同時接続・スループットを計測 | リリース前 |
```

- [ ] **Step 4: 目視確認**

- `## テスト粒度と命名` セクションに3項目（命名規則・1アサーション・AAA パターン）があること
- `## CI 種別と定義` テーブルに5行（Unit/Integration/E2E/Smoke/Load・Stress）と実行タイミング列があること
- 既存の「テスト方針」セクション（`## TDD`・`## テスト方針`）が変更されていないこと

- [ ] **Step 5: コミット**

```bash
git add rules/testing.md
git commit -m "docs(rules): testing.md にテスト粒度・命名規則と CI 種別定義を追加"
```

---

## セルフレビュー

### 1. 修正カバレッジ

| Fix | 問題 | 対応タスク |
|---|---|---|
| Fix 1 | `github.md` frontmatter なし | Task 1 ✓ |
| Fix 2 | `design-review.md` paths 欠落 | Task 2 ✓ |
| Fix 3 | N+1 説明の重複 | Task 3 ✓ |
| Fix 4 | シークレット管理の重複 | Task 4 ✓ |
| Fix 5 | `testing.md` 内容不足 | Task 5 ✓ |
| Fix 6 | 重要度ラベルなし | Task 2 ✓ |
| Fix 7 | 言語指定なし | Task 1 ✓ |

### 2. プレースホルダーチェック

プレースホルダーなし ✓

### 3. 一貫性チェック

- Task 2 の【必須】4件・【推奨】5件の合計9件が現在の観点見出し数（9件）と一致 ✓
- Task 1 の `paths: ["**"]` は `**/*.html` などより広く、全ファイル一致。github.md の意図（全体適用）と合致 ✓
- Task 5 で追加するセクションは既存の `## TDD`・`## テスト方針` の後に配置。既存セクションは変更しない ✓
