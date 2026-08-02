# tdd-gates 軽量化設計（CP-C証拠取得の圧縮＋evaluatorモデル階層化）

## 背景・動機

`tdd-gates`（`~/.claude/skills/tdd-gates/`）はsuperpowersチェーン（brainstorming→writing-plans→SDD→finishing）に寄生する品質規律レイヤーで、CP-A〜Fの6チェックポイントを持つ。substantialなタスクでは全チェックポイントを通すため、トークン消費・所要時間（wall-clock）の両面で処理が重いという懸念がユーザーから提起された。

構造を分析した結果、コストの主因はCP-Cにあると判断した。CP-A/B/Dは1回きりの実行だが、CP-Cは**SDDのタスク単位で繰り返される**。1タスクにつき`tdd-evaluator`が全体テストスイートを最大2回（GREEN確認・REFACTOR確認）自力再実行し、これがプラン内のタスク数だけ倍加する。さらに`tdd-evaluator`のモデルは`model: sonnet`に固定されており、タスクの複雑度に関わらず一律のモデル階層で評価が行われている。

## スコープ

- **対象**: CP-C（および同じSDDタスクループに乗るCP-E）における証拠取得手順とevaluatorのモデル選択。
- **対象外**:
  - CP-A/B（1回きりの実行で乗数効果が無く、要件抜け漏れ検出という高度な判断を要するため現行モデル・現行証拠要件を維持）
  - CP-D（「唯一の実レビュー層」として過去に意図的に現状維持と決定した経緯があり、本設計では変更しない）
  - 真の並列実行（タスクの並列dispatch）: `subagent-driven-development`が明示的に「Never dispatch multiple implementation subagents in parallel (conflicts)」と定めており、この制約はtdd-gates側の変更では解消できない。サブプロジェクト単位の分割によるworktree並列は別の大きな構造変更であり、本設計のスコープ外とする。

## 変更1: CP-C証拠取得の圧縮

### RED確認は対象テストのみ実行と明示化

現状の `checkpoints.md` はRED確認でフルスイート実行を要求していないが、文言が曖昧なためevaluatorが念のためフルスイートを実行してしまう余地がある。「対象テストのみ実行で足りる（フルスイート不要）」と明記する。

### REFACTORのフルスイート再実行を条件付き化

現状は毎タスク、REFACTOR確認で無条件に全体テストスイートを再実行している。以下の手順に変更する。

1. `tdd-evaluator`が`git diff`（GREEN確定コミット〜現在HEAD）を自ら取得する。
2. 差分が空（実装者がリファクタ不要と判断し、GREEN後に何も変更しなかった）なら、GREENで既に確認済みの全緑結果を援用し、フルスイート再実行を**省略**する。
3. 差分がある場合は、従来通りテストファイル不変の確認＋フルスイート再実行を行う。

evaluatorが自らgit diffを取得して空であることを独立に確認するため、実装者の申告を鵜呑みにするわけではなく、証拠不信の原則は維持される。差分が空である以上、テストも実装コードも変わっていないことは論理的に保証されており、フルスイート再実行は同一結果を返すだけの冗長な検証である。

### 効果

タスクあたりのフルスイート再実行が、リファクタが実質的に発生しないタスク（多くの小粒タスクが該当）では2回→1回に減る。

### 影響ファイル

- `checkpoints.md`（CP-C RED/REFACTOR行）
- `task-evidence-addendum.md`（差分2の記述）
- `profiles/pytest.md`（CP-C証拠ルールの記述）
- `tdd-evaluator.md`（採点プロセスstep3の該当行）

## 変更2: evaluatorモデル階層化

CP-C（および同じタスクループに乗るCP-E）で`tdd-evaluator`をディスパッチする際、Mainが既に持っている情報（CP-Bのsmall-route判定・security/perf敏感フラグ）を使ってモデルを指定する。新たな判定ロジックは追加せず、既存の判定結果を再利用する。

| タスクの状態 | モデル | 理由 |
|---|---|---|
| CP-Bでsmall-route該当と判定済み（≤2ファイル・≤50行・公開IF不変・既存テスト被覆） | 廉価モデル（haiku） | 判断の複雑さが構造的に低いことをCP-Bが既に厳密に検証済み |
| 上記以外の通常タスク | 現行のsonnet（変更なし） | 標準的な判断品質を維持 |
| CP-Bでsecurity/perf敏感と印付けされたタスク | 上位モデル（opus） | 偽装テスト検知・assert骨抜き検知など繊細な判断が必要な場面でグレードを上げる |

### 優先順位

small-route該当かつsecurity/perf敏感の両方に該当するタスク（例: 差分は小さいが認証ロジックに触れる）は、security/perf敏感を優先し`opus`を指定する。

### 適用しないもの

CP-A/B・CP-D（理由は「スコープ」節参照）。

### トレードオフ

small-routeタスクでの偽装テスト検知・assert骨抜き検知の精度が、廉価モデルにより理論上わずかに下がる可能性がある。ただしsmall-route自体が「既存テストが変更対象範囲を被覆」を要件としているため、そもそも新規assertの複雑度が低いタスクに限定される。

### 影響ファイル

- `checkpoints.md`（CP-C節に評価者モデル階層化の表を追加）
- `task-evidence-addendum.md`（`[MODEL]`プレースホルダの埋め方に階層化ルールへの参照を追加）
- `ci-gate-task-template.md`（CP-Eが同じルールに乗ることを一言追記）

## 検証方針

本設計はトークン数・所要時間を自動計測する仕組みを持たない。成功の判定基準は定性的なものとする。

- タスクあたりのフルスイート再実行回数が、リファクタ差分の無いタスクで2回→1回に減っていること（`checkpoints.md`・`task-evidence-addendum.md`の記述で確認）。
- small-routeタスクのCP-C evaluatorディスパッチが`haiku`を指定していること（実運用のディスパッチ例で確認）。
- 既存のCritical即FAIL・証拠不信の原則（貼付ログ不信・自力再実行・ミューテーション検証義務）が一切緩んでいないこと。

## 実装上の注意（次工程への申し送り）

変更対象ファイルは`~/.claude/skills/tdd-gates/`および`~/.claude/agents/tdd-evaluator.md`の実体であり、`my-claude/claude/`はミラーのため直接編集しない（`scripts/sync.sh`で上書きされる）。実装後は`scripts/sync.sh`で本リポジトリへ同期する。

本変更はMarkdown指示文書の編集のみであり、コード・テストは存在しない。次工程（`writing-plans`）では、tdd-gates自体をこの変更に適用するのではなく、`doc-updater`による構成整合を伴う編集としての実装計画を検討すること。
