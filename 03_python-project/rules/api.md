---
paths:
  - "src/**"
  - "docs/design/**"
  - "docs/spec.md"
---
# API設計規約

API エンドポイントの実装・仕様書作成時に参照する。

## HTTP メソッド

| メソッド | 用途 |
|---|---|
| GET | リソースの取得（冪等・副作用なし） |
| POST | リソースの作成、またはアクション実行 |
| PUT | リソースの完全更新（冪等） |
| PATCH | リソースの部分更新 |
| DELETE | リソースの削除（冪等） |

## エンドポイント命名

- リソース名は**複数形スネークケース**（例: `/api/v1/order_items`）
- 動詞はメソッドで表現し、パスに含めない（NG: `/api/v1/getOrders`）
- ネストは2階層以内（例: `/api/v1/orders/{id}/items`）
- **アクション型操作**（キャンセル・承認など CRUD に収まらない操作）は `POST /api/v1/orders/{id}/cancel` のように動詞サブリソースで表現する

## バージョニング

- URL パス方式（`/api/v1/`）を採用する
- 破壊的変更（フィールド削除・型変更・既存仕様変更）時はバージョンを上げる
- 後方互換の追加（フィールド追加）はバージョンを上げない

## レスポンス形式

成功（単一リソース）:
```json
{"data": {"id": 1, "name": "example"}}
```

成功（一覧）:
```json
{"data": [...], "meta": {"total": 100, "next_cursor": "xxx", "has_next": true}}
```

成功（作成・201 Created）: 作成したリソースをそのまま返す（`Location` ヘッダーは使わない）:
```json
{"data": {"id": 42, "name": "new item"}}
```

エラー（単一メッセージ）:
```json
{"error": {"code": "NOT_FOUND", "message": "指定されたリソースが存在しません。"}}
```

エラー（バリデーション、複数フィールド）:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "入力値に誤りがあります。",
    "details": [
      {"field": "email", "message": "メールアドレスの形式が不正です。"},
      {"field": "name", "message": "必須項目です。"}
    ]
  }
}
```

## ステータスコード

| コード | 用途 |
|---|---|
| 200 OK | 取得・更新成功 |
| 201 Created | 作成成功（レスポンスボディに作成リソースを含む） |
| 204 No Content | 削除成功（ボディなし） |
| 400 Bad Request | リクエスト構造の問題（JSON パース失敗・必須ヘッダー欠落） |
| 401 Unauthorized | 認証失敗（トークン未提供・無効・期限切れ） |
| 403 Forbidden | 認可失敗（認証済みだが権限なし） |
| 404 Not Found | リソースが存在しない |
| 409 Conflict | 重複リソースの作成（メールアドレス重複など） |
| 422 Unprocessable Entity | スキーマバリデーションエラー（FastAPI / Pydantic のデフォルト） |
| 429 Too Many Requests | レート制限超過 |
| 500 Internal Server Error | サーバー内部エラー |
| 503 Service Unavailable | 依存サービス（DB・外部 API）のダウン |

**400 と 422 の使い分け**: 400 はリクエスト自体が壊れている場合（JSON として解析不能など）、422 は構造は正しいが値が不正な場合（FastAPI が自動で返す）。

## 認証

- Bearer トークンを `Authorization: Bearer <token>` ヘッダーで渡す
- トークン形式（JWT / Opaque）・有効期限・更新方法は仕様書（`docs/spec.md`）に記載する
- 認証不要のエンドポイント（ヘルスチェック・パブリック API）は仕様書で明示する

## ページネーション

- カーソルベースを優先（`cursor` + `limit`）。データ量が増えてもパフォーマンスが安定する
- オフセット方式（`offset` + `limit`）は小規模・管理画面向けデータのみ許可する
- `cursor` は opaque string（内部実装を隠蔽。base64 エンコード等）とする
- `limit` のデフォルト値: 20、上限: 100。上限超過時は 422 を返す
- ソート順（`order_by`）が必要な場合は仕様書（`docs/spec.md`）で定義する
