---
name: python-testing
description: pytest を使った Python テスト戦略：TDD メソドロジー、フィクスチャ、モック、パラメトライズ、カバレッジ要件。
origin: ECC
---

# Python テストパターン

pytest、TDD メソドロジー、ベストプラクティスを使った Python アプリケーションの総合テスト戦略。

## 使用場面

- 新規 Python コードを書くとき（TDD に従う: レッド → グリーン → リファクタリング）
- Python プロジェクトのテストスイートを設計するとき
- Python のテストカバレッジをレビューするとき
- テストインフラをセットアップするとき

## テストの核心哲学

### テスト駆動開発（TDD）

常に TDD サイクルに従う:

1. **RED**: 期待する動作に対して失敗するテストを書く
2. **GREEN**: テストを通過させる最小限のコードを書く
3. **REFACTOR**: テストをグリーンに保ちながらコードを改善する

```python
# Step 1: 失敗するテストを書く（RED）
def test_add_numbers():
    result = add(2, 3)
    assert result == 5

# Step 2: 最小限の実装を書く（GREEN）
def add(a, b):
    return a + b

# Step 3: 必要に応じてリファクタリング（REFACTOR）
```

### カバレッジ要件

- **目標**: コードカバレッジ 80% 以上
- **クリティカルパス**: 100% カバレッジが必須
- `pytest --cov` でカバレッジを計測する

```bash
pytest --cov=mypackage --cov-report=term-missing --cov-report=html
```

## pytest の基礎

### 基本的なテスト構造

```python
import pytest

def test_addition():
    """Test basic addition."""
    assert 2 + 2 == 4

def test_string_uppercase():
    """Test string uppercasing."""
    text = "hello"
    assert text.upper() == "HELLO"

def test_list_append():
    """Test list append."""
    items = [1, 2, 3]
    items.append(4)
    assert 4 in items
    assert len(items) == 4
```

### アサーション

```python
# 等値
assert result == expected

# 不等値
assert result != unexpected

# 真偽値
assert result  # Truthy
assert not result  # Falsy
assert result is True  # 厳密に True
assert result is False  # 厳密に False
assert result is None  # 厳密に None

# メンバーシップ
assert item in collection
assert item not in collection

# 比較
assert result > 0
assert 0 <= result <= 100

# 型チェック
assert isinstance(result, str)

# 例外テスト（推奨アプローチ）
with pytest.raises(ValueError):
    raise ValueError("error message")

# 例外メッセージのチェック
with pytest.raises(ValueError, match="invalid input"):
    raise ValueError("invalid input provided")

# 例外属性のチェック
with pytest.raises(ValueError) as exc_info:
    raise ValueError("error message")
assert str(exc_info.value) == "error message"
```

## フィクスチャ

### 基本的なフィクスチャの使い方

```python
import pytest

@pytest.fixture
def sample_data():
    """Fixture providing sample data."""
    return {"name": "Alice", "age": 30}

def test_sample_data(sample_data):
    """Test using the fixture."""
    assert sample_data["name"] == "Alice"
    assert sample_data["age"] == 30
```

### セットアップ/ティアダウン付きフィクスチャ

```python
@pytest.fixture
def database():
    """Fixture with setup and teardown."""
    # セットアップ
    db = Database(":memory:")
    db.create_tables()
    db.insert_test_data()

    yield db  # テストに提供

    # ティアダウン
    db.close()

def test_database_query(database):
    """Test database operations."""
    result = database.query("SELECT * FROM users")
    assert len(result) > 0
```

### フィクスチャのスコープ

```python
# function スコープ（デフォルト）— テストごとに実行
@pytest.fixture
def temp_file():
    with open("temp.txt", "w") as f:
        yield f
    os.remove("temp.txt")

# module スコープ — モジュールごとに1回実行
@pytest.fixture(scope="module")
def module_db():
    db = Database(":memory:")
    db.create_tables()
    yield db
    db.close()

# session スコープ — テストセッションで1回実行
@pytest.fixture(scope="session")
def shared_resource():
    resource = ExpensiveResource()
    yield resource
    resource.cleanup()
```

### パラメーター付きフィクスチャ

```python
@pytest.fixture(params=[1, 2, 3])
def number(request):
    """Parameterized fixture."""
    return request.param

def test_numbers(number):
    """Test runs 3 times, once for each parameter."""
    assert number > 0
```

### 複数フィクスチャの使用

```python
@pytest.fixture
def user():
    return User(id=1, name="Alice")

@pytest.fixture
def admin():
    return User(id=2, name="Admin", role="admin")

def test_user_admin_interaction(user, admin):
    """Test using multiple fixtures."""
    assert admin.can_manage(user)
```

### autouse フィクスチャ

