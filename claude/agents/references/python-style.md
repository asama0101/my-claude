# Python 実装パターン（詳細リファレンス）

> dev-python エージェント用のオンデマンド参照ファイル（エージェント定義ではない）。
> 本体 `dev-python.md` から必要時に Read して参照する。

## Python 実装パターン（詳細）

### 基本原則

#### 1. 可読性を最優先に

Python は可読性を重視する。コードは明快で理解しやすくあるべきだ。

```python
### Good: 明確で読みやすい
def get_active_users(users: list[User]) -> list[User]:
    """Return only active users from the provided list."""
    return [user for user in users if user.is_active]


### Bad: 巧みだが分かりにくい
def get_active_users(u):
    return [x for x in u if x.a]
```

#### 2. 暗黙より明示を

マジックを避け、コードが何をするかを明確に示す。

```python
### Good: 明示的な設定
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

### Bad: 隠れた副作用
import some_module
some_module.setup()  # What does this do?
```

#### 3. EAFP — 許可より謝罪を求めやすく

Python は条件チェックより例外処理を好む。

```python
### Good: EAFP スタイル
def get_value(dictionary: dict, key: str, default: Any = None) -> Any:
    try:
        return dictionary[key]
    except KeyError:
        return default

### Bad: LBYL (Look Before You Leap) スタイル
def get_value(dictionary: dict, key: str, default: Any = None) -> Any:
    if key in dictionary:
        return dictionary[key]
    else:
        return default
```

### docstring（Google スタイル）

public な関数・クラスの docstring は Google Python Style Guide に従い、要約行のあとに `Args` / `Returns` / `Raises` セクションを置く。単純な関数は1行要約のみでよい。

```python
def fetch_user(user_id: str, *, include_deleted: bool = False) -> User:
    """指定 ID のユーザーを取得する。

    Args:
        user_id: 取得対象のユーザー ID。
        include_deleted: 論理削除済みユーザーも対象に含めるか。

    Returns:
        取得した User エンティティ。

    Raises:
        UserNotFoundError: 該当ユーザーが存在しないとき。
    """
    ...
```

docstring・コメントは次の細則に従う。

- **日本語**で書く。ただし セクションヘッダ（`Args:` / `Returns:` / `Raises:` / `Yields:`）・コード識別子・シンボル・例外名・設計参照タグ（`SS7.2` 等）は**英語のまま**残す。
- 要約行は全角「。」で終える（このため下記 ruff で `D400`/`D415` を無効化する）。
- **簡潔に**書く。1文を run-on にしない（ダッシュ挿入句・入れ子括弧・セミコロン連結で長大化させず、短い複数文へ分ける）。コメントも同様。
- **モジュール docstring（ファイル冒頭）が長い場合**は「要約1行 → 空行 → 箇条書き（`-`）」で構造化する。処理ステップ・責務・トレードオフの列挙は箇条書きにする。

```python
"""結果ファイルの writer: 単一のフォーマット/IO 経路 (spec SS6)。

確定は次の順で行われ、読み手が書きかけの最終ファイルを目にすることはない:

- `{final}.tmp` へストリーミングする(0600、書き込み中は所有者のみ)
- flush + fsync する
- chmod 0644 にする
- os.rename で確定する
"""
```

### 型ヒント

#### 基本的な型アノテーション

```python
### Python 3.8 以前との互換性が必要な場合（レガシースタイル）
### Python 3.9+ では list[str], dict[str, Any], str | None を使用推奨
from typing import Optional, List, Dict, Any

def process_user(
    user_id: str,
    data: Dict[str, Any],
    active: bool = True
) -> Optional[User]:
    """Process a user and return the updated User or None."""
    if not active:
        return None
    return User(user_id, data)
```

#### モダンな型ヒント（Python 3.9+）

```python
### Python 3.9+ — 組み込み型を使用
def process_items(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

### Python 3.8 以前 — typing モジュールを使用
from typing import List, Dict

def process_items(items: List[str]) -> Dict[str, int]:
    return {item: len(item) for item in items}
```

#### 型エイリアスと TypeVar

```python
from typing import TypeVar, Union

### 複雑な型のエイリアス
JSON = Union[dict[str, Any], list[Any], str, int, float, bool, None]

def parse_json(data: str) -> JSON:
    return json.loads(data)

### ジェネリック型
T = TypeVar('T')

def first(items: list[T]) -> T | None:
    """Return the first item or None if list is empty."""
    return items[0] if items else None
```

#### Protocol によるダックタイピング

