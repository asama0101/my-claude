---
name: fastapi-patterns
description: 非同期 API、依存性注入、Pydantic リクエスト/レスポンスモデル、OpenAPI ドキュメント、テスト、セキュリティ、本番運用に向けた FastAPI パターン集。
origin: community
---

# FastAPI パターン

FastAPI サービスのための本番志向パターン集。

## 使用場面

- FastAPI アプリを新規構築またはレビューするとき。
- ルーター、スキーマ、依存関係、DB アクセスを分割するとき。
- DB や外部サービスを呼び出す非同期エンドポイントを書くとき。
- 認証、認可、OpenAPI ドキュメント、テスト、デプロイ設定を追加するとき。
- FastAPI PR をコピー可能なサンプルと本番リスクの観点でレビューするとき。

## 設計方針

FastAPI アプリは「薄い HTTP レイヤー + 明示的な依存関係 + サービスコード」として扱う:

- `main.py` — アプリ生成、ミドルウェア、例外ハンドラー、ルーター登録を担当。
- `schemas/` — Pydantic のリクエスト/レスポンスモデルを担当。
- `dependencies.py` — DB、認証、ページネーション、リクエストスコープの依存関係を担当。
- `services/` または `crud/` — ビジネスロジックと永続化処理を担当。
- `tests/` — 本番リソースを開かず依存関係をオーバーライドして使用。

小さなルーターと明示的な `response_model` 宣言を優先。生の ORM オブジェクト、シークレット、フレームワークのグローバル変数をレスポンススキーマに含めない。

## プロジェクト構成

```text
app/
|-- main.py
|-- config.py
|-- dependencies.py
|-- exceptions.py
|-- api/
|   `-- routes/
|       |-- users.py
|       `-- health.py
|-- core/
|   |-- security.py
|   `-- middleware.py
|-- db/
|   |-- session.py
|   `-- crud.py
|-- models/
|-- schemas/
`-- tests/
```

## アプリケーションファクトリ

テストやワーカーが制御された設定でアプリを構築できるよう、ファクトリパターンを使用する。

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, users
from app.config import settings
from app.db.session import close_db, init_db
from app.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=bool(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    register_exception_handlers(app)
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
    return app


app = create_app()
```

`allow_origins=["*"]` と `allow_credentials=True` を同時に使わないこと。ブラウザがその組み合わせを拒否し、Starlette も認証情報付きリクエストではこれを許可しない。

## Pydantic スキーマ

リクエスト・更新・レスポンスモデルは分離して定義する。

```python
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    full_name: Annotated[str, Field(min_length=1, max_length=100)]


class UserCreate(UserBase):
    password: Annotated[str, Field(min_length=12, max_length=128)]


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: Annotated[str | None, Field(min_length=1, max_length=100)] = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
```

レスポンスモデルにパスワードハッシュ、アクセストークン、リフレッシュトークン、内部の認可状態を含めてはならない。

## 依存関係

リクエストスコープのリソースには依存性注入を使用する。

```python
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import session_factory
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(token)
    user_id = UUID(payload["sub"])
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user
```

セッション、クライアント、認証情報をルートハンドラーの内部でインラインに生成しないこと。

## 非同期エンドポイント

I/O を伴う場合はルートハンドラーを async にし、内部でも非同期ライブラリを使用する。

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.user import UserResponse


router = APIRouter()


@router.get("/", response_model=list[UserResponse])
async def list_users(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return result.scalars().all()
```

async ハンドラーからの外部 HTTP 呼び出しには `httpx.AsyncClient` を使うこと。async ルート内で `requests` を呼んではならない。

## エラーハンドリング

ドメイン例外を集約し、レスポンス形式を安定させる。

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
```

## OpenAPI カスタマイズ

カスタム OpenAPI 関数を `app.openapi` に代入すること。関数を一度だけ呼び出して終わりにしてはいけない。

```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def install_openapi(app: FastAPI) -> None:
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        app.openapi_schema = get_openapi(
            title="Service API",
            version="1.0.0",
            routes=app.routes,
        )
        return app.openapi_schema

    app.openapi = custom_openapi
```

## テスト

ルートハンドラーが参照しない内部ヘルパーではなく、`Depends` が使う依存関係を直接オーバーライドする。

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.main import create_app


@pytest.fixture
async def client(test_session: AsyncSession):
    app = create_app()

    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

## 設定管理

`pydantic-settings` の `BaseSettings` で環境変数を型安全に管理する。

```python
from functools import lru_cache

from pydantic import AnyHttpUrl, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    api_title: str = "My API"
    api_version: str = "1.0.0"
    database_url: str
    cors_origins: list[AnyHttpUrl] = []
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

`.env` ファイルからも環境変数からも読み込む。`@lru_cache` でシングルトン化し、テストでは `dependency_overrides` で差し替える。

```python
# テストでの上書き例
app.dependency_overrides[get_settings] = lambda: Settings(database_url="sqlite:///:memory:")
```

## セキュリティチェックリスト

- パスワードは `argon2-cffi`、`bcrypt`、または現行の passlib 対応ハッシャーでハッシュ化する。
- JWT の issuer、audience、expiry、署名アルゴリズムを検証する。
- CORS origin は環境ごとに設定する。
- 認証エンドポイントや書き込み頻度の高いエンドポイントにレート制限を設ける。
- 全リクエストボディに Pydantic モデルを使用する。
- ORM パラメーターバインディングまたは SQLAlchemy Core 式を使用し、f-string で SQL を組み立てない。
- トークン、Authorization ヘッダー、Cookie、パスワードをログから除去する。
- CI で依存関係の脆弱性チェックを実行する。

## パフォーマンスチェックリスト

- DB コネクションプールを明示的に設定する。
- リスト系エンドポイントにページネーションを追加する。
- N+1 クエリに注意し、Eager Loading は意図的に使用する。
- async パスでは非同期 HTTP/DB クライアントを使用する。
- 圧縮はペイロードサイズと CPU トレードオフを確認してから追加する。
- 安定した高コストな読み取りは、明示的な無効化を伴うキャッシュで賄う。

## 関連スキル

- Skill: `python-patterns`
- Skill: `python-testing`
- Skill: `api-design`
