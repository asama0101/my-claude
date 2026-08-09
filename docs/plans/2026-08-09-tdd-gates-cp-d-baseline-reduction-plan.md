# tdd-gates CP-D 常時起動本数削減 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: 本計画はコード・テストを持たないMarkdown指示文書の編集のみで構成される。詳細は「実行方式（Execution Handoff）」節を参照——標準のsubagent-driven-development/executing-plansの二択とは異なる方式を採る。

**Goal:** `tdd-gates`（`~/.claude/skills/tdd-gates/`・`~/.claude/agents/tdd-evaluator.md`）に、設計書`docs/specs/2026-08-09-tdd-gates-cp-d-baseline-reduction-design.md`の変更を適用し、CP-Dの常時起動reviewerを3本（correctness/test/maintainability）→2本（correctness/test）に削減し、maintainabilityをsecurity/performanceと同じ条件付き起動（構造変更フラグ）に揃える。

**Architecture:** 対象5ファイルはすべてMarkdown指示文書で、コード・自動テストを持たない。各タスクは「現在の正確な文言→新しい文言」への置換として完全に事前確定されている（探索・判断の余地はない）。実行はExecution Handoff節で述べる方式に従う。

**Tech Stack:** Markdown（対象ファイルはすべて `~/.claude/skills/tdd-gates/` および `~/.claude/agents/tdd-evaluator.md` の実体。`my-claude/claude/` はミラーのため直接編集しない）。

## Global Constraints

- 変更対象は `~/.claude/skills/tdd-gates/` 配下（`references/checkpoints.md`・`SKILL.md`・`templates/final-scorecard-review-prompt.md`・`templates/plan-quality-review-addendum.md`）と `~/.claude/agents/tdd-evaluator.md` の実体ファイルのみ。`my-claude/claude/` は編集しない。
- `~/.claude` はgitリポジトリではない。そのため各タスクに `git commit` ステップは含めない。全タスク完了後、`scripts/sync.sh`（本リポジトリから実行）が `~/.claude` → `my-claude/claude/` への同期とcommit+pushを一括で行う。
- 各エディットは「現在のファイルにこの正確な文字列が存在する」ことを前提にしている。適用前に対象箇所をRead/Grepで確認し、文字列が完全一致しない場合は実行を止めて報告する（推測で適用しない）。
- 用語は設計書の語彙に統一する: 「常時2本」「条件付き最大3本」「計2〜5本」「構造変更フラグ」。既存のsecurity/perf敏感フラグと同じ定性判定パターンに揃え、行数等のマジックナンバーは発明しない。
- CP-Dの集約ロジック・Critical判定基準（偽装テスト検出・ミューテーション検証義務）は変更しない。起動本数と、どのreviewerが常時/条件付きかのみを変更する。

---

## Task 1: checkpoints.md への反映（正典ファイル）

**Files:**
- Modify: `~/.claude/skills/tdd-gates/references/checkpoints.md`

**Cross-references:** 本タスクは正典ファイルであり、Task 2〜5はここで確定した文言（「計2〜5本」「構造変更フラグ」）を参照する。他タスクより先に実施すること。

- [ ] **Edit 1: 3ロール分離セクションのCP-D本数表記を更新**

変更前（該当行のみ）:
```
- **Evaluator役**（全CP共通）= `tdd-evaluator`。SDD が標準で使う汎用 task reviewer / final code-reviewer を、CP単位で `tdd-evaluator`（または CP-D の review-*条件付き3〜5本＋集約、CP-F の doc-verifier・review-doc-readability）に差し替える。
```

変更後:
```
- **Evaluator役**（全CP共通）= `tdd-evaluator`。SDD が標準で使う汎用 task reviewer / final code-reviewer を、CP単位で `tdd-evaluator`（または CP-D の review-*条件付き2〜5本＋集約、CP-F の doc-verifier・review-doc-readability）に差し替える。
```

- [ ] **Edit 2: CP-D上乗せ先の本数表記を更新**

