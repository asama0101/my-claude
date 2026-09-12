# 言語プロファイル: Bash / bats-core

fx2provリポジトリの`scripts/*.sh`運用スクリプトを対象とする。`tests/bats/test_helper.bash`が確立した「PATHにスタブコマンドを差し込み、副作用をスクリプト外に一切出さず検証する」流儀に従う。ゲート骨格は言語非依存のため変更しない。

## テスト種別 → ランナー / パスパターン判定

| 対象パス（例） | テスト種別 | ランナー | テスト置き場（例） |
|----------------|-----------|----------|--------------------|
| `scripts/*.sh` | integration | `bats` | `tests/bats/<script_name>.bats` |

bashスクリプトは外部コマンド（`fx2prov`本体・SSH等）とファイルシステムに依存するプロセス単位の振る舞いが本質であり、関数単位の孤立した「unit」層は設けない。`tests/bats/fixtures/`にスタブ実行体を置き`PATH`経由で差し込むことで、外部依存を隔離しつつプロセスごとテストする（`tests/bats/test_helper.bash:17`）。e2e層も設けない（本番相当のFX2実機やSFTP/SSH実サーバへの接続はCIで行わない）。

## 実行コマンド

```bash
# 単一テスト（RED/GREEN の証拠）
bats tests/bats/<script_name>.bats

# RED 再現（tdd-evaluator が隔離 worktree で実行する）
git worktree add <scratchpad>/red-<slug> <RED_SHA>
bats <scratchpad>/red-<slug>/tests/bats/<script_name>.bats
git worktree remove <scratchpad>/red-<slug>

# 全体（既存回帰の確認。起動時のベースライン取得と CP-D 手順0 で各1回実行する。CP-C では実行しない）
bats tests/bats/

# カバレッジ
# 本プロファイルではカバレッジ計測ツールを導入しない（bashの標準的カバレッジ計測手段が無く、CIにも未導入のため）。
```

## 層別テストコマンド（CP-B の3層戦略）

```bash
# unit（業務ロジック・高速多数）
# 該当なし（bashスクリプトはプロセス単位のintegrationのみ）
# integration（機能品質・主軸）
bats tests/bats/<script_name>.bats
# e2e（最後の砦・最小限）
# 該当なし（実機・実サーバ接続はCI対象外）
```

## CI ステージ（CP-E・CI プロバイダ既定 = GitHub Actions）

`.github/workflows/ci.yml:38-41`に準拠。

| ステージ | コマンド |
|---------|---------|
| lint | 未導入（shellcheck等は本リポジトリに存在しない。新規導入は本プロファイルのスコープ外） |
| typecheck | 該当なし（bashに静的型検査なし） |
| build | 該当なし（コンパイル・ビルド工程なし） |
| unit test | 該当なし |
| integration test | `bats tests/bats/`（CI: `.github/workflows/ci.yml:39-40`で`bats-core`をaptインストール後に実行） |
| 主要E2E | 該当なし |
| preview デプロイ（任意） | 対象外・既定off |

## Critical 証拠ルール（このランナーでの合格ログの形）

- **CP-C(RED)**: 失敗を示す出力パターン = `not ok <N> <test名>`（bats標準のTAP形式失敗行）。無効例（FAIL扱い）= テストファイル自体の構文エラーで全件が実行前に落ちる（`bats: command not found`等の環境起因エラーも無効）。
- **CP-C(GREEN)**: 通過を示す出力 = `ok <N> <test名>`が対象テスト全件で出力され、`not ok`が0件。フルスイートは実行しない（全体の新規失敗0はCP-D手順0で確認する）。
- **CP-C(REFACTOR)**: テスト不変（diffにテスト変更なし）かつ対象テストが緑。

## カバレッジ閾値

- 目標: 定めない（本リポジトリのbashテストにカバレッジ計測ツールが存在しないため、計測不能な数値目標を設定しない）。

## 参照委譲

深い作法（スタブの書き方・`FX2PROV_HOME`隔離パターン等）は`tests/bats/test_helper.bash`・`tests/bats/ha_guard.bats`の既存実装を参照する（専用ドキュメントは無く、既存コードが正典）。
