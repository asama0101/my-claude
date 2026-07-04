# 言語プロファイル: Python / unittest（標準ライブラリのみ）

tdd-gates のゲートを **依存ゼロ（stdlib-only）Python プロジェクト**で駆動するためのゲート用グルー。
pytest が導入できない/しない方針のリポジトリ（例: sshtool）で使う。深い Python 実装作法は `~/.claude/agents/references/python.md` へ委譲する。

## テスト種別 → ランナー / パスパターン判定

| 対象パス（例） | テスト種別 | ランナー | テスト置き場（例） |
|----------------|-----------|----------|--------------------|
| `<pkg>/**/*.py`（ライブラリ/CLI 本体） | unit | unittest | `tests/test_*.py`（フラット配置） |
| ローカルサーバ/サブプロセスを介す検証（`http.server`・fake subprocess 等） | integration | unittest（同上のフラット配置に同居） | `tests/test_*.py` |
| 実機・実網への接続テスト | e2e | リポジトリ規約に従う（例: `e2e/`、git 管理外） | ゲート対象外（環境依存のため） |

- ブラウザ UI が無い CLI リポジトリでは Gate7(UI/UX) は常にスキップ（台帳に明記）。
- プロジェクト構成が異なる場合はリポジトリの CLAUDE.md / README のテスト節を優先する。

## 実行コマンド

```bash
# 単一テスト（RED/GREEN の証拠取得に使う）
python3 -m unittest tests.test_<module> -v
python3 -m unittest tests.test_<module>.<Class>.<test_method> -v

# 全体（既存回帰の確認・Gate5/6 の緑維持証拠）
python3 -m unittest discover -s tests -v

# カバレッジ
# 計測ツールなし（依存ゼロ方針のため coverage.py を導入しない）。
# Gate8 の test-quality 次元で test-reviewer が定性評価（シナリオ網羅・境界値・エラーパス）で代替する。
```

## Critical 証拠ルール（このランナーでの合格ログの形）

- **Gate4(RED)**: 出力末尾が `FAILED (failures=N)`（N≥1）で、`FAIL:` 行が対象テストを指し、トレースバックが対象 assert 行の `AssertionError` を示す。
  - **許容される例外（初回 RED のみ）**: 新規モジュール/新規シンボルが未実装であることに起因する `ERROR`（`ModuleNotFoundError` / `ImportError` / `AttributeError` / `TypeError: unexpected keyword argument`）で `FAILED (errors=N)` となるケースは、TDD の自然な初回 RED として**有効**。ただし GREEN に進む前に**二段階 RED を必須**とする: Generator がスタブ（署名だけの雑最小実装）を置いて再実行し、対象 assert の失敗（`FAIL:` 行＋`AssertionError`）で落ちることを evaluator が確認し台帳に記録する。ERROR のまま GREEN に進んではならない。
  - 無効例（0 点＝FAIL 扱い）: ログなしの「多分落ちる」／`Ran 0 tests`（未収集）／対象と無関係な収集時クラッシュ。
- **Gate5(GREEN)**: 単一テストの出力が `OK`、かつ `python3 -m unittest discover -s tests -v` の末尾が `OK`（`FAILED` なし＝既存回帰なし）。
- **Gate6(REFACTOR)**: `git diff` にテストファイルの変更が無く（＝振る舞い不変）、discover 全体が `OK`。

## カバレッジ閾値

- 数値目標なし（計測ツール非導入）。代替として Gate8 で test-reviewer が「主要分岐・エラーパスにテストが対応しているか」を所見として明示すること。

## 参照委譲

- 実装スタイル・設計パターン（Gate6 で参照）: `~/.claude/agents/references/python.md`
- unittest の作法はこのプロファイルの範囲では標準（`unittest.TestCase`・`setUp`/`addCleanup`・`assertRaises`・`mock.patch.object`）に従い、リポジトリ既存テストの慣行（fixture mixin・tmpdir・注入点）を最優先する。