変更前:
```
- **上乗せ先**: SDDの「## Final Review」。`requesting-code-review/code-reviewer.md`の単独ディスパッチを、review-*条件付き3〜5本並列起動＋`tdd-evaluator`集約に差し替える（`templates/final-scorecard-review-prompt.md`、Phase2）。
```

変更後:
```
- **上乗せ先**: SDDの「## Final Review」。`requesting-code-review/code-reviewer.md`の単独ディスパッチを、review-*条件付き2〜5本並列起動＋`tdd-evaluator`集約に差し替える（`templates/final-scorecard-review-prompt.md`、Phase2）。
```

- [ ] **Edit 3: CP-D担当をmaintainability条件付き化に更新**

変更前:
```
- **担当**: MainがCP-Bのsecurity/perf敏感フラグに基づき`review-*`を**条件付き並列起動**する——`review-correctness`／`review-test`／`review-maintainability`は常時起動、`review-security`／`review-performance`はCP-Bで該当と判定された場合のみ追加起動（計3〜5本）。`tdd-evaluator`が1枚のスコアカードに集約＋Critical判定。**各reviewerには所見をscratchpadの所見ファイルに直接書き出させ**（例`reviews/<タスクスラッグ>-cp-d-<dimension>.md`）、`tdd-evaluator`がそのファイル群を自らReadして集約採点する（review-*は所見のみ、tdd-evaluatorが点数化）。Mainは所見本文を要約・改変せず経路から外れる。
```

変更後:
```
- **担当**: MainがCP-Bの構造変更フラグ・security/perf敏感フラグに基づき`review-*`を**条件付き並列起動**する——`review-correctness`／`review-test`は常時起動、`review-maintainability`はCP-Bで構造変更ありと判定された場合のみ、`review-security`／`review-performance`はCP-Bで該当と判定された場合のみ追加起動（計2〜5本）。`tdd-evaluator`が1枚のスコアカードに集約＋Critical判定。**各reviewerには所見をscratchpadの所見ファイルに直接書き出させ**（例`reviews/<タスクスラッグ>-cp-d-<dimension>.md`）、`tdd-evaluator`がそのファイル群を自らReadして集約採点する（review-*は所見のみ、tdd-evaluatorが点数化）。Mainは所見本文を要約・改変せず経路から外れる。
```

- [ ] **Edit 4: CP-D採点項目をmaintainability条件付き化に更新**

変更前:
```
- **採点項目**: 起動した次元それぞれ（常時: 正確性／テスト品質／保守性。条件付き: セキュリティ／性能）。
```

変更後:
```
- **採点項目**: 起動した次元それぞれ（常時: 正確性／テスト品質。条件付き: 保守性／セキュリティ／性能）。
```

- [ ] **Edit 5: 文書レビューパターン節の本数表記を更新**

変更前:
```
要件定義書・設計文書・計画書など**文書・設計成果物**の品質を問うとき（CP-Aの要件整理レビュー・CP-Fの大規模doc整備・TDD文脈外の文書レビュー）は、次元別チェックリスト（コード用のreview-*、条件付き3〜5次元）の代わりに**命題駆動の敵対レビュー**を使ってよい。**コード差分のCP-Dはこのパターンで置き換えない**（review-*の次元別チェックリストが確立済みのため現行維持）。
```

変更後:
```
要件定義書・設計文書・計画書など**文書・設計成果物**の品質を問うとき（CP-Aの要件整理レビュー・CP-Fの大規模doc整備・TDD文脈外の文書レビュー）は、次元別チェックリスト（コード用のreview-*、条件付き2〜5次元）の代わりに**命題駆動の敵対レビュー**を使ってよい。**コード差分のCP-Dはこのパターンで置き換えない**（review-*の次元別チェックリストが確立済みのため現行維持）。
```

- [ ] **Step 6: 検証**

```bash
grep -n "3〜5本\|3〜5次元" ~/.claude/skills/tdd-gates/references/checkpoints.md
```

期待結果: 0件（すべて「2〜5本」「2〜5次元」に置き換わっている）。

---

## Task 2: SKILL.md への反映

**Files:**
- Modify: `~/.claude/skills/tdd-gates/SKILL.md`

