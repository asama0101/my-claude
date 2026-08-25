# CP-A ディスパッチアドオン（spec-gap-review-addendum）

**土台テンプレ**: `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.2.0/skills/brainstorming/spec-document-reviewer-prompt.md`

このファイルは土台テンプレの本文を複製しない。`tdd-evaluator` を CP-A でディスパッチする際、Main は土台テンプレを Read した上で、以下の差分を適用したプロンプトを組み立てる。

## 適用手順

1. 土台テンプレのプロンプト本文（`## What to Check` 〜 `## Output Format`）をベースに使う。
2. 下記「差分1〜4」を適用する。
3. 「ディスパッチ時に埋めるプレースホルダ」を実値で埋めて `tdd-evaluator` に渡す。

## 差分1: ディスパッチ先の差し替え

- 土台の `Subagent (general-purpose)` を `tdd-evaluator` に差し替える（model 指定は不要。`tdd-evaluator.md` の既定 `model: sonnet` に従う）。
- description は `"CP-A: Review spec document (gap analysis)"` とする。

## 差分2: 追加セクション「抜け漏れ候補の敵対的リストアップ」

土台の `## What to Check` 表の直後に、以下のセクションを追加する。

> ## 抜け漏れ候補の敵対的リストアップ（tdd-gates 追加）
>
> spec に書かれていない要件・暗黙のうちに前提とされている要件・想定されていないエッジケースを、承認する側でなく崩す側の視点で列挙する。各項目には根拠（既存コードの `file:line`、または要求文の該当箇所）を必ず添える。網羅性の判定基準は `~/.claude/skills/tdd-gates/references/checkpoints.md` CP-A の「採点項目」に従う。

## 差分3: 出力形式の差し替え

土台の `## Output Format`（`Status: Approved | Issues Found` 形式）は使わない。代わりに `~/.claude/skills/tdd-gates/references/scoring.md` の「スコアカード出力形式（CP-A/B用）」（Quality Gate Report 形式）で返すよう指示する。

- ヘッダ: `Quality Gate Report: CP-A - 要件ギャップレビュー`
- 評価項目: `checkpoints.md` CP-A の採点項目4件（コンテキスト把握の的確さ／要件抽出・構造化／要件の網羅性（抜け漏れ・暗黙要件）／スコープの単一性）
- 判定: PASS / CONDITIONAL / FAIL（`scoring.md` の閾値。最大2回の再評価）

## 差分4: 「Approve unless serious gaps」方針の上書き（Stop&Ask）

土台の Calibration にある `Approve unless there are serious gaps that would lead to a flawed plan.` という自動承認寄りの方針は、tdd-gates では上書きする。

非自明な抜け漏れ候補（ユーザーの意図に関わり、実装側が推測で埋めることになる項目）が1件でもあれば、`tdd-evaluator` は判定を PASS にせず CONDITIONAL 以下に留め、差し戻し指摘に「ユーザー確認が必要な項目」として明記する。`tdd-evaluator` 自身はユーザーに直接質問しない——Main がこの指摘を受け取ってユーザーに確認し、結果を spec に反映してから CP-A を再評価する。

## ディスパッチ時に Main が埋めるプレースホルダ

- `[SPEC_FILE_PATH]`: brainstorming が `docs/superpowers/specs/` に書いた spec 文書パス
- 既存コード・制約の参照範囲: CP-A の「コンテキスト把握」採点のため、`tdd-evaluator` が Read すべき既存実装のディレクトリ／ファイルを Main が明記する（evaluator 側の推測に任せない）
