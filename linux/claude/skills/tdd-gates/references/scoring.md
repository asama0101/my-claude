# 採点ルーブリック（scoring.md）

すべてのCPはこのルーブリックで採点する。**主張ではなく証拠（実行ログ・差分）で採点する**こと。証拠が無い項目は自動的に0点。

**出力形式は2モードに分岐する**（下記）。**CONDITIONAL再評価の上限（最大2回）はCP-A/CP-Bのみに適用**する。CP-C以降はSDDのラウンド機構（5ラウンドfix loop／Final Reviewの1修正波+1 scoped re-review）に従い、tdd-gates独自の再評価上限は適用しない。

## 項目スコア（0–3点）

| 点 | ラベル | 意味 |
|----|--------|------|
| 0 | Missing | 未対応。証拠なし。 |
| 1 | Partial | 着手のみ。重大な欠落がある。 |
| 2 | Good | 要件を満たす。軽微な改善余地。 |
| 3 | Excellent | 要件を完全に満たし、エッジケース・証拠も揃う。 |

## CP合否（CP-A/Bのみ）

CP-A・CP-Bは複数の採点項目を持つ。合計点を満点で割った割合で判定する。

- **PASS**: スコア率 **≥ 80%** かつ **Critical項目がすべて達成**
- **CONDITIONAL**: スコア率 **60–79%**（Criticalは達成済み）→ 指摘を修正して**再評価**。
- **FAIL**: スコア率 **< 60%**、または Critical項目が1つでも未達。

CP-C以降は「PASS/CONDITIONAL/FAIL」ではなく、SDD互換のSpec Compliance形式（✅/❌/⚠️）で判定する（下記「CP-C〜F用スコアカード形式」）。

## Critical即FAIL（最重要ルール・全CP共通）

**Critical項目が未達なら、他の項目が満点でもそのCPは即FAIL（またはSDD形式ではCritical finding）。** スコア率では救済されない。
各CPのCritical項目の具体内容（CP-C RED=実失敗ログ／CP-C GREEN=実通過ログ／CP-C REFACTOR=振る舞い不変／CP-D=偽装テスト検出 等）は、**`checkpoints.md`の各CP定義（Critical行）を単一ソース**とする。ここでは重複定義しない。

## CONDITIONAL再評価の上限（CP-A/Bのみ・無限ループ防止）

この再評価はワークフロー内の正規ループであり、Mainは各回のユーザー承認を待たずに実行する（停止するのは上限到達によるFAILの時のみ。`GUARDRAIL_HALT: retry_limit_exceeded`）。

- CP-A・CP-BのCONDITIONALは**最大2回**まで再評価する。
- **2回目の再評価でもPASSに届かなければFAILに格上げ**し、ユーザーに差し戻して停止する。
- 再評価回数はMainがスコアカード応答の中で追跡する（CP-A/Bは専用台帳を持たないため、直近のスコアカードが再評価カウンタの記録）。
- **各再評価では、tdd-evaluatorが前回スコアカードの差し戻し指摘を引用し、カウンタと整合を確認する**。引用が無い／カウンタが不整合（往復でリセットされている等）な再評価は上限到達（FAIL）とみなす。
- **逐項目3値判定（再評価スコアカードの必須要素）**: 前回の差し戻し指摘を1件ずつ**解消／部分解消／未解消**の3値で判定し、各判定に証拠を添える（「対応済み」の一括宣言は無効＝引用なしと同じ扱い）。**部分解消・未解消が1件でも残る再評価はPASSにできない**。
- **新規混入の検査**: 修正差分そのものが新たな問題を生んでいないか（別のCritical違反・回帰・指摘外箇所の劣化）を再評価の採点対象に含め、逐項目判定表とは別に「新規混入: なし／<所見>」を明記する。

CP-C以降はSDDのラウンド機構（実装者への差し戻し→scoped re-review→ADDRESSED/NOT ADDRESSED判定）に従うため、上記の独自カウンタ・逐項目3値判定は適用しない（SDDの`re-review-prompt.md`が同等の役割を担う）。

## 停止シグナル（GUARDRAIL_HALT・ガードレール停止）

前提条件が欠けている、または自動化ループの上限に到達したときの停止は、曖昧な自然文でなく次の構造化フォーマットで行う。**これは「都度の承認待ち」ではない**——正常系のPASS/CONDITIONAL進行では発火せず、前提が崩れた異常系でのみ発火する（正常系の唯一の停止点はSKILL.md「CP-A〜Fを1サイクルとして自動で通し、受け入れ確認は最後に一度だけ」節）。

