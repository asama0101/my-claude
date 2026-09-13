---
name: evidence-check
description: |
  superpowers subagent-driven-development の task-reviewer ディスパッチを差し替え、実装者の申告を信じず`tdd-evaluator`が自ら再実行して検証する（trust-but-verify チェーンの旧CP-C相当）。UI/UX・security/perfは条件付き追加。SDD純正の5ラウンドfix loopをそのまま使う。

  `trust-but-verify:trust-but-verify` チェーンのタスクレビュー段階に必ず自動組込で使う。単体で呼び出し可能なスキルとしても存在するが、`evidence-check`自体を単体運用の起点にはしない（専門レビュアー群だけを単発利用したい場合は`trust-but-verify:review-aggregate`を使う）。
---

# trust-but-verify:evidence-check — タスク証拠検証

`trust-but-verify:trust-but-verify` チェーンの evidence-check ステップ（旧CP-C）。superpowers `subagent-driven-development` の task-reviewer ディスパッチを差し替える（汎用reviewerでなく`tdd-evaluator`）。

**中核原則**: SDD の `task-reviewer-prompt.md` には既定で "Do not re-run the suite to confirm their report."（実装者の報告を信頼し再実行しない）とあるが、evidence-check が乗る場面ではこれを**明示的に上書きする**。RED/GREEN のテスト実行結果は実装者の報告のまま信用せず、必ず自ら再実行して確認する。上書きの適用手順は `~/.claude/skills/trust-but-verify/templates/task-evidence-addendum.md` が正典（Main がディスパッチプロンプトを組み立てる際に適用する差分であり、`tdd-evaluator`はその結果として渡されたプロンプトに従って再実行する）。

**証拠の記録先**: タスク単位のtodoはSDDが自前で作成するため重複して作らない。証拠行（RED／GREEN コミット SHA、RED/GREEN コマンドと出力）は SDD の `progress.md` に追記する形に統一する。

**証拠主義**: 「テストは通るはず」「多分失敗する」は無効。RED/GREEN は必ず実行ログを証拠として `progress.md` に残す（`~/.claude/skills/trust-but-verify/references/scoring.md` の証拠フォーマット）。特にRED は「実際に失敗したログ」が無ければ通さない（Critical即FAIL）。

**仕様変更時の巻き戻し**: ユーザー起因の仕様変更が入ったら、① `progress.md` に「仕様変更」エントリ（日時・変更内容・ユーザー指示の要旨）を記録し、② 影響するテストはRED からやり直す。③ `tdd-evaluator` はこのエントリと照合し、正当なテスト変更と assert 骨抜きを区別する。④ 変更が実装詳細でなく要件レベルの場合は、Mainが変更後の要件を一行で再言語化しユーザーに確認を取る。

**small判定時の簡略ルート**: `trust-but-verify:plan-audit` でsmall判定された場合、RED→GREEN 中心の簡略パイプに降格してよいが、Critical（実失敗ログ）はいかなる場合も省略しない。

リトライ機構はSDD純正の5ラウンドfix loopをそのまま使用する（独自カウンタは持たない）。目的・Critical基準・証拠要件の正典は `~/.claude/skills/trust-but-verify/references/checkpoints.md`「CP-C」節。採点形式の正典は `~/.claude/skills/trust-but-verify/references/scoring.md`「スコアカード出力形式（CP-C〜F用・SDD互換）」。
