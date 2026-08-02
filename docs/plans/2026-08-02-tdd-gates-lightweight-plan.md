# tdd-gates 軽量化 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: 本計画はコード・テストを持たないMarkdown指示文書の編集のみで構成される。詳細は「実行方式（Execution Handoff）」節を参照——標準のsubagent-driven-development/executing-plansの二択とは異なる方式を採る。

**Goal:** `tdd-gates`（`~/.claude/skills/tdd-gates/`・`~/.claude/agents/tdd-evaluator.md`）に、設計書`docs/specs/2026-08-02-tdd-gates-lightweight-design.md`の4つの変更＋前提の是正を適用し、CP-Cの証拠取得コストとCP-Dの起動本数を圧縮する。

**Architecture:** 対象8ファイルはすべてMarkdown指示文書で、コード・自動テストを持たない。各タスクは「現在の正確な文言→新しい文言」への置換として完全に事前確定されている（探索・判断の余地はない）。実行はExecution Handoff節で述べる方式に従う。

**Tech Stack:** Markdown（対象ファイルはすべて `~/.claude/skills/tdd-gates/` および `~/.claude/agents/tdd-evaluator.md` の実体。`my-claude/claude/` はミラーのため直接編集しない）。

## Global Constraints

- 変更対象は `~/.claude/skills/tdd-gates/` 配下と `~/.claude/agents/tdd-evaluator.md` の実体ファイルのみ。`my-claude/claude/` は編集しない。
- `~/.claude` はgitリポジトリではない（`git -C ~/.claude rev-parse --is-inside-work-tree` で確認済み）。そのため各タスクに `git commit` ステップは含めない。全タスク完了後、`scripts/sync.sh`（本リポジトリから実行）が `~/.claude` → `my-claude/claude/` への同期とcommit+pushを一括で行う。
- 各エディットは「現在のファイルにこの正確な文字列が存在する」ことを前提にしている。適用前に対象箇所をRead/Grepで確認し、文字列が完全一致しない場合は実行を止めて報告する（推測で適用しない）。
- 用語は設計書の語彙に統一する: 「small-route」「security/perf敏感」「evaluatorモデル階層化」「条件付き3〜5本」。新しい語彙を発明しない。

---

## Task 1: checkpoints.md への反映（正典ファイル）

**Files:**
- Modify: `~/.claude/skills/tdd-gates/references/checkpoints.md`

**Cross-references:** 本タスクは正典ファイルであり、Task 2〜8はここで確定した文言（「evaluatorモデル階層化」「条件付き3〜5本」等）を参照する。他タスクより先に実施すること。

- [ ] **Edit 1: 3ロール分離セクションのCP-D記述を条件付き化**

変更前（該当行のみ）:
```
- **Evaluator役**（全CP共通）= `tdd-evaluator`。SDD が標準で使う汎用 task reviewer / final code-reviewer を、CP単位で `tdd-evaluator`（または CP-D の review-*5本＋集約、CP-F の doc-verifier・review-doc-readability）に差し替える。
```

変更後:
```
- **Evaluator役**（全CP共通）= `tdd-evaluator`。SDD が標準で使う汎用 task reviewer / final code-reviewer を、CP単位で `tdd-evaluator`（または CP-D の review-*条件付き3〜5本＋集約、CP-F の doc-verifier・review-doc-readability）に差し替える。
```

- [ ] **Edit 2: CP-B採点項目にタスク粒度の妥当性を追加**

変更前:
```
- **採点項目**: 受入基準の明確さ・検証可能性／シナリオ網羅（正常・異常・境界）／テスト種別の妥当性・3層割り当て／トレーサビリティ／既存構造の把握／セキュリティ観点（権限漏れ含む）／業務ロジックの分離（unitテスト可能性）／ファイルサイズ・責務分割（`review-maintainability` の基準に従う）。
```

変更後:
```
- **採点項目**: 受入基準の明確さ・検証可能性／シナリオ網羅（正常・異常・境界）／テスト種別の妥当性・3層割り当て／トレーサビリティ／既存構造の把握／セキュリティ観点（権限漏れ含む）／業務ロジックの分離（unitテスト可能性）／ファイルサイズ・責務分割（`review-maintainability` の基準に従う）／タスク粒度の妥当性（過剰分割・過小分割の検査、`templates/plan-quality-review-addendum.md`差分7）。
```

- [ ] **Edit 3: CP-C見出しをSDD限定に是正**

変更前:
```
## CP-C: タスク証拠検証（旧Gate4-7・SDD/executing-plans に寄生）
```

変更後:
```
## CP-C: タスク証拠検証（旧Gate4-7・SDD に寄生）
```

- [ ] **Edit 4: CP-C上乗せ先をSDD限定に是正**

変更前:
```
- **上乗せ先**: `subagent-driven-development`（または `executing-plans`）の「### 3. Review the task」ステップ。SDDが標準ディスパッチする `task-reviewer-prompt.md` を、tdd-gates版アドオン（`templates/task-evidence-addendum.md`、Phase2）を追記したプロンプトに差し替える。
```

変更後:
```
- **上乗せ先**: `subagent-driven-development`の「### 3. Review the task」ステップ。SDDが標準ディスパッチする `task-reviewer-prompt.md` を、tdd-gates版アドオン（`templates/task-evidence-addendum.md`、Phase2）を追記したプロンプトに差し替える。`executing-plans`は独立レビュアーへのdispatchステップを持たず、実装者と評価者の分離が成立しないため対象外（サブエージェントへのアクセスが無い場合のフォールバックとして位置づけられており、その場合`tdd-evaluator`のdispatch自体が不可能）。
```

