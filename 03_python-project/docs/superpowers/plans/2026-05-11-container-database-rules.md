# container.md / database.md 新規追加 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `rules/container.md` と `rules/database.md` を新規作成し、`CLAUDE.md` の参照ドキュメント索引に登録する

**Architecture:** ドキュメントのみの変更（コードなし）。各 rules ファイルは frontmatter の paths で適用対象を限定し、Claude が該当ファイルを編集する文脈でのみ自動ロードされる。`container.md` はコンテナ構成ファイル限定、`database.md` は Repository 層・モデル・マイグレーション限定。

**Tech Stack:** Markdown のみ

---

## ファイル構成

```
rules/
  container.md    ← Task 1 で新規作成
  database.md     ← Task 2 で新規作成
CLAUDE.md         ← Task 3 で参照ドキュメント索引に2行追加
```

---

## Task 1: container.md 作成

**Files:**
- Create: `rules/container.md`

- [ ] **Step 1: 以下の内容で `rules/container.md` を作成する**

````markdown
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
````

- [ ] **Step 2: ファイルを読み直して以下を確認する**

  - frontmatter の paths に `"Dockerfile"` / `"docker-compose*.yml"` / `"".dockerignore"` の3つがあること
  - 7セクション（ベースイメージ・multi-stage・non-root・.dockerignore・ヘルスチェック・ARG vs ENV・レイヤー最適化）が存在すること
  - docker-compose セクションが末尾にあること

- [ ] **Step 3: コミット**

```bash
git add rules/container.md
git commit -m "docs(rules): container.md を新規作成（Dockerfile/docker-compose規約）"
```

---

## Task 2: database.md 作成

**Files:**
- Create: `rules/database.md`

- [ ] **Step 1: 以下の内容で `rules/database.md` を作成する**

````markdown
---
paths:
  - "src/**/repositories/**"
  - "src/**/models/**"
  - "**/alembic/**"
  - "*.toml"
---
# DB アクセス規約

Repository 層・ORM モデル・Alembic マイグレーション作成・編集時に参照する。

## Repository パターン

`Protocol` でインターフェースを定義し、実装と分離する:

```python
from typing import Protocol
from uuid import UUID
from myapp.models.order import Order

class OrderRepositoryProtocol(Protocol):
    async def get_by_id(self, order_id: UUID) -> Order | None: ...
    async def save(self, order: Order) -> Order: ...
    async def delete(self, order_id: UUID) -> None: ...
```

実装クラスは `Protocol` を継承せず、構造的部分型（structural subtyping）で適合させる。
テスト時は `Protocol` に適合するモックを注入する。

## N+1 問題の回避

リレーション取得時は lazy loading に依存せず、ロード戦略を明示する:

```python
# NG: N+1が起きる
orders = await session.execute(select(Order))
for order in orders.scalars():
    print(order.items)  # 都度クエリが発行される

# OK: selectin_load で一括取得
from sqlalchemy.orm import selectin_load

stmt = select(Order).options(selectin_load(Order.items))
orders = await session.execute(stmt)
```

- 1対多: `selectin_load`（個別 IN クエリ、デフォルト推奨）
- 多対1: `joinedload`（JOIN クエリ、単一行の取得に向く）

## トランザクション管理

Unit of Work パターン: 複数リポジトリをまたぐ操作は1つのトランザクションにまとめる。

```python
async def transfer(
    from_id: UUID,
    to_id: UUID,
    amount: Decimal,
    session: AsyncSession,
) -> None:
    async with session.begin():
        from_account = await account_repo.get_by_id(from_id, session)
        to_account = await account_repo.get_by_id(to_id, session)
        from_account.withdraw(amount)
        to_account.deposit(amount)
        # begin() を抜けると自動コミット、例外で自動ロールバック
```

ネストが必要な場合は `SAVEPOINT` を使う:

```python
async with session.begin_nested():  # SAVEPOINT
    ...  # 失敗しても外側のトランザクションは継続
```

## マイグレーション（Alembic）

### 破壊的変更の3フェーズ対応

列削除・型変更は一度に行わず、3段階に分ける:

| フェーズ | PR | 内容 |
|---|---|---|
| 1. 追加 | PR-A | 新しい列/型を追加。旧列も残す |
| 2. 移行 | PR-B | アプリコードを新列/型に切り替える |
| 3. 削除 | PR-C | 旧列/型を削除するマイグレーションをリリース |

### downgrade は必ず実装する

```python
def upgrade() -> None:
    op.add_column("orders", sa.Column("status_v2", sa.String(20)))

def downgrade() -> None:
    op.drop_column("orders", "status_v2")  # 省略禁止
```

### メッセージ命名規則

動詞始まりのスネークケースで記述する:

