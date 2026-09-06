# tdd-gates 高速化 実装計画

> **For agentic workers:** この計画の対象 `~/.claude/` は git リポジトリではないため、SDD／executing-plans のコミット単位タスクループは使わない。各タスクは事前確定した exact-edit の列であり、Main が Edit ツールで直接適用する（グローバル CLAUDE.md「例外（Main直接可）: 内容が事前確定した exact-edit」）。チェックボックス（`- [ ]`）で進捗を追跡する。

**Goal:** tdd-gates の CP-C／CP-D の所要時間を、実証済みの検出力を落とさずに削る。

**Architecture:** 4件の変更（A' CP-C フルスイートの CP-D 冒頭集約、A'' RED 再現手順の明文化、B CP-D ミューテーションの徴候ベース化、E review-correctness の sonnet 化）を、正典行（`checkpoints.md`）→写し先（agents・templates・profiles・SKILL.md）の順に同期編集する。編集後に grep で写し先の取り残しを検証し、`tdd-evaluator` に設計文書と実ファイルを敵対的照合させる。

**Tech Stack:** Markdown（Claude Code の skill／agent 定義）、Edit ツール、grep。

**Spec:** `docs/specs/2026-09-06-tdd-gates-speedup-design.md`

## Global Constraints

- 編集対象は `~/.claude/skills/tdd-gates/` 配下と `~/.claude/agents/{tdd-evaluator,tdd-implementer,review-correctness}.md` のみ。`linux/claude/`・`windows/claude/` は直接編集しない（`my-claude-pull`／`my-claude-mirrors` で同期する）。
- 各 Edit の `old_string` は本計画に記した現行テキストと一字一句一致させる。一致しなければ止めて報告する（推測で近い行を編集しない）。
- Markdown はハードラップしない。1文・1箇条書き項目は1行で書く。
- 指示文書は命令形で書く。出所説明・メタ宣言は書かない。
- 安全指示: 安全装置（hooks）にブロックされたら別手段で回避せず停止し、BLOCKED として報告する。
- タスク順序は Task 1→2→3→4 を守る。Task 3・4 の `old_string` は前タスク適用後のテキストを前提にしている。

---

### Task 1: review-correctness のモデル統一（E）

**Files:**
- Modify: `~/.claude/agents/review-correctness.md:5`

- [ ] **Step 1: モデル行を書き換える**

Edit: `~/.claude/agents/review-correctness.md`

old_string:
```
model: opus
```
new_string:
```
model: sonnet
```

- [ ] **Step 2: 検証**

Run: `grep -rn 'opus' ~/.claude/agents ~/.claude/skills/tdd-gates`
Expected: `agents/planner.md:5:model: opus` の1件のみ。

---

### Task 2: CP-D ミューテーションの徴候ベース化（B）

**Files:**
- Modify: `~/.claude/skills/tdd-gates/references/checkpoints.md:86`
- Modify: `~/.claude/agents/tdd-evaluator.md:3,18,19,20`
- Modify: `~/.claude/skills/tdd-gates/templates/final-scorecard-review-prompt.md:37-40,44`
- Modify: `~/.claude/skills/tdd-gates/SKILL.md:33`

- [ ] **Step 1: checkpoints.md の CP-D Critical（正典行）**

old_string:
```
検出は目視に加えミューテーション検証を実施——徴候があれば必須・無くても代表1テストにスモーク）。
```
new_string:
```
検出は目視に加え、徴候（期待値が実装の写し・assertが実装側の定数/内部関数を参照・実装から期待値を計算）が1つでもあればミューテーション検証を必須とする。徴候が無ければ実施せず、その旨をスコアカードに明記する）。
```

- [ ] **Step 2: tdd-evaluator.md の description（3行目）**

old_string:
```
の所見を集約してミューテーション検証込みで最終スコアカード化、
```
new_string:
```
の所見を集約し、徴候があればミューテーション検証を加えて最終スコアカード化、
```

- [ ] **Step 3: tdd-evaluator.md の実施義務の見出し文（18行目）**

old_string:
```
CP-C／CP-D では目視だけに頼らず、能動的にバグ注入検証を行う。実施条件は CP によって異なる（詳細は
```
new_string:
```
CP-C／CP-D では目視だけに頼らず、徴候があるときに能動的にバグ注入検証を行う。実施条件は CP-C／CP-D とも同じ徴候ベースである（詳細は
```

- [ ] **Step 4: tdd-evaluator.md の CP-C 行（19行目）を共通行に**

