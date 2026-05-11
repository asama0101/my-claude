---
name: python-coding-rules
description: Pythonコードの生成・編集・レビュー・プロジェクトセットアップ時に必ず参照するコーディングルール集。.pyや.ipynbファイルを新規作成・編集するとき、既存Pythonコードをレビューするとき、pyproject.toml/requirements.txtを触るとき、テストを書くときは、このスキルを必ず適用すること。型ヒント・docstring・importの順序・エラーハンドリング・仮想環境・ruff/mypyの設定など、すべてのPython作業において積極的に使用する。
---

# Python コーディングルール

Python 3.10 以降を前提とする。`match` 文、`X | Y` 形式の Union を使用可。

## このスキルの使い方

| 作業種別 | 適用方法 |
|---|---|
| **新規コード生成** | 以下のルールをすべて満たすコードを生成する |
| **既存コードの編集** | 変更箇所と影響範囲でルール違反があれば同時に修正する |
| **コードレビュー** | 違反箇所を「ルール番号 + 理由 + 修正例」の形式で列挙する |
| **プロジェクトセットアップ** | 7節（仮想環境）・8節（Lint設定）に従って pyproject.toml 等を生成する |

---

## 1. 基本原則

- 合理的な範囲で **KISS / DRY** に従う。早すぎる抽象化は避ける。
- 一回限りの操作にヘルパーを作らない。類似コードが 3 行程度で済むなら素直に書く。
- 発生し得ないシナリオへの防御的コーディングは追加しない（過剰な try/except、念のための None チェック等）。
- 既存テストを維持するための不合理なコード変更はしない。テストの修正を厭わない。
- 簡易的な調査・試験スクリプトは `scripts/` に配置する。本体コードや `tests/` に混入させない。
- ドキュメント（`docs/` 配下）はユーザーから明示的に依頼されたときのみ生成・更新する。

---

## 2. Imports

- すべての `import` はファイル最上部（モジュール docstring 直後）に置く。
- 順序は `stdlib → third-party → local` とし、各グループ間は **空白行 1 行** で区切る。
- 関数内・メソッド内・`if` 内の import は **禁止**（循環 import 解消の最終手段のみ、理由をコメント）。
- `from module import *` 禁止。
- 相対 import は同一パッケージ内のみ。それ以外は絶対 import。

---

## 3. 命名・スタイル

- 変数・関数・メソッド：`snake_case`
- クラス：`PascalCase`
- 定数：`UPPER_SNAKE_CASE`
- プライベート：先頭 `_`
- ruff / black のデフォルト（行長 88、スペース 4、ダブルクォート）に従う。

---

## 4. Type Hints（必須）

- **すべての関数・メソッドに型ヒントを付ける**（引数・戻り値の両方）。
- built-in ジェネリクス（`list[int]`, `dict[str, Any]`）を使う。`typing.List` 等は使わない。
- Union は `X | Y`、Optional は `X | None`。
- `Any` の濫用禁止。やむを得ない場合は理由をコメント。
- 構造化データには `dataclass` / `TypedDict` / Pydantic モデルを使い、生 `dict` を引き回さない。
- デフォルト引数に `list` / `dict` / `set` 等のミュータブルな値を直接渡さない。`None` を初期値にし、関数内で生成する：

```python
# NG
def append_item(item: int, items: list[int] = []) -> list[int]: ...

# OK
def append_item(item: int, items: list[int] | None = None) -> list[int]:
    items = items if items is not None else []
    items.append(item)
    return items
```

---

## 5. Docstring（必須）

- モジュール・クラス・関数・メソッドに **Google スタイル** の docstring を必須化。
- 含める項目：概要、Args、Returns、Raises（該当時）、Examples（公開関数・主要 API の場合）。1 行で済ませない。
- `Examples:` には `>>>` 形式の最小実行例を入れる（doctest としても機能させる）。
- 行コメントは **「なぜそうしているか」** を中心に書く。自明な処理にはコメント不要。

```python
def fetch_user(user_id: int) -> User:
    """ユーザー ID から User を取得する。

    キャッシュにヒットすればそれを返し、なければ DB を参照する。

    Args:
        user_id: 取得対象のユーザー ID（1 以上）。

    Returns:
        取得した User オブジェクト。

    Raises:
        UserNotFoundError: 指定 ID が存在しない場合。

    Examples:
        >>> user = fetch_user(1)
        >>> user.name
        'alice'
    """
```

