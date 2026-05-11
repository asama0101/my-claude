---
paths:
  - "src/**"
---
# セキュリティ規約

src/ 配下のコード作成・レビュー時に参照する。

## 入力バリデーション

- ユーザー入力・外部入力は必ずバリデーションライブラリ（Pydantic 等）でスキーマ検証する
- 手動の `if` チェックのみに頼らない。スキーマ定義を一次情報にする

## コマンドインジェクション対策

- `subprocess` 呼び出しは `shell=False`（デフォルト）で引数をリスト形式で渡す
- `shell=True` は禁止。外部入力を含む文字列をシェル経由で実行しない

```python
# NG
subprocess.run(f"convert {user_input}", shell=True)

# OK
subprocess.run(["convert", user_input])
```

## 認可（IDOR 対策）

- リソースへのアクセス時は必ず所有者確認を行う。ID が存在するだけではアクセスを許可しない
- 「認証済み = 全リソースにアクセス可」ではない。`order.owner_id == current_user.id` のような確認を必ず実装する
- 確認漏れを防ぐため、リソース取得ヘルパー関数に所有者チェックを組み込む

## シークレット管理

- 認証情報・API キー・パスワードをコードに直書き禁止
- **開発環境**: 環境変数を `.env` 経由で注入する。`.env` は `.gitignore` で除外する（`rules/github.md` の必須エントリ参照）
- **本番環境**: `.env` ファイルを使わず、Secrets Manager（AWS Secrets Manager / GCP Secret Manager 等）から注入する
- 定期ローテーション: シークレットの更新周期・担当者を仕様書（`docs/design/security.html`）に定義する
- ログ・例外メッセージに認証情報・個人情報を平文出力しない。出力前にマスク処理する

## SQL インジェクション対策

- SQL は ORM またはパラメータ化クエリのみ使用する
- f 文字列・`.format()` で SQL を文字列結合することを禁止する
- パフォーマンス上 Raw SQL が必要な場合は SQLAlchemy の `text()` + バインドパラメータを使用する

```python
# NG
db.execute(f"SELECT * FROM orders WHERE id = {order_id}")

# OK（ORM）
db.query(Order).filter(Order.id == order_id).first()

# OK（Raw SQL が必要な場合）
from sqlalchemy import text
db.execute(text("SELECT * FROM orders WHERE id = :id"), {"id": order_id})
```

## CORS 設定

- 許可オリジンは明示的に指定する。ワイルドカード（`*`）は禁止
- 許可するオリジン・メソッド・ヘッダーは仕様書（`docs/design/security.html`）に定義する

```python
# NG
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# OK
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
```

## エラーレスポンスの情報漏洩防止

- HTTP レスポンスにスタックトレース・内部パス・DB スキーマを含めない
- 500 エラーはログに詳細を記録し、レスポンスには汎用メッセージのみ返す
- `coding.md` の「例外を握り潰さない」ルールと組み合わせる: **ログには出す、レスポンスには含めない**

```python
# OK
try:
    result = process()
except Exception as e:
    logger.error("処理に失敗しました。", error=str(e))  # ログに詳細
    raise HTTPException(status_code=500, detail="内部エラーが発生しました。")  # レスポンスは汎用
```

## ファイルパス操作

- 外部入力に基づくファイルパス操作は `pathlib.Path.resolve()` でサニタイズしてからアクセスする
- 許可ベースディレクトリ内に収まることを確認し、ディレクトリトラバーサル（`../../` 等）を防ぐ

## 依存パッケージ

- `uv.lock` を git 管理する。ロックファイルなしでは依存バージョンが固定されず、脆弱性が混入するリスクがある
- 脆弱性スキャンを CI に組み込む（例: `uv run pip-audit`）
- 不要なパッケージを追加しない。追加する場合は目的を PR 本文に明記する
