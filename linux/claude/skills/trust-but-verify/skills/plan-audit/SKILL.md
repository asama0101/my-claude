---
name: plan-audit
description: |
  writing-plans の Self-Review 後・Execution Handoff 前に独立エージェントの計画品質レビューを挿入する（trust-but-verify チェーンの旧CP-B相当）。`tdd-evaluator` が担当し、独自PASS/CONDITIONAL/FAIL（最大2回の再評価）で完結する。small/substantial判定の実施場所でもある。

  `trust-but-verify:trust-but-verify` チェーンの一部として自動組込で使うのが基本。
---

# trust-but-verify:plan-audit — 計画品質レビュー

`trust-but-verify:trust-but-verify` チェーンの plan-audit ステップ（旧CP-B）。superpowers `writing-plans` の Self-Review 後・Execution Handoff 前に、`tdd-evaluator` による独立の計画品質レビューを挿入する。

土台は `~/.claude/skills/trust-but-verify/templates/plan-quality-review-addendum.md`（`plan-document-reviewer-prompt.md`への差分追記。トレーサビリティ表・3層戦略・small/substantial判定・業務ロジック分離監査を追加）。

**small/substantial判定**: 判定主体は本ステップ。`git diff --stat` 見込みと既存テスト一覧でグローバル CLAUDE.md 作業ルーティング表 small 行の4条件を照合する。該当すれば `trust-but-verify:evidence-check` はRED→GREEN相当だけの簡略ルートを取ってよい。

目的・Critical基準・証拠要件の正典は `~/.claude/skills/trust-but-verify/references/checkpoints.md`「CP-B」節。採点形式の正典は `~/.claude/skills/trust-but-verify/references/scoring.md`「スコアカード出力形式（CP-A/B用）」。

> **実効性メモ（2026-09-13）**: design-audit（旧CP-A）ほどの実効性実証記録が無い。今後の運用実績を見て要否を再判断する対象として注記しておく。
