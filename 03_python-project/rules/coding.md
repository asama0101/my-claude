---
paths:
  - "src/**"
  - "tests/**"
  - "pyproject.toml"
---
# コーディング規約

コーディング・PR作成時に参照する。

## 基本ルール

- 型ヒント必須、`mypy --strict` を通すこと
- 設定値のスキーマは `pydantic-settings` で定義する（環境変数の型安全な読み込み）
- Linter/Formatter: ruff
- 依存管理: uv（`requirements.txt` の直接編集禁止）
- ディレクトリ: `src/` レイアウト
- ログ: structlog（`print` 禁止）
- 例外を握り潰さない（ログ出力 or 再 raise）

## 型ヒント

- Python 3.10+ の記法を使う: `X | None`（`Optional[X]` は使わない）、`list[str]`（`List[str]` は使わない）
- `Any` は原則禁止。型スタブのないサードパーティライブラリで回避不能な場合のみ、理由をコメントで明記して使用する
- `TypeAlias`・`TypeVar`・`Protocol` を活用して曖昧な `dict` / `Any` を避ける

## 命名規則

| 対象 | 規則 | 例 |
|---|---|---|
| 変数・関数・モジュール | `snake_case` | `user_id`, `get_order()` |
| クラス・型エイリアス | `PascalCase` | `OrderService`, `UserId` |
| 定数 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| 非公開（モジュール内限定） | 先頭 `_` | `_parse_response()` |
| テストファイル | `test_*.py` | `test_order_service.py` |
| テストクラス | `Test*` | `TestOrderService` |
| テスト関数 | `test_*` | `test_create_order_returns_201` |

## 関数・クラスの設計

- 1関数1つの責務。複数の責務が混在していると感じたら分割する
- 関数の目安: 30行以内。超える場合は分割を検討する
- ネストの深さ: 3段階以内。早期リターンで深いネストを避ける
- カスタム例外は `src/<package>/core/exceptions.py` に定義し、基底クラス（`AppError`）を継承する
- `except Exception` はエントリーポイント（APIハンドラ）のみ許容。それ以外は具体的な例外型を指定する

## async/await

- FastAPI のエンドポイントは原則 `async def` で定義する
- DB・HTTP などの I/O 操作は非同期ライブラリ（`asyncpg`, `httpx` 等）を使い `await` する
- `async def` 内でブロッキング処理（同期 I/O・重い CPU 処理）を直接呼ばない。必要な場合は `asyncio.to_thread()` を使う
- `asyncio.run()` はエントリーポイント（`main.py`）以外で呼ばない

## import

- 絶対インポートのみ使用する（相対インポート `from . import` は禁止）
- `src/` レイアウトではパッケージ名を起点にする（例: `from myapp.services.order import OrderService`）

## ログ

- モジュールの先頭で `logger = structlog.get_logger()` を宣言する
- キー名は英語、メッセージは日本語で書く
- 機密情報（認証トークン・パスワード）をログに含めない（`security.md` 参照）

```python
logger = structlog.get_logger()

logger.info("注文を処理しました。", order_id=order_id, user_id=user_id)
logger.error("外部API呼び出しに失敗しました。", url=url, status_code=status)
```

## docstring

公開 API（`_` なし）には Google スタイルで記述する。内部関数・クラスは省略可。
docstring の文は日本語で書く。

```python
def process(value: int) -> str:
    """値を文字列に変換する。

    Args:
        value: 変換する整数値。

    Returns:
        変換後の文字列。

    Raises:
        ValueError: value が負の場合。
    """
```