**Cross-references:** Task 1で確定した「2〜5本」の語彙を使う。

- [ ] **Edit 1: CP対応表のCP-D行を本数更新**

変更前:
```
| CP-D 最終スコアカード（旧8） | SDD Final Review の `code-reviewer.md` を差し替え | `review-*`条件付き3〜5本並列→`tdd-evaluator`集約（ミューテーション検証必須） | SDD純正のFinal Review（1修正波+1 scoped re-review） |
```

変更後:
```
| CP-D 最終スコアカード（旧8） | SDD Final Review の `code-reviewer.md` を差し替え | `review-*`条件付き2〜5本並列→`tdd-evaluator`集約（ミューテーション検証必須） | SDD純正のFinal Review（1修正波+1 scoped re-review） |
```

- [ ] **Edit 2: 受け入れチェックリスト生成の説明を本数更新**

変更前（該当文のみ）:
```
この受け入れ確認の際、`tdd-evaluator` が受け入れチェックリスト（受入基準＋CP-Dの実施次元（3〜5本）＋CP-E/Fの整備状況＋例外処理・権限漏れ・変更影響範囲）を生成する。
```

変更後:
```
この受け入れ確認の際、`tdd-evaluator` が受け入れチェックリスト（受入基準＋CP-Dの実施次元（2〜5本）＋CP-E/Fの整備状況＋例外処理・権限漏れ・変更影響範囲）を生成する。
```

- [ ] **Step 3: 検証**

```bash
grep -n "3〜5本" ~/.claude/skills/tdd-gates/SKILL.md
```

期待結果: 0件。

---

## Task 3: final-scorecard-review-prompt.md への反映

**Files:**
- Modify: `~/.claude/skills/tdd-gates/templates/final-scorecard-review-prompt.md`

**Cross-references:** Task 1で確定した語彙を使う。

- [ ] **Edit 1: 冒頭説明文の本数更新**

変更前:
```
SDD の「## Final Review」は既定で `code-reviewer.md` を単独ディスパッチする。CP-D はこの単独ディスパッチを、**review-*（条件付き3〜5本）の並列起動 + `tdd-evaluator` 集約**に丸ごと差し替える。本ファイルは土台テンプレの本文を複製せず、差し替え後の手順のみを記述する（各 reviewer の詳細チェックリストは `~/.claude/agents/review-*.md` と `~/.claude/agents/references/review.md` が正典）。
```

変更後:
```
SDD の「## Final Review」は既定で `code-reviewer.md` を単独ディスパッチする。CP-D はこの単独ディスパッチを、**review-*（条件付き2〜5本）の並列起動 + `tdd-evaluator` 集約**に丸ごと差し替える。本ファイルは土台テンプレの本文を複製せず、差し替え後の手順のみを記述する（各 reviewer の詳細チェックリストは `~/.claude/agents/review-*.md` と `~/.claude/agents/references/review.md` が正典）。
```

- [ ] **Edit 2: 手順1をmaintainability条件付き化に更新**

変更前:
```
`superpowers:dispatching-parallel-agents` の機構に従い、次のエージェントを**同一メッセージ内で並列**に起動する。逐次起動しない。

- **常時起動**: `review-correctness` / `review-test` / `review-maintainability`
- **条件付き起動**（CP-Bのsecurity/perf敏感フラグに基づく）: `review-security`（security敏感と判定された場合のみ）／`review-performance`（perf敏感と判定された場合のみ）

起動本数は3〜5本になる。各エージェントへの指示に、対象の `[BASE_SHA]`・`[HEAD_SHA]`（土台テンプレと同じプレースホルダ）と、**所見の書き出し先ファイルパス**を明記する。
```

変更後:
```
`superpowers:dispatching-parallel-agents` の機構に従い、次のエージェントを**同一メッセージ内で並列**に起動する。逐次起動しない。

- **常時起動**: `review-correctness` / `review-test`
- **条件付き起動**（CP-Bの構造変更フラグ・security/perf敏感フラグに基づく）: `review-maintainability`（構造変更ありと判定された場合のみ）／`review-security`（security敏感と判定された場合のみ）／`review-performance`（perf敏感と判定された場合のみ）

起動本数は2〜5本になる。各エージェントへの指示に、対象の `[BASE_SHA]`・`[HEAD_SHA]`（土台テンプレと同じプレースホルダ）と、**所見の書き出し先ファイルパス**を明記する。
```

