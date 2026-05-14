---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python テスト

## フレームワーク

テストフレームワークとして **pytest** を使用する。

## 最低テストカバレッジ: 80%

テスト種別（すべて必須）:
1. **ユニットテスト** — 個々の関数、ユーティリティ
2. **統合テスト** — APIエンドポイント、データベース操作
3. **E2Eテスト** — 重要なユーザーフロー

## テスト駆動開発

必須ワークフロー:
1. まずテストを書く（RED）
2. テストを実行 — 失敗するはず
3. 最小限の実装を書く（GREEN）
4. テストを実行 — 成功するはず
5. リファクタリング（IMPROVE）
6. カバレッジを確認（80%以上）

## カバレッジ

```bash
pytest --cov=src --cov-report=term-missing
```

## テストの整理

テストの分類には `pytest.mark` を使用する:

```python
import pytest

@pytest.mark.unit
def test_calculate_total():
    ...

@pytest.mark.integration
def test_database_connection():
    ...
```

## テストデータの初期化・クリーンアップ（必須）

すべてのテストは **独立していなければならない**。テスト実行前にデータを初期化し、実行後に必ずクリーンアップすること。

**必須パターン（yield フィクスチャ）:**

```python
@pytest.fixture
def db_session():
    session.begin()
    setup_test_data(session)   # テスト前: 初期データ投入
    yield session
    session.rollback()         # テスト後: 必ずロールバック

@pytest.fixture(autouse=True)
def reset_state():
    initialize()               # テスト前: 状態をリセット
    yield
    cleanup()                  # テスト後: 必ずクリーンアップ
```

**禁止事項:**
- テスト間でデータ・状態を共有する（グローバル変数への書き込みなど）
- ティアダウンを省略する（`yield` 後はテスト失敗時も必ず実行される）
- DB テストでロールバック/削除なしにコミットしたままにする

---

## テスト構造（AAAパターン）

Arrange-Act-Assert（準備-実行-検証）構造を優先する:

```python
def test_calculates_similarity_correctly():
    # Arrange（準備）
    vector1 = [1, 0, 0]
    vector2 = [0, 1, 0]

    # Act（実行）
    similarity = calculate_cosine_similarity(vector1, vector2)

    # Assert（検証）
    assert similarity == 0.0
```

## テスト命名

テスト対象の振る舞いを説明する記述的な名前を使用する:

```python
def test_returns_empty_list_when_no_items_match():
def test_raises_value_error_when_api_key_missing():
def test_falls_back_to_db_when_cache_unavailable():
```

## テスト失敗のトラブルシューティング

1. **tdd-guide** エージェントを使用する
2. テストの独立性を確認する
3. モックが正しいことを確認する
4. テストではなく実装を修正する（テストが間違っている場合を除く）

## エージェントサポート

- **tdd-guide** — 新機能に対して積極的に使用し、テストファーストを強制する

## 非同期テスト

非同期エンドポイントのテストには `pytest-asyncio` と `httpx` を使用する:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_user(async_client: AsyncClient):
    response = await async_client.get("/users/1")
    assert response.status_code == 200
```

## 参考

スキル: `python-testing` で詳細なpytestパターンとフィクスチャを参照。