```bash
# OK
alembic revision --autogenerate -m "add_status_v2_to_orders"
alembic revision --autogenerate -m "drop_legacy_user_token_column"

# NG（何をしたか不明）
alembic revision --autogenerate -m "orders_table"
```

## インデックス設計原則

- 外部キー列には必ずインデックスを付ける
- 頻繁に `WHERE` 句で使われる列にはインデックスを付ける
- 複合インデックスは選択性の高い列（値の種類が多い列）を先頭に置く

```python
class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_id_created_at", "user_id", "created_at"),
        # user_id の選択性が created_at より高いため先頭に置く
    )
```

## テスト時の DB 扱い

テストごとにトランザクションを開始して `rollback` でリセットする（DB の状態が次のテストに漏れない）:

```python
# tests/fixtures/db.py
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from myapp.core.database import Base

@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/testdb")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as db:
        async with db.begin():
            yield db
            await db.rollback()  # テスト終了後にロールバック
```

`pyproject.toml` の `[tool.pytest.ini_options]` に `asyncio_mode = "auto"` を設定する:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```
````

- [ ] **Step 2: ファイルを読み直して以下を確認する**

  - frontmatter の paths に `"src/**/repositories/**"` / `"src/**/models/**"` / `"**/alembic/**"` / `"*.toml"` の4つがあること
  - 6セクション（Repository パターン・N+1回避・トランザクション・マイグレーション・インデックス・テスト時 DB）が存在すること
  - マイグレーションセクションに「3フェーズ対応」「downgrade 必須」「命名規則」の3サブセクションがあること

- [ ] **Step 3: コミット**

```bash
git add rules/database.md
git commit -m "docs(rules): database.md を新規作成（Repository/N+1/トランザクション/マイグレーション規約）"
```

---

## Task 3: CLAUDE.md 参照ドキュメント索引の更新

**Files:**
- Modify: `CLAUDE.md`（「参照ドキュメント索引」テーブル）

- [ ] **Step 1: `CLAUDE.md` の参照ドキュメント索引テーブルを確認する**

現在のテーブル末尾は以下になっているはず:

```markdown
| `.claude/rules/design-review.md` | `docs/**`, `**/*.html`, `**/*.md` | 仕様レビュー観点 |
```

- [ ] **Step 2: テーブル末尾に2行追加する**

```markdown
| `.claude/rules/container.md` | `Dockerfile`, `docker-compose*.yml`, `.dockerignore` | コンテナ構成規約（multi-stage・non-root・ヘルスチェック等） |
| `.claude/rules/database.md` | `src/**/repositories/**`, `src/**/models/**`, `**/alembic/**`, `*.toml` | DB アクセス規約（N+1回避・トランザクション・マイグレーション） |
```

- [ ] **Step 3: 目視確認**

  - テーブルに8行（既存6行 + 新規2行）あること
  - `container.md` の paths と `rules/container.md` の frontmatter が一致すること
  - `database.md` の paths と `rules/database.md` の frontmatter が一致すること

- [ ] **Step 4: コミット**

```bash
git add CLAUDE.md
git commit -m "docs(CLAUDE.md): container.md と database.md を参照ドキュメント索引に追加"
```

---

## セルフレビュー

### 1. 仕様カバレッジ

| 仕様要件 | 対応タスク |
|---|---|
| container.md: paths `Dockerfile`, `docker-compose*.yml`, `.dockerignore` | Task 1 ✓ |
| container.md: ベースイメージ・multi-stage・non-root・.dockerignore・ヘルスチェック・ARG vs ENV・レイヤー最適化 | Task 1 ✓ |
| container.md: docker-compose の depends_on とネットワーク | Task 1 ✓ |
| database.md: paths `src/**/repositories/**`, `src/**/models/**`, `**/alembic/**`, `*.toml` | Task 2 ✓ |
| database.md: Repository パターン・N+1・トランザクション・マイグレーション・インデックス・テスト時 DB | Task 2 ✓ |
| CLAUDE.md 索引に2行追加 | Task 3 ✓ |

### 2. プレースホルダーチェック

- `python:3.12-slim` のバージョンはプレースホルダーではなく例示。実プロジェクトで置き換えることを意図した値のため問題なし ✓
- `myapp.models.order` は例示のパッケージ名。実プロジェクトで置き換えることを意図 ✓

### 3. 一貫性チェック

- Task 1 の container.md frontmatter の paths と Task 3 の CLAUDE.md 追記内容が一致 ✓
- Task 2 の database.md frontmatter の paths と Task 3 の CLAUDE.md 追記内容が一致 ✓
- `AsyncSession` の変数名が Task 2 全体で `session` / `db` と揺れているが、どちらも Python で一般的な命名。フィクスチャのみ `db` を使い、引数では `session` を使う設計は意図的 ✓