- [ ] **Edit 3: 手順2を本数・次元表記の更新**

変更前:
```
Main は `tdd-evaluator` を起動し、上記の起動された全ファイル（3〜5本）のパス一覧を渡す。その際 description は `"CP-D: Aggregate and score review files"` とする。`tdd-evaluator` は次を行う。

1. 渡されたファイルすべてを自ら Read する（Main による要約・選別を経由しない）。
2. 所見ファイル数がMainから伝えられた起動本数（3〜5本）と一致するか照合する。不足があれば採点せず、不足次元を明記して Main に差し戻す。
3. `~/.claude/skills/tdd-gates/references/scoring.md`「スコアカード出力形式（CP-C〜F用）」の Spec Compliance 形式に集約する。起動した次元（常時: 正確性／テスト品質／保守性。条件付き: セキュリティ／性能）それぞれの所見を反映する。
```

変更後:
```
Main は `tdd-evaluator` を起動し、上記の起動された全ファイル（2〜5本）のパス一覧を渡す。その際 description は `"CP-D: Aggregate and score review files"` とする。`tdd-evaluator` は次を行う。

1. 渡されたファイルすべてを自ら Read する（Main による要約・選別を経由しない）。
2. 所見ファイル数がMainから伝えられた起動本数（2〜5本）と一致するか照合する。不足があれば採点せず、不足次元を明記して Main に差し戻す。
3. `~/.claude/skills/tdd-gates/references/scoring.md`「スコアカード出力形式（CP-C〜F用）」の Spec Compliance 形式に集約する。起動した次元（常時: 正確性／テスト品質。条件付き: 保守性／セキュリティ／性能）それぞれの所見を反映する。
```

- [ ] **Step 4: 検証**

```bash
grep -n "3〜5本\|review-test\` / \`review-maintainability" ~/.claude/skills/tdd-gates/templates/final-scorecard-review-prompt.md
```

期待結果: いずれも0件。

---

## Task 4: tdd-evaluator.md への反映

**Files:**
- Modify: `~/.claude/agents/tdd-evaluator.md`

**Cross-references:** Task 1で確定した語彙を使う。

- [ ] **Edit 1: frontmatter descriptionの本数更新**

変更前（該当部分のみ）:
```
CP-D は review-*（条件付き3〜5本）の所見を集約してミューテーション検証込みで最終スコアカード化、
```

変更後:
```
CP-D は review-*（条件付き2〜5本）の所見を集約してミューテーション検証込みで最終スコアカード化、
```

- [ ] **Edit 2: 入力セクションCP-Dの本数・次元表記を更新**

変更前:
```
- **CP-D（最終スコアカード）**: Main が条件付き並列起動した `review-*`（3〜5本。常時: correctness/test/maintainability、条件付き: security/performance）が scratchpad に書き出した**所見ファイルのパス一覧**。各ファイルを**あなた自身が Read** して集約する（Main の要約・選別を介さない＝工程当事者による Critical 所見の軟化を排除）。プロンプトの組み立ては `templates/final-scorecard-review-prompt.md` に従う。
```

変更後:
```
- **CP-D（最終スコアカード）**: Main が条件付き並列起動した `review-*`（2〜5本。常時: correctness/test、条件付き: maintainability/security/performance）が scratchpad に書き出した**所見ファイルのパス一覧**。各ファイルを**あなた自身が Read** して集約する（Main の要約・選別を介さない＝工程当事者による Critical 所見の軟化を排除）。プロンプトの組み立ては `templates/final-scorecard-review-prompt.md` に従う。
```

- [ ] **Edit 3: 所見の充足チェックの本数表記を更新**

