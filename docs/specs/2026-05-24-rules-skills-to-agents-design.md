# 設計仕様: Rules・Skills → Agents 完全移行

**日付**: 2026-05-24  
**目標**: rules/ と skills/ を全廃し、コンテキストをエージェント定義に閉じ込める。メインセッションのコンテキスト消費を最小化し、サブエージェント使用を Hook で自動強制する。

---

## 背景と動機

現状、`~/.claude/rules/` は11ファイル、`~/.claude/skills/` は9ディレクトリが存在し、一部はファイルパス一致で自動ロード（rules/python/*, rules/go/*）、残りは Skill ツールで都度ロードされる。いずれもメインセッションのコンテキストを消費する。

エージェントは独立したコンテキストウィンドウで動作するため、ドメイン知識をエージェント定義に移すことで、メインセッションは「どのエージェントを呼ぶか」だけを知ればよい状態にできる。

---

## 設計概要（変更前後）

| | 変更前 | 変更後 |
|-|-------|-------|
| agents/ | 7本 | **10本**（+3新規、3強化） |
| skills/ | 9ディレクトリ | **1本**（session-close-improve のみ） |
| rules/ | 11ファイル | **0ファイル**（全廃） |

---

## 新規エージェント（3本）

### 1. `python-dev`

**役割**: Python / FastAPI コードの実装担当  
**ツール**: Read, Write, Edit, Bash, Grep, Glob  
**モデル**: sonnet

**内容の吸収元（マージ順）**:
1. `skills/python-patterns/SKILL.md` — Python イディオム、型ヒント、dataclass、非同期
2. `skills/fastapi-patterns/SKILL.md` — FastAPI ルーター、Pydantic、DI、OpenAPI
3. `rules/python/coding-style.md` — PEP 8、型アノテーション必須
4. `rules/python/patterns.md` — Protocol ベースリポジトリパターン
5. `rules/python/fastapi.md` — create_app() 構造、薄いルーター、スキーマ分離

**エージェント定義の構造**:
```
---（frontmatter）---
## 呼び出しタイミング  ← 「Python/FastAPI コードを書くとき」
## Python コーディングスタイル  ← coding-style.md から
## Python パターン  ← patterns.md + skills/python-patterns から
## FastAPI パターン  ← fastapi.md + skills/fastapi-patterns から
```

---

### 2. `go-dev`

**役割**: Go / Gin コードの実装担当  
**ツール**: Read, Write, Edit, Bash, Grep, Glob  
**モデル**: sonnet

**内容の吸収元（マージ順）**:
1. `skills/go-patterns/SKILL.md` — Go イディオム、インターフェース、エラーハンドリング
2. `skills/gin-patterns/SKILL.md` — Gin ルーター、ミドルウェア、DI、バリデーション
3. `rules/go/coding-style.md` — Effective Go、gofmt/goimports
4. `rules/go/patterns.md` — 「インターフェースを受け取り、構造体を返す」
5. `rules/go/gin.md` — NewRouter() 関数、ミドルウェア構成

**エージェント定義の構造**:
```
---（frontmatter）---
## 呼び出しタイミング  ← 「Go/Gin コードを書くとき」
## Go コーディングスタイル  ← coding-style.md から
## Go パターン  ← patterns.md + skills/go-patterns から
## Gin パターン  ← gin.md + skills/gin-patterns から
```

---

### 3. `api-designer`

**役割**: REST API エンドポイント設計・レビュー  
**ツール**: Read, Grep, Glob  
**モデル**: sonnet

**内容の吸収元**:
1. `skills/api-design/SKILL.md` — リソース命名、ステータスコード、ページネーション、エラーレスポンス、バージョニング

---

## 既存エージェント強化（3本）

### `tdd-guide`（強化）

**追加内容**:
- `skills/python-testing/SKILL.md` — pytest フィクスチャ、モック、パラメトライズ、非同期テスト
- `skills/go-testing/SKILL.md` — testify、テーブル駆動テスト、t.Cleanup、カバレッジ
- `rules/python/testing.md` — pytest 必須、80% カバレッジ、ユニット/統合/E2E
- `rules/go/testing.md` — testify + TDD、テストカバレッジ 80%+

**変更点**: 前回「言語別詳細ルール」で参照先パスを追加したが、今回は内容をインライン統合に昇格。

---

### `code-reviewer`（強化）

**追加内容**:
- `rules/python/coding-style.md` — PEP 8 違反、型アノテーション欠如のフラグ
- `rules/go/coding-style.md` — gofmt 未適用、KISS/DRY 違反のフラグ

**変更点**: 既に Python/Go レビューセクションあり。coding-style ルールの内容で補完。

---

### `doc-updater`（強化）

**追加内容**:
- `skills/impl-doc-builder/SKILL.md` — 実装済みシステムのドキュメント整備 3フェーズワークフロー

---

## CLAUDE.md の更新

### エージェント表に3行追加

```diff
 | tdd-guide | テスト駆動開発 | **新機能・バグ修正時は必須** |
 | code-reviewer | 品質/セキュリティレビュー | コード作成・変更後に必ず使用 |
+| python-dev | Python/FastAPI実装 | Python/FastAPI コードを書くとき |
+| go-dev | Go/Gin実装 | Go/Gin コードを書くとき |
+| api-designer | REST API設計 | エンドポイント・スキーマ設計時 |
 | e2e-runner | Playwright E2E テスト | 重要ユーザーフローの動作確認時 |
```

### スキル欄を更新

```diff
-ローカル: `~/.claude/skills/`（session-close-improve / api-design / fastapi-patterns 等）。
+ローカル: `~/.claude/skills/session-close-improve`（セッション終了時の改善ワークフロー専用）。
```

---

## Hook 強化

### `tdd-guard.sh`（改修）

現状: Python 実装ファイル編集時に「tdd-guide を使ったか？」を促す。  
改修後: **「python-dev または tdd-guide を使ったか？」** に変更。

```diff
-echo "   tdd-guide エージェントを使って TDD（テストファースト）で開発しましたか？"
+echo "   python-dev エージェント（実装）または tdd-guide エージェント（TDD）を使いましたか？"
```

### `tdd-guard-go.sh`（改修）

同様に Go 実装ファイルで `go-dev` を促す：

```diff
-echo "   tdd-guide エージェントを使って TDD（テストファースト）で開発しましたか？"
+echo "   go-dev エージェント（実装）または tdd-guide エージェント（TDD）を使いましたか？"
```

---

## 廃止ファイル一覧

### skills/（8ディレクトリ削除）
- `skills/api-design/` → `api-designer` エージェントへ
- `skills/fastapi-patterns/` → `python-dev` エージェントへ
- `skills/python-patterns/` → `python-dev` エージェントへ
- `skills/python-testing/` → `tdd-guide` エージェントへ
- `skills/go-patterns/` → `go-dev` エージェントへ
- `skills/go-testing/` → `tdd-guide` エージェントへ
- `skills/gin-patterns/` → `go-dev` エージェントへ
- `skills/impl-doc-builder/` → `doc-updater` エージェントへ

### rules/（11ファイル削除）
- `rules/python/coding-style.md` → `python-dev`, `code-reviewer` へ
- `rules/python/patterns.md` → `python-dev` へ
- `rules/python/fastapi.md` → `python-dev` へ
- `rules/python/testing.md` → `tdd-guide` へ
- `rules/go/coding-style.md` → `go-dev`, `code-reviewer` へ
- `rules/go/patterns.md` → `go-dev` へ
- `rules/go/gin.md` → `go-dev` へ
- `rules/go/testing.md` → `tdd-guide` へ
- `rules/common/planning-checklist.md` → `planner` 参照済み（削除）
- `rules/common/code-review.md` → `code-reviewer` 参照済み（削除）
- `rules/common/agents.md` → CLAUDE.md に情報あり（削除）

---

## 実装順序

1. **tdd-guide 強化**（既存強化・リスク低）
2. **code-reviewer 強化**（既存強化・リスク低）
3. **doc-updater 強化**（既存強化・リスク低）
4. **python-dev 新規作成**（新規・コア変更）
5. **go-dev 新規作成**（新規・コア変更）
6. **api-designer 新規作成**（新規・小規模）
7. **CLAUDE.md 更新**
8. **Hook 改修**（tdd-guard.sh, tdd-guard-go.sh）
9. **旧ファイル削除**（skills/ 8本, rules/ 11ファイル）
10. **sync_file.sh で同期・commit**

---

## 検証方法

```bash
# エージェント数確認（10本）
ls ~/.claude/agents/ | wc -l

# スキル残存確認（session-close-improve のみ）
ls ~/.claude/skills/

# rules 全廃確認
ls ~/.claude/rules/

# CLAUDE.md にエージェント3本追加されているか
grep -E "python-dev|go-dev|api-designer" ~/.claude/CLAUDE.md

# フック改修確認
grep "python-dev\|go-dev" ~/.claude/hooks/tdd-guard.sh
grep "python-dev\|go-dev" ~/.claude/hooks/tdd-guard-go.sh
```
