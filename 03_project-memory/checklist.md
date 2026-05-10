# 開発チェックリスト

Claude とのセッション開始時・フェーズ移行時・PR 提出前に確認する。
完了した項目は `[x]` に変えて記録する（コミットしてもよい）。

---

## プロジェクト開始時

`.claude/setup.md` の手順を完了させてから、以下を確認する。

- [ ] `.claude/プロジェクトCLAUDE.md` のプレースホルダー 5 箇所をすべて埋めた
- [ ] `docs/PHASE.html` を作成し、現在のフェーズを記載した
- [ ] ディレクトリ構造（`src/`, `tests/`, `docs/`）が作成済み
- [ ] `uv` で仮想環境・依存関係を初期化した（`uv.lock` が存在する）
- [ ] `pyproject.toml` に ruff / mypy / pytest の設定を記載した
- [ ] `ruff check .` がエラーなしで通る
- [ ] `mypy --strict src/` がエラーなしで通る
- [ ] `pytest` がエラーなしで通る（テストがなければスキップ可）
- [ ] GitHub リポジトリを Private で作成した
- [ ] `main` と `develop` に Branch Protection Rule を設定した
- [ ] `.gitignore` に機密ファイル（`config/credentials.yaml`, `.env` 等）を追加した

---

## 各フェーズ移行前

フェーズを進める前に前フェーズの成果物が揃っているか確認する。

| 移行 | 必須成果物 |
|---|---|
| 要求整理 → 要件定義 | `docs/requirements/01_overview.html` |
| 要件定義 → 基本設計 | `docs/requirements/02_functional.html`, `03_non_functional.html` |
| 基本設計 → 詳細設計 | `docs/design/architecture.html`, `data_model.html`, `interfaces.html` |
| 詳細設計 → 実装 | 各機能の処理フロー図（`docs/design/flows/*.html`） |

- [ ] 前フェーズの成果物が `docs/` に存在する
- [ ] Claude が `docs/PHASE.html` を読み、現在のフェーズを把握している
- [ ] 今フェーズで作成する成果物の一覧を Issue に記録した

---

## コーディング中（セッション開始時）

各コーディングセッションの開始時に確認する。

- [ ] 今日のタスクが明確か（対応する Issue 番号がある）
- [ ] `develop` ブランチから `feature/[issue番号]-[説明]` ブランチを切った
- [ ] 実装前に失敗するテストを書いた（TDD）
- [ ] 型ヒントを漏れなく付けている（`mypy --strict` を意識）
- [ ] ログは `structlog` を使い、`print` を使っていない
- [ ] 例外を握りつぶしていない（ログ出力 or 再 raise）

---

## PR 提出前

`feature/*` → `develop` の PR を出す前に確認する。

- [ ] `ruff check .` がエラーなし
- [ ] `mypy --strict src/` がエラーなし
- [ ] `pytest tests/unit/ tests/integration/` がすべてパス
- [ ] 変更した機能に対応するドキュメントの更新を同じ PR に含めた
  - 処理フロー図（`docs/design/flows/`）
  - 要件・設計書（変更がある場合）
- [ ] コミットが Conventional Commits 形式か（例: `feat(subport): subport 登録 API を追加`）
- [ ] PR 本文に「変更概要・関連 Issue（`Closes #N`）・テスト結果」を記載した
- [ ] セルフレビューを実施した（一晩寝かせて翌日読み返すことを推奨）

---

## リリース前（develop → main）

`develop` → `main` のマージ前に確認する。

- [ ] E2E テストがすべてパス（`pytest tests/e2e/`）
- [ ] Smoke テストを本番同等環境で実施した（`docs/operations/setup.html` 参照）
- [ ] 運用手順書（`docs/operations/`）が最新の実装に合っている
  - `setup.html`（構築・デプロイ手順）
  - `daily.html`（日常運用）
  - `incident.html`（障害対応）
- [ ] `CHANGELOG` または リリースノートを更新した
- [ ] `develop` → `main` の PR を作成し、セルフレビューを実施した