変更前:
```
**所見の充足チェック（CP-D、および CP-B で条件付き reviewer を起動した場合）**: 採点前に所見ファイル数を既定本数（CP-D=Mainが起動時に指定した本数（CP-Bのsecurity/perf敏感フラグに基づく3〜5本）。CP-Bは条件付き起動時のみ、起動した本数）と照合する。不足していれば**採点せず、不足次元を明記して Main に差し戻す**（自分で観点を補って代替しない——reviewer 層の欠落を無音で吸収すると集約採点が単独レビューに縮退するため）。自力で `git diff` と対象ファイルを Read して観点を補ってよいのは、**単独起動（TDD 文脈外の汎用レビュー）**・**CP-A／既定のCP-B（evaluator 単独）**・**CP-C のように reviewer 所見が工程上存在しないCP**のみ。
```

変更後:
```
**所見の充足チェック（CP-D、および CP-B で条件付き reviewer を起動した場合）**: 採点前に所見ファイル数を既定本数（CP-D=Mainが起動時に指定した本数（CP-Bの構造変更フラグ・security/perf敏感フラグに基づく2〜5本）。CP-Bは条件付き起動時のみ、起動した本数）と照合する。不足していれば**採点せず、不足次元を明記して Main に差し戻す**（自分で観点を補って代替しない——reviewer 層の欠落を無音で吸収すると集約採点が単独レビューに縮退するため）。自力で `git diff` と対象ファイルを Read して観点を補ってよいのは、**単独起動（TDD 文脈外の汎用レビュー）**・**CP-A／既定のCP-B（evaluator 単独）**・**CP-C のように reviewer 所見が工程上存在しないCP**のみ。
```

- [ ] **Edit 4: 受け入れチェックリスト生成の本数表記を更新**

変更前:
```
**受け入れチェックリスト生成（CP-F 完了後の受け入れ確認時）**: 依頼されたら、受入基準（CP-B）＋品質観点（CP-D の実施次元、3〜5本）＋CP-E/Fの整備状況＋観点（例外処理・権限漏れ・変更影響範囲）から**再現可能な受け入れチェックリスト**を機械的に導出して返す（台帳保存は Main）。
```

変更後:
```
**受け入れチェックリスト生成（CP-F 完了後の受け入れ確認時）**: 依頼されたら、受入基準（CP-B）＋品質観点（CP-D の実施次元、2〜5本）＋CP-E/Fの整備状況＋観点（例外処理・権限漏れ・変更影響範囲）から**再現可能な受け入れチェックリスト**を機械的に導出して返す（台帳保存は Main）。
```

- [ ] **Step 5: 検証**

```bash
grep -n "3〜5本" ~/.claude/agents/tdd-evaluator.md
```

期待結果: 0件。

---

## Task 5: plan-quality-review-addendum.md への反映（差分8新設）

**Files:**
- Modify: `~/.claude/skills/tdd-gates/templates/plan-quality-review-addendum.md`

**Cross-references:** 差分6（security/perf敏感タスクの印付け）と同じ判定タイミング（CP-B）・同じ定性判定パターンに揃える。

- [ ] **Edit 1: 差分8を新設（差分7の直後、プレースホルダ節の直前）**

変更前:
```
## 差分7: 追加セクション「タスク粒度の適正さ監査」

> ## タスク粒度の適正さ監査（tdd-gates 追加）
>
> 計画中の各タスクの粒度を0–3点で採点する（`references/scoring.md`の項目スコアに準拠。0=Missing/1=Partial/2=Good/3=Excellent）。
> - **過剰分割の兆候**: 隣接タスクが同一ファイル群への変更で、互いに独立してレビュー・承認・却下する意味が無い（一方だけ却下してもう一方だけ承認する状況が想定できない）場合、減点し統合を推奨する。
> - **過小分割（バンドル）の兆候**: 1タスクに複数の独立した振る舞い変更が含まれ、個別にテスト・レビュー可能な単位へ分割できるにも関わらず1タスクにまとめられている場合、減点し分割を推奨する。
> - Criticalには追加しない（品質・効率観点のためスコア率にのみ反映する）。判定基準はwriting-plansの「Task Right-Sizing」原則（隣接タスクを承認しつつ当該タスクだけを却下しうる境界でのみ分割する）を援用し、新しい基準は発明しない。

## ディスパッチ時に Main が埋めるプレースホルダ
```

