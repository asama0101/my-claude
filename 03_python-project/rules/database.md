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
