---
paths:
  - "src/**"
  - "tests/**"
  - "pyproject.toml"
  - "*.toml"
---
# 開発・Git運用

開発ガイドライン、テスト方針、GitHub運用をまとめる。
コーディング・コミット・PR作成時に参照する。

## 開発ガイドライン

- 型ヒント必須、`mypy --strict` を通すこと
- 設定ファイルのスキーマはバリデーションライブラリで定義（技術スタックに従う）
- TDD: 新規機能は失敗するテストを先に書く
- Linter/Formatter: ruff
- 依存管理: uv（requirements.txt の直接編集禁止）
- ディレクトリ: src/ レイアウト
- ログ: structlog（print 禁止）
- 例外を握り潰さない（ログ出力 or 再 raise）

## テスト方針

- pytest 使用
- 外部サービス・HTTP 通信は HTTP クライアント層でモック化
- サブプロセス呼び出し（`subprocess`, `docker run` 等）はサブプロセス層でモック化
- 外部応答サンプルは tests/fixtures/ 配下に保存
- 自動化（CI）: Unit / Integration / E2E / Smoke / Load・Stress（例: Locust）
- 手動: Scenario（Acceptance）。手順書は docs/scenario/ に配置

## GitHub運用

### ブランチ戦略

| ブランチ | 用途 | 派生元 → マージ先 |
|---|---|---|
| `main` | リリース版（常にデプロイ可能な状態を維持） | - |
| `develop` | 開発統合 | - |
| `feature/*` | 機能追加・修正 | develop → develop |

命名: `feature/[issue番号]-[簡潔な説明]`（例: `feature/42-add-maintenance-mode`）

リリース時は `develop` → `main` にマージする。

### コミット規約

Conventional Commits を採用。形式: `<type>(<scope>): <subject>`

type: `feat` / `fix` / `docs` / `style` / `refactor` / `test` / `chore` / `perf`

例: `feat(auth): JWTトークン検証を追加`

### PR運用

- `feature/*` → `develop` で統合
- PR本文に変更概要・関連Issue（`Closes #N`）・テスト結果を記載
- ローカルで lint/型チェック/テストがパスしていること
- マージ方式: **Squash and merge**（履歴を1コミットにまとめる）
- セルフレビュー後にマージ可（PR作成→一晩寝かせる→翌日読み返してからマージ を推奨）

### Issue管理

- 必須項目: 概要・受け入れ基準
- ラベル分類: 種別（`type:*`）/ 優先度（`priority:*`）
- ブランチ名・コミット・PR本文で Issue 番号を参照する

### セキュリティ

#### コミット禁止

ファイル単位での除外は `.gitignore` で行う。

`.gitignore` 必須エントリ:

```
config/credentials.yaml
.env
.env.*
*.pem
*.key
__pycache__/
*.pyc
*.egg-info/
dist/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.vscode/
.idea/
```

#### 機密情報を誤コミットした場合

該当認証情報を **ローテーション（変更）する**。履歴削除では不十分。

#### リポジトリ保護

- 本番影響のあるリポジトリは Public にしない
- `main` `develop` に Branch Protection Rule を設定（force push 禁止、ブランチ削除禁止）
