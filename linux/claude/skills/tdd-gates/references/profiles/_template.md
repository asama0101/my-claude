# 言語プロファイル: <言語 / テストランナー>（新言語追加用スケルトン）

新しい言語で tdd-gates を回すには、このファイルを `profiles/<runner>.md`（例: `gotest.md`）としてコピーし、以下を埋める。
ゲート骨格（順序・採点・Critical・証拠主義）は言語非依存なので変更しない。**このプロファイルは「ゲート用グルー」だけ**を定義する。

## テスト種別 → ランナー / パスパターン判定

| 対象パス（例） | テスト種別 | ランナー | テスト置き場（例） |
|----------------|-----------|----------|--------------------|
| `<pattern>` | unit | `<runner>` | `<location>` |
| `<pattern>` | integration | `<runner>` | `<location>` |
| `<pattern>` | e2e | `<e2e tool>` | `<location>` |

## 実行コマンド

```bash
# 単一テスト（RED/GREEN の証拠）
<cmd>

# RED 再現（tdd-evaluator が隔離 worktree で実行する）
git worktree add <scratchpad>/red-<slug> <RED_SHA>
<worktree 内で単一テストを実行する cmd。ランナーが本体ツリーのモジュールを優先解決する場合は環境変数で worktree 側を指す>
git worktree remove <scratchpad>/red-<slug>

# 全体（既存回帰の確認。起動時のベースライン取得と CP-D 手順0 で各1回実行する。CP-C では実行しない）
<cmd>

# カバレッジ
<cmd>
```

## 層別テストコマンド（CP-B の3層戦略）

```bash
# unit（業務ロジック・高速多数）
<cmd>
# integration（機能品質・主軸）
<cmd>
# e2e（最後の砦・最小限）
<cmd>
```

## CI ステージ（CP-E・CI プロバイダ既定 = <provider>）

CP-E が被覆すべき必須ステージと具体コマンド（グローバル skill 側は抽象ステージ名のみ保持）。

| ステージ | コマンド |
|---------|---------|
| lint | `<cmd>` |
| typecheck | `<cmd>` |
| build | `<cmd>` |
| unit test | `<cmd>` |
| integration test | `<cmd>` |
| 主要E2E | `<cmd>` |
| preview デプロイ（任意） | プロジェクト固有・既定 off |

## Critical 証拠ルール（このランナーでの合格ログの形）

- **CP-C(RED)**: 失敗を示す出力パターン = `<...>`。無効例（FAIL 扱い）= `<...>`。
- **CP-C(GREEN)**: 通過を示す出力 = `<...>`。フルスイートは実行しない（全体の新規失敗 0 は CP-D 手順0 で確認する）。
- **CP-C(REFACTOR)**: テスト不変（diff にテスト変更なし）かつ対象テストが緑。

## カバレッジ閾値

- 目標 `<x>%`。

## 参照委譲

深い作法（フィクスチャ/セットアップ/モック/非同期等）は `<言語の深い参照ファイルパス>` へ委譲する（無ければ本ファイルに最小限記述）。