---

## 6. エラーハンドリング / ログ

- 裸の `except:` / `except Exception:` でのもみ消しは **禁止**。具体的な例外型を指定する。
- 捕捉したら「回復」「ログ＋再 raise」「上位伝播」のいずれかを行う。再 raise は `raise NewError(...) from e`。
- **`print` でのデバッグ出力は禁止**。`logging.getLogger(__name__)` を使う。
- ログフォーマット：`%(asctime)s [%(levelname)s] %(name)s:%(funcName)s: %(message)s`
- 機密情報（パスワード、API キー、個人情報）はログに出さない。
- 例外メッセージには「何が」失敗したか、可能なら「なぜ」も含める。

---

## 7. 仮想環境 / パッケージ管理

- プロジェクトルート直下に **`venv/`** を作成し、ライブラリは必ずここにインストールする。
- ツールは **uv 推奨**、`venv` + `pip` も許容（プロジェクト内で統一）。
- `venv/` は `.gitignore` に追加。依存は `pyproject.toml` + `uv.lock` / `requirements.txt` で管理。
- システム Python に直接インストールするのは禁止。

```bash
# uv（推奨）
uv venv venv && source venv/bin/activate
uv sync
uv add <pkg>        # 本番依存
uv add --dev <pkg>  # 開発依存
```

---

## 8. Lint / Formatter / 型チェック

標準ツール：**ruff**（Linter + Formatter）、**mypy** または **pyright**（strict）。

コミット前に通すこと：

```bash
uv run ruff format .
uv run ruff check . --fix
uv run mypy .
uv run pytest --disable-warnings -q
```

`pyproject.toml` 設定例：

```toml
[tool.ruff]
line-height = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "RUF"]

[tool.mypy]
strict = true
python_version = "3.10"
```

---

## 9. コードレビュー観点

コードを生成・修正したあとは、以下の観点でセルフレビューを行う：

1. **可読性**：6 ヶ月後の自分・他人が読んで理解できるか。命名・構造・コメントは十分か。
2. **拡張性**：新要件に対して変更箇所が局所的に収まるか。責務が分離されているか。
3. **テスタビリティ**：単体テストが書きやすい構造か。副作用・依存が引数で注入されているか。
4. **セキュリティ**：入力値検証、エスケープ処理、機密情報の扱いが適切か。

---

## 10. プロジェクト構成

src レイアウトを採用：

```
project_root/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── venv/                # git 管理外
├── src/<package_name>/  # 本体コード
├── tests/
│   ├── support/         # テスト共通モジュール
│   └── test_*.py
├── scripts/             # 調査・試験用スクリプト
└── docs/                # 開発ドキュメント（明示的依頼時のみ）
```

---

## 11. Tests

- pytest を使用（`unittest` ベースは新規作成しない）。
- 正常系・異常系・境界ケースを網羅。
- ファイル名 `test_<対象>.py`、関数名 `test_<観点>`。
- **2 ファイル以上で使う共通処理は `tests/support/` 配下に置く**。
- フィクスチャは `conftest.py` または `tests/support/` で定義し、スコープを適切に設定。

```bash
uv run pytest --disable-warnings -q
uv run pytest --disable-warnings -q --cov=src --cov-report=term-missing
```

---

## 12. その他のコーディング方針

- 関数は単一責任。長大化したら分割する（目安：50 行以内）。
- グローバル状態に依存しない。依存は引数で受け取る。
- マジックナンバー・マジックストリングは定数化または `Enum` 化する。
- 文字列フォーマットは f-string、パス操作は `pathlib.Path`、ファイル I/O は `with` を使う。
- 並行処理は I/O バウンドなら `asyncio` / `ThreadPoolExecutor`、CPU バウンドなら `multiprocessing` / `ProcessPoolExecutor`。
- 設定値は環境変数 + `pydantic-settings` 等で管理し、ハードコードを避ける。

---

## 13. コマンド実行（bash）

- 出力が長くなりうるコマンドは `head -n N` / `tail -n N` で制限する。
- ファイル検索は `rg`（ripgrep）を優先：`rg "pattern" src/ --type py`
- 破壊的操作（`rm -rf`, `git reset --hard` 等）は実行前に対象を必ず確認する。
