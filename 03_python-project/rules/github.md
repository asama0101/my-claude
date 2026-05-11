# GitHub運用

ブランチ操作・コミット・PR・Issue作成時に参照する。

## ブランチ戦略

| ブランチ | 用途 | 派生元 → マージ先 |
|---|---|---|
| `main` | リリース版（常にデプロイ可能な状態を維持） | - |
| `develop` | 開発統合 | - |
| `feature/*` | 機能追加・修正 | develop → develop |

命名: `feature/[issue番号]-[簡潔な説明]`（例: `feature/42-add-maintenance-mode`）

リリース時は `develop` → `main` にマージする。

## コミット規約

Conventional Commits を採用。形式: `<type>(<scope>): <subject>`

type: `feat` / `fix` / `docs` / `style` / `refactor` / `test` / `chore` / `perf`

例: `feat(auth): JWTトークン検証を追加`

## PR運用

- `feature/*` → `develop` で統合
- PR本文に変更概要・関連Issue（`Closes #N`）・テスト結果を記載
- ローカルで lint/型チェック/テストがパスしていること
- マージ方式: **Squash and merge**（履歴を1コミットにまとめる）
- セルフレビュー後にマージ可（PR作成→一晩寝かせる→翌日読み返してからマージ を推奨）

## Issue管理

- 必須項目: 概要・受け入れ基準
- ラベル分類: 種別（`type:*`）/ 優先度（`priority:*`）
- ブランチ名・コミット・PR本文で Issue 番号を参照する

## セキュリティ

### コミット禁止

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

### 機密情報を誤コミットした場合

該当認証情報を **ローテーション（変更）する**。履歴削除では不十分。

### リポジトリ保護

- 本番影響のあるリポジトリは Public にしない
- `main` `develop` に Branch Protection Rule を設定（force push 禁止、ブランチ削除禁止）
