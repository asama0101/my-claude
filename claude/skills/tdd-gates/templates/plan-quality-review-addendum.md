# CP-B ディスパッチアドオン（plan-quality-review-addendum）

**土台テンプレ**: `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.2.0/skills/writing-plans/plan-document-reviewer-prompt.md`

このファイルは土台テンプレの本文を複製しない。`tdd-evaluator` を CP-B でディスパッチする際、Main は土台テンプレを Read した上で、以下の差分を適用したプロンプトを組み立てる。

## 適用手順

1. 土台テンプレのプロンプト本文（`## What to Check` 〜 `## Output Format`）をベースに使う。
2. 下記「差分1〜6」を適用する。
3. 「ディスパッチ時に埋めるプレースホルダ」を実値で埋めて `tdd-evaluator` に渡す。

## 差分1: ディスパッチ先の差し替え

- 土台の `Subagent (general-purpose)` を `tdd-evaluator` に差し替える（model 指定不要）。
- description は `"CP-B: Review plan document (quality + traceability)"` とする。

## 差分2: 追加セクション「要件↔受入基準↔テストシナリオのトレーサビリティ表」

土台の `## What to Check` 表の直後に追加する。

> ## トレーサビリティ表（tdd-gates 追加）
>
> CP-A で確定した要件を列挙し、各要件が「どの受入基準で検証可能に言語化されているか」「どのテストシナリオで担保されるか」「どのファイル・テスト種別/層が担うか」を1行1要件で表にする。**各要件に最低1受入基準、各受入基準に最低1シナリオ**が無ければ Critical 未達。

## 差分3: 追加セクション「テスト3層戦略の妥当性」

> ## テスト3層戦略（tdd-gates 追加）
>
> `~/.claude/skills/tdd-gates/references/checkpoints.md` CP-B「テスト3層戦略」の方針（unit=業務ロジック分離／integration=主軸／e2e=最小限）に沿って、各シナリオがどの層で守られるかを判定する。e2e を安易に増やしていないか、業務ロジックが unit で高速に守られているかを検査する。層別の実行コマンドは対象言語プロファイル（`references/profiles/*.md`）を参照する。

## 差分4: 追加セクション「small/substantial 4条件判定」

> ## small/substantial 判定（tdd-gates 追加）
>
> `git diff --stat` 見込みと既存テスト一覧を根拠に、次の4条件をすべて満たすか照合する。
> 1. 差分2ファイル以下
> 2. 実装差分50行以下（テスト除く）
> 3. 公開インターフェース不変
> 4. 既存テストが変更対象範囲を被覆
>
> 1つでも外れれば substantial としてフル工程（CP-C を通常ルートで通す）。該当すれば CP-C は簡略ルートを取ってよい旨をスコアカードに明記する（CP-C の Critical＝実失敗ログはいかなる場合も省略しない）。判定基準の数値の正典はグローバル CLAUDE.md 作業ルーティング表 small 行。

## 差分5: 追加セクション「業務ロジックの unit 分離可能性監査」

> ## 業務ロジック分離監査（tdd-gates 追加）
>
> 計画中の実装ファイル構成が、業務ロジックを I/O・フレームワーク・UI から分離した設計になっているか監査する。分離できていない設計は unit テストが書けず CP-C(RED) で高コストな統合テストに頼ることになるため、Important 以上の指摘とする。

## 差分6: 追加セクション「security/perf 敏感タスクの印付け」

> ## security/perf 敏感タスクの印付け（tdd-gates 追加）
>
> 計画中の各タスクが認証・入力処理・機密データを扱う（security 敏感）、または大量データ・ホットパスを扱う（perf 敏感）かを判定し、該当タスクにタグを付ける。タグを付けたタスクは、次の2箇所で追加レビューの起動条件になる。
> - **CP-B 自身**: 該当があれば `review-security`／`review-performance` を条件付きで並列起動する（最大2本）。
> - **CP-C**: `templates/task-evidence-addendum.md` の「security/perf 追加レビュー起動条件」が、この印付けを参照して該当タスクの task-reviewer 差し替え時に追加起動する。

## ディスパッチ時に Main が埋めるプレースホルダ

- `[PLAN_FILE_PATH]`: writing-plans が書いた plan 文書パス
- `[SPEC_FILE_PATH]`: CP-A で確定した spec 文書パス（Reference for spec alignment）
- 対象言語プロファイルのパス（`references/profiles/pytest.md` 等）
