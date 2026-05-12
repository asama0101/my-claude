---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python パターン

## 新規プロジェクト立ち上げ

既存のスケルトンやテンプレートが利用可能な場合はそれを優先する。
ゼロから始める場合は **planner** エージェントで設計から着手する。

## デザインパターン

### リポジトリパターン

`Protocol` を使って一貫したインターフェースの後ろにデータアクセスをカプセル化する:

```python
from typing import Protocol

class UserRepository(Protocol):
    def find_by_id(self, id: str) -> dict | None: ...
    def save(self, entity: dict) -> dict: ...
    def find_all(self) -> list[dict]: ...
    def delete(self, id: str) -> None: ...
```

ビジネスロジックは抽象インターフェースに依存し、ストレージの実装には依存しない — データソースの切り替えが容易になり、モックを使ったテストが簡単になる。

### APIレスポンス形式

すべてのAPIレスポンスに一貫したエンベロープを使用する:

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

## DTOとしてのデータクラス

```python
from dataclasses import dataclass

@dataclass
class CreateUserRequest:
    name: str
    email: str
    age: int | None = None
```

## コンテキストマネージャーとジェネレーター

リソース管理には `with` 文、遅延評価には `yield` を使用する:

```python
# コンテキストマネージャー: ファイル・DB接続など自動クリーンアップ
with open("data.csv") as f:
    data = f.read()

# ジェネレーター: 大量データを1件ずつ処理してメモリを節約
def read_large_file(path: str):
    with open(path) as f:
        for line in f:
            yield line.strip()
```

## 参考

スキル: `python-patterns` でデコレーター・並行処理・パッケージ構成を含む包括的なパターンを参照。
