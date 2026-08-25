# 言語プロファイル: Bash Hook Test（`~/.claude/hooks/*.sh` 向け）

Claude Code の PreToolUse/Stop 等フックスクリプト（`hooks/*.sh`）とその隣接テスト（`hooks/*.test.sh`）を対象とする。
フレームワーク非依存の素朴なアサーション形式（`assert_exit`等のヘルパーを各テストファイル内に自前定義）を前提とする。

## テスト種別 → ランナー / パスパターン判定

| 対象パス（例） | テスト種別 | ランナー | テスト置き場（例） |
|----------------|-----------|----------|--------------------|
| `hooks/*.sh`（`*.test.sh` を除く） | unit | 隣接する `<同名>.test.sh` を `bash` で直接実行 | `hooks/<name>.test.sh` |

フックスクリプトは `mktemp -d` で作った使い捨て git リポジトリ内でフック本体に JSON 入力を `stdin` 経由で渡し、
終了コードで判定する（外部ネットワーク・実リポジトリへの副作用なし）。

## 実行コマンド

```bash
# 単一テストファイル（RED/GREEN の証拠。ファイル内の全ケースを毎回実行する——
# ケース単位の分離実行機構を持たないため、これが「対象テストのみ」の粒度）
bash "$HOME/.claude/hooks/<name>.test.sh"

# 全体（既存回帰の確認。hooks/ 配下の全 *.test.sh を実行）
for f in "$HOME"/.claude/hooks/*.test.sh; do bash "$f" || echo "FAILED: $f"; done

# カバレッジ
未計測（対象外。フックはケース網羅で担保する）
```

## 層別テストコマンド（CP-B の3層戦略）

```bash
# unit（業務ロジック・高速多数）→ 唯一の層。フックの分岐条件そのものが業務ロジック
bash "$HOME/.claude/hooks/<name>.test.sh"
# integration / e2e → 対象外（フックは単体で完結する純粋関数的スクリプトのため）
```

## CI ステージ（CP-E・CIプロバイダ既定 = GitHub Actions）

このリポジトリ（my-claude）はCIを運用しないため、CP-Eは対象外としてスキップする（plan文書にスキップ理由を記載）。

## Critical 証拠ルール（このランナーでの合格ログの形）

- **CP-C(RED)**: 対象ケースの行が `FAIL: <ラベル> (expected exit X, got Y)` として出力され、かつファイル全体の最終行が `SOME TESTS FAILED`（終了コード1）。
  無効例（FAIL扱い）: 該当ケースが実行されずスキップされた、またはシェル構文エラーで全体が実行不能になっただけの失敗（意図した分岐に到達していない）。
- **CP-C(GREEN)**: 全ケースの行が `PASS: <ラベル>` となり、ファイル全体の最終行が `ALL PASS`（終了コード0）。既存ケースに新規failedが無いこと。
- **CP-C(REFACTOR)**: テストファイル（`*.test.sh`）が不変、かつ再実行で全緑（`ALL PASS`）。

## カバレッジ閾値

- 対象外（ケース網羅性はCP-Bのシナリオ表とCP-Dのreview-testで担保する）。

## 参照委譲

深い作法は無し（本ファイルの記述で完結する規模のプロファイル）。
