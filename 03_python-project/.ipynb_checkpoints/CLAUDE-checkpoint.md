# CLAUDE.md — Python バックエンド（業務システム）用テンプレート

## コマンド一覧

> コピー後に実際のコマンドへ置き換える。存在しないコマンドは削除する。

```bash
# セットアップ
uv sync                    # 依存関係インストール

# 開発
uv run pytest tests/       # テスト実行
uv run pytest tests/ -x    # 最初の失敗で停止
uv run ruff check src/     # Lint
uv run ruff format src/    # フォーマット
uv run mypy src/           # 型チェック

# まとめて実行
uv run ruff check src/ && uv run mypy src/ && uv run pytest tests/
```

## プロジェクト概要

> 2〜3 行でシステムの目的を記載。略語は初出時に定義する。
> NG例: 「受発注を管理するシステム」（何と何の間か不明）
> OK例: 「社内WMS（倉庫管理システム）から受注データを受け取り、ERP（基幹システム）へ連携する中継API」

（ここに記入）

## ローカルセットアップ

> 初めてこのリポジトリに触るClaude・開発者が迷わず動かせるよう、手順を順番に記述する。
> NG例: 「適宜設定する」
> OK例: 「3. .env.sample をコピーして .env を作成し、DATABASE_URL を設定する」

1. （依存インストール: 例 `uv sync`）
2. （環境変数設定: 例 `.env.sample` を `.env` にコピーして各変数を設定）
3. （DB初期化・マイグレーション: 例 `uv run alembic upgrade head`）
4. （開発サーバー起動: 例 `uv run uvicorn src.main:app --reload`）

## 環境変数

> `.env` に必要な全変数を列挙する。「どこで使われるか」も書くとClaude が文脈を把握しやすい。
> NG例: 「各自設定すること」
> OK例: 下表の形式で必須・任意を明記する

| 変数名 | 用途 | 必須 | 例 |
|--------|------|------|-----|
| DATABASE_URL | DBへの接続文字列 | ○ | `postgresql://user:pass@localhost/dbname` |
| （変数名） | （用途） | ○/△ | （例） |

## 機能一覧

> 動詞始まりの箇条書き。機能 ID は要件定義書（docs/requirements/）の FR-xxx と揃える。
> NG例: 「ユーザー管理」
> OK例: 「ユーザーを登録・更新・削除する（FR-001）」

- （機能1: FR-001）
- （機能2: FR-002）

## アーキテクチャ

> Mermaid flowchart で主要コンポーネントとデータの流れを示す。15 要素以内に収める。
> 15 要素を超える場合は「全体像」と「サブシステム詳細」に分割する。

```mermaid
flowchart TD
    Client[クライアント] -->|HTTP| API[APIサーバ]
    API --> SVC[サービス層]
    SVC --> DB[(DB)]
    SVC --> EXT[外部システム]
```

## 技術スタック

> 「要選択」の行をプロジェクト開始時に埋める。「固定」はこのテンプレートの標準として変更しない。

| 区分 | 採用技術 | 種別 |
|---|---|---|
| 言語 | Python X.XX | 要選択 |
| Web フレームワーク | （例: FastAPI） | 要選択 |
| バリデーション | （例: Pydantic） | 要選択 |
| 非同期 HTTP | （例: aiohttp） | 要選択 |
| DB / ストレージ | （例: PostgreSQL + SQLAlchemy） | 要選択 |
| ログ | structlog | 固定 |
| テスト | pytest / pytest-asyncio | 固定 |
| Lint / 型検査 | ruff / mypy --strict | 固定 |
| 依存管理 | uv | 固定 |
| コンテナ | Docker | 固定 |

## 外部 I/F 仕様

> 詳細は docs/spec.md に分離し、ここではポインタと主要エンドポイントのみ記載する。
> NG例: 「APIあり」
> OK例: 主要エンドポイントを下表に列挙し、詳細は docs/spec.md へリンクする

| メソッド | パス | 概要 |
|---|---|---|
| POST | `/api/v1/resources` | リソース登録 |
| GET  | `/api/v1/resources/{id}` | リソース取得 |

