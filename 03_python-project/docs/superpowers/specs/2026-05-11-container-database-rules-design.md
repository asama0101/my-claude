# container.md / database.md 新規追加 Design

## 背景・判断根拠

### 作成する理由

既存ルールファイルでの DB・コンテナ関連の coverage は最小限（security.md の SQLインジェクション対策3行・coding.md の非同期 I/O 言及1行・testing.md の docker run モック化1行）にとどまる。

Claude がフェーズ5（実装）で Dockerfile・Repository 層・Alembic マイグレーションを書く際、ルールがなければ品質基準が属人化する。DB/ストレージはプロジェクト固有だが、ORM/ドライバー非依存の原則（N+1回避・トランザクション管理・マイグレーションの破壊的変更対応）は全プロジェクトに共通して適用できる。

### 採用アプローチ: 2ファイル分離

`container.md` と `database.md` を独立ファイルとして作成する。

- **代替案A（infrastructure.md に統合）**: paths を広く設定せざるを得ず、無関係な場面でもロードされる
- **代替案B（既存ファイルへ吸収）**: coding.md が肥大化し責務が曖昧になる

分離することで paths を最小限に絞り、Claude が該当ファイルを編集する文脈でのみ参照できる。

---

## container.md 設計

### paths

```yaml
paths:
  - "Dockerfile"
  - "docker-compose*.yml"
  - ".dockerignore"
```

### 規定内容（7項目）

| 項目 | 規定内容 |
|---|---|
| ベースイメージ | `python:X.XX-slim` を標準。`latest` タグ禁止。digest ピン留め推奨 |
| multi-stage build | `builder`（依存インストール）→ `runtime`（実行）の2段構成を標準化 |
| non-root ユーザー | `RUN useradd` + `USER` で非特権ユーザー必須 |
| .dockerignore | `.git`, `__pycache__`, `tests/`, `.env` 等の除外ルール |
| ヘルスチェック | `HEALTHCHECK` 記述必須。間隔・タイムアウト・retries の既定値を規定 |
| ARG vs ENV | ビルド時変数は `ARG`、ランタイム変数は `ENV`。シークレットを `ENV` に書かない |
| レイヤー最適化 | `COPY pyproject.toml uv.lock .` → `RUN uv sync` → `COPY src/ .` のキャッシュ活用順序 |

docker-compose: `depends_on` + `condition: service_healthy` の使用とネットワーク明示を規定する。

### 除外項目と理由

| 除外項目 | 理由 |
|---|---|
| イメージスキャン（Trivy 等） | CI/CD 実行手順の担当。rules.md の責務外 |
| マルチプラットフォームビルド | 業務システムは x86_64 前提。必要なプロジェクトが個別対応 |
| レジストリ設定・タギング戦略 | ECR/GCR/DockerHub 等がプロジェクト固有 |
| コンテナのリソース制限 | CLAUDE.md「システムスケール要件」表が担う |
| ログドライバー設定 | structlog は coding.md 固定済み。ドライバー選択は ops 設計書の範疇 |
| Docker secrets 実装詳細 | シークレットを ENV に書かないルールは security.md が担う |
| tini / dumb-init | Python アプリで常に必須とは言えない。プロジェクト判断に委ねる |

---

## database.md 設計

### paths

```yaml
paths:
  - "src/**/repositories/**"
  - "src/**/models/**"
  - "**/alembic/**"
  - "*.toml"
```

### 規定内容（6項目）

| 項目 | 規定内容 |
|---|---|
| Repository パターン | `Protocol` で抽象インターフェースを定義し実装と分離。テスト時のモック差し替えを可能にする構造を必須とする |
| N+1問題の回避 | リレーション取得は `selectin_load` / `joinedload` を明示指定。デフォルトの lazy loading に依存しない |
| トランザクション管理 | Unit of Work パターン。複数リポジトリをまたぐ操作は1トランザクションにまとめる。ネストは `SAVEPOINT` を使う |
| マイグレーション | 破壊的変更（列削除・型変更）は3フェーズ対応（追加→移行→削除）。`downgrade` は必ず実装する |
| インデックス設計原則 | 外部キー・頻繁な絞り込み条件にはインデックスを付与。複合インデックスは選択性の高い列を先頭に置く |
| テスト時の DB 扱い | テストごとにトランザクションを開始して `rollback` でリセット（`pytest-asyncio` + `AsyncSession` のフィクスチャパターンを明示） |

### 除外項目と理由

| 除外項目 | 理由 |
|---|---|
| 接続プーリングの数値設定 | プロジェクトのスケール要件に依存。CLAUDE.md「システムスケール要件」表が担う |
| DB 固有の SQL 方言 | PostgreSQL / MySQL 等は「要選択」のため汎用ルールにできない |
| シャーディング・レプリカ設定 | 業務システムテンプレートのスコープを超える |

---

## CLAUDE.md 参照ドキュメント索引への追記

「参照ドキュメント索引」テーブルに2行追加する:

| ファイル | 適用パス | 内容 |
|---|---|---|
| `.claude/rules/container.md` | `Dockerfile`, `docker-compose*.yml`, `.dockerignore` | コンテナ構成規約（multi-stage・non-root・ヘルスチェック等） |
| `.claude/rules/database.md` | `src/**/repositories/**`, `src/**/models/**`, `**/alembic/**`, `*.toml` | DB アクセス規約（N+1回避・トランザクション・マイグレーション） |

---

## 成果物

| ファイル | 操作 |
|---|---|
| `rules/container.md` | 新規作成 |
| `rules/database.md` | 新規作成 |
| `CLAUDE.md` | 参照ドキュメント索引に2行追加 |
