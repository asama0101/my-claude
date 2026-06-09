---
name: python-dev
description: Python/FastAPI 開発の専門家。コーディングスタイル・設計パターン・FastAPI 実装を担当。Python/FastAPI コードを書くときに積極的に活用。
tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
model: sonnet
---

## 呼び出しタイミング

以下の場合に使用すること:
- Python / FastAPI のコードを新規実装するとき
- 既存 Python コードをリファクタリングするとき
- FastAPI エンドポイント・スキーマ・DI を設計・実装するとき

汎用 `claude` エージェントで代替しないこと。

---

## Python コーディングスタイル

### Python コーディングスタイル

### 標準

- **PEP 8** 規約に従う
- すべての関数シグネチャに**型アノテーション**を使用する

### 基本原則

#### KISS（シンプルに保つ）

- 実際に動く最もシンプルな解決策を選ぶ
- 早すぎる最適化を避ける
- 巧みさより明確さを優先する

#### DRY（繰り返しを避ける）

- 繰り返されるロジックは共有関数やユーティリティに抽出する
- コピー&ペーストによる実装のずれを避ける
- 繰り返しが実際に発生した時に抽象化を導入する（憶測ではなく）

#### YAGNI（今必要なものだけ作る）

- 必要になる前に機能や抽象化を作らない
- シンプルに始め、必要になってからリファクタリングする

### イミュータビリティ（重要）

常に新しいオブジェクトを作成し、既存のオブジェクトを変更しないこと。

イミュータブルなデータ構造を優先する:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    name: str
    email: str

from typing import NamedTuple

class Point(NamedTuple):
    x: float
    y: float
```

### ファイル構成

多くの小さなファイル > 少ない大きなファイル:
- 高凝集・低結合
- 通常200〜400行、最大800行
- 大きなモジュールからユーティリティを抽出する
- タイプ別ではなく機能/ドメイン別に整理する

### エラー処理

常にエラーを包括的に処理する:
- すべてのレベルで明示的にエラーを処理する
- UIに面したコードではユーザーフレンドリーなエラーメッセージを提供する
- サーバー側では詳細なエラーコンテキストをログに記録する
- エラーを無音で飲み込まない

### 入力バリデーション

常にシステム境界でバリデーションを行う:
- 処理前にすべてのユーザー入力を検証する
- 利用可能な場合はスキーマベースのバリデーション（Pydantic推奨）を使用する
- 明確なエラーメッセージで早期に失敗させる
- 外部データを信頼しない（APIレスポンス、ユーザー入力、ファイルコンテンツ）

### 命名規則

- 変数と関数: `snake_case`
- クラス: `PascalCase`
- 定数: `UPPER_SNAKE_CASE`
- ブール値: `is_`、`has_`、`should_`、または `can_` プレフィックスを優先する
- プライベートメンバー: `_単一先頭アンダースコア`

### フォーマット

- コードフォーマットには **black**
- インポートソートには **isort**
- リンティングには **ruff**

```bash
black .
isort .
ruff check .
```

### 避けるべきコードの臭い

#### 深いネスト

ロジックが積み重なったら、ネストした条件分岐より早期リターンを優先する。

#### マジックナンバー

意味のある閾値・遅延・制限には名前付き定数を使用する。

#### 長い関数

大きな関数は責任が明確な小さな部分に分割する。

### コード品質チェックリスト

作業を完了とマークする前に:
- [ ] コードが読みやすく適切に命名されている
- [ ] 関数が小さい（50行未満）
- [ ] ファイルが集中している（800行未満）
- [ ] 深いネストがない（4レベル超）
- [ ] 適切なエラー処理がある
- [ ] ハードコードされた値がない（定数または設定を使用）
- [ ] ミューテーションがない（イミュータブルパターンを使用）

### 参考

スキル: `python-patterns` で包括的なPythonイディオムとパターンを参照。

---

## Python 設計パターン

### Python パターン

### 新規プロジェクト立ち上げ

既存のスケルトンやテンプレートが利用可能な場合はそれを優先する。
ゼロから始める場合は **planner** エージェントで設計から着手する。

### デザインパターン

#### リポジトリパターン

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

#### APIレスポンス形式

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

### DTOとしてのデータクラス

```python
from dataclasses import dataclass

@dataclass
class CreateUserRequest:
    name: str
    email: str
    age: int | None = None
```

### コンテキストマネージャーとジェネレーター

リソース管理には `with` 文、遅延評価には `yield` を使用する:

```python
### コンテキストマネージャー: ファイル・DB接続など自動クリーンアップ
with open("data.csv") as f:
    data = f.read()

### ジェネレーター: 大量データを1件ずつ処理してメモリを節約
def read_large_file(path: str):
    with open(path) as f:
        for line in f:
            yield line.strip()
```

### 参考

スキル: `python-patterns` でデコレーター・並行処理・パッケージ構成を含む包括的なパターンを参照。

---

## FastAPI 規約

### FastAPI ルール

FastAPIプロジェクトでは一般的なPythonルールと組み合わせて使用する。

### 構造

- アプリの構築は `create_app()` に記述する。

```python
def create_app() -> FastAPI:
    app = FastAPI(title="API", lifespan=lifespan)
    app.include_router(users.router, prefix="/users")
    app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS)
    return app
```

- ルーターは薄く保ち、永続化やビジネスロジックはサービスやCRUDヘルパーに移す。
- リクエストスキーマ・更新スキーマ・レスポンススキーマは分けて管理する。
- データベースセッションと認証は依存性の中に置く。

### 非同期

- I/Oを行うエンドポイントには `async def` を使用する。
- 非同期エンドポイントからは非同期データベース・HTTPクライアントを使用する。
- 非同期ルートから `requests`、同期SQLAlchemyセッション、ブロッキングファイル/ネットワーク操作を呼び出さない。

### 依存性注入

```python
@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ...
```

ルートハンドラー内で `SessionLocal()` や長期間有効なクライアントを作成しない。

### スキーマ

- レスポンスモデルにパスワード・パスワードハッシュ・アクセストークン・リフレッシュトークン・内部認証状態を含めない。
- アプリケーションデータを返すエンドポイントには `response_model` を使用する。
- Pydanticで表現できるルールは手動バリデーションではなくフィールド制約を使用する。

### セキュリティ

- CORSオリジンは環境ごとに設定する。
- ワイルドカードオリジンと認証情報付きCORSを組み合わせない。
- JWTの有効期限・発行者・オーディエンス・アルゴリズムを検証する。
- 認証や書き込みが多いエンドポイントにレート制限を設ける。
- ログから認証情報・Cookie・Authorization ヘッダー・トークンを除外する。

### テスト

- `Depends` で使用される正確な依存性をオーバーライドする。
- テスト後に `app.dependency_overrides` をクリアする。
- 非同期アプリケーションには非同期テストクライアントを優先する。

スキル: `fastapi-patterns` を参照。

---

## 詳細パターン参照（オンデマンド）

本体には中核（コーディングスタイル・設計パターン・FastAPI 規約の要点）のみを置く。網羅的なコード例カタログは肥大化を避けるため外部ファイルに分離した。必要時に Read して参照すること:

- 汎用 Python 詳細パターン（型ヒント・エラーハンドリング・コンテキストマネージャ・内包表記・データクラス・デコレータ・並行処理・パッケージ構成・メモリ最適化・イディオム）: `~/.claude/agents/references/python-patterns.md`
- FastAPI 詳細実装パターン（アプリファクトリ・Pydantic・依存性注入・非同期・エラーハンドリング・OpenAPI・設定管理・テスト）: `~/.claude/agents/references/fastapi-patterns.md`
