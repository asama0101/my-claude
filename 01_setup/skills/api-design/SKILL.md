---
name: api-design
description: REST API 設計パターン：リソース命名、ステータスコード、ページネーション、フィルタリング、エラーレスポンス、バージョニング、レート制限。
origin: ECC
---

# API 設計パターン

一貫性があり、開発者に優しい REST API を設計するための規約とベストプラクティス。

## 使用場面

- 新規 API エンドポイントを設計するとき
- 既存の API 契約をレビューするとき
- ページネーション、フィルタリング、ソートを追加するとき
- API のエラーハンドリングを実装するとき
- API バージョニング戦略を計画するとき
- 公開 API やパートナー向け API を構築するとき

## リソース設計

### URL 構造

```
# リソースは名詞・複数形・小文字・kebab-case
GET    /api/v1/users
GET    /api/v1/users/:id
POST   /api/v1/users
PUT    /api/v1/users/:id
PATCH  /api/v1/users/:id
DELETE /api/v1/users/:id

# 関係性にはサブリソースを使用
GET    /api/v1/users/:id/orders
POST   /api/v1/users/:id/orders

# CRUD にマッピングできないアクション（動詞は控えめに）
POST   /api/v1/orders/:id/cancel
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
```

### 命名規則

```
# GOOD
/api/v1/team-members          # 複数単語リソースは kebab-case
/api/v1/orders?status=active  # フィルタリングはクエリパラメーター
/api/v1/users/123/orders      # 所有関係にはネストリソース

# BAD
/api/v1/getUsers              # URL に動詞
/api/v1/user                  # 単数形（複数形を使うこと）
/api/v1/team_members          # URL に snake_case
/api/v1/users/123/getOrders   # ネストリソースに動詞
```

## HTTP メソッドとステータスコード

### メソッドのセマンティクス

| メソッド | 冪等性 | 安全性 | 用途 |
|---------|--------|--------|------|
| GET | あり | あり | リソースの取得 |
| POST | なし | なし | リソースの作成、アクションのトリガー |
| PUT | あり | なし | リソースの完全置換 |
| PATCH | なし* | なし | リソースの部分更新 |
| DELETE | あり | なし | リソースの削除 |

*適切に実装すれば PATCH も冪等にできる

### ステータスコードリファレンス

```
# 成功
200 OK                    — GET, PUT, PATCH（レスポンスボディあり）
201 Created               — POST（Location ヘッダーを含める）
204 No Content            — DELETE, PUT（レスポンスボディなし）

# クライアントエラー
400 Bad Request           — バリデーション失敗、不正な JSON
401 Unauthorized          — 認証情報が欠如または無効
403 Forbidden             — 認証済みだが権限なし
404 Not Found             — リソースが存在しない
409 Conflict              — 重複エントリー、状態の競合
422 Unprocessable Entity  — 意味論的に無効（JSON は正しいがデータが不正）
429 Too Many Requests     — レート制限超過

# サーバーエラー
500 Internal Server Error — 予期しない障害（詳細を露出しないこと）
502 Bad Gateway           — 上流サービスの障害
503 Service Unavailable   — 一時的な過負荷、Retry-After を含める
```

### よくある間違い

```
# BAD: 全てに 200 を返す
{ "status": 200, "success": false, "error": "Not found" }

# GOOD: HTTP ステータスコードを意味的に使用する
HTTP/1.1 404 Not Found
{ "error": { "code": "not_found", "message": "User not found" } }

# BAD: バリデーションエラーに 500 を返す
# GOOD: フィールドレベルの詳細付きで 400 または 422 を返す

# BAD: 作成したリソースに 200 を返す
# GOOD: Location ヘッダー付きで 201 を返す
HTTP/1.1 201 Created
Location: /api/v1/users/abc-123
```

## レスポンス形式

### 成功レスポンス

```json
{
  "data": {
    "id": "abc-123",
    "email": "alice@example.com",
    "name": "Alice",
    "created_at": "2025-01-15T10:30:00Z"
  }
}
```

