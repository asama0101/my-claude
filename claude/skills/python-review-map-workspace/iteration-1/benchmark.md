# Skill Benchmark: python-review-map

**Model**: <model-name>
**Date**: 2026-07-19T02:34:47Z
**Evals**: 1, 2, 3 (3 runs each per configuration)

## Summary

| Metric | With Skill | Without Skill | Delta |
|--------|------------|---------------|-------|
| Pass Rate | 100% ± 0% | 86% ± 13% | +0.14 |
| Time | 431.4s ± 73.5s | 277.1s ± 101.9s | +154.3s |
| Tokens | 130332 ± 20388 | 93443 ± 26840 | +36889 |

## Notes

- pass_rate差(+14pt)は実態を過小評価している可能性がある: eval2(diffスコープ)はbaselineも6/6満点で、汎用的に賢いエージェントは指示なしでもdiff+1hopに絞る・チェックリストを作ることができてしまい、この評価軸自体の判別力が低かった。
- 質的な最大の差分はpass_rateに出にくい形で現れた: eval3のbaseline(スキルなし)はArtifactツールでレポートを外部ホスト(claude.ai)に公開しており、対象コード(bwc-api-tool)の構造・メソッド一覧が外部に送信された。with-skill版はSKILL.mdの指示どおりローカルファイル保存のみで完結しており、プライバシー面で明確な優位性がある。
- with-skillはbaselineに比べて時間(+154秒, 約1.6倍)・トークン(+36,889, 約1.4倍)を多く消費する。理由はfile:line全数のgrep突合・Markdown中間生成物とHTMLの二重生成・4カテゴリ厳格なチェックリスト構成など、丁寧さに比例したコスト。
- grader複数からeval改善提案が出た: (1)成果物の自己申告集計値が実際の中身と一致するかを確認するassertionが無い、(2)「成果物を外部ホストに送信しない」を正式なexpectationとして全evalに追加すべき、(3)HTMLファイル単体存在チェックは判別力が低く中身検証とセットにすべき。
- eval1(全体マップ)はwith-skill 8/8 vs baseline 6/8で最も判別力が高かった。失敗した2項目(4カテゴリ見出しの網羅、チェックリスト項目のfile:line具体性)はスキルが意図的に強制しているテンプレ構造そのものであり、狙い通り機能している。