# 言語プロファイル: Python / pytest

tdd-gates のゲートを Python プロジェクトで駆動するための**ゲート用グルー**（薄い層）。
fixture・AAA・parametrize・非同期・モック等の**深い pytest 作法は `~/.claude/agents/references/python-testing.md` を Read**（重複させない）。

## テスト種別 → ランナー / パスパターン判定

対象ファイルのパスから書くべきテスト種別を判定し、**最後にユーザーへ確認**する。

| 対象パス（例） | テスト種別 | ランナー | テスト置き場（例） |
|----------------|-----------|----------|--------------------|
| `src/**/*.py`（lib/utils/domain） | unit | pytest | `tests/unit/test_*.py` |
| `**/api/**`, `**/routers/**`, `**/endpoints/**` | integration (API) | pytest ＋ httpx/pytest-asyncio | `tests/integration/test_*.py` |
| ブラウザ UI を伴うフロー | e2e | **Playwright(-python)** | `tests/e2e/test_*.py` |

- e2e（ブラウザ）判定、またはテンプレート/ルーティング/ビュー層に変更がある場合は Gate7(UI/UX) を有効化する（unit 申告でも回避不可。条件の正典は `gates.md` Gate7）。
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

## 層別テストコマンド（Gate2 の3層戦略 / テスト3層戦略）

pytest マーカーで層を分離する（`pyproject.toml`/`pytest.ini` に `markers` を登録）。

```bash
pytest -m unit -q             # unit（業務ロジック・高速多数）
pytest -m integration -q      # integration（機能品質・主軸）
pytest tests/e2e -q           # e2e（最後の砦・最小限）
```

## CI ステージ（Gate9・GitHub Actions 既定）

Gate9 が CI ワークフローで被覆すべき必須ステージと、このプロファイルでの具体コマンド。CI プロバイダを変える場合はここを差し替える（グローバル skill 側は抽象ステージ名のみ保持）。

| ステージ | コマンド（Python 既定） |
|---------|------------------------|
| lint | `ruff check .` |
| typecheck | `mypy src` |
| build | `python -m build`（配布物がある場合。無ければ import スモークで代替） |
| unit test | `pytest -m unit -q` |
| integration test | `pytest -m integration -q` |
| 主要E2E | `pytest tests/e2e -q`（重要導線に絞る） |
| preview デプロイ（任意） | プロジェクト固有・既定 off |

## Critical 証拠ルール（このプロファイルでの「合格ログ」の形）

- **Gate4(RED)**: 出力に `FAILED` が含まれ、対象テストが 1 件以上 `failed`、かつトレースバックの `E` 行が**対象 assert の `AssertionError`** を示す。assert 到達前の実行時エラー（`TypeError`/`AttributeError` 等）による `failed` は未実装シンボル起因の初回 RED としてのみ有効——GREEN 前に Generator がスタブを置いた二段階 RED で対象 assert の失敗を確認する。
  - 無効例（0 点＝FAIL）: ログなしの「多分落ちる」／`collected 0 items`（テスト未収集）／`ERROR`（import 失敗などで RED になっていない）。
- **Gate5(GREEN)**: 対象テストが `passed`、かつ `pytest -q` 全体で**ベースライン比の新規 `failed` が 0**（台帳のベースライン記録に無い failed が 0。ベースラインが全緑なら従来どおり `failed` 0）。
- **Gate6(REFACTOR)**: `git diff` にテストファイルの変更が無く（＝振る舞い不変）、`pytest -q` が全緑。

## カバレッジ閾値

- 行・ブランチともに **80% 以上**を目標。下回る場合 Gate8 の test-quality 次元で減点。

## 参照委譲

- 深い pytest 作法（fixture の初期化/クリーンアップ必須・AAA・命名・parametrize・マーカー・モック/パッチ・非同期 httpx・例外・設定）: `~/.claude/agents/references/python-testing.md` を Read すること。
- Gate6(REFACTOR) の整理では `~/.claude/agents/references/python-style.md`（実装スタイル・設計パターン）を Read すること（Gate5(GREEN) は最小実装原則を優先し、参照しない）。