old_string:
```
- **CP-C（徴候ベースで都度実施）**: 期待値が実装ロジックの写しに見える／assert が実装側の定数・内部関数を参照している／テストが実装から期待値を計算している——このような徴候が1つでもあるときのみ実施する。
```
new_string:
```
- **CP-C／CP-D 共通（徴候ベース）**: 期待値が実装ロジックの写しに見える／assert が実装側の定数・内部関数を参照している／テストが実装から期待値を計算している——このような徴候が1つでもあるときのみ、該当テストに実施する。徴候が無ければ実施しない。
```

- [ ] **Step 5: tdd-evaluator.md の CP-D 行（20行目）**

old_string:
```
- **CP-D（徴候なしでも代表1件スモーク必須）**: 徴候の有無にかかわらず、差分の中心となる代表1テストに1箇所バグを注入し、落ちることを確認する。徴候があれば該当テストにも追加で実施する。注入箇所と結果はスコアカードの証拠に含める。
```
new_string:
```
- **CP-D の追記事項**: 実施した場合は注入箇所と結果をスコアカードの証拠に含める。徴候が無く未実施の場合はスコアカードに「ミューテーション検証: 徴候なし・未実施」と明記する。
```

- [ ] **Step 6: final-scorecard-review-prompt.md の実施条件（37-40行目）**

old_string:
```
- **実施条件**:
  - **必須**: 期待値が実装ロジックの写しに見える／assert が実装側の定数・内部関数を参照している／テストが実装から期待値を計算している——このような徴候が1つでもあるとき。
  - **スモーク**: 徴候が無くても、差分の中心となる代表1テストに1箇所バグを注入し、落ちることを確認する。
```
new_string:
```
- **実施条件**: 期待値が実装ロジックの写しに見える／assert が実装側の定数・内部関数を参照している／テストが実装から期待値を計算している——このような徴候が1つでもあるとき、該当テストに実施する。徴候が無ければ実施せず、スコアカードに「ミューテーション検証: 徴候なし・未実施」と明記する。
```

- [ ] **Step 7: final-scorecard-review-prompt.md の同一性注記（44行目）**

old_string:
```
CP-D 用に新設する手順ではなく、CP-D で必ず実施することをここで明記する。）
```
new_string:
```
CP-D 用に新設する手順ではなく、CP-D でも同じ徴候ベースで実施することをここで明記する。）
```

- [ ] **Step 8: SKILL.md の CP対応表 CP-D 行（33行目）**

old_string:
```
`tdd-evaluator`集約（ミューテーション検証必須）
```
new_string:
```
`tdd-evaluator`集約（徴候時はミューテーション検証必須）
```

- [ ] **Step 9: 検証**

Run: `grep -rn 'スモーク\|徴候の有無にかかわらず\|徴候なしでも\|ミューテーション検証必須' ~/.claude/skills/tdd-gates ~/.claude/agents`
Expected: `SKILL.md:33` の「徴候時はミューテーション検証必須」1件のみ。他は0件。

---

### Task 3: CP-C フルスイートの CP-D 冒頭への集約（A'）

**Files:**
- Modify: `~/.claude/skills/tdd-gates/references/checkpoints.md:69,73,75,79,85,89`
- Modify: `~/.claude/agents/tdd-evaluator.md:48,49,50`
- Modify: `~/.claude/skills/tdd-gates/templates/task-evidence-addendum.md:28`
- Modify: `~/.claude/skills/tdd-gates/templates/final-scorecard-review-prompt.md:7,26,29,50-53`
- Modify: `~/.claude/skills/tdd-gates/references/profiles/pytest.md:25,65,66`
- Modify: `~/.claude/skills/tdd-gates/references/profiles/_template.md:20,55,56`
- Modify: `~/.claude/skills/tdd-gates/references/profiles/bash-hook-test.md:22,45,46`
- Modify: `~/.claude/skills/tdd-gates/references/profiles/browser-manual-e2e.md:23-24,66-67`
- Modify: `~/.claude/skills/tdd-gates/SKILL.md:22,33`

**Interfaces:**
- Produces: プレースホルダ名 `[FULL_SUITE_LOG]`（CP-D 手順0 の出力ファイル。既定名 `reviews/[TASK_SLUG]-cp-d-fullsuite.log`）。Task 4 は使わない。

- [ ] **Step 1: checkpoints.md GREEN Critical（69行目）**

old_string:
```
  - `tdd-evaluator` が自ら再実行し、テストが通過する（対象`passed`かつ全体でベースライン比の新規`failed`0）。
```
new_string:
```
  - `tdd-evaluator` が自ら再実行し、対象テストが通過する（対象`passed`）。フルスイートは再実行しない——既存回帰の独立検証はCP-D手順0のフルスイート1回に集約する。
```

- [ ] **Step 2: checkpoints.md REFACTOR 冒頭（73行目）**