```python
from typing import Protocol

class Renderable(Protocol):
    def render(self) -> str:
        """Render the object to a string."""

def render_all(items: list[Renderable]) -> str:
    """Render all items that implement the Renderable protocol."""
    return "\n".join(item.render() for item in items)
```

### エラーハンドリングパターン

#### 特定の例外を捕捉する

```python
### Good: 特定の例外を捕捉
def load_config(path: str) -> Config:
    try:
        with open(path) as f:
            return Config.from_json(f.read())
    except FileNotFoundError as e:
        raise ConfigError(f"Config file not found: {path}") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config: {path}") from e

### Bad: 素の except
def load_config(path: str) -> Config:
    try:
        with open(path) as f:
            return Config.from_json(f.read())
    except:
        return None  # Silent failure!
```

#### 例外チェーン

```python
def process_data(data: str) -> Result:
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as e:
        # トレースバックを保持するために例外をチェーン
        raise ValueError(f"Failed to parse data: {data}") from e
```

#### カスタム例外階層

```python
class AppError(Exception):
    """Base exception for all application errors."""
    pass

class ValidationError(AppError):
    """Raised when input validation fails."""
    pass

class NotFoundError(AppError):
    """Raised when a requested resource is not found."""
    pass

### 使用例
def get_user(user_id: str) -> User:
    user = db.find_user(user_id)
    if not user:
        raise NotFoundError(f"User not found: {user_id}")
    return user
```

### コンテキストマネージャー

#### リソース管理

```python
### Good: コンテキストマネージャーを使用
def process_file(path: str) -> str:
    with open(path, 'r') as f:
        return f.read()

### Bad: 手動リソース管理
def process_file(path: str) -> str:
    f = open(path, 'r')
    try:
        return f.read()
    finally:
        f.close()
```

#### カスタムコンテキストマネージャー

```python
from contextlib import contextmanager

@contextmanager
def timer(name: str):
    """Context manager to time a block of code."""
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    print(f"{name} took {elapsed:.4f} seconds")

### 使用例
with timer("data processing"):
    process_large_dataset()
```

#### クラスベースのコンテキストマネージャー

```python
class DatabaseTransaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.begin_transaction()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        return False  # Don't suppress exceptions

### 使用例
with DatabaseTransaction(conn):
    user = conn.create_user(user_data)
    conn.create_profile(user.id, profile_data)
```

### 内包表記とジェネレーター

#### リスト内包表記

```python
### Good: シンプルな変換にリスト内包表記を使用
names = [user.name for user in users if user.is_active]

### Bad: 手動ループ
names = []
for user in users:
    if user.is_active:
        names.append(user.name)

### 複雑な内包表記は展開する
### Bad: 複雑すぎる
result = [x * 2 for x in items if x > 0 if x % 2 == 0]

### Good: ジェネレーター関数を使用
def filter_and_transform(items: Iterable[int]) -> list[int]:
    result = []
    for x in items:
        if x > 0 and x % 2 == 0:
            result.append(x * 2)
    return result
```

#### ジェネレーター式

```python
### Good: 遅延評価にジェネレーターを使用
total = sum(x * x for x in range(1_000_000))

### Bad: 大きな中間リストを生成してしまう
total = sum([x * x for x in range(1_000_000)])
```

#### ジェネレーター関数

```python
def read_large_file(path: str) -> Iterator[str]:
    """Read a large file line by line."""
    with open(path) as f:
        for line in f:
            yield line.strip()

### 使用例
for line in read_large_file("huge.txt"):
    process(line)
```

### データクラスと名前付きタプル

#### データクラス

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class User:
    """User entity with automatic __init__, __repr__, and __eq__."""
    id: str
    name: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True

### 使用例
user = User(
    id="123",
    name="Alice",
    email="alice@example.com"
)
```

#### バリデーション付きデータクラス

```python
@dataclass
class User:
    email: str
    age: int

    def __post_init__(self):
        # メールフォーマットの検証
        if "@" not in self.email:
            raise ValueError(f"Invalid email: {self.email}")
        # 年齢範囲の検証
        if self.age < 0 or self.age > 150:
            raise ValueError(f"Invalid age: {self.age}")
```

#### 名前付きタプル

```python
from typing import NamedTuple

class Point(NamedTuple):
    """Immutable 2D point."""
    x: float
    y: float

    def distance(self, other: 'Point') -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

