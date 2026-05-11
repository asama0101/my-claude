---
paths:
  - "src/**"
  - "tests/**"
  - "pyproject.toml"
  - "*.toml"
---
# コーディング規約

コーディング・コミット・PR作成時に参照する。

## 基本ルール

- 型ヒント必須、`mypy --strict` を通すこと
- 設定ファイルのスキーマはバリデーションライブラリで定義（技術スタックに従う）
- TDD: 新規機能は失敗するテストを先に書く
- Linter/Formatter: ruff
- 依存管理: uv（requirements.txt の直接編集禁止）
- ディレクトリ: src/ レイアウト
- ログ: structlog（print 禁止）
- 例外を握り潰さない（ログ出力 or 再 raise）

## 命名規則

| 対象 | 規則 | 例 |
|---|---|---|
| 変数・関数・モジュール | `snake_case` | `user_id`, `get_order()` |
| クラス・型エイリアス | `PascalCase` | `OrderService`, `UserId` |
| 定数 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| 非公開（モジュール内限定） | 先頭 `_` | `_parse_response()` |

## docstring

公開 API（`_` なし）には Google スタイルで記述する。内部関数は省略可。
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
