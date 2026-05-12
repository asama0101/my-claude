---
paths:
  - "**/app/**/*.py"
  - "**/fastapi/**/*.py"
  - "**/*_api.py"
  - "**/routers/**/*.py"
  - "**/services/**/*.py"
  - "**/api/**/*.py"
---
# FastAPI ルール

FastAPIプロジェクトでは一般的なPythonルールと組み合わせて使用する。

## 構造

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

## 非同期

- I/Oを行うエンドポイントには `async def` を使用する。
- 非同期エンドポイントからは非同期データベース・HTTPクライアントを使用する。
- 非同期ルートから `requests`、同期SQLAlchemyセッション、ブロッキングファイル/ネットワーク操作を呼び出さない。

## 依存性注入

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

## スキーマ

- レスポンスモデルにパスワード・パスワードハッシュ・アクセストークン・リフレッシュトークン・内部認証状態を含めない。
- アプリケーションデータを返すエンドポイントには `response_model` を使用する。
- Pydanticで表現できるルールは手動バリデーションではなくフィールド制約を使用する。

## セキュリティ

- CORSオリジンは環境ごとに設定する。
- ワイルドカードオリジンと認証情報付きCORSを組み合わせない。
- JWTの有効期限・発行者・オーディエンス・アルゴリズムを検証する。
- 認証や書き込みが多いエンドポイントにレート制限を設ける。
- ログから認証情報・Cookie・Authorization ヘッダー・トークンを除外する。

## テスト

- `Depends` で使用される正確な依存性をオーバーライドする。
- テスト後に `app.dependency_overrides` をクリアする。
- 非同期アプリケーションには非同期テストクライアントを優先する。

スキル: `fastapi-patterns` を参照。