### コレクションレスポンス（ページネーション付き）

```json
{
  "data": [
    { "id": "abc-123", "name": "Alice" },
    { "id": "def-456", "name": "Bob" }
  ],
  "meta": {
    "total": 142,
    "page": 1,
    "per_page": 20,
    "total_pages": 8
  },
  "links": {
    "self": "/api/v1/users?page=1&per_page=20",
    "next": "/api/v1/users?page=2&per_page=20",
    "last": "/api/v1/users?page=8&per_page=20"
  }
}
```

### エラーレスポンス

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Must be a valid email address",
        "code": "invalid_format"
      },
      {
        "field": "age",
        "message": "Must be between 0 and 150",
        "code": "out_of_range"
      }
    ]
  }
}
```

### レスポンスエンベロープの選択肢

```typescript
// Option A: data ラッパー付きエンベロープ（公開 API に推奨）
interface ApiResponse<T> {
  data: T;
  meta?: PaginationMeta;
  links?: PaginationLinks;
}

interface ApiError {
  error: {
    code: string;
    message: string;
    details?: FieldError[];
  };
}

// Option B: フラットなレスポンス（シンプル、内部 API に多い）
// 成功時: リソースをそのまま返す
// エラー時: error オブジェクトを返す
// HTTP ステータスコードで区別する
```

## ページネーション

### オフセットベース（シンプル）

```
GET /api/v1/users?page=2&per_page=20

# 実装
SELECT * FROM users
ORDER BY created_at DESC
LIMIT 20 OFFSET 20;
```

**メリット:** 実装が簡単、「N ページ目へジャンプ」をサポート
**デメリット:** 大きなオフセットで遅い（OFFSET 100000）、並行挿入で結果がずれる

### カーソルベース（スケーラブル）

```
GET /api/v1/users?cursor=eyJpZCI6MTIzfQ&limit=20

# 実装
SELECT * FROM users
WHERE id > :cursor_id
ORDER BY id ASC
LIMIT 21;  -- 次ページの有無判定のため1件多く取得
```

```json
{
  "data": [...],
  "meta": {
    "has_next": true,
    "next_cursor": "eyJpZCI6MTQzfQ"
  }
}
```

**メリット:** 位置によらず一定のパフォーマンス、並行挿入でも安定
**デメリット:** 任意のページへジャンプ不可、カーソルが不透明

### 使い分け

| ユースケース | ページネーション種別 |
|------------|----------------|
| 管理ダッシュボード、小規模データ（<1万件） | オフセット |
| 無限スクロール、フィード、大規模データ | カーソル |
| 公開 API | カーソル（デフォルト）＋オフセット（オプション） |
| 検索結果 | オフセット（ユーザーがページ番号を期待する） |

## フィルタリング・ソート・検索

### フィルタリング

```
# 単純な等値
GET /api/v1/orders?status=active&customer_id=abc-123

# 比較演算子（ブラケット記法を使用）
GET /api/v1/products?price[gte]=10&price[lte]=100
GET /api/v1/orders?created_at[after]=2025-01-01

# 複数値（カンマ区切り）
GET /api/v1/products?category=electronics,clothing

# ネストフィールド（ドット記法）
GET /api/v1/orders?customer.country=US
```

### ソート

```
# 単一フィールド（- プレフィックスで降順）
GET /api/v1/products?sort=-created_at

# 複数フィールド（カンマ区切り）
GET /api/v1/products?sort=-featured,price,-created_at
```

### 全文検索

```
# 検索クエリパラメーター
GET /api/v1/products?q=wireless+headphones

# フィールド指定検索
GET /api/v1/users?email=alice
```

### スパースフィールドセット

```
# 指定フィールドのみ返す（ペイロード削減）
GET /api/v1/users?fields=id,name,email
GET /api/v1/orders?fields=id,total,status&include=customer.name
```

## 認証と認可

### トークンベース認証

```
# Authorization ヘッダーに Bearer トークン
GET /api/v1/users
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