```python
@pytest.fixture(autouse=True)
def reset_config():
    """Automatically runs before every test."""
    Config.reset()
    yield
    Config.cleanup()

def test_without_fixture_call():
    # reset_config が自動実行される
    assert Config.get_setting("debug") is False
```

### 共有フィクスチャ用 conftest.py

```python
# tests/conftest.py
import pytest

@pytest.fixture
def client():
    """Shared fixture for all tests."""
    app = create_app(testing=True)
    with app.test_client() as client:
        yield client

@pytest.fixture
def auth_headers(client):
    """Generate auth headers for API testing."""
    response = client.post("/api/login", json={
        "username": "test",
        "password": "test"
    })
    token = response.json["token"]
    return {"Authorization": f"Bearer {token}"}
```

## パラメトライズ

### 基本的なパラメトライズ

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("PyThOn", "PYTHON"),
])
def test_uppercase(input, expected):
    """Test runs 3 times with different inputs."""
    assert input.upper() == expected
```

### 複数パラメーター

```python
@pytest.mark.parametrize("a,b,expected", [
    (2, 3, 5),
    (0, 0, 0),
    (-1, 1, 0),
    (100, 200, 300),
])
def test_add(a, b, expected):
    """Test addition with multiple inputs."""
    assert add(a, b) == expected
```

### ID 付きパラメトライズ

```python
@pytest.mark.parametrize("input,expected", [
    ("valid@email.com", True),
    ("invalid", False),
    ("@no-domain.com", False),
], ids=["valid-email", "missing-at", "missing-domain"])
def test_email_validation(input, expected):
    """Test email validation with readable test IDs."""
    assert is_valid_email(input) is expected
```

### パラメトライズドフィクスチャ

```python
@pytest.fixture(params=["sqlite", "postgresql", "mysql"])
def db(request):
    """Test against multiple database backends."""
    if request.param == "sqlite":
        return Database(":memory:")
    elif request.param == "postgresql":
        return Database("postgresql://localhost/test")
    elif request.param == "mysql":
        return Database("mysql://localhost/test")

def test_database_operations(db):
    """Test runs 3 times, once for each database."""
    result = db.query("SELECT 1")
    assert result is not None
```

## マーカーとテスト選択

### カスタムマーカー

```python
# 遅いテストにマーク
@pytest.mark.slow
def test_slow_operation():
    time.sleep(5)

# 統合テストにマーク
@pytest.mark.integration
def test_api_integration():
    response = requests.get("https://api.example.com")
    assert response.status_code == 200

# ユニットテストにマーク
@pytest.mark.unit
def test_unit_logic():
    assert calculate(2, 3) == 5
```

### 特定テストの実行

```bash
# 速いテストだけ実行
pytest -m "not slow"

# 統合テストだけ実行
pytest -m integration

# 統合テストまたは遅いテストを実行
pytest -m "integration or slow"

# ユニットテストで遅くないものを実行
pytest -m "unit and not slow"
```

### pytest.ini でのマーカー設定

```ini
[pytest]
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    django: marks tests as requiring Django
```

## モックとパッチ

### 関数のモック

```python
from unittest.mock import patch, Mock

@patch("mypackage.external_api_call")
def test_with_mock(api_call_mock):
    """Test with mocked external API."""
    api_call_mock.return_value = {"status": "success"}

    result = my_function()

    api_call_mock.assert_called_once()
    assert result["status"] == "success"
```

### 戻り値のモック

```python
@patch("mypackage.Database.connect")
def test_database_connection(connect_mock):
    """Test with mocked database connection."""
    connect_mock.return_value = MockConnection()

    db = Database()
    db.connect()

    connect_mock.assert_called_once_with("localhost")
```

### 例外のモック

```python
@patch("mypackage.api_call")
def test_api_error_handling(api_call_mock):
    """Test error handling with mocked exception."""
    api_call_mock.side_effect = ConnectionError("Network error")

    with pytest.raises(ConnectionError):
        api_call()

    api_call_mock.assert_called_once()
```

### コンテキストマネージャーのモック

```python
@patch("builtins.open", new_callable=mock_open)
def test_file_reading(mock_file):
    """Test file reading with mocked open."""
    mock_file.return_value.read.return_value = "file content"

    result = read_file("test.txt")

    mock_file.assert_called_once_with("test.txt", "r")
    assert result == "file content"
```

### autospec の使用

```python
@patch("mypackage.DBConnection", autospec=True)
def test_autospec(db_mock):
    """Test with autospec to catch API misuse."""
    db = db_mock.return_value
    db.query("SELECT * FROM users")

    # DBConnection に query メソッドがなければ失敗する
    db_mock.assert_called_once()