- [ ] **Edit 5: RED Criticalに対象テストのみ実行と明記**

変更前:
```
- **RED の Critical（即FAIL）**:
  - `tdd-evaluator` が自ら再実行し、テストが実際に失敗する（プロファイルの失敗ログ形式に一致）。「おそらく失敗する」は0点。
```

変更後:
```
- **RED の Critical（即FAIL）**:
  - `tdd-evaluator` が**対象テストのみ**（フルスイート不要）を自ら再実行し、テストが実際に失敗する（プロファイルの失敗ログ形式に一致）。「おそらく失敗する」は0点。
```

- [ ] **Edit 6: REFACTOR Criticalを条件付きスキップに変更**

変更前:
```
- **REFACTOR の Critical（即FAIL）**:
  - 新機能・新しい振る舞いを追加していない。`tdd-evaluator`が`git diff`を取得し、テストファイルとテスト設定ファイルが不変（skip/xfail等の実行除外追加を含め変更なし）かつ既存テストが到達しない新規branchが加わっていないことを確認する。
  - リファクタ後もプロファイル定義のテスト実行コマンドで全緑。
```

変更後:
```
- **REFACTOR の Critical（即FAIL）**:
  - `tdd-evaluator`がGREEN確定コミット〜現在HEADの`git diff`を自ら取得する。**差分が空なら**GREENで確認済みの全緑結果を援用し、以下のフルスイート再実行を**省略**してよい（軽量化。`references/profiles/*.md`「CP-C証拠ルール」参照）。**差分がある場合**は以下を通常通り検証する。
  - 新機能・新しい振る舞いを追加していない。テストファイルとテスト設定ファイルが不変（skip/xfail等の実行除外追加を含め変更なし）かつ既存テストが到達しない新規branchが加わっていないことを確認する。
  - リファクタ後もプロファイル定義のテスト実行コマンドで全緑。
```

- [ ] **Edit 7: CP-C節にevaluatorモデル階層化を新設**

「UI/UX条件付き検査」の行の直後・「リトライ機構」の行の直前に、新しい箇条書きを1行挿入する。

変更前（該当2行の連続部分）:
```
- **UI/UX条件付き検査**: テスト種別がe2e（ブラウザ）、または**テンプレート/ルーティング/ビュー層に変更がある場合**（unit申告でも回避不可）、`frontend-design`スキル＋敵対的クロスレビューを追加で必須化する。最大3ラウンド（確認→修正）。ブラウザ不可環境は静的解析で代替する。
- **リトライ機構**: **SDD純正の5ラウンドfix loopをそのまま使用**（独自カウンタ・独自CONDITIONALは持たない）。出力形式はSDD互換のSpec Compliance形式（`scoring.md`のCP-C〜F用）。
```

変更後:
```
- **UI/UX条件付き検査**: テスト種別がe2e（ブラウザ）、または**テンプレート/ルーティング/ビュー層に変更がある場合**（unit申告でも回避不可）、`frontend-design`スキル＋敵対的クロスレビューを追加で必須化する。最大3ラウンド（確認→修正）。ブラウザ不可環境は静的解析で代替する。
- **evaluatorモデル階層化（軽量化）**: `tdd-evaluator`をディスパッチするモデルは、CP-Bが確定したsmall-route判定を再利用する。small-route該当タスクは`haiku`、それ以外の全タスク（security/perf敏感タスクを含む）は現行の`sonnet`を指定する。CP-E（同じタスクループに乗る）も同じ規則に従う。新たな判定ロジックは追加しない。
- **リトライ機構**: **SDD純正の5ラウンドfix loopをそのまま使用**（独自カウンタ・独自CONDITIONALは持たない）。出力形式はSDD互換のSpec Compliance形式（`scoring.md`のCP-C〜F用）。
```

- [ ] **Edit 8: CP-D上乗せ先を条件付き本数に更新**

変更前:
```
- **上乗せ先**: SDDの「## Final Review」。`requesting-code-review/code-reviewer.md`の単独ディスパッチを、review-*5本並列起動＋`tdd-evaluator`集約に差し替える（`templates/final-scorecard-review-prompt.md`、Phase2）。
```

変更後:
```
- **上乗せ先**: SDDの「## Final Review」。`requesting-code-review/code-reviewer.md`の単独ディスパッチを、review-*条件付き3〜5本並列起動＋`tdd-evaluator`集約に差し替える（`templates/final-scorecard-review-prompt.md`、Phase2）。
```

- [ ] **Edit 9: CP-D担当を条件付き起動に更新**

変更前:
```
- **担当**: Mainが`review-*`5次元（correctness/security/performance/test/maintainability）を**並列起動**し、`tdd-evaluator`が1枚のスコアカードに集約＋Critical判定。**各reviewerには所見をscratchpadの所見ファイルに直接書き出させ**（例`reviews/<タスクスラッグ>-cp-d-<dimension>.md`）、`tdd-evaluator`がそのファイル群を自らReadして集約採点する（review-*は所見のみ、tdd-evaluatorが点数化）。Mainは所見本文を要約・改変せず経路から外れる。
```

変更後:
```
- **担当**: MainがCP-Bのsecurity/perf敏感フラグに基づき`review-*`を**条件付き並列起動**する——`review-correctness`／`review-test`／`review-maintainability`は常時起動、`review-security`／`review-performance`はCP-Bで該当と判定された場合のみ追加起動（計3〜5本）。`tdd-evaluator`が1枚のスコアカードに集約＋Critical判定。**各reviewerには所見をscratchpadの所見ファイルに直接書き出させ**（例`reviews/<タスクスラッグ>-cp-d-<dimension>.md`）、`tdd-evaluator`がそのファイル群を自らReadして集約採点する（review-*は所見のみ、tdd-evaluatorが点数化）。Mainは所見本文を要約・改変せず経路から外れる。
```

- [ ] **Edit 10: CP-D採点項目を起動した次元のみに更新**

変更前:
```
- **採点項目**: 5次元それぞれ（正確性／セキュリティ／性能／テスト品質／保守性）。
```

変更後:
```
- **採点項目**: 起動した次元それぞれ（常時: 正確性／テスト品質／保守性。条件付き: セキュリティ／性能）。
```

- [ ] **Edit 11: CP-E上乗せ先をSDD限定に是正**

変更前:
```
- **上乗せ先**: `writing-plans`が条件を満たせば、計画の末尾タスクとして自動追加する（`templates/ci-gate-task-template.md`、Phase2。writing-plansの Task Structure 形式に沿う）。追加後はCP-Cと同じ仕組み（SDD/executing-plansの通常タスクループ）に乗る——CP-Eは「タスクの中身」を規定するだけで、独自のディスパッチ・リトライ機構は持たない。
```

変更後:
```
- **上乗せ先**: `writing-plans`が条件を満たせば、計画の末尾タスクとして自動追加する（`templates/ci-gate-task-template.md`、Phase2。writing-plansの Task Structure 形式に沿う）。追加後はCP-Cと同じ仕組み（SDDの通常タスクループ）に乗る——CP-Eは「タスクの中身」を規定するだけで、独自のディスパッチ・リトライ機構は持たない。
```

- [ ] **Edit 12: 文書レビューパターン節の「review-*5次元」を可変本数の表現に更新**

変更前:
```
要件定義書・設計文書・計画書など**文書・設計成果物**の品質を問うとき（CP-Aの要件整理レビュー・CP-Fの大規模doc整備・TDD文脈外の文書レビュー）は、次元別チェックリスト（コード用のreview-*5次元）の代わりに**命題駆動の敵対レビュー**を使ってよい。**コード差分のCP-Dはこのパターンで置き換えない**（review-*5次元のチェックリストが確立済みのため現行維持）。
```

変更後:
```
要件定義書・設計文書・計画書など**文書・設計成果物**の品質を問うとき（CP-Aの要件整理レビュー・CP-Fの大規模doc整備・TDD文脈外の文書レビュー）は、次元別チェックリスト（コード用のreview-*、条件付き3〜5次元）の代わりに**命題駆動の敵対レビュー**を使ってよい。**コード差分のCP-Dはこのパターンで置き換えない**（review-*の次元別チェックリストが確立済みのため現行維持）。
```

- [ ] **Step 13: 検証**

```bash
grep -n "executing-plans\|5本\|5次元" ~/.claude/skills/tdd-gates/references/checkpoints.md
```

期待結果: いずれも0件（すべて「条件付き3〜5本」「条件付き3〜5次元」等に置き換わっている）。

---

## Task 2: SKILL.md への反映

**Files:**
- Modify: `~/.claude/skills/tdd-gates/SKILL.md`

**Cross-references:** Task 1で確定した「SDD限定」「条件付き3〜5本」の語彙を使う。

- [ ] **Edit 1: frontmatter descriptionのexecuting-plans併記を削除**

変更前（該当行のみ）:
```
  superpowers のスキルチェーン（brainstorming → writing-plans → subagent-driven-development/executing-plans → finishing-a-development-branch）に上乗せする品質規律レイヤー。
```

変更後:
```
  superpowers のスキルチェーン（brainstorming → writing-plans → subagent-driven-development → finishing-a-development-branch）に上乗せする品質規律レイヤー。
```

- [ ] **Edit 2: 証拠の記録先セクションのexecuting-plans併記を削除**

変更前（該当文のみ）:
```
**CP-C 以降は SDD（`subagent-driven-development` または `executing-plans`）の `progress.md` に証拠行（RED/GREEN コマンドと出力）を追記する形に統一**し、
```

変更後:
```
**CP-C 以降は SDD（`subagent-driven-development`）の `progress.md` に証拠行（RED/GREEN コマンドと出力）を追記する形に統一**し、
```

- [ ] **Edit 3: superpowersチェーン起動セクションのexecuting-plans併記を削除**

変更前（該当文のみ）:
```
CP-C 以降のタスク単位の todo は SDD/executing-plans が自前で作成するため、tdd-gates 側で重複して作らない。
```

変更後:
```
CP-C 以降のタスク単位の todo は SDD が自前で作成するため、tdd-gates 側で重複して作らない。
```

- [ ] **Edit 4: CP対応表のCP-C行をSDD限定に更新**

変更前:
```
| CP-C タスク証拠検証（旧4-7） | SDD/executing-plans の task-reviewer ディスパッチを差し替え（汎用reviewerでなく`tdd-evaluator`）。UI/UX・security/perfは条件付き追加 | `tdd-evaluator` | SDD純正の5ラウンドfix loopをそのまま使用（独自カウンタは持たない） |
```

変更後:
```
| CP-C タスク証拠検証（旧4-7） | SDD の task-reviewer ディスパッチを差し替え（汎用reviewerでなく`tdd-evaluator`）。UI/UX・security/perfは条件付き追加 | `tdd-evaluator` | SDD純正の5ラウンドfix loopをそのまま使用（独自カウンタは持たない） |
```

- [ ] **Edit 5: CP対応表のCP-D行を条件付き本数に更新**

変更前:
```
| CP-D 最終スコアカード（旧8） | SDD Final Review の `code-reviewer.md` を差し替え | `review-*`5本並列→`tdd-evaluator`集約（ミューテーション検証必須） | SDD純正のFinal Review（1修正波+1 scoped re-review） |
```

変更後:
```
| CP-D 最終スコアカード（旧8） | SDD Final Review の `code-reviewer.md` を差し替え | `review-*`条件付き3〜5本並列→`tdd-evaluator`集約（ミューテーション検証必須） | SDD純正のFinal Review（1修正波+1 scoped re-review） |
```

- [ ] **Edit 6: 冒頭説明文の「5次元専門レビュアー」を可変本数の表現に更新**

変更前:
```
あなた（Main）は、superpowers のスキルチェーンを背骨として使う。tdd-gates は自前の駆動ループを持たない。チェーンの各ステップに寄生してチェックポイント（CP-A〜F）を差し込み、「証拠不信の原則」「5次元専門レビュアー」「0–3点採点語彙・Critical即FAIL」を、そのステップの担当エージェントに上乗せするだけの薄いレイヤーである。
```

変更後:
```
あなた（Main）は、superpowers のスキルチェーンを背骨として使う。tdd-gates は自前の駆動ループを持たない。チェーンの各ステップに寄生してチェックポイント（CP-A〜F）を差し込み、「証拠不信の原則」「専門レビュアーによる多次元評価」「0–3点採点語彙・Critical即FAIL」を、そのステップの担当エージェントに上乗せするだけの薄いレイヤーである。
```

- [ ] **Edit 7: 受け入れチェックリスト生成の説明にある「CP-Dの5次元」を更新**

変更前（該当文のみ）:
```
この受け入れ確認の際、`tdd-evaluator` が受け入れチェックリスト（受入基準＋CP-Dの5次元＋CP-E/Fの整備状況＋例外処理・権限漏れ・変更影響範囲）を生成する。
```

変更後:
```
この受け入れ確認の際、`tdd-evaluator` が受け入れチェックリスト（受入基準＋CP-Dの実施次元（3〜5本）＋CP-E/Fの整備状況＋例外処理・権限漏れ・変更影響範囲）を生成する。
```

- [ ] **Step 8: 検証**

```bash
grep -n "executing-plans\|5本\|5次元" ~/.claude/skills/tdd-gates/SKILL.md
```

期待結果: いずれも0件。

---

## Task 3: tdd-evaluator.md への反映

**Files:**
- Modify: `~/.claude/agents/tdd-evaluator.md`

**Cross-references:** Task 1で確定した語彙を使う。

- [ ] **Edit 1: frontmatter descriptionのSDD/executing-plans併記を削除**

変更前（該当文のみ）:
```
CP-C は SDD の task-reviewer 役を差し替えて実装者の報告を自ら再実行検証、CP-D は review-*5本の所見を集約してミューテーション検証込みで最終スコアカード化、
```

変更後:
```
CP-C は SDD の task-reviewer 役を差し替えて実装者の報告を自ら再実行検証、CP-D は review-*（条件付き3〜5本）の所見を集約してミューテーション検証込みで最終スコアカード化、
```

（このfrontmatter行は元々「SDD の task-reviewer」であり `executing-plans` の併記は無いため、この行はCP-D部分のみ変更する。）

- [ ] **Edit 2: 入力セクションCP-Cの説明からexecuting-plans併記を削除**

変更前:
```
- **CP-C（タスク証拠検証）**: SDD/executing-plans の task-reviewer ディスパッチを差し替えて渡される、タスクブリーフ・実装者レポート・diff ファイルのパス（SDD 標準の `task-reviewer-prompt.md` と同じ入力群）。reviewer 所見という概念は無く、あなた自身が RED/GREEN を再実行し `git diff` を自ら取得して検証する。プロンプトの組み立ては `templates/task-evidence-addendum.md` に従う（上記「CP-C での明示的な上書き」を含む）。
```

変更後:
```
- **CP-C（タスク証拠検証）**: SDD の task-reviewer ディスパッチを差し替えて渡される、タスクブリーフ・実装者レポート・diff ファイルのパス（SDD 標準の `task-reviewer-prompt.md` と同じ入力群）。reviewer 所見という概念は無く、あなた自身が RED/GREEN を再実行し `git diff` を自ら取得して検証する。プロンプトの組み立ては `templates/task-evidence-addendum.md` に従う（上記「CP-C での明示的な上書き」を含む）。
```

- [ ] **Edit 3: 入力セクションCP-Dの説明を条件付き本数に更新**

変更前:
```
- **CP-D（最終スコアカード）**: Main が並列起動した `review-*`5本（correctness/security/performance/test/maintainability）が scratchpad に書き出した**所見ファイルのパス一覧**。各ファイルを**あなた自身が Read** して集約する（Main の要約・選別を介さない＝工程当事者による Critical 所見の軟化を排除）。プロンプトの組み立ては `templates/final-scorecard-review-prompt.md` に従う。
```

変更後:
```
- **CP-D（最終スコアカード）**: Main が条件付き並列起動した `review-*`（3〜5本。常時: correctness/test/maintainability、条件付き: security/performance）が scratchpad に書き出した**所見ファイルのパス一覧**。各ファイルを**あなた自身が Read** して集約する（Main の要約・選別を介さない＝工程当事者による Critical 所見の軟化を排除）。プロンプトの組み立ては `templates/final-scorecard-review-prompt.md` に従う。
```

- [ ] **Edit 4: 所見の充足チェックのCP-D既定本数を可変に更新**

変更前:
```
**所見の充足チェック（CP-D、および CP-B で条件付き reviewer を起動した場合）**: 採点前に所見ファイル数を既定本数（CP-D=5本。CP-Bは条件付き起動時のみ、起動した本数）と照合する。
```

変更後:
```
**所見の充足チェック（CP-D、および CP-B で条件付き reviewer を起動した場合）**: 採点前に所見ファイル数を既定本数（CP-D=Mainが起動時に指定した本数（CP-Bのsecurity/perf敏感フラグに基づく3〜5本）。CP-Bは条件付き起動時のみ、起動した本数）と照合する。
```

- [ ] **Edit 5: 採点プロセスstep3のCP-C・REDに対象テストのみ実行を明記**

変更前:
```
   - **CP-C・RED**: 対象テストを再実行し実際に失敗するか確認。加えて**テスト本体を Read** し、assert が具体的な期待値/オブジェクトを検証しているかを点検（無意味な失敗パターンの具体列挙は `checkpoints.md` の CP-C「RED の Critical」行を参照）。さらに `git diff` を自ら取得し、変更が**テストファイルのみ**（実装ファイルの変更なし）であることを確認する。
```

変更後:
```
   - **CP-C・RED**: 対象テストのみを再実行し（フルスイート不要）実際に失敗するか確認。加えて**テスト本体を Read** し、assert が具体的な期待値/オブジェクトを検証しているかを点検（無意味な失敗パターンの具体列挙は `checkpoints.md` の CP-C「RED の Critical」行を参照）。さらに `git diff` を自ら取得し、変更が**テストファイルのみ**（実装ファイルの変更なし）であることを確認する。
```

- [ ] **Edit 6: 採点プロセスstep3のCP-C・REFACTORを条件付きスキップに更新**

変更前:
```
   - **CP-C・REFACTOR**: `git diff` で**テストファイル不変**かつ新規 branch/機能の追加が無いことを確認し、全緑を再実行。
```

変更後:
```
   - **CP-C・REFACTOR**: GREEN確定コミット〜現在HEADの`git diff`を自ら取得する。**差分が空ならGREENの全緑結果を援用しフルスイート再実行を省略**してよい。差分がある場合は**テストファイル不変**かつ新規branch/機能の追加が無いことを確認し、全緑を再実行する。
```

- [ ] **Edit 7: 受け入れチェックリスト生成の説明にある「CP-Dの5次元」を更新**

変更前:
```
**受け入れチェックリスト生成（CP-F 完了後の受け入れ確認時）**: 依頼されたら、受入基準（CP-B）＋品質観点（CP-D の5次元）＋CP-E/Fの整備状況＋観点（例外処理・権限漏れ・変更影響範囲）から**再現可能な受け入れチェックリスト**を機械的に導出して返す（台帳保存は Main）。
```

変更後:
```
**受け入れチェックリスト生成（CP-F 完了後の受け入れ確認時）**: 依頼されたら、受入基準（CP-B）＋品質観点（CP-D の実施次元、3〜5本）＋CP-E/Fの整備状況＋観点（例外処理・権限漏れ・変更影響範囲）から**再現可能な受け入れチェックリスト**を機械的に導出して返す（台帳保存は Main）。
```

- [ ] **Step 8: 検証**

```bash
grep -n "executing-plans\|CP-D=5本\|review-\*5本\|CP-D の5次元" ~/.claude/agents/tdd-evaluator.md
```

期待結果: いずれも0件。

---

## Task 4: task-evidence-addendum.md への反映

**Files:**
- Modify: `~/.claude/skills/tdd-gates/templates/task-evidence-addendum.md`

**Cross-references:** Task 1のcheckpoints.md「evaluatorモデル階層化」を参照する。

- [ ] **Edit 1: 冒頭説明文のexecuting-plans併記を削除**

変更前:
```
このファイルは土台テンプレの本文を複製しない。SDD（または executing-plans）が「### 3. Review the task」でディスパッチする task-reviewer プロンプトを、Main は土台テンプレを Read した上で以下の差分を適用してから `tdd-evaluator` に差し替えて渡す。
```

変更後:
```
このファイルは土台テンプレの本文を複製しない。SDDが「### 3. Review the task」でディスパッチする task-reviewer プロンプトを、Main は土台テンプレを Read した上で以下の差分を適用してから `tdd-evaluator` に差し替えて渡す。
```

- [ ] **Edit 2: 差分2の上書き文にRED範囲とREFACTOR条件付きスキップを追記**

変更前:
```
> ## Tests（tdd-gates による上書き）
>
> 実装者（SDD implementer）が報告した RED 失敗ログ・GREEN 通過ログを、**そのままでは信用しない**。あなた（`tdd-evaluator`）自身が対象テストを Bash で再実行し、実際に失敗（RED 時点）・実際に通過（GREEN 時点）することを自分の目で確認する。再現できないログ、対象テストパスが申告と一致しないログは Critical 未達（0点）として扱う。実行コマンド・失敗/通過の判定基準は対象言語プロファイル（例 `references/profiles/pytest.md` の「Critical 証拠ルール」）に従う。
```

変更後:
```
> ## Tests（tdd-gates による上書き）
>
> 実装者（SDD implementer）が報告した RED 失敗ログ・GREEN 通過ログを、**そのままでは信用しない**。あなた（`tdd-evaluator`）自身が対象テストを Bash で再実行し、実際に失敗（RED 時点）・実際に通過（GREEN 時点）することを自分の目で確認する。**RED は対象テストのみの再実行で足り、フルスイート実行は不要**。再現できないログ、対象テストパスが申告と一致しないログは Critical 未達（0点）として扱う。実行コマンド・失敗/通過の判定基準は対象言語プロファイル（例 `references/profiles/pytest.md` の「Critical 証拠ルール」）に従う。**REFACTOR確認**は、GREEN確定コミット〜現在HEADの`git diff`を自ら取得し、差分が空ならGREENの全緑結果を援用してフルスイート再実行を省略してよい。差分があれば通常通りテストファイル不変の確認＋フルスイート再実行を行う。
```

- [ ] **Edit 3: プレースホルダ節にMODEL選択ルールへの参照を追加**

変更前:
```
## ディスパッチ時に Main が埋めるプレースホルダ

土台テンプレの `[MODEL]`・`[BRIEF_FILE]`・`[GLOBAL_CONSTRAINTS]`・`[REPORT_FILE]`・`[BASE_SHA]`・`[HEAD_SHA]`・`[DIFF_FILE]` に加えて:

- 対象言語プロファイルのパス（Critical 証拠ルールの参照先として必須明記）
- テスト種別（unit/integration/e2e）の判定結果（CP-C 内 UI/UX 追加検査の要否に直結）
- CP-B での security/perf 印付け結果（該当タスクのみ）
```

変更後:
```
## ディスパッチ時に Main が埋めるプレースホルダ

土台テンプレの `[MODEL]`・`[BRIEF_FILE]`・`[GLOBAL_CONSTRAINTS]`・`[REPORT_FILE]`・`[BASE_SHA]`・`[HEAD_SHA]`・`[DIFF_FILE]` に加えて:

- `[MODEL]`: CP-Bのsmall-route判定結果に基づき指定する（small-route該当→`haiku`、それ以外→`sonnet`。判定ルールは`checkpoints.md`CP-C「evaluatorモデル階層化」を参照）
- 対象言語プロファイルのパス（Critical 証拠ルールの参照先として必須明記）
- テスト種別（unit/integration/e2e）の判定結果（CP-C 内 UI/UX 追加検査の要否に直結）
- CP-B での security/perf 印付け結果（該当タスクのみ）
```

- [ ] **Step 4: 検証**

```bash
grep -n "executing-plans" ~/.claude/skills/tdd-gates/templates/task-evidence-addendum.md
grep -n "evaluatorモデル階層化" ~/.claude/skills/tdd-gates/templates/task-evidence-addendum.md
```

期待結果: 前者0件、後者1件以上。

---

## Task 5: profiles/pytest.md への反映

**Files:**
- Modify: `~/.claude/skills/tdd-gates/references/profiles/pytest.md`

- [ ] **Edit 1: CP-C(RED)にフルスイート不要を明記**

変更前:
```
- **CP-C(RED)**: 出力に `FAILED` が含まれ、対象テストが 1 件以上 `failed`、かつトレースバックの `E` 行が**対象 assert の `AssertionError`** を示す。assert 到達前の実行時エラー（`TypeError`/`AttributeError` 等）による `failed` は未実装シンボル起因の初回 RED としてのみ有効——GREEN 前に実装者がスタブを置いた二段階 RED で対象 assert の失敗を確認する。
```

変更後:
```
- **CP-C(RED)**: 対象テストのみ実行する（フルスイート不要）。出力に `FAILED` が含まれ、対象テストが 1 件以上 `failed`、かつトレースバックの `E` 行が**対象 assert の `AssertionError`** を示す。assert 到達前の実行時エラー（`TypeError`/`AttributeError` 等）による `failed` は未実装シンボル起因の初回 RED としてのみ有効——GREEN 前に実装者がスタブを置いた二段階 RED で対象 assert の失敗を確認する。
```

- [ ] **Edit 2: CP-C(REFACTOR)を条件付きスキップに更新**

変更前:
```
- **CP-C(REFACTOR)**: `git diff` にテストファイルの変更が無く（＝振る舞い不変）、`pytest -q` が全緑。
```

変更後:
```
- **CP-C(REFACTOR)**: GREEN確定コミット〜現在HEADの`git diff`を確認する。**差分が空ならGREENの全緑結果を援用しフルスイート再実行を省略**してよい。差分がある場合はテストファイルの変更が無いこと（＝振る舞い不変）と、`pytest -q` が全緑であることを確認する。
```

- [ ] **Step 3: 検証**

```bash
grep -n "CP-C(REFACTOR)" ~/.claude/skills/tdd-gates/references/profiles/pytest.md
```

期待結果: 「差分が空なら」を含む文が1件。

---

## Task 6: final-scorecard-review-prompt.md への反映

**Files:**
- Modify: `~/.claude/skills/tdd-gates/templates/final-scorecard-review-prompt.md`

- [ ] **Edit 1: 冒頭説明文を条件付き本数に更新**

変更前:
```
SDD の「## Final Review」は既定で `code-reviewer.md` を単独ディスパッチする。CP-D はこの単独ディスパッチを、**review-* 5本の並列起動 + `tdd-evaluator` 集約**に丸ごと差し替える。本ファイルは土台テンプレの本文を複製せず、差し替え後の手順のみを記述する（各 reviewer の詳細チェックリストは `~/.claude/agents/review-*.md` と `~/.claude/agents/references/review.md` が正典）。
```

変更後:
```
SDD の「## Final Review」は既定で `code-reviewer.md` を単独ディスパッチする。CP-D はこの単独ディスパッチを、**review-*（条件付き3〜5本）の並列起動 + `tdd-evaluator` 集約**に丸ごと差し替える。本ファイルは土台テンプレの本文を複製せず、差し替え後の手順のみを記述する（各 reviewer の詳細チェックリストは `~/.claude/agents/review-*.md` と `~/.claude/agents/references/review.md` が正典）。
```

- [ ] **Edit 2: 手順1を条件付き起動リストに更新**

変更前:
```
## 手順1: 並列ディスパッチ（Main が実施）

`superpowers:dispatching-parallel-agents` の機構に従い、次の5エージェントを**同一メッセージ内で並列**に起動する。逐次起動しない。

- `review-correctness`
- `review-security`
- `review-performance`
- `review-test`
- `review-maintainability`

各エージェントへの指示に、対象の `[BASE_SHA]`・`[HEAD_SHA]`（土台テンプレと同じプレースホルダ）と、**所見の書き出し先ファイルパス**を明記する。
```

変更後:
```
## 手順1: 並列ディスパッチ（Main が実施）

`superpowers:dispatching-parallel-agents` の機構に従い、次のエージェントを**同一メッセージ内で並列**に起動する。逐次起動しない。

- **常時起動**: `review-correctness` / `review-test` / `review-maintainability`
- **条件付き起動**（CP-Bのsecurity/perf敏感フラグに基づく）: `review-security`（security敏感と判定された場合のみ）／`review-performance`（perf敏感と判定された場合のみ）

起動本数は3〜5本になる。各エージェントへの指示に、対象の `[BASE_SHA]`・`[HEAD_SHA]`（土台テンプレと同じプレースホルダ）と、**所見の書き出し先ファイルパス**を明記する。
```

- [ ] **Edit 3: 手順2冒頭のディスパッチ説明を可変本数に更新**

変更前:
```
Main は `tdd-evaluator` を起動し、上記5ファイルのパス一覧を渡す。その際 description は `"CP-D: Aggregate and score 5 review files"` とする。`tdd-evaluator` は次を行う。

1. 5ファイルすべてを自ら Read する（Main による要約・選別を経由しない）。
2. 所見ファイル数が5本と一致するか照合する。不足があれば採点せず、不足次元を明記して Main に差し戻す。
3. `~/.claude/skills/tdd-gates/references/scoring.md`「スコアカード出力形式（CP-C〜F用）」の Spec Compliance 形式に集約する。5次元（正確性／セキュリティ／性能／テスト品質／保守性）それぞれの所見を反映する。
```

変更後:
```
Main は `tdd-evaluator` を起動し、上記の起動された全ファイル（3〜5本）のパス一覧を渡す。その際 description は `"CP-D: Aggregate and score review files"` とする。`tdd-evaluator` は次を行う。

1. 渡されたファイルすべてを自ら Read する（Main による要約・選別を経由しない）。
2. 所見ファイル数がMainから伝えられた起動本数（3〜5本）と一致するか照合する。不足があれば採点せず、不足次元を明記して Main に差し戻す。
3. `~/.claude/skills/tdd-gates/references/scoring.md`「スコアカード出力形式（CP-C〜F用）」の Spec Compliance 形式に集約する。起動した次元（常時: 正確性／テスト品質／保守性。条件付き: セキュリティ／性能）それぞれの所見を反映する。
```

- [ ] **Edit 4: リトライ機構の記述を条件付き本数に更新**

変更前:
```
SDD 純正の Final Review（1修正波 + 1 scoped re-review、adjudicate residuals）にそのまま従う。tdd-gates 独自の再評価カウンタは持たない。修正波のディスパッチ先も `review-*` 5本ではなく、指摘された次元の実装者（SDD implementer）への差し戻しである点は SDD 標準と同じ。
```

変更後:
```
SDD 純正の Final Review（1修正波 + 1 scoped re-review、adjudicate residuals）にそのまま従う。tdd-gates 独自の再評価カウンタは持たない。修正波のディスパッチ先も起動した `review-*` 群ではなく、指摘された次元の実装者（SDD implementer）への差し戻しである点は SDD 標準と同じ。
```

- [ ] **Step 5: 検証**

```bash
grep -n "5本\|5次元\|5ファイル\|5 review files" ~/.claude/skills/tdd-gates/templates/final-scorecard-review-prompt.md
```

期待結果: いずれも0件（すべて「3〜5本」等に置換済み）。

---

## Task 7: ci-gate-task-template.md への反映

**Files:**
- Modify: `~/.claude/skills/tdd-gates/templates/ci-gate-task-template.md`

- [ ] **Edit 1: executing-plans併記を削除**

変更前:
```
writing-plans が CP-E の条件（CI を運用するプロジェクト）を満たすと判定した場合、計画書の末尾タスクとして以下の雛形をそのまま追加する。追加後は CP-C と同じ SDD/executing-plans の通常タスクループに乗る——CP-E は「タスクの中身」を規定するだけで、独自のディスパッチ・リトライ機構は持たない。
```

変更後:
```
writing-plans が CP-E の条件（CI を運用するプロジェクト）を満たすと判定した場合、計画書の末尾タスクとして以下の雛形をそのまま追加する。追加後は CP-C と同じ SDD の通常タスクループに乗る——CP-E は「タスクの中身」を規定するだけで、独自のディスパッチ・リトライ機構は持たない。
```

- [ ] **Edit 2: レビュー役の行にモデル階層化ルールへの参照を追加**

変更前:
```
**実装役**: `doc-updater`
**レビュー役**: `tdd-evaluator`（CP-C の仕組みに乗り、必須ステージの被覆を採点する）
```

変更後:
```
**実装役**: `doc-updater`
**レビュー役**: `tdd-evaluator`（CP-C の仕組みに乗り、必須ステージの被覆を採点する。ディスパッチモデルはCP-Cと同じ階層化ルール[`checkpoints.md`CP-C「evaluatorモデル階層化」]に従う）
```

- [ ] **Step 3: 検証**

```bash
grep -n "executing-plans\|evaluatorモデル階層化" ~/.claude/skills/tdd-gates/templates/ci-gate-task-template.md
```

期待結果: 前者0件、後者1件。

---

## Task 8: plan-quality-review-addendum.md への反映（差分7新設）

**Files:**
- Modify: `~/.claude/skills/tdd-gates/templates/plan-quality-review-addendum.md`

- [ ] **Edit 1: 差分7を新設（差分6の直後、プレースホルダ節の直前）**

変更前:
```
## 差分6: 追加セクション「security/perf 敏感タスクの印付け」

> ## security/perf 敏感タスクの印付け（tdd-gates 追加）
>
> 計画中の各タスクが認証・入力処理・機密データを扱う（security 敏感）、または大量データ・ホットパスを扱う（perf 敏感）かを判定し、該当タスクにタグを付ける。タグを付けたタスクは、次の2箇所で追加レビューの起動条件になる。
> - **CP-B 自身**: 該当があれば `review-security`／`review-performance` を条件付きで並列起動する（最大2本）。
> - **CP-C**: `templates/task-evidence-addendum.md` の「security/perf 追加レビュー起動条件」が、この印付けを参照して該当タスクの task-reviewer 差し替え時に追加起動する。

## ディスパッチ時に Main が埋めるプレースホルダ
```

変更後:
```
## 差分6: 追加セクション「security/perf 敏感タスクの印付け」

> ## security/perf 敏感タスクの印付け（tdd-gates 追加）
>
> 計画中の各タスクが認証・入力処理・機密データを扱う（security 敏感）、または大量データ・ホットパスを扱う（perf 敏感）かを判定し、該当タスクにタグを付ける。タグを付けたタスクは、次の2箇所で追加レビューの起動条件になる。
> - **CP-B 自身**: 該当があれば `review-security`／`review-performance` を条件付きで並列起動する（最大2本）。
> - **CP-C**: `templates/task-evidence-addendum.md` の「security/perf 追加レビュー起動条件」が、この印付けを参照して該当タスクの task-reviewer 差し替え時に追加起動する。

## 差分7: 追加セクション「タスク粒度の適正さ監査」

> ## タスク粒度の適正さ監査（tdd-gates 追加）
>
> 計画中の各タスクの粒度を0–3点で採点する（`references/scoring.md`の項目スコアに準拠。0=Missing/1=Partial/2=Good/3=Excellent）。
> - **過剰分割の兆候**: 隣接タスクが同一ファイル群への変更で、互いに独立してレビュー・承認・却下する意味が無い（一方だけ却下してもう一方だけ承認する状況が想定できない）場合、減点し統合を推奨する。
> - **過小分割（バンドル）の兆候**: 1タスクに複数の独立した振る舞い変更が含まれ、個別にテスト・レビュー可能な単位へ分割できるにも関わらず1タスクにまとめられている場合、減点し分割を推奨する。
> - Criticalには追加しない（品質・効率観点のためスコア率にのみ反映する）。判定基準はwriting-plansの「Task Right-Sizing」原則（隣接タスクを承認しつつ当該タスクだけを却下しうる境界でのみ分割する）を援用し、新しい基準は発明しない。

## ディスパッチ時に Main が埋めるプレースホルダ
```

- [ ] **Step 2: 検証**

```bash
grep -n "差分7" ~/.claude/skills/tdd-gates/templates/plan-quality-review-addendum.md
```

期待結果: 見出し行を含め1件以上。

---

## 全タスク完了後: 横断検証

```bash
grep -rn "executing-plans" ~/.claude/skills/tdd-gates/ ~/.claude/agents/tdd-evaluator.md
```

期待結果: 0件（`checkpoints.md`のCP-C「上乗せ先」に残す「`executing-plans`は独立レビュアーへのdispatchステップを持たず…」という説明文のみが唯一の言及として残る。これは削除対象ではなく前提の是正そのものなので誤検知として扱ってよい）。

```bash
grep -rn "review-\*5本\|review-\*.5本\|CP-D=5本\|CP-Dの5次元\|CP-D の5次元\|5次元それぞれ\|5次元(" ~/.claude/skills/tdd-gates/ ~/.claude/agents/tdd-evaluator.md
```

期待結果: 0件。（checkpoints.md CP-Dの担当行にあった`5次元（correctness/...)`は変更対象。CP-Bの担当行等、CP-D以外の文脈で使われる「5次元」相当の表現がもし残っていても、それは本設計の対象外である旨をこの検証で確認する。）

## 実行方式（Execution Handoff）

標準のwriting-plansは「Subagent-Driven（SDD）」「Inline Execution（executing-plans）」の二択を提示するが、本計画には適用しない。理由:

1. 対象がすべてMarkdown指示文書の編集であり、コード・自動テストが存在しない。SDDのRED/GREEN検証・独立レビュアーによる自己承認排除は、テストの無いプロース編集には適用対象がない。
2. `~/.claude`はgitリポジトリではないため、SDDの前提（各タスクがgit commitを生み、ledgerがコミットハッシュを記録して復旧する）が機能しない。
3. 全編集は本計画内で完全に事前確定されている（探索・判断の余地がない「内容が事前確定したexact-edit」に該当）。

**推奨する実行方式**: Main（またはMainが直接委任する一括実行）が、Task 1〜8を順に、各Editの通りにEditツールで適用する。各タスクの検証ステップ（grep）で確認しながら進める。全タスク完了後、本リポジトリから`scripts/sync.sh`を実行して`~/.claude`の変更を`my-claude`へ同期・commit・pushする。