## システムスケール要件

> 数値で定量的に記載。「高速」「多い」などの曖昧な表現は禁止。不要な行は削除する。

| 指標 | 目標値 |
|---|---|
| レスポンスタイム | p95 ≤ X 秒 |
| 同時接続数 | ≤ X セッション |
| 可用性 | X % 以上 |
| データ量（DB） | X GB 以下 |
| バッチ処理時間 | X 分以内 |

## Claudeの振る舞い

### 判断の方針

- **曖昧さ**: 設計判断に関わる曖昧さは確認質問を返す。命名・文言の曖昧さは妥当な選択肢を1つ採用しPR本文に明記。前例があれば前例に倣う
- **不確実性**: バージョン依存・ベンダー仕様は「未確認」「要検証」と明示し一次情報源リンクを添える。憶測で断言しない
- **不整合の発見**: ドキュメントとコード、またはADRと提案が食い違う場合は修正前にどちらが正かの判断を求める

### ドキュメント管理

- 仕様の検討・変更は `docs/` で合意してからコードへ反映する。コードを先行させない
- 重要な設計判断は ADR（`docs/design/decisions/`）に記録する
- 機能追加・変更 PR には対応するドキュメント更新を同梱する

### プロジェクト固有の禁止事項

> このプロジェクト特有の「やってはいけないこと」を記載する。ない場合はこのセクションごと削除する。
> OK例: 「装置への直接SSH接続は禁止（REST API 経由のみ許可）」
> OK例: 「config/credentials.yaml を平文でログ出力しない」

- （禁止事項1）
- （禁止事項2）

### 変更の規模制御

- **大規模変更の計画提示**: 5 ファイル超 or 200 行超の新規実装は、実装前に計画を提示し承認を得る
- **既存ファイルのリファクタ**: 依頼されない限り行わない。改善余地は PR本文への記載 or 別Issueとして提案する

### 出力言語

- コード内コメント・docstring: 日本語
- コミットメッセージ: type/scope は英小文字、subject は日本語（例: `feat(auth): JWTトークン検証を追加`）
- Issue・PR・ドキュメント: 日本語
- 例外メッセージ・ログメッセージ: 日本語（structlogのキー名は英語）

## 開発フェーズ

作業開始時、Claudeは必ず `.claude/task.md` を読み現在のフェーズを確認する。フェーズ移行はユーザーの明示的な承認後に行う。当フェーズの成果物を作成・更新し、前フェーズの成果物は参照・補足更新のみとする。

| フェーズ | 作成・更新する成果物 |
|---|---|
| 1. 要求整理 | docs/requirements/01_overview.html |
| 2. 要件定義 | docs/requirements/02_functional.html, 03_non_functional.html |
| 3. 基本設計 | docs/design/architecture.html, data_model.html, interfaces.html, security.html, infrastructure.html, monitoring.html, spec.md, performance_thresholds.html, test_plan.html |
| 4. 詳細設計 | docs/design/api.html, error_codes.html, flows/[機能名].html（処理フロー図）, 各モジュールの docstring |
| 5. 実装 | src/ 配下のコード, tests/ 配下のテスト（TDD） |

### docs/PHASE.html の記載フォーマット

```html
<p>現在のフェーズ: X. フェーズ名</p>
<p>移行日: YYYY-MM-DD</p>
<p>完了基準: （このフェーズを終えるための条件）</p>
```

## 参照ドキュメント索引

以下の rules ファイルは paths 指定により該当ファイル編集時に自動ロードされる。

| ファイル | 適用パス | 内容 |
|---|---|---|
| `.claude/rules/dev.md` | `src/**`, `tests/**`, `*.toml` | 開発ガイドライン、テスト方針、GitHub運用 |
| `.claude/rules/docs.md` | `docs/**`, `**/*.html` | ドキュメント配置・記法、図示ガイドライン |
| `.claude/rules/design-review.md` | `docs/**`, `**/*.html`, `**/*.md` | 仕様レビュー観点 |