```

### クラスインスタンスのモック

```python
class TestUserService:
    @patch("mypackage.UserRepository")
    def test_create_user(self, repo_mock):
        """Test user creation with mocked repository."""
        repo_mock.return_value.save.return_value = User(id=1, name="Alice")

        service = UserService(repo_mock.return_value)
        user = service.create_user(name="Alice")

        assert user.name == "Alice"
        repo_mock.return_value.save.assert_called_once()
```

### プロパティのモック

```python
@pytest.fixture
def mock_config():
    """Create a mock with a property."""
    config = Mock()
    type(config).debug = PropertyMock(return_value=True)
    type(config).api_key = PropertyMock(return_value="test-key")
    return config

def test_with_mock_config(mock_config):
    """Test with mocked config properties."""
    assert mock_config.debug is True
    assert mock_config.api_key == "test-key"
```

### pytest-mock の mocker フィクスチャ

`@patch` デコレーターより Pythonic で、複数フィクスチャと組み合わせが容易（`pip install pytest-mock` が必要）。

```python
def test_with_mocker(mocker):
    """pytest-mock の mocker フィクスチャを使用。"""
    mock_call = mocker.patch("mypackage.external_api_call")
    mock_call.return_value = {"status": "success"}

    result = my_function()

    mock_call.assert_called_once()
    assert result["status"] == "success"


def test_async_with_mocker(mocker):
    """非同期関数のモック。"""
    mock_call = mocker.AsyncMock(return_value={"status": "ok"})
    mocker.patch("mypackage.async_api_call", mock_call)

    result = asyncio.run(my_async_function())

    mock_call.assert_awaited_once()
```

## 非同期コードのテスト

### pytest-asyncio による非同期テスト

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_add(2, 3)
    assert result == 5

@pytest.mark.asyncio
async def test_async_with_fixture(async_client):
    """Test async with async fixture."""
    response = await async_client.get("/api/users")
    assert response.status_code == 200
```

### 非同期フィクスチャ

```python
@pytest.fixture
async def async_client():
    """Async fixture providing async test client."""
    app = create_app()
    async with app.test_client() as client:
        yield client

@pytest.mark.asyncio
async def test_api_endpoint(async_client):
    """Test using async fixture."""
    response = await async_client.get("/api/data")
    assert response.status_code == 200
```

### 非同期関数のモック

```python
@pytest.mark.asyncio
@patch("mypackage.async_api_call")
async def test_async_mock(api_call_mock):
    """Test async function with mock."""
    api_call_mock.return_value = {"status": "ok"}

    result = await my_async_function()

    api_call_mock.assert_awaited_once()
    assert result["status"] == "ok"
```

## 例外のテスト

### 期待される例外のテスト

```python
def test_divide_by_zero():
    """Test that dividing by zero raises ZeroDivisionError."""
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)

def test_custom_exception():
    """Test custom exception with message."""
    with pytest.raises(ValueError, match="invalid input"):
        validate_input("invalid")
```

### 例外属性のテスト

```python
def test_exception_with_details():
    """Test exception with custom attributes."""
    with pytest.raises(CustomError) as exc_info:
        raise CustomError("error", code=400)

    assert exc_info.value.code == 400
    assert "error" in str(exc_info.value)
```

## 副作用のテスト

### ファイル操作のテスト

```python
import tempfile
import os

def test_file_processing():
    """Test file processing with temp file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("test content")
        temp_path = f.name

    try:
        result = process_file(temp_path)
        assert result == "processed: test content"
    finally:
        os.unlink(temp_path)
```

### pytest の tmp_path フィクスチャを使ったテスト

```python
def test_with_tmp_path(tmp_path):
    """Test using pytest's built-in temp path fixture."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")

    result = process_file(str(test_file))
    assert result == "hello world"
    # tmp_path は自動クリーンアップされる
```

### tmpdir フィクスチャを使ったテスト

```python
def test_with_tmpdir(tmpdir):
    """Test using pytest's tmpdir fixture."""
    test_file = tmpdir.join("test.txt")
    test_file.write("data")

    result = process_file(str(test_file))
    assert result == "data"
```

## テスト整理

### ディレクトリ構成

```
tests/
├── conftest.py                 # 共有フィクスチャ
├── __init__.py
├── unit/                       # ユニットテスト
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_utils.py
│   └── test_services.py
├── integration/                # 統合テスト
│   ├── __init__.py
│   ├── test_api.py
│   └── test_database.py
└── e2e/                        # E2E テスト
    ├── __init__.py
    └── test_user_flow.py
```

### テストクラス

