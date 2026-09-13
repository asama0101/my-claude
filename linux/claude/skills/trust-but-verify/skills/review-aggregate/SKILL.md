---
name: review-aggregate
description: |
  superpowers subagent-driven-development の Final Review（`code-reviewer.md`）を差し替え、Mainのフルスイート実行1回→`review-*`条件付き2〜5本並列→`tdd-evaluator`集約という最終スコアカード化を行う（trust-but-verify チェーンの旧CP-D相当）。徴候があればミューテーション検証を加える。

  `trust-but-verify:trust-but-verify` チェーンの一部として自動組込で使うのが基本。専門レビュアー群（`review-*`）だけを単発利用したい場合はこのスキルを起点にする（「レビュー単独」経路）。
---

# trust-but-verify:review-aggregate — 最終スコアカード

`trust-but-verify:trust-but-verify` チェーンの review-aggregate ステップ（旧CP-D）。superpowers `subagent-driven-development` の Final Review にある `code-reviewer.md` 単独ディスパッチを、Main のフルスイート実行1回（手順0）→`review-*`条件付き2〜5本並列→`tdd-evaluator`集約に丸ごと差し替える。土台は `~/.claude/skills/trust-but-verify/templates/final-scorecard-review-prompt.md`。

**モデル選定**: どの `review-*` をどのモデル階層（haiku/sonnet等）で起動するかは、このスキル独自のルールを持たず、superpowers `subagent-driven-development` 本体の Model Selection 節を参照する。

**手順0**: タスクループ開始前に Main が記録したプロファイル全体実行コマンドのベースライン結果（`progress.md`）と比較する。`evidence-check`の各タスクではフルスイートを再実行しないため、この手順0が唯一のフルスイート再実行点になる。

**集約スコアカード**: Main が `progress.md` に書き出す。Critical: 偽装テスト検出・ミューテーション検証条件（徴候があれば必須）。

**受け入れチェックリストへの組込**: チェーン完了後の受け入れ確認時、`tdd-evaluator` が受け入れチェックリスト（受入基準＋本ステップの実施次元（2〜5本）＋CI整備/文書同期の整備状況＋例外処理・権限漏れ・変更影響範囲）と、本ステップで修正済みの「スコープ外の既存問題」一覧を生成する。

リトライ機構はSDD純正のFinal Review（1修正波+1 scoped re-review）。目的・Critical基準・証拠要件の正典は `~/.claude/skills/trust-but-verify/references/checkpoints.md`「CP-D」節。採点形式の正典は `~/.claude/skills/trust-but-verify/references/scoring.md`「スコアカード出力形式（CP-C〜F用・SDD互換）」。

> **スコープメモ（2026-09-13）**: `review-maintainability`の判定基準をponytailのラダー式に差し替える案は本タスクの対象外。前提事実（「プロファイル階層」は`checkpoints.md`に実在しない）を洗い直した上で別タスクとして扱う。