変更後:
```
## 差分7: 追加セクション「タスク粒度の適正さ監査」

> ## タスク粒度の適正さ監査（tdd-gates 追加）
>
> 計画中の各タスクの粒度を0–3点で採点する（`references/scoring.md`の項目スコアに準拠。0=Missing/1=Partial/2=Good/3=Excellent）。
> - **過剰分割の兆候**: 隣接タスクが同一ファイル群への変更で、互いに独立してレビュー・承認・却下する意味が無い（一方だけ却下してもう一方だけ承認する状況が想定できない）場合、減点し統合を推奨する。
> - **過小分割（バンドル）の兆候**: 1タスクに複数の独立した振る舞い変更が含まれ、個別にテスト・レビュー可能な単位へ分割できるにも関わらず1タスクにまとめられている場合、減点し分割を推奨する。
> - Criticalには追加しない（品質・効率観点のためスコア率にのみ反映する）。判定基準はwriting-plansの「Task Right-Sizing」原則（隣接タスクを承認しつつ当該タスクだけを却下しうる境界でのみ分割する）を援用し、新しい基準は発明しない。

## 差分8: 追加セクション「構造変更タスクの印付け」

> ## 構造変更タスクの印付け（tdd-gates 追加）
>
> 計画中の各タスクが構造変更（新規ファイル/ディレクトリの追加、責務分割の変更、命名体系の変更等）を伴うかを判定し、該当タスクにタグを付ける。タグを付けたタスクが1つでもあれば、CP-Dで`review-maintainability`を条件付きで追加起動する（`templates/final-scorecard-review-prompt.md`「手順1」参照）。行数等のマジックナンバーは判定に使わない。security/perf敏感タスクの印付け（差分6）と同じ判定タイミング（CP-B）・同じ定性判定パターンに揃える。

## ディスパッチ時に Main が埋めるプレースホルダ
```

- [ ] **Step 2: 検証**

```bash
grep -n "差分8" ~/.claude/skills/tdd-gates/templates/plan-quality-review-addendum.md
```

期待結果: 見出し行を含め1件以上。

---

## 全タスク完了後: 横断検証

```bash
grep -rn "3〜5本\|3〜5次元" ~/.claude/skills/tdd-gates/ ~/.claude/agents/tdd-evaluator.md
```

期待結果: 0件（すべて「2〜5本」「2〜5次元」に置換済み）。

```bash
grep -rn "構造変更フラグ\|構造変更タスクの印付け" ~/.claude/skills/tdd-gates/ ~/.claude/agents/tdd-evaluator.md
```

期待結果: 4件以上（checkpoints.md CP-D「担当」行、final-scorecard-review-prompt.md「手順1」、tdd-evaluator.md「所見の充足チェック」、plan-quality-review-addendum.md「差分8」見出し＋本文）。

## 実行方式（Execution Handoff）

標準のwriting-plansは「Subagent-Driven（SDD）」「Inline Execution（executing-plans）」の二択を提示するが、本計画には適用しない。理由（`docs/plans/2026-08-02-tdd-gates-lightweight-plan.md`と同じ前例に従う）:

1. 対象がすべてMarkdown指示文書の編集であり、コード・自動テストが存在しない。SDDのRED/GREEN検証・独立レビュアーによる自己承認排除は、テストの無いプロース編集には適用対象がない。
2. `~/.claude`はgitリポジトリではないため、SDDの前提（各タスクがgit commitを生み、ledgerがコミットハッシュを記録して復旧する）が機能しない。
3. 全編集は本計画内で完全に事前確定されている（探索・判断の余地がない「内容が事前確定したexact-edit」に該当）。

**推奨する実行方式**: Main（またはMainが直接委任する一括実行）が、Task 1〜5を順に、各Editの通りにEditツールで適用する。各タスクの検証ステップ（grep）で確認しながら進める。全タスク完了後、本リポジトリから`scripts/sync.sh`を実行して`~/.claude`の変更を`my-claude`へ同期・commit・pushする。
