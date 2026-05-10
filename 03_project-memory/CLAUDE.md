# CLAUDE.md  - Project Memory

## プロジェクト概要

<!-- 例: 以下を参考に 2〜3 行で記載。略語は初出時に定義する -->
帯域制御装置（QoS 装置）を REST API 経由で一元管理するバックエンドサービス。
subport（サブポート: 帯域制御の最小単位）の CRUD・ステータス取得・設定一括適用を提供し、
複数拠点の装置を asyncio で並列制御する。

## 機能一覧

<!-- 例: 動詞始まりの箇条書き。機能 ID は要件定義書（docs/requirements/）の FR-xxx と揃える -->
- subport の登録・更新・削除・一覧取得（FR-001〜004）
- 装置ステータスのポーリング取得（FR-005）
- 複数装置への設定一括適用（FR-006）
- 設定失敗時の Syslog 通知（FR-007）
- メンテナンスモードの切替（FR-008）
- 装置追加・撤去（FR-009）

## アーキテクチャ

<!-- 例: Mermaid flowchart で主要コンポーネントとデータの流れを示す。15 要素以内に収める -->
```mermaid
flowchart TD
    Client[クライアント] -->|HTTP| API[FastAPI\nAPIサーバ]
    API --> SVC[サービス層\nビジネスロジック]
    SVC --> HTTP[HTTPクライアント層\naiohttp]
    HTTP -->|HTTPS| DEV[帯域制御装置群\n複数拠点]
    SVC --> LOG[structlog\nログ出力]
```

## 装置仕様

<!-- 例: 詳細は docs/spec.md に分離し、ここではポインタと主要エンドポイントのみ記載 -->
詳細は `docs/spec.md` を参照。主なエンドポイント:

| メソッド | パス | 概要 |
|---|---|---|
| POST | `/api/v1/subports` | subport 登録 |
| GET | `/api/v1/devices/{id}/status` | ステータス取得 |
| POST | `/api/v1/devices/bulk-apply` | 設定一括適用 |

## システムスケール要件

<!-- 例: 数値で定量的に記載。「高速」「多い」などの曖昧な表現は禁止 -->
| 指標 | 目標値 |
|---|---|
| レスポンスタイム | p95 ≤ 2 秒（装置 1 台への操作） |
| 同時接続数 | ≤ 50 セッション |
| 管理装置数 | ≤ 200 台 |
| subport 数 | 装置あたり ≤ 1,000 |
| 設定一括適用 | 200 台同時送信で ≤ 30 秒 |

## Claudeの振る舞い

### 判断の方針

- **曖昧さの扱い**: 仕様が曖昧な場合、以下で判断する
  - 設計判断に影響する曖昧さ(I/F・データ構造・エラーハンドリング・ルーティング・冪等性): 必ず確認質問を返す
  - 命名・ログ文言・コメント表現の曖昧さ: 妥当な選択肢を1つ採用し、PR本文に「想定」として明記
  - 既存コードに前例がある曖昧さ: 前例に倣い、その旨を明記
- **不確実性の表明**: バージョン依存の挙動・ベンダー仕様の解釈・未確認のライブラリ仕様などは「未確認」「要検証」と明示し、可能な限り一次情報源(公式ドキュメント・装置のAPI仕様書)へのリンクを添える。憶測で断言しない
- **テストと実装の整合**: テストと実装が食い違う場合、docs/ の仕様に照らしてどちらが正かを判断する。仕様が不明確ならまず仕様を確定させる。テストを通すために実装を歪めない、実装を通すためにテストを甘くしない
- **ドキュメントとコードの不整合**: 発見したら修正前にどちらが正かの判断を求める。判断後、必要なら同じPRで両方を整合させる
- **過去の判断の尊重**: 既存のADR(`docs/design/decisions/`)に反する提案をする場合、先に該当ADRを更新するPRを出すか、本文でADRへの異議を明記する

### 変更の規模制御

- **大規模変更の計画提示**: 10ファイル超 or 100行超の新規実装は、実装前に計画を提示し承認を得る。
- **既存ファイルのリファクタ**: 依頼されない限り行わない。改善余地を発見した場合は PR本文への記載 or 別Issueとして提案する(自走で実施はしない)

### 不可逆操作の統制

副作用のある操作は実行前に確認を取る。対象例:

- **Git**: push、force push、merge、rebase、ブランチ削除、tag操作
- **GitHub**: Issue/PR作成、コメント投稿、ラベル変更
- **ファイルシステム**: ファイル/ディレクトリ削除、設定ファイル上書き

### 出力言語

- コード内コメント・docstring: 日本語
- コミットメッセージ: type/scope は英小文字、subject は日本語(例: `feat(launcher): ワーカー同時起動数の上限制御を追加`)
- Issue・PR・ドキュメント: 日本語
- 例外メッセージ・ログメッセージ: 日本語(structlogのキー名は英語)

## 開発フェーズ

作業開始時、Claudeは必ず docs/PHASE.html を読み、現在のフェーズに対応する成果物のみを扱う。

| フェーズ | 成果物 |
|---|---|
| 1. 要求整理 | docs/requirements/01_overview.html |
| 2. 要件定義 | docs/requirements/02_functional.html, 03_non_functional.html |
| 3. 基本設計 | docs/design/architecture.html, data_model.html, interfaces.html |
| 4. 詳細設計 | docs/design/配下 + 各モジュールのdocstring(*.html) + **処理フロー図** |
| 5. 実装 | TDD(処理フロー図に沿って実装) |

## 参照ドキュメント索引

タスクに応じて以下を参照する。Claudeは作業開始時に該当ファイルを読むこと。

| ファイル | 内容 | 読むタイミング |
|---|---|---|
| `.claude/dev.md` | 開発ガイドライン、テスト方針、GitHub運用 | コーディング・コミット・PR作成時 |
| `.claude/docs.md` | 仕様検討ルール、ドキュメント配置・記法、処理フロー設計、図示ガイドライン、仕様レビュー観点 | ドキュメント作成・設計レビュー時 |

## 新プロジェクトへの適用手順

新規プロジェクト開始時に一度だけ実施する。

### 前提条件

| ツール | バージョン |
|---|---|
| Python | 3.11+ |
| uv | 最新 |
| Docker | 20.10+ |
| GitHub CLI (`gh`) | 最新 |

### 手順

1. **テンプレートをコピー**
   ```bash
   mkdir -p .claude
   cp -r /path/to/03_project-memory/* .claude/
   ```

2. **このファイル（CLAUDE.md）のプレースホルダーを埋める** — 上記の各セクションにある `<!-- 例: -->` コメントを参照して記入し、コメント行は削除する

3. **ディレクトリ構造を作成**
   ```bash
   mkdir -p src/{pkg} tests/{unit,integration,e2e} tests/fixtures \
     docs/{design/decisions,design/flows,operations,requirements,scenario} config
   ```
   `docs/PHASE.html` を作成して現在のフェーズを記載する

4. **仮想環境・依存関係を初期化**
   ```bash
   uv init
   uv add fastapi uvicorn pydantic structlog
   uv add --dev pytest pytest-asyncio mypy ruff httpx
   ```

5. **pyproject.toml を設定**（ruff / mypy / pytest の設定を追加）

6. **GitHub リポジトリを作成・Branch Protection を設定**
   ```bash
   gh repo create {プロジェクト名} --private --source . --push
   ```
   `main` と `develop` に force push 禁止・ブランチ削除禁止を設定する

7. **ruff / mypy / pytest が通ることを確認して開発開始**
