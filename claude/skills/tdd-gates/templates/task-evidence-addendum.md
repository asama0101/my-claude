# CP-C ディスパッチアドオン（task-evidence-addendum）

**土台テンプレ**: `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.2.0/skills/subagent-driven-development/task-reviewer-prompt.md`

このファイルは土台テンプレの本文を複製しない。SDD（または executing-plans）が「### 3. Review the task」でディスパッチする task-reviewer プロンプトを、Main は土台テンプレを Read した上で以下の差分を適用してから `tdd-evaluator` に差し替えて渡す。

## 適用手順

1. 土台テンプレのプロンプト本文をベースに使う（`## What Was Requested` 〜 `## Output Format` の骨格はそのまま流用する）。
2. 下記「差分1〜5」を適用する。特に差分2は土台の既定動作を**明示的に上書きする**——欠かすと証拠不信の原則が機能しない。
3. 「ディスパッチ時に埋めるプレースホルダ」を実値で埋める。

## 差分1: ディスパッチ先の差し替え

- 土台の `Subagent (general-purpose)` を `tdd-evaluator` に差し替える。
- description は `"CP-C: Review Task N (RED/GREEN/REFACTOR evidence)"` とする。

## 差分2: 「テストを再実行しない」の明示的上書き（最重要）

土台テンプレ「## Tests」節にある次の一文を、tdd-gates が乗る場面では**そのまま採用しない**。

> `Do not re-run the suite to confirm their report.`

この一文を、渡すプロンプトの同じ位置で次のように**明示的に上書き**する（引用の上に取り消し線的に「この節は tdd-gates では以下に置き換える」と書き、原文をそのまま残さない）。

> ## Tests（tdd-gates による上書き）
>
> 実装者（SDD implementer）が報告した RED 失敗ログ・GREEN 通過ログを、**そのままでは信用しない**。あなた（`tdd-evaluator`）自身が対象テストを Bash で再実行し、実際に失敗（RED 時点）・実際に通過（GREEN 時点）することを自分の目で確認する。再現できないログ、対象テストパスが申告と一致しないログは Critical 未達（0点）として扱う。実行コマンド・失敗/通過の判定基準は対象言語プロファイル（例 `references/profiles/pytest.md` の「Critical 証拠ルール」）に従う。

## 差分3: 追加セクション「assert 骨抜き検知」

土台テンプレ「## Part 2: Code Quality」の直後に追加する。

> ## assert 骨抜き検知（tdd-gates 追加）
>
> 新規・変更されたテストの assert を読み、次のいずれかに該当するテストが無いか確認する: assert が無い／`assert True` 等の常に真の assert／例外 raise の有無だけを見て内容を検証しない／期待値が実装コードの写経（実装の定数・内部関数をそのままテスト側で再計算している）。該当すればテスト種別を問わず Critical（偽装テスト）とする。

## 差分4: 追加セクション「UI/UX レビュー起動条件」

> ## UI/UX レビュー起動条件（tdd-gates 追加）
>
> 対象ファイルが言語プロファイルの view/template/routing パターン（例 `references/profiles/pytest.md` の該当行、または e2e＝ブラウザ判定）に一致する場合、unit 申告であっても回避不可で、`frontend-design` スキルの起動と敵対的クロスレビューを追加する。最大3ラウンド（確認→修正）。ブラウザが使えない環境は静的解析で代替する。

## 差分5: 追加セクション「security/perf 追加レビュー起動条件」

> ## security/perf 追加レビュー起動条件（tdd-gates 追加）
>
> CP-B（`templates/plan-quality-review-addendum.md` 差分6）で security 敏感／perf 敏感の印が付いたタスクに限り、`review-security`／`review-performance` を本タスクの task-reviewer ディスパッチに追加起動する。印が無いタスクには追加起動しない（過剰レビューを避ける）。

## 出力形式・リトライ機構

出力形式は土台テンプレの `## Output Format`（Spec Compliance / Strengths / Issues / Assessment）をそのまま使う。リトライは SDD 純正の5ラウンド fix loop に従い、tdd-gates 独自のカウンタは持たない。Critical 判定の根拠には `~/.claude/skills/tdd-gates/references/checkpoints.md` CP-C の Critical 行を明記する（`scoring.md` の「スコアカード出力形式（CP-C〜F用）」参照）。

## ディスパッチ時に Main が埋めるプレースホルダ

土台テンプレの `[MODEL]`・`[BRIEF_FILE]`・`[GLOBAL_CONSTRAINTS]`・`[REPORT_FILE]`・`[BASE_SHA]`・`[HEAD_SHA]`・`[DIFF_FILE]` に加えて:

- 対象言語プロファイルのパス（Critical 証拠ルールの参照先として必須明記）
- テスト種別（unit/integration/e2e）の判定結果（CP-C 内 UI/UX 追加検査の要否に直結）
- CP-B での security/perf 印付け結果（該当タスクのみ）
