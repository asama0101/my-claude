# 言語プロファイル: Python / pytest

tdd-gates のゲートを Python プロジェクトで駆動するための**ゲート用グルー**（薄い層）。
fixture・AAA・parametrize・非同期・モック等の**深い pytest 作法は `~/.claude/agents/references/pytest-patterns.md` を Read**（重複させない）。

## テスト種別 → ランナー / パスパターン判定

対象ファイルのパスから書くべきテスト種別を判定し、**最後にユーザーへ確認**する。

| 対象パス（例） | テスト種別 | ランナー | テスト置き場（例） |
|----------------|-----------|----------|--------------------|
| `src/**/*.py`（lib/utils/domain） | unit | pytest | `tests/unit/test_*.py` |
| `**/api/**`, `**/routers/**`, `**/endpoints/**` | integration (API) | pytest ＋ httpx/pytest-asyncio | `tests/integration/test_*.py` |
| ブラウザ UI を伴うフロー | e2e | **Playwright(-python)** | `tests/e2e/test_*.py` |

- e2e（ブラウザ）と判定された場合のみ Gate7(UI/UX) を有効化する。
- プロジェクト構成が異なる場合、この対応表を各 repo の `CLAUDE.md`／`pytest.ini`／`pyproject.toml` に合わせて読み替える。

## 実行コマンド

```bash
# 単一テスト（RED/GREEN の証拠取得に使う）
pytest <path>::<test> -q

# 全体（既存回帰の確認・Gate5/6 の緑維持証拠）
pytest -q

# カバレッジ（目標 80% 以上・行/ブランチ）
pytest --cov=src --cov-report=term-missing
```

Playwright(-python)（e2e / Gate7）:
```bash
pytest tests/e2e -q            # playwright pytest plugin 前提
```

## Critical 証拠ルール（このプロファイルでの「合格ログ」の形）

- **Gate4(RED)**: 出力に `FAILED` もしくは `E  <AssertionError...>` が含まれ、対象テストが 1 件以上 `failed`。
  - 無効例（0 点＝FAIL）: ログなしの「多分落ちる」／`collected 0 items`（テスト未収集）／`ERROR`（import 失敗などで RED になっていない）。
- **Gate5(GREEN)**: 対象テストが `passed`、かつ `pytest -q` 全体で `failed` が 0（既存回帰なし）。
- **Gate6(REFACTOR)**: `git diff` にテストファイルの変更が無く（＝振る舞い不変）、`pytest -q` が全緑。

## カバレッジ閾値

- 行・ブランチともに **80% 以上**を目標。下回る場合 Gate8 の test-quality 次元で減点。

## 参照委譲

- 深い pytest 作法（fixture の初期化/クリーンアップ必須・AAA・命名・parametrize・マーカー・モック/パッチ・非同期 httpx・例外・設定）: `~/.claude/agents/references/pytest-patterns.md` を Read すること。
- Gate6(REFACTOR) の整理では `~/.claude/agents/references/python-patterns.md`（実装スタイル・設計パターン）を Read すること（Gate5(GREEN) は最小実装原則を優先し、参照しない）。