### 使用例
p1 = Point(0, 0)
p2 = Point(3, 4)
print(p1.distance(p2))  # 5.0
```

### 設計パターン（Repository/APIレスポンス/DTO）

#### リポジトリパターン

`Protocol` を使って一貫したインターフェースの後ろにデータアクセスをカプセル化する。ビジネスロジックは抽象インターフェースに依存し、ストレージの実装には依存しない — データソースの切り替えが容易になり、モックを使ったテストが簡単になる。

```python
from typing import Protocol

class UserRepository(Protocol):
    def find_by_id(self, id: str) -> dict | None: ...
    def save(self, entity: dict) -> dict: ...
    def find_all(self) -> list[dict]: ...
    def delete(self, id: str) -> None: ...
```

#### APIレスポンス形式（エンベロープ）

すべてのAPIレスポンスに一貫したエンベロープを使用する。

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

@dataclass
class ApiResponse(Generic[T]):
    success: bool
    data: T | None = None
    error: str | None = None

@dataclass
class PaginatedResponse(Generic[T]):
    success: bool
    data: list[T]
    total: int
    page: int
    limit: int
```

#### DTOとしてのデータクラス

境界をまたぐ入力・リクエストは軽量な DTO（データクラス）で表現する。

```python
from dataclasses import dataclass

@dataclass
class CreateUserRequest:
    name: str
    email: str
    age: int | None = None
```

### デコレーター

#### 関数デコレーター

```python
import functools
import time

def timer(func: Callable) -> Callable:
    """Decorator to time function execution."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} took {elapsed:.4f}s")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)

### slow_function() prints: slow_function took 1.0012s
```

#### パラメーター付きデコレーター

```python
def repeat(times: int):
    """Decorator to repeat a function multiple times."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            results = []
            for _ in range(times):
                results.append(func(*args, **kwargs))
            return results
        return wrapper
    return decorator

@repeat(times=3)
def greet(name: str) -> str:
    return f"Hello, {name}!"

### greet("Alice") returns ["Hello, Alice!", "Hello, Alice!", "Hello, Alice!"]
```

#### クラスベースのデコレーター

```python
class CountCalls:
    """Decorator that counts how many times a function is called."""
    def __init__(self, func: Callable):
        functools.update_wrapper(self, func)
        self.func = func
        self.count = 0

    def __call__(self, *args, **kwargs):
        self.count += 1
        print(f"{self.func.__name__} has been called {self.count} times")
        return self.func(*args, **kwargs)

@CountCalls
def process():
    pass

### Each call to process() prints the call count
```

### 並行処理パターン

#### I/O バウンドタスクにはスレッドを使用

```python
import concurrent.futures
import threading

def fetch_url(url: str) -> str:
    """Fetch a URL (I/O-bound operation)."""
    import urllib.request
    with urllib.request.urlopen(url) as response:
        return response.read().decode()

def fetch_all_urls(urls: list[str]) -> dict[str, str]:
    """Fetch multiple URLs concurrently using threads."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(fetch_url, url): url for url in urls}
        results = {}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception as e:
                results[url] = f"Error: {e}"
    return results
```

#### CPU バウンドタスクにはマルチプロセスを使用

```python
def process_data(data: list[int]) -> int:
    """CPU-intensive computation."""
    return sum(x ** 2 for x in data)

def process_all(datasets: list[list[int]]) -> list[int]:
    """Process multiple datasets using multiple processes."""
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(process_data, datasets))
    return results
```

#### 並行 I/O には async/await を使用

```python
import asyncio

async def fetch_async(url: str) -> str:
    """Fetch a URL asynchronously."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

async def fetch_all(urls: list[str]) -> dict[str, str]:
    """Fetch multiple URLs concurrently."""
    tasks = [fetch_async(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return dict(zip(urls, results))
```

### パッケージ構成

#### 標準プロジェクトレイアウト

```
myproject/
├── src/
│   └── mypackage/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── user.py
│       └── utils/
│           ├── __init__.py
│           └── helpers.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api.py
│   └── test_models.py
├── pyproject.toml
├── README.md
└── .gitignore
```

#### レイアウト規約: src を基本とする

- **src を基本とせよ**。新規 Python パッケージは上図の src レイアウト（`src/mypackage/`）を既定とせよ。
- **flat レイアウト**（`mypackage/` をリポジトリ直下に置く）は、**配布しないアプリ/スクリプト**に限り、理由を添えて選べ。理由なき flat は避けよ。
- 理由: src はインストール状態でのみ import できるため、同梱漏れ・import shadowing をテスト/CI が検知できる。flat はルートが `sys.path` に入り未インストールでも import が通るため、これらを見逃す。

```
### flat レイアウト（配布しないアプリ/スクリプト限定）
myproject/
├── mypackage/
│   └── __init__.py
├── tests/
└── pyproject.toml
```