# API キー（サーバー間通信用）
GET /api/v1/data
X-API-Key: sk_live_abc123
```

### 認可パターン

```typescript
// リソースレベル: 所有権チェック
app.get("/api/v1/orders/:id", async (req, res) => {
  const order = await Order.findById(req.params.id);
  if (!order) return res.status(404).json({ error: { code: "not_found" } });
  if (order.userId !== req.user.id) return res.status(403).json({ error: { code: "forbidden" } });
  return res.json({ data: order });
});

// ロールベース: 権限チェック
app.delete("/api/v1/users/:id", requireRole("admin"), async (req, res) => {
  await User.delete(req.params.id);
  return res.status(204).send();
});
```

## レート制限

### ヘッダー

```
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000

# 超過時
HTTP/1.1 429 Too Many Requests
Retry-After: 60
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Try again in 60 seconds."
  }
}
```

### レート制限ティア

| ティア | 制限 | ウィンドウ | ユースケース |
|-------|------|-----------|------------|
| 匿名 | 30/分 | IP ごと | 公開エンドポイント |
| 認証済み | 100/分 | ユーザーごと | 標準 API アクセス |
| プレミアム | 1000/分 | API キーごと | 有料 API プラン |
| 内部 | 10000/分 | サービスごと | サービス間通信 |

## バージョニング

### URL パスバージョニング（推奨）

```
/api/v1/users
/api/v2/users
```

**メリット:** 明示的、ルーティングが簡単、キャッシュ可能
**デメリット:** バージョン間で URL が変わる

### ヘッダーバージョニング

```
GET /api/users
Accept: application/vnd.myapp.v2+json
```

**メリット:** URL がクリーン
**デメリット:** テストしにくい、忘れやすい

### バージョニング戦略

```
1. /api/v1/ から始める — 必要になるまでバージョンを切らない
2. 有効なバージョンは最大2つ（現行 + 前バージョン）を保持する
3. 廃止スケジュール:
   - 廃止を告知する（公開 API は6か月前に）
   - Sunset ヘッダーを追加: Sunset: Sat, 01 Jan 2026 00:00:00 GMT
   - Sunset 日以降は 410 Gone を返す
4. 後方互換の変更は新バージョン不要:
   - レスポンスへの新フィールド追加
   - 新しいオプションクエリパラメーターの追加
   - 新エンドポイントの追加
5. 破壊的変更は新バージョンが必要:
   - フィールドの削除または名前変更
   - フィールドの型変更
   - URL 構造の変更
   - 認証方式の変更
```

## API 設計チェックリスト

新規エンドポイントをリリースする前に確認:

- [ ] リソース URL が命名規則に従っている（複数形、kebab-case、動詞なし）
- [ ] 正しい HTTP メソッドを使用している（読み取りは GET、作成は POST など）
- [ ] 適切なステータスコードを返している（全てに 200 を返していない）
- [ ] スキーマでバリデーションしている（Zod、Pydantic、Bean Validation など）
- [ ] エラーレスポンスがコードとメッセージを含む標準形式に従っている
- [ ] リスト系エンドポイントにページネーションを実装している（カーソルまたはオフセット）
- [ ] 認証が必要（または明示的に公開とマークされている）
- [ ] 認可チェックを行っている（ユーザーは自分のリソースのみアクセス可）
- [ ] レート制限を設定している
- [ ] レスポンスが内部詳細を漏らしていない（スタックトレース、SQL エラーなど）
- [ ] 既存エンドポイントと一貫した命名（camelCase か snake_case か）
- [ ] ドキュメント化されている（OpenAPI/Swagger spec を更新済み）

## 関連スキル

- Skill: `fastapi-patterns`（Python/FastAPI での実装パターン）
- Skill: `python-testing`（API エンドポイントのテスト）