```python
class TestUserService:
    """関連するテストをクラスにグループ化する。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """このクラスの各テスト前に実行される。"""
        self.service = UserService()

    def test_create_user(self):
        """Test user creation."""
        user = self.service.create_user("Alice")
        assert user.name == "Alice"

    def test_delete_user(self):
        """Test user deletion."""
        user = User(id=1, name="Bob")
        self.service.delete_user(user)
        assert not self.service.user_exists(1)
```

## ベストプラクティス

### すべきこと

- **TDD に従う**: コードより先にテストを書く（レッド → グリーン → リファクタリング）
- **1つのことをテストする**: 各テストは単一の動作を検証する
- **説明的な名前を使う**: `test_user_login_with_invalid_credentials_fails`
- **フィクスチャを使う**: フィクスチャで重複を排除する
- **外部依存関係をモックする**: 外部サービスに依存しない
- **エッジケースをテストする**: 空入力、None 値、境界条件
- **80% 以上のカバレッジを目指す**: クリティカルパスに集中する
- **テストを速く保つ**: マークで遅いテストを分離する

### すべきでないこと

- **実装をテストしない**: 内部ではなく動作をテストする
- **テスト内で複雑な条件分岐を使わない**: テストはシンプルに保つ
- **テスト失敗を無視しない**: 全テストが通過しなければならない
- **サードパーティコードをテストしない**: ライブラリの動作を信頼する
- **テスト間で状態を共有しない**: テストは独立していること
- **テスト内で例外を捕捉しない**: `pytest.raises` を使用する
- **print 文を使わない**: アサーションと pytest の出力を使う
- **脆すぎるテストを書かない**: 過度に詳細なモックを避ける

## よくあるパターン

### API エンドポイントのテスト（FastAPI/Flask）

```python
@pytest.fixture
def client():
    app = create_app(testing=True)
    return app.test_client()

def test_get_user(client):
    response = client.get("/api/users/1")
    assert response.status_code == 200
    assert response.json["id"] == 1

def test_create_user(client):
    response = client.post("/api/users", json={
        "name": "Alice",
        "email": "alice@example.com"
    })
    assert response.status_code == 201
    assert response.json["name"] == "Alice"
```

### データベース操作のテスト

```python
@pytest.fixture
def db_session():
    """テスト用データベースセッションを作成する。"""
    with Session(engine) as session:  # SQLAlchemy 2.x スタイル（bind= は廃止済み）
        session.begin()
        yield session
        session.rollback()

def test_create_user(db_session):
    user = User(name="Alice", email="alice@example.com")
    db_session.add(user)
    db_session.commit()

    retrieved = db_session.query(User).filter_by(name="Alice").first()
    assert retrieved.email == "alice@example.com"
```

### クラスメソッドのテスト

```python
class TestCalculator:
    @pytest.fixture
    def calculator(self):
        return Calculator()

    def test_add(self, calculator):
        assert calculator.add(2, 3) == 5

    def test_divide_by_zero(self, calculator):
        with pytest.raises(ZeroDivisionError):
            calculator.divide(10, 0)
```

## pytest 設定

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --strict-markers
    --disable-warnings
    --cov=mypackage
    --cov-report=term-missing
    --cov-report=html
asyncio_mode = auto
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    unit: marks tests as unit tests
```

### pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--cov=mypackage",
    "--cov-report=term-missing",
    "--cov-report=html",
]
asyncio_mode = "auto"
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]
```

## テスト実行コマンド

```bash
# 全テストを実行
pytest

# 特定ファイルを実行
pytest tests/test_utils.py

# 特定テストを実行
pytest tests/test_utils.py::test_function

# 詳細出力で実行
pytest -v

# カバレッジ付きで実行
pytest --cov=mypackage --cov-report=html

# 速いテストだけ実行
pytest -m "not slow"

# 最初の失敗で停止
pytest -x

# N 件失敗で停止
pytest --maxfail=3

# 最後に失敗したテストを実行
pytest --lf

# パターンでテストを実行
pytest -k "test_user"

# 失敗時にデバッガーを起動
pytest --pdb
```

## クイックリファレンス

| パターン | 使い方 |
|---------|--------|
| `pytest.raises()` | 期待される例外のテスト |
| `@pytest.fixture()` | 再利用可能なテストフィクスチャの作成 |
| `@pytest.mark.parametrize()` | 複数入力でテストを実行 |
| `@pytest.mark.slow` | 遅いテストにマーク |
| `pytest -m "not slow"` | 遅いテストをスキップ |
| `@patch()` | 関数とクラスのモック |
| `tmp_path` フィクスチャ | 自動一時ディレクトリ |
| `pytest --cov` | カバレッジレポート生成 |
| `assert` | シンプルで読みやすいアサーション |

**覚えておくこと**: テストもコードだ。クリーンで読みやすく、保守しやすく保つこと。良いテストはバグを捕まえ、優れたテストはバグを未然に防ぐ。
