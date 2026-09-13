---
name: design-audit
description: |
  brainstorming の Spec Self-Review 後・User Review Gate 前に独立エージェントの敵対的検査を挿入し、要件ギャップを検出する（trust-but-verify チェーンの旧CP-A相当）。`tdd-evaluator` が担当し、独自PASS/CONDITIONAL/FAIL（最大2回の再評価）で完結する。決定ツリーを一問一答で詰め、各分岐に推奨回答を示したかも監査基準に含む。

  `trust-but-verify:trust-but-verify` チェーンの一部として自動組込で使うのが基本。設計文書単体の敵対的レビューが独立して欲しい場合のみ単体起動する。
---

# trust-but-verify:design-audit — 要件ギャップレビュー

`trust-but-verify:trust-but-verify` チェーンの design-audit ステップ（旧CP-A）。superpowers `brainstorming` の Spec Self-Review 後・User Review Gate 前に、`tdd-evaluator` による独立の敵対的検査を挿入する。

土台は `~/.claude/skills/trust-but-verify/templates/spec-gap-review-addendum.md`（`spec-document-reviewer-prompt.md`への差分追記）。

**監査基準**: 抜け漏れ検出時は `~/.claude/skills/trust-but-verify/references/scoring.md`「停止シグナル（GUARDRAIL_HALT）」形式で提示する。加えて、決定ツリーを依存順に一問一答で詰め、各分岐に推奨回答を示したか（grillingスキル相当の徹底度）も監査項目に含める。

**再開時の軽量チェック**: brainstormingを経由せず既存のspec文書から再開する場合（別セッションでdesign-audit承認済みの場合等）は、対象spec文書のcommit日時以降に参照範囲のコードへ変更が入っていないか`git log`で確認し、変更があれば一言ユーザーに確認する（design-audit再実行ではなく差分有無の軽量チェック）。

目的・Critical基準・証拠要件の正典は `~/.claude/skills/trust-but-verify/references/checkpoints.md`「CP-A」節。採点形式の正典は `~/.claude/skills/trust-but-verify/references/scoring.md`「スコアカード出力形式（CP-A/B用）」。