old_string:
```
**差分が空なら**GREENで確認済みの全緑結果を援用し、以下のフルスイート再実行を**省略**してよい（軽量化。`references/profiles/*.md`「CP-C証拠ルール」参照）。
```
new_string:
```
**差分が空なら**GREENで確認済みの対象テスト結果を援用し、以下の再実行を**省略**してよい（`references/profiles/*.md`「CP-C証拠ルール」参照）。
```

- [ ] **Step 3: checkpoints.md REFACTOR 全緑（75行目）**

old_string:
```
  - リファクタ後もプロファイル定義のテスト実行コマンドで全緑。
```
new_string:
```
  - リファクタ後も対象テストがプロファイル定義の単一テスト実行コマンドで緑（フルスイートは再実行しない）。
```

- [ ] **Step 4: checkpoints.md CP-C 証拠（79行目）**

old_string:
```
- **証拠**: RED失敗ログ／GREEN通過ログ（全既存テスト緑を含む）／REFACTOR後の緑ログ／
```
new_string:
```
- **証拠**: RED失敗ログ／GREEN通過ログ（対象テスト）／REFACTOR後の対象テスト緑ログ／
```

- [ ] **Step 5: checkpoints.md CP-D 担当の直前に手順0 を追加（85行目）**

old_string:
```
- **担当**: MainがCP-Bの構造変更フラグ・security/perf敏感フラグに基づき`review-*`を**条件付き並列起動**する
```
new_string:
```
- **手順0（フルスイート1回）**: `review-*`起動前にMainがプロファイル定義の全体実行コマンドを1回実行し、出力をscratchpad配下にファイル化する（既定名`reviews/<タスクスラッグ>-cp-d-fullsuite.log`）。判定は「起動時に`progress.md`へ記録したベースライン比の新規`failed`0」。CP-Cでは各タスクのフルスイートを再実行しないため、既存回帰の独立検証はこの1回が担う。ログのパスは集約`tdd-evaluator`へ渡す。
- **担当**: MainがCP-Bの構造変更フラグ・security/perf敏感フラグに基づき`review-*`を**条件付き並列起動**する
```

- [ ] **Step 6: checkpoints.md CP-D 証拠（89行目）**

old_string:
```
- **証拠**: 集約スコアカード（review-*所見に裏付け）。
```
new_string:
```
- **証拠**: 手順0のフルスイートログ／集約スコアカード（review-*所見に裏付け）。
```

- [ ] **Step 7: tdd-evaluator.md CP-C・GREEN（48行目）**

old_string:
```
   - **CP-C・GREEN**: 対象＋全体を再実行し緑を確認。
```
new_string:
```
   - **CP-C・GREEN**: 対象テストのみを再実行し緑を確認（フルスイートは再実行しない。既存回帰の独立検証は CP-D 手順0 が担う）。
```

- [ ] **Step 8: tdd-evaluator.md CP-C・REFACTOR（49行目）**

old_string:
```
**差分が空ならGREENの全緑結果を援用しフルスイート再実行を省略**してよい。差分がある場合は**テストファイル不変**かつ新規branch/機能の追加が無いことを確認し、全緑を再実行する。
```
new_string:
```
**差分が空ならGREENの対象テスト結果を援用し再実行を省略**してよい。差分がある場合は**テストファイル不変**かつ新規branch/機能の追加が無いことを確認し、対象テストを再実行して緑を確認する。
```

- [ ] **Step 9: tdd-evaluator.md CP-D（50行目）**

old_string:
```
   - **CP-D**: **偽装テスト**・仕様不適合・既存回帰を検出したら Critical 未達（偽装テストの定義は `checkpoints.md` の CP-D「Critical」行を参照）。
```
new_string:
```
   - **CP-D**: **偽装テスト**・仕様不適合・既存回帰を検出したら Critical 未達（偽装テストの定義は `checkpoints.md` の CP-D「Critical」行を参照）。既存回帰は Main から渡される手順0 のフルスイートログを `progress.md` のベースラインと照合し、新規 `failed` の有無で判定する。
```

- [ ] **Step 10: task-evidence-addendum.md（28行目・2箇所）**

old_string:
```
**RED は対象テストのみの再実行で足り、フルスイート実行は不要**。
```
new_string:
```
**RED・GREEN とも対象テストのみの再実行で足り、フルスイート実行は不要**（既存回帰の独立検証は CP-D 手順0 に集約する）。
```

old_string:
```
差分が空ならGREENの全緑結果を援用してフルスイート再実行を省略してよい。差分があれば通常通りテストファイル不変の確認＋フルスイート再実行を行う。
```
new_string:
```
差分が空ならGREENの対象テスト結果を援用して再実行を省略してよい。差分があればテストファイル不変の確認＋対象テストの再実行を行う。
```

- [ ] **Step 11: final-scorecard-review-prompt.md に手順0 節を新設（7行目の直前）**

old_string:
```
## 手順1: 並列ディスパッチ（Main が実施）
```
new_string:
```
## 手順0: フルスイート1回（Main が実施）

review-* を起動する前に、Main が対象言語プロファイルの全体実行コマンド（例 `pytest.md` の `pytest -q`）を1回実行し、出力を scratchpad の `[FULL_SUITE_LOG]` にファイル化する。判定は「起動時に `progress.md` へ記録したベースライン比で新規 `failed` が 0」。CP-C では各タスクのフルスイートを再実行しないため、既存回帰の独立検証はこの1回が担う。新規 `failed` があれば集約時に Critical（既存回帰）となる。

## 手順1: 並列ディスパッチ（Main が実施）
```

- [ ] **Step 12: final-scorecard-review-prompt.md 集約への引き渡し（26行目）**

old_string:
```
Main は `tdd-evaluator` を起動し、上記の起動された全ファイル（2〜5本）のパス一覧を渡す。
```
new_string:
```
Main は `tdd-evaluator` を起動し、上記の起動された全ファイル（2〜5本）のパス一覧と手順0 の `[FULL_SUITE_LOG]` のパスを渡す。
```

- [ ] **Step 13: final-scorecard-review-prompt.md Critical 判定（手順2 の項目4）**

old_string:
```
4. Critical 判定基準は `~/.claude/skills/tdd-gates/references/checkpoints.md` CP-D の Critical 行（仕様不適合／既存回帰／偽装テスト検出）に従う。
```
new_string:
```
4. Critical 判定基準は `~/.claude/skills/tdd-gates/references/checkpoints.md` CP-D の Critical 行（仕様不適合／既存回帰／偽装テスト検出）に従う。既存回帰は `[FULL_SUITE_LOG]` を `progress.md` のベースラインと照合し、新規 `failed` の有無で判定する。
```

- [ ] **Step 14: final-scorecard-review-prompt.md プレースホルダ節（末尾）**

old_string:
```
- `[TASK_SLUG]`: 所見ファイル名に使う一意スラッグ
```
new_string:
```
- `[TASK_SLUG]`: 所見ファイル名に使う一意スラッグ
- `[FULL_SUITE_LOG]`: 手順0 のフルスイート出力ファイルのパス（既定名 `reviews/[TASK_SLUG]-cp-d-fullsuite.log`）
```

- [ ] **Step 15: pytest.md 全体コマンドのコメント（25行目）**

old_string:
```
# 全体（既存回帰の確認・CP-C(GREEN/REFACTOR) の緑維持証拠）
```
new_string:
```
# 全体（既存回帰の確認。起動時のベースライン取得と CP-D 手順0 で各1回実行する。CP-C では実行しない）
```

- [ ] **Step 16: pytest.md CP-C(GREEN)（65行目）**

old_string:
```
- **CP-C(GREEN)**: 対象テストが `passed`、かつ `pytest -q` 全体で**ベースライン比の新規 `failed` が 0**（進捗記録のベースライン記録に無い failed が 0。ベースラインが全緑なら従来どおり `failed` 0）。
```
new_string:
```
- **CP-C(GREEN)**: 対象テストが `passed`。フルスイートは実行しない。既存回帰は CP-D 手順0 の `pytest -q` で**ベースライン比の新規 `failed` が 0**を確認する（`progress.md` のベースライン記録に無い failed が 0。ベースラインが全緑なら `failed` 0）。
```

- [ ] **Step 17: pytest.md CP-C(REFACTOR)（66行目）**

old_string:
```
**差分が空ならGREENの全緑結果を援用しフルスイート再実行を省略**してよい。差分がある場合はテストファイルの変更が無いこと（＝振る舞い不変）と、`pytest -q` が全緑であることを確認する。
```
new_string:
```
**差分が空ならGREENの対象テスト結果を援用し再実行を省略**してよい。差分がある場合はテストファイルの変更が無いこと（＝振る舞い不変）と、対象テストが `passed` であることを確認する。
```

- [ ] **Step 18: _template.md（20,55,56行目）**

old_string:
```
# 全体（既存回帰の確認）
<cmd>
```
new_string:
```
# 全体（既存回帰の確認。起動時のベースライン取得と CP-D 手順0 で各1回実行する。CP-C では実行しない）
<cmd>
```

old_string:
```
- **CP-C(GREEN)**: 通過を示す出力 = `<...>`、かつ全体で失敗 0。
- **CP-C(REFACTOR)**: テスト不変（diff にテスト変更なし）かつ全緑。
```
new_string:
```
- **CP-C(GREEN)**: 通過を示す出力 = `<...>`。フルスイートは実行しない（全体の新規失敗 0 は CP-D 手順0 で確認する）。
- **CP-C(REFACTOR)**: テスト不変（diff にテスト変更なし）かつ対象テストが緑。
```

- [ ] **Step 19: bash-hook-test.md（22,45,46行目）**

old_string:
```
# 全体（既存回帰の確認。hooks/ 配下の全 *.test.sh を実行）
```
new_string:
```
# 全体（既存回帰の確認。hooks/ 配下の全 *.test.sh を実行。起動時のベースライン取得と CP-D 手順0 で各1回実行する。CP-C では実行しない）
```

old_string:
```
ファイル全体の最終行が `ALL PASS`（終了コード0）。既存ケースに新規failedが無いこと。
- **CP-C(REFACTOR)**: テストファイル（`*.test.sh`）が不変、かつ再実行で全緑（`ALL PASS`）。
```
new_string:
```
ファイル全体の最終行が `ALL PASS`（終了コード0）。他の `*.test.sh` は実行しない（既存回帰は CP-D 手順0 で確認する）。
- **CP-C(REFACTOR)**: テストファイル（`*.test.sh`）が不変、かつ対象ファイルの再実行で `ALL PASS`。
```

- [ ] **Step 20: browser-manual-e2e.md（23-24,66-67行目）**

old_string:
```
# 全体（既存回帰の確認）
# 下記シナリオ一覧を全件、実装後にもう一度流す
```
new_string:
```
# 全体（既存回帰の確認。CP-D 手順0 で1回だけ実施する。CP-C では実施しない）
# 下記シナリオ一覧を全件、CP-D 手順0 でもう一度流す
```

old_string:
```
- **CP-C(GREEN)**: 実装後に同一シナリオを実行し、期待する状態変化が起きることを示す。かつ既存の全シナリオ
  （回帰確認分）も合わせて実行し失敗0を確認する。
```
new_string:
```
- **CP-C(GREEN)**: 実装後に同一シナリオを実行し、期待する状態変化が起きることを示す。既存の全シナリオの回帰確認は CP-D 手順0 で1回行い、CP-C では対象シナリオのみ実行する。
```

- [ ] **Step 21: SKILL.md 証拠の記録先にベースライン取得を追加（22行目）**

old_string:
```
**CP-D の集約スコアカードも Main が `progress.md` に書き出す**。tdd-gates 独自の台帳
```
new_string:
```
**CP-D の集約スコアカードも Main が `progress.md` に書き出す**。**タスクループ開始前に Main がプロファイルの全体実行コマンドを1回実行し、その結果をベースラインとして `progress.md` に記録する**（CP-D 手順0 の比較基準。CP-C の各タスクではフルスイートを再実行しない）。tdd-gates 独自の台帳
```

- [ ] **Step 22: SKILL.md CP対応表 CP-D 行（33行目。Task 2 適用後のテキスト）**

old_string:
```
| `review-*`条件付き2〜5本並列→`tdd-evaluator`集約（徴候時はミューテーション検証必須）
```
new_string:
```
| Mainがフルスイート1回（手順0）→`review-*`条件付き2〜5本並列→`tdd-evaluator`集約（徴候時はミューテーション検証必須）
```

- [ ] **Step 23: 検証**

Run: `grep -rn 'フルスイート\|全緑\|全体で' ~/.claude/skills/tdd-gates ~/.claude/agents/tdd-evaluator.md ~/.claude/agents/tdd-implementer.md`
Expected: 残るのは次の文脈のみ。「再実行しない／実行しない／不要／省略」という否定文脈、CP-D 手順0 の記述、起動時ベースラインの記述、`tdd-implementer.md:45` の「全体実行の合格サマリ」（implementer の実行は維持）。GREEN／REFACTOR で evaluator にフルスイートを要求する肯定文が0件であること。

Run: `grep -rn 'FULL_SUITE_LOG\|手順0' ~/.claude/skills/tdd-gates ~/.claude/agents/tdd-evaluator.md`
Expected: checkpoints.md（CP-D 節）、final-scorecard-review-prompt.md（手順0 節・手順2・プレースホルダ節）、tdd-evaluator.md:48,50、task-evidence-addendum.md:28、profiles 4本、SKILL.md:22,33 に出現する。

---

### Task 4: RED 再現手順の明文化（A''）

**Files:**
- Modify: `~/.claude/agents/tdd-implementer.md:13,37-45,57`
- Modify: `~/.claude/agents/tdd-evaluator.md:16,47`
- Modify: `~/.claude/skills/tdd-gates/references/checkpoints.md:65,67,79`
- Modify: `~/.claude/skills/tdd-gates/SKILL.md:22`
- Modify: `~/.claude/skills/tdd-gates/templates/task-evidence-addendum.md:28`
- Modify: `~/.claude/skills/tdd-gates/references/profiles/pytest.md`（実行コマンド節）
- Modify: `~/.claude/skills/tdd-gates/references/profiles/_template.md`（実行コマンド節）
- Modify: `~/.claude/skills/tdd-gates/references/profiles/bash-hook-test.md`（実行コマンド節）
- Modify: `~/.claude/skills/tdd-gates/references/profiles/browser-manual-e2e.md`（実行コマンド節）

**Interfaces:**
- Produces: 用語「RED コミット」「GREEN コミット」（implementer が切るコミット）、プレースホルダ `<RED_SHA>`、worktree パス規約 `<scratchpad>/red-<タスクスラッグ>`、プロファイルの節見出し「RED 再現」。全ファイルで同じ語を使う。

- [ ] **Step 1: tdd-implementer.md にコミット粒度規定を追加（13行目の直後）**

old_string:
```
の実行手順はこのスキルが正典。フェーズごとの詳細手順はここでは繰り返さない。
```
new_string:
```
の実行手順はこのスキルが正典。フェーズごとの詳細手順はここでは繰り返さない。

**コミット粒度（tdd-gates 固有）**: 1タスクにつき RED コミット（テストファイルのみ。実装ファイルを含めない）→ GREEN コミット（実装）→ REFACTOR コミット（差分がある場合のみ）の順に分けて切る。RED コミットは `tdd-evaluator` が隔離 worktree で RED を再現する基点になるため、GREEN と混ぜない。
```

- [ ] **Step 2: tdd-implementer.md TDD Evidence 雛形に SHA 欄を追加（37-45行目）**

old_string:
```
### RED
実行コマンド: <cmd>
```
new_string:
```
### RED
RED コミット: <short SHA>（テストファイルのみ）
実行コマンド: <cmd>
```

old_string:
```
### GREEN
実行コマンド: <cmd>
```
new_string:
```
### GREEN
GREEN コミット: <short SHA>
実行コマンド: <cmd>
```

- [ ] **Step 3: tdd-implementer.md 最終メッセージ（57行目）**

old_string:
```
- 作成したコミット（short SHA + subject）
```
new_string:
```
- 作成したコミット（RED／GREEN／REFACTOR の順に short SHA + subject）
```

- [ ] **Step 4: tdd-evaluator.md 読み取り専用 Bash の例外（16行目）**

old_string:
```
は**一切使わない**。テストを自分で通るように書き換えて採点するのは自己承認であり禁止。
```
new_string:
```
は**一切使わない**。例外として、RED 再現のための `git worktree add <scratchpad>/red-<タスクスラッグ> <RED_SHA>` と検証後の `git worktree remove <scratchpad>/red-<タスクスラッグ>` のみ許可する（scratchpad 配下限定。本体の作業ツリーは不変）。`git stash`／`git checkout`／`git reset` は本体の作業ツリーを変えるため引き続き禁止。テストを自分で通るように書き換えて採点するのは自己承認であり禁止。
```

- [ ] **Step 5: tdd-evaluator.md CP-C・RED（47行目・2箇所）**

old_string:
```
   - **CP-C・RED**: 対象テストのみを再実行し（フルスイート不要）実際に失敗するか確認。
```
new_string:
```
   - **CP-C・RED**: 実装者が報告した RED コミット SHA を `git worktree add <scratchpad>/red-<タスクスラッグ> <RED_SHA>` で隔離展開し、その中でプロファイル「RED 再現」のコマンドにより対象テストのみを再実行して実際に失敗するか確認する（確認後 `git worktree remove` で片付ける）。
```

old_string:
```
さらに `git diff` を自ら取得し、変更が**テストファイルのみ**（実装ファイルの変更なし）であることを確認する。
```
new_string:
```
さらに `git diff --stat <RED_SHA>^ <RED_SHA>` を自ら取得し、RED コミットの変更が**テストファイルのみ**（実装ファイルの変更なし）であることを確認する。
```

- [ ] **Step 6: checkpoints.md RED Critical（65行目）**

old_string:
```
  - `tdd-evaluator` が**対象テストのみ**（フルスイート不要）を自ら再実行し、テストが実際に失敗する（プロファイルの失敗ログ形式に一致）。「おそらく失敗する」は0点。
```
new_string:
```
  - `tdd-evaluator` が実装者の報告した RED コミットを scratchpad 配下の隔離 worktree（`git worktree add`）に展開し、その中で**対象テストのみ**（フルスイート不要）をプロファイル「RED 再現」のコマンドで自ら再実行し、テストが実際に失敗する（プロファイルの失敗ログ形式に一致）。本体の作業ツリーは変更しない（`git stash`／`checkout` 禁止）。「おそらく失敗する」は0点。
```

- [ ] **Step 7: checkpoints.md 実装差分ゼロ検証（67行目）**

old_string:
```
  - evaluatorが自ら取得した `git diff` で、変更がテストファイルのみであること。
```
new_string:
```
  - evaluatorが自ら取得した `git diff --stat <RED_SHA>^ <RED_SHA>` で、RED コミットの変更がテストファイルのみであること。
```

- [ ] **Step 8: checkpoints.md CP-C 証拠（79行目。Task 3 適用後のテキスト）**

old_string:
```
- **証拠**: RED失敗ログ／GREEN通過ログ（対象テスト）／REFACTOR後の対象テスト緑ログ／
```
new_string:
```
- **証拠**: RED コミット SHA／RED失敗ログ（隔離 worktree での再現）／GREEN コミット SHA／GREEN通過ログ（対象テスト）／REFACTOR後の対象テスト緑ログ／
```

- [ ] **Step 9: SKILL.md 証拠行スキーマ（22行目）**

old_string:
```
に証拠行（RED/GREEN コマンドと出力）を追記する形に統一**
```
new_string:
```
に証拠行（RED／GREEN コミット SHA、RED/GREEN コマンドと出力）を追記する形に統一**
```

- [ ] **Step 10: task-evidence-addendum.md RED 再現手順（28行目）**

old_string:
```
実際に失敗（RED 時点）・実際に通過（GREEN 時点）することを自分の目で確認する。
```
new_string:
```
実際に失敗（RED 時点）・実際に通過（GREEN 時点）することを自分の目で確認する。RED 時点は、実装者が報告した RED コミット SHA を `git worktree add <scratchpad>/red-<タスクスラッグ> <RED_SHA>` で隔離展開し、その中でプロファイル「RED 再現」のコマンドを実行して再現する（確認後 `git worktree remove`。本体の作業ツリーは変更しない）。
```

- [ ] **Step 11: pytest.md 実行コマンド節に RED 再現を追加**

old_string:
```
# 単一テスト（RED/GREEN の証拠取得に使う）
pytest <path>::<test> -q

```
new_string:
```
# 単一テスト（RED/GREEN の証拠取得に使う）
pytest <path>::<test> -q

# RED 再現（tdd-evaluator が隔離 worktree で実行する。editable install は本体の src/ を指すため、PYTHONPATH で worktree 側を優先させる。src/ レイアウトでなければ worktree ルートを指す）
git worktree add <scratchpad>/red-<slug> <RED_SHA>
PYTHONPATH=<scratchpad>/red-<slug>/src python -m pytest <scratchpad>/red-<slug>/<path>::<test> -q -p no:cacheprovider --rootdir=<scratchpad>/red-<slug>
git worktree remove <scratchpad>/red-<slug>

```

- [ ] **Step 12: _template.md 実行コマンド節に RED 再現を追加**

old_string:
```
# 単一テスト（RED/GREEN の証拠）
<cmd>

```
new_string:
```
# 単一テスト（RED/GREEN の証拠）
<cmd>

# RED 再現（tdd-evaluator が隔離 worktree で実行する）
git worktree add <scratchpad>/red-<slug> <RED_SHA>
<worktree 内で単一テストを実行する cmd。ランナーが本体ツリーのモジュールを優先解決する場合は環境変数で worktree 側を指す>
git worktree remove <scratchpad>/red-<slug>

```

- [ ] **Step 13: bash-hook-test.md 実行コマンド節に RED 再現の適用不可を明記**

old_string:
```
bash "$HOME/.claude/hooks/<name>.test.sh"

```
new_string:
```
bash "$HOME/.claude/hooks/<name>.test.sh"

# RED 再現: 適用不可。対象の $HOME/.claude/hooks/ は git 管理外のため RED コミット・worktree 方式が成立しない。
# tdd-evaluator は実装者の RED ログを、テストファイルの FAIL 行（expected exit）と実装後の挙動差から照合して検証する。

```

- [ ] **Step 14: browser-manual-e2e.md 実行コマンド節に RED 再現の代替を明記**

old_string:
```
（自動化スクリプトなし。claude-in-chromeツール呼び出しの手順として都度実施）

```
new_string:
```
（自動化スクリプトなし。claude-in-chromeツール呼び出しの手順として都度実施）

# RED 再現: 手動 E2E のため worktree 再現は行わない。RED コミット時点のシナリオ手順書（テスト定義）と実装者の実行記録（スクリーンショット・JS評価結果）を照合して代替する。

```

- [ ] **Step 15: 検証**

Run: `grep -rn 'RED_SHA\|worktree\|RED コミット\|REDコミット' ~/.claude/skills/tdd-gates ~/.claude/agents/tdd-evaluator.md ~/.claude/agents/tdd-implementer.md`
Expected: tdd-implementer.md（コミット粒度・Evidence 雛形・最終メッセージ）、tdd-evaluator.md:16,47、checkpoints.md:65,67,79、SKILL.md:22、task-evidence-addendum.md:28、profiles 4本に出現する。`SKILL.md:54` の既存「並列実装・worktree分離」行も残る（変更対象外）。

Run: `grep -rn 'git stash\|git checkout' ~/.claude/agents/tdd-evaluator.md ~/.claude/skills/tdd-gates/references/checkpoints.md`
Expected: 禁止文脈の出現のみ。

---

### Task 5: 全体 grep 検証と設計文書との敵対的照合

**Files:**
- Read only（変更なし）

- [ ] **Step 1: 仕様 §9 の grep を一括実行**

Run:
```bash
cd ~/.claude && grep -rn 'opus' agents skills/tdd-gates; echo ---; grep -rn 'スモーク\|徴候の有無にかかわらず\|徴候なしでも' agents skills/tdd-gates; echo ---; grep -rn 'フルスイート\|全緑\|全体で' skills/tdd-gates agents/tdd-evaluator.md agents/tdd-implementer.md
```
Expected: opus は `planner.md` のみ。スモーク系は0件。フルスイート系は否定文脈・手順0・ベースライン・implementer 雛形のみ。

- [ ] **Step 2: tdd-evaluator を単独起動して設計文書と実ファイルを敵対的照合**

Agent（`tdd-evaluator`、model は既定）に次を渡す。
- 設計文書パス `docs/specs/2026-09-06-tdd-gates-speedup-design.md` と本計画パス。
- 検査項目: (1) 設計 §4.2・§5.5・§6.2・§7 の編集対象表の各行が実ファイルに反映されているか。(2) 設計に書いていない変更が入っていないか。(3) 写し先間で文言が矛盾していないか（例: CP-C GREEN のフルスイート要否が checkpoints.md と profiles で食い違わないか。ミューテーション条件が tdd-evaluator.md と final-scorecard-review-prompt.md で同一か）。(4) `final-scorecard-review-prompt.md` の「tdd-evaluator.md と同一である」注記が真か。
- 返却: 不一致の `file:line` と1行要点のみ。全文引用禁止。
- 安全指示: 読み取り専用。ブロックされたら BLOCKED 報告。

- [ ] **Step 3: 不一致があれば該当 Edit を修正し、Step 1 を再実行**

---

### Task 6: ミラー同期と PR

**Files:**
- Modify（スキル経由）: `linux/claude/skills/tdd-gates/**`、`linux/claude/agents/{tdd-evaluator,tdd-implementer,review-correctness}.md`、`windows/claude/` の同パス

- [ ] **Step 1: 実機→linux ミラー**

Skill: `my-claude-pull`
Run: `git status --short && git diff --stat`
Expected: 変更ファイルは `linux/claude/skills/tdd-gates/` 配下（SKILL.md・checkpoints.md・task-evidence-addendum.md・final-scorecard-review-prompt.md・profiles 4本）と `linux/claude/agents/` の3本のみ。他の差分が出たら止めて報告する。

- [ ] **Step 2: linux→windows ミラー**

Skill: `my-claude-mirrors`
Expected: 上記ファイル群が windows 側へ同内容で揃う。台帳（ledger.json）に新規の意図的差分は追加しない。

- [ ] **Step 3: 実体確認**

Run: `diff -rq linux/claude/skills/tdd-gates windows/claude/skills/tdd-gates; diff -q linux/claude/agents/tdd-evaluator.md windows/claude/agents/tdd-evaluator.md; diff -q linux/claude/agents/tdd-implementer.md windows/claude/agents/tdd-implementer.md; diff -q linux/claude/agents/review-correctness.md windows/claude/agents/review-correctness.md`
Expected: 出力なし（一致）。

- [ ] **Step 4: PR 作成**

Skill: `pr-create`（ブランチ `docs/tdd-gates-speedup-design` 上で、設計文書・本計画・両ミラーの変更をまとめて commit・push・PR）。

- [ ] **Step 5: メモリ更新**

`~/.claude/projects/-home-asama-my-claude/memory/project-tdd-gates-harness.md` に 2026-09-06 節を追記する。内容: 採用4案（A'・A''・B・E）と却下案（CP-C バッチ化・CP-D 集約廃止保留・implementer フルスイート維持）、bash-hook-test プロファイルは git 管理外のため RED 再現が適用不可である事実、commit ハッシュ。
