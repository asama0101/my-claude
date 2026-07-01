---
name: tdd-gates
description: |
  TDD × 9品質ゲートのオーケストレータ。AI駆動開発の品質問題（動くように見えて中身がバグだらけ・テストの形骸化・RED未確認・自己承認）を、ゲート順序の強制と Critical即FAIL＋証拠要求の採点で構造的に潰す。substantial な実装（新機能・バグ修正・非自明な変更）で使う。

  以下のような発言・状況で起動すること:「TDDで実装して」「テストファーストで」「品質ゲートを回して」「gate を回して」「新機能を実装して（テスト付きで）」「バグを直して（回帰テスト付きで）」。substantial なコード変更の着手時に積極的に起動する。trivial（数行・設定/ドキュメント）は使わず単一軽量 Agent に委任する（比例ルール）。
---

# TDD 9品質ゲート・オーケストレータ

あなた（Main）は**オーケストレータ**に徹する。自分でテストや実装を書かず、各ゲートを担当ロールのサブエージェントへ委任し、順序と合否を強制し、台帳に証拠を残す。

**中核原則**: superpowers の Iron Law「NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST」を規律の根拠とする（`superpowers:test-driven-development` を原則レイヤとして参照）。本スキルはその工程を**強制**する層。

## 起動時にやること（チェックリスト）

各項目を todo 化して順に実施する。

1. **プロファイル確定**: 対象言語のプロファイルを1つ選ぶ（Python は `references/profiles/pytest.md`）。パス→テスト種別の対応表を読み、対象ファイルからテスト種別（unit/integration/e2e）を判定し、**ユーザーに確認**する。
2. **台帳を作成**: セッション scratchpad に `tdd-gates-ledger.md` を作り、各ゲートの verdict・スコア率・証拠スニペット・CONDITIONAL 再評価回数を記録していく（ゲートのバイパスと自己承認を防ぐ監査証跡）。台帳には次を必須で残す:
   - **各 PASS には、その採点を行った gate-evaluator が自ら再実行した検証コマンドの出力行を添付**する。evaluator の実行痕跡が無い PASS は無効（未実施扱い）とし、次ゲートへ進めない。
   - **Gate4(RED) 時点でテストファイルの内容（パス＋本文 or ハッシュ）を固定記録**し、Gate5・Gate6 で照合する（assert 骨抜き検知）。
3. **ゲートを順に駆動**（下記）。

## ゲート駆動ループ

`references/gates.md` の定義と `references/scoring.md` の採点で、次の順に進める:

```
Gate1-2(計画) → Gate3(事前レビュー) → Gate4(RED) → Gate5(GREEN) → Gate6(REFACTOR)
  → [e2e なら Gate7(UI/UX)] → Gate8(採点判定) → 受け入れ確認 → [doc影響あれば Gate9] → 完了
```

各ゲートで:
1. **担当ロールへ委任**（下表）。Generator と Evaluator は**必ず別サブエージェント**で起動する（自己承認の構造的排除）。
2. **証拠を受け取り採点**: Evaluator ゲートは `gate-evaluator` が `scoring.md` でスコアカード化。
3. **合否で分岐**:
   - **PASS**（≥80% かつ Critical 達成）→ 台帳に記録して次ゲート。
   - **CONDITIONAL**（60–79%）→ 指摘を Generator に戻して修正 → 再評価。**最大2回**。台帳の再評価カウンタを増やす。
   - **FAIL**（<60% または Critical 未達、あるいは CONDITIONAL 2回で未達）→ **停止してユーザーに差し戻す**。勝手に先へ進めない。

### ロール委任表

| ゲート | 委任先 | 起動方法 |
|--------|--------|----------|
| 1–2 計画 | `planner` が起草 → `gate-evaluator` が rubric で採点（PASS で次へ） | 起草＋採点 |
| 3 事前レビュー | 関連する `reviewer-*` を**並列**起動 → `gate-evaluator` が集約採点 | 並列＋集約 |
| 4 RED / 5 GREEN / 6 REFACTOR | `gate-generator` | 段階ごとに委任。各段階の採点は毎回 `gate-evaluator`（別コンテキスト） |
| 7 UI/UX（e2e時のみ） | `frontend-design` スキル＋敵対的クロスレビュー | 条件付き |
| 8 採点判定 | `reviewer-*` 5次元を**並列**起動 → `gate-evaluator` が集約スコアカード | 並列＋集約 |
| 9 doc同期（影響時） | `doc-updater` | 条件付き |

- **Gate3 / Gate8 の並列集約**: Main が reviewer-* を並列起動して所見を集め、それを `gate-evaluator` に渡して採点＋Critical即FAIL判定させる（reviewer-*＝所見のみ、gate-evaluator＝点数化）。

## 重要ルール

- **証拠主義**: 「テストは通るはず」「多分失敗する」は無効。RED/GREEN は必ず**実行ログ**を証拠として台帳に残す（`scoring.md` の証拠フォーマット）。
- **Critical即FAIL**: スコアが高くても Critical 未達なら即 FAIL。特に Gate4 は「実際に失敗したログ」が無ければ通さない。
- **自己承認の禁止**: 実装した `gate-generator` の出力は、必ず別の `gate-evaluator`／`reviewer-*` が採点する。
- **オーケストレータのコンテキスト衛生**: Main は生ログ全文を抱えない。各サブエージェントには結論・スコア・証拠スニペット・`file:line` だけを蒸留して返させ、台帳に要点を残す。
- **段階導入の限界**: Gate4–5(RED→GREEN) だけへの簡略は、比例ルールの **trivial には満たないが substantial とも言い切れない小変更に限る**（差分が小さく既存テストがある等）。**substantial では Gate3(事前レビュー)・Gate8(採点判定) を省略不可**（唯一の実レビュー層のため）。簡略の可否は Gate1 で planner／gate-evaluator が明示承認し台帳に記録する。Gate4 の Critical（実失敗ログ）はいかなる場合も省略しない。
- **Gate8 → 受け入れ確認 → Gate9**: Gate8 PASS 後、Gate9(doc同期) に進む前に**ユーザーの受け入れ確認を取る**（グローバル CLAUDE.md「実装後の受け入れ→ドキュメント更新」準拠）。NG なら修正へ戻る。

## 参照ファイル

- `references/gates.md` — 9ゲートの内容・Critical・証拠要件・順序。
- `references/scoring.md` — 0–3採点・80%/60–79%・Critical即FAIL・CONDITIONAL上限・証拠/スコアカード形式。
- `references/profiles/pytest.md` — Python/pytest のパス判定・実行コマンド・合格ログ形式（深い作法は pytest-patterns.md へ委譲）。
- `references/profiles/_template.md` — 新言語追加用スケルトン。