```
GUARDRAIL_HALT: <reason_code>
---
missing/ambiguous: <不足・曖昧な項目を1件1行で列挙。file:line や参照した既存資料も添える>
options: <ユーザーが選べる選択肢を列挙>
```

**reason_code**（新規のcode体系を増やさず、既存の停止発火点にのみ適用する）:

- `requirement_gap` — CP-Aの非自明な抜け漏れ候補（`checkpoints.md` CP-A）
- `retry_limit_exceeded` — CP-A/BのCONDITIONAL再評価が2回に到達してもPASSに届かない（本ファイル「CONDITIONAL再評価の上限」）
- `profile_undefined` — 対象言語のプロファイルが未確定（SKILL.md起動時チェックリスト項目1）

Mainは`missing/ambiguous`と`options`を必ず埋めてユーザーに提示し、回答を得るまで該当CPを先に進めない。

## 証拠（Evidence）フォーマット

各CPの証拠は、**実行したコマンドとその出力スニペット**を必ず含める。

```
$ pytest tests/test_foo.py::test_bar -q
FAILED tests/test_foo.py::test_bar - AssertionError: expected 3 got None
1 failed in 0.12s
```

- 実行ログのない主張（「テストは通るはず」「多分失敗する」）は証拠として無効＝該当項目0点。
- 差分が証拠になる場合（CP-C REFACTOR等）は`git diff`の該当箇所を貼る。

## スコアカード出力形式（CP-A/B用）

CP-A・CP-Bで、`tdd-evaluator`は以下の**Quality Gate Report**形式で返す。**「評価理由」欄には根拠となる証拠（実行ログ行・`git diff`該当箇所・`file:line`）を必ず含める**（証拠なしの項目は上記のとおり0点）。

```
Quality Gate Report: CP-<A/B> - <CP名>

| # | 評価項目 | 点数 | 評価理由（証拠つき） |
|---|---------|------|--------------------|
| 1 | <項目名> | X/3 | <具体的な評価理由 ＋ 証拠スニペット> |
| 2 | ...     | ...  | ...                |

スコア: XX / YY（ZZ%）
判定: PASS / CONDITIONAL / FAIL
Critical違反: なし / <違反項目>

指摘事項（CONDITIONAL / FAIL 時のみ）
- <修正が必要な具体的指摘>

前回指摘の逐項目判定（再評価時のみ・必須）
| 前回指摘 | 判定（解消 / 部分解消 / 未解消） | 証拠 |
|---------|--------------------------------|------|
| <前回スコアカードからの引用> | 解消 | <確認した実行ログ・diff> |

新規混入: なし / <修正差分が新たに生んだ問題>

次のアクション
- PASS        → 次のCPへ進む
- CONDITIONAL → <修正対象> を修正後、再評価
- FAIL        → <差し戻し先> から再実行（ユーザーに差し戻して停止）
```

## スコアカード出力形式（CP-C〜F用・SDD互換）

CP-C以降で`tdd-evaluator`（CP-Dは集約後の`tdd-evaluator`、CP-Fは`doc-verifier`）は、SDDの`task-reviewer-prompt.md`と同型の**Spec Compliance形式**で返す。**Critical/Important判定の根拠には、対応する0–3ルーブリックの該当項目（`checkpoints.md`のCritical行）を添える**——SDD標準のreviewerと違い、tdd-gatesはCritical判定を主観でなくルーブリックに紐付ける。

```
### Spec Compliance

- ✅ Spec compliant | ❌ Issues found: [何が不足/過剰/誤解、file:line付き]
- ⚠️ Cannot verify from diff: [diffだけでは検証できない要件]

### Strengths
[何が良くできているか。具体的に。]

### Issues

#### Critical (Must Fix)
[各所見に、対応する0–3ルーブリック項目（checkpoints.mdのCritical行）を明記]

#### Important (Should Fix)
#### Minor (Nice to Have)

各所見: file:line、何が問題か、なぜ重要か、直し方（自明でなければ）。

### Assessment

**Task quality:** [Approved | Needs fixes]

**Reasoning:** [1–2文の技術的評価]
```

- 判定閾値（PASS≥80%／CONDITIONAL 60–79%／Critical即FAIL）とCP-A/Bの上限2回は**変更しない**——変えるのは出力レイアウトと適用範囲（CP-C以降はSDD形式・独自上限なし）のみ。
