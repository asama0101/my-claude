# 言語プロファイル: Bash / bats-core

外部スケジューラ(cron)から呼ばれる単体のBashスクリプト（例: `scripts/fx2prov-ha-guard.sh`）向け。
スクリプトは単一エントリポイントで、外部コマンド(Pacemakerステータスコマンド相当・`fx2prov` CLI)を
モック/スタブに差し替えて[bats-core](https://github.com/bats-core/bats-core)から起動する構成を前提とする。
関数単位のユニットテストは行わず、スクリプト全体を1プロセスとして実行する **integration 層のみ** を持つ
（`browser-manual-e2e.md`が「全てe2e」とするのと同様に、本プロファイルは「全てintegration」として扱う）。

## テスト種別 → ランナー / パスパターン判定

| 対象パス（例） | テスト種別 | ランナー | テスト置き場 |
|----------------|-----------|----------|--------------------|
| `scripts/*.sh` | integration | bats-core | `tests/bats/<script名>.bats` |

unit層・e2e層は本プロファイルの対象外（spec非スコープ。実機Pacemaker/実機Nexus等との結合はテストしない）。

## 実行コマンド

```bash
# 単一テスト（RED/GREEN の証拠。-f はテスト名の部分一致フィルタ）
bats tests/bats/ha_guard.bats -f "<test name substring>"

# RED 再現（tdd-evaluator が隔離 worktree で実行する）
git worktree add <scratchpad>/red-<slug> <RED_SHA>
bats <scratchpad>/red-<slug>/tests/bats/ha_guard.bats -f "<test name substring>"
git worktree remove <scratchpad>/red-<slug>

# 全体（既存回帰の確認。起動時のベースライン取得と CP-D 手順0 で各1回実行する。CP-C では実行しない）
bats tests/bats/

# カバレッジ
# 自動カバレッジ計測ツールはbatsに存在しない。代替として、spec 4章のテスト対象一覧
# （Active/Standby判定の成否パターン、マーカー作成・削除、reconcileループの部分失敗継続、
#  `fx2prov fx2 list`失敗時にマーカーを作らないこと）を完了チェックリストとし、
# 各項目に最低1つのGREENテストが対応することを最低ラインとする。
```

## 層別テストコマンド（CP-B の3層戦略）

```bash
# unit（該当なし。スクリプトは単一エントリポイントで関数分割・個別公開を行わない）
-
# integration（唯一の層。外部コマンドをモック関数/スタブスクリプトに差し替えてスクリプト全体を実行）
bats tests/bats/ha_guard.bats
# e2e（該当なし。実Pacemaker/実fx2prov本体との結合はspec非スコープ）
-
```

外部コマンドのモック方法: `PATH`を一時ディレクトリに向けてスタブスクリプトを配置するか、bats内で同名のshell関数を
`export -f`してオーバーライドする。`STATUS_COMMAND`は任意のシェルコマンド文字列なのでテスト側で完全に差し替え可能。

## CI ステージ（CP-E）

このリポジトリのCIは既存のPython/pytestパイプライン(`.github/workflows/ci.yml`)が主体であり、bashスクリプトは
そこに1ステップとして追加されるのみ（spec 4章で明示済み）。lint/typecheck/build相当のステージはbash側に存在しない
（shellcheck等の新規導入はspecの非スコープであり追加しない）。

| ステージ | コマンド |
|---------|---------|
| lint | 対象外（spec非スコープ） |
| typecheck | 対象外（bashに型検査なし） |
| build | 対象外（ビルド不要） |
| unit test | 対象外（unit層なし） |
| integration test | `sudo apt-get update && sudo apt-get install -y bats` → `bats tests/bats/`（spec 4章の追加ステップそのもの） |
| 主要E2E | 対象外 |

## Critical 証拠ルール

- **CP-C(RED)**: `bats`出力に失敗テストが含まれ、失敗理由（assert差分・期待exit code不一致等）が明示されていること。
  無効例（FAIL扱い）: テストファイル自体が存在しない/構文エラーで動かないだけの状態を「RED」と称すること、
  exit codeのみ確認して失敗メッセージを提示しないこと。
- **CP-C(GREEN)**: `bats`出力が対象テストについて `ok` （failures 0）であること。フルスイートは実行しない
  （全体の新規失敗0はCP-D手順0で確認する）。
- **CP-C(REFACTOR)**: `.bats`ファイルのdiffが空（テスト内容不変）かつ対象テストが緑であること。

## カバレッジ閾値

自動カバレッジ計測なし。spec 4章のテスト対象一覧（Active/Standby判定・マーカー作成/削除・reconcileループ部分失敗時の
継続動作・`fx2prov fx2 list`失敗時にマーカーを作らないこと）を全項目カバーすることを最低ラインとする。

## 参照委譲

なし。bats-core特有の作法（`setup`/`teardown`、`run`コマンド、`PATH`スタブ手法）が複雑化した場合は本ファイルに追記する。
