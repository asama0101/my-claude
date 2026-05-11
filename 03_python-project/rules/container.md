---
paths:
  - "Dockerfile"
  - "docker-compose*.yml"
  - ".dockerignore"
---
# コンテナ構成規約

Dockerfile・docker-compose・.dockerignore 作成・編集時に参照する。

## ベースイメージ

- `python:X.XX-slim` を標準とする（`latest` タグ禁止）
- 可能であれば digest でピン留めする: `python:3.12-slim@sha256:...`
- `alpine` はバイナリ互換性の問題が起きやすいため避ける

## multi-stage build

builder と runtime の2段構成を標準とする:

```dockerfile
# builder: 依存インストール
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# runtime: 実行環境
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY src/ ./src/
```

## non-root ユーザー

root で実行しない:

```dockerfile
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser
```

## .dockerignore

最低限以下を除外する:

```
.git
__pycache__
*.pyc
*.pyo
.env
.env.*
tests/
docs/
*.md
.mypy_cache
.ruff_cache
```

## ヘルスチェック

すべての本番用コンテナに `HEALTHCHECK` を記述する:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

既定値: `interval=30s` / `timeout=10s` / `start-period=10s` / `retries=3`

## ARG と ENV の使い分け

- ビルド時のみ使う値は `ARG`
- コンテナ実行時に必要な値は `ENV`
- シークレット（パスワード・API キー）を `ARG` / `ENV` に直書きしない（`--secret` を使う）

```dockerfile
# NG: docker history にシークレットが残る
ARG DATABASE_PASSWORD

# OK: ランタイムで環境変数として注入する
ENV DATABASE_URL=""
```

## レイヤーキャッシュ最適化

変更頻度の低いものを先にコピーする:

```dockerfile
# 依存ファイルを先にコピー（ここまでキャッシュが効く）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ソースコードを後でコピー（コード変更時のみ再実行）
COPY src/ ./src/
```

## docker-compose

`depends_on` にはヘルスチェック条件を必ず付ける:

```yaml
depends_on:
  db:
    condition: service_healthy
```

ネットワークは明示的に定義する（`default` ネットワークに暗黙依存しない）:

```yaml
networks:
  backend:
    driver: bridge
```