#### インポート規約

```python
### Good: インポート順 — 標準ライブラリ、サードパーティ、ローカル
import os
import sys
from pathlib import Path

import requests
from fastapi import FastAPI

from mypackage.models import User
from mypackage.utils import format_name

### Good: isort で自動ソート
### pip install isort
```

#### パッケージエクスポート用 __init__.py

```python
### mypackage/__init__.py
"""mypackage - A sample Python package."""

__version__ = "1.0.0"

### パッケージレベルで主要クラス/関数をエクスポート
from mypackage.models import User, Post
from mypackage.utils import format_name

__all__ = ["User", "Post", "format_name"]
```

### メモリとパフォーマンス

#### メモリ効率化に __slots__ を使用

```python
### Bad: 通常クラスは __dict__ を使う（メモリ消費が大きい）
class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

### Good: __slots__ でメモリ削減
class Point:
    __slots__ = ['x', 'y']

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
```

#### 大量データにはジェネレーターを使用

```python
### Bad: リスト全体をメモリに返す
def read_lines(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f]

### Good: 1行ずつ yield する
def read_lines(path: str) -> Iterator[str]:
    with open(path) as f:
        for line in f:
            yield line.strip()
```

#### ループ内での文字列連結を避ける

```python
### Bad: 文字列の不変性により O(n²)
result = ""
for item in items:
    result += str(item)

### Good: join を使って O(n)
result = "".join(str(item) for item in items)

### Good: StringIO を使って構築
from io import StringIO

buffer = StringIO()
for item in items:
    buffer.write(str(item))
result = buffer.getvalue()
```

### Python ツール連携

#### 主要コマンド

```bash
### コードフォーマット
black .
isort .

### リンティング
ruff check .          # E/F/I/N/W + D（docstring 形式）
darglint mypackage/   # docstring と実シグネチャの整合
pylint mypackage/

### 型チェック
mypy .

### テスト
pytest --cov=mypackage --cov-report=html

### セキュリティスキャン
bandit -r .

### 依存関係管理
pip-audit
safety check
```

#### pyproject.toml 設定

```toml
[project]
name = "mypackage"
version = "1.0.0"
requires-python = ">=3.9"
dependencies = [
    "requests>=2.31.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "darglint>=1.8.0",
    "mypy>=1.5.0",
]

[tool.black]
line-length = 88
target-version = ['py39']

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "W", "D"]   # D を追加（pydocstyle: docstring 規約）
ignore = ["D400", "D415"]                 # 要約を全角「。」で終える日本語 docstring を許容

[tool.ruff.lint.pydocstyle]
convention = "google"                       # Google 形式のみを対象に

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["D"]                          # テスト関数は名前で自己説明的なため docstring 規約の対象外

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

#### darglint 設定（setup.cfg）

darglint は pyproject.toml を読まないため、`setup.cfg` / `tox.ini` / `.darglint` に置く。

```ini
[darglint]
docstring_style = google
strictness = short
```

> pytest の設定（`testpaths`/`addopts` 等）は `agents/references/python-testing.md`「pytest 設定」を単一ソースとする。

### Python イディオム クイックリファレンス

| イディオム | 説明 |
|-----------|------|
| EAFP | 許可より謝罪を求めやすく |
| コンテキストマネージャー | リソース管理に `with` を使用 |
| リスト内包表記 | シンプルな変換に使用 |
| ジェネレーター | 遅延評価と大量データに使用 |
| 型ヒント | 関数シグネチャにアノテーション |
| データクラス | 自動生成メソッド付きデータコンテナ |
| `__slots__` | メモリ最適化に使用 |
| f-string | 文字列フォーマット（Python 3.6+） |
| `pathlib.Path` | パス操作（Python 3.4+） |
| `enumerate` | ループでインデックスと要素のペアを取得 |

### 避けるべきアンチパターン

```python
### Bad: ミュータブルなデフォルト引数
def append_to(item, items=[]):
    items.append(item)
    return items

### Good: None を使って新しいリストを生成
def append_to(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items

### Bad: type() で型チェック
if type(obj) == list:
    process(obj)

### Good: isinstance を使用
if isinstance(obj, list):
    process(obj)

### Bad: None を == で比較
if value == None:
    process()

### Good: is を使用
if value is None:
    process()

### Bad: from module import *
from os.path import *

### Good: 明示的なインポート
from os.path import join, exists

### Bad: 素の except
try:
    risky_operation()
except:
    pass

### Good: 特定の例外を指定
try:
    risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
```

