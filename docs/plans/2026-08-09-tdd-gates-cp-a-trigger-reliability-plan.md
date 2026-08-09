# tdd-gates CP-A 発火信頼性ギャップ対応 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: 本計画はコード・テストを持たないMarkdown指示文書の編集のみで構成される。詳細は「実行方式（Execution Handoff）」節を参照——標準のsubagent-driven-development/executing-plansの二択とは異なる方式を採る。

**Goal:** `tdd-gates`（`~/.claude/skills/tdd-gates/SKILL.md`）に、設計書`docs/specs/2026-08-09-tdd-gates-cp-a-trigger-reliability-design.md`の3つの軽量チェック追記を適用し、CP-Aがセッション分割・スコープ拡大・trivial/small誤判定で素通りされる構造的ギャップを緩和する。

**Architecture:** 対象は`SKILL.md`1ファイルのみで、コード・自動テストを持たない。3箇所の追記はすべて「現在の正確な文言→新しい文言」への置換として完全に事前確定されている（探索・判断の余地はない）。実行はExecution Handoff節で述べる方式に従う。

**Tech Stack:** Markdown（対象ファイルは`~/.claude/skills/tdd-gates/SKILL.md`の実体。`my-claude/claude/`はミラーのため直接編集しない）。

## Global Constraints

- 変更対象は `~/.claude/skills/tdd-gates/SKILL.md` の実体ファイルのみ。`my-claude/claude/` は編集しない。
- `~/.claude` はgitリポジトリではない。そのためタスクに `git commit` ステップは含めない。全タスク完了後、`scripts/sync.sh`（本リポジトリから実行）が `~/.claude` → `my-claude/claude/` への同期とcommit+pushを一括で行う。
- 各エディットは「現在のファイルにこの正確な文字列が存在する」ことを前提にしている。適用前に対象箇所をRead/Grepで確認し、文字列が完全一致しない場合は実行を止めて報告する（推測で適用しない）。
- 新しいゲート・新しい判定ロジックは作らない。既存の記述への一文追加に留める（設計書のスコープ制約）。
- 変更2・変更3は独立エージェントの追加起動を要求しない（Main自身の軽量チェックに留める）。

---

## Task 1: SKILL.md への3箇所追記

**Files:**
- Modify: `~/.claude/skills/tdd-gates/SKILL.md`

- [ ] **Edit 1: セッション分割対応（起動時チェックリスト項目3への追記）**

変更前:
```
3. **superpowers チェーンを起動**: `superpowers:using-superpowers` の案内どおり `brainstorming` から入り、下記 CP対応表に従って各ステップのレビュアーを差し替える。CP-C 以降のタスク単位の todo は SDD が自前で作成するため、tdd-gates 側で重複して作らない。
```

変更後:
```
3. **superpowers チェーンを起動**: `superpowers:using-superpowers` の案内どおり `brainstorming` から入り、下記 CP対応表に従って各ステップのレビュアーを差し替える。CP-C 以降のタスク単位の todo は SDD が自前で作成するため、tdd-gates 側で重複して作らない。**brainstormingを経由せず既存のspec/plan文書から再開する場合**（別セッションでCP-A承認済みの場合等）は、対象spec文書のcommit日時以降に参照範囲のコードへ変更が入っていないか`git log`で確認し、変更があれば一言ユーザーに確認する（CP-A再実行ではなく差分有無の軽量チェック）。
```

- [ ] **Edit 2: スコープ拡大対応（仕様変更時の巻き戻し節への追記）**

変更前:
```
- **仕様変更時の巻き戻し**: ユーザー起因の仕様変更が入ったら、① CP-C以降なら `progress.md` に「仕様変更」エントリ（日時・変更内容・ユーザー指示の要旨）を記録し、② 影響するテストは CP-C の RED からやり直す。③ `tdd-evaluator` はこのエントリと照合し、正当なテスト変更と assert 骨抜きを区別する。
```

変更後:
```
- **仕様変更時の巻き戻し**: ユーザー起因の仕様変更が入ったら、① CP-C以降なら `progress.md` に「仕様変更」エントリ（日時・変更内容・ユーザー指示の要旨）を記録し、② 影響するテストは CP-C の RED からやり直す。③ `tdd-evaluator` はこのエントリと照合し、正当なテスト変更と assert 骨抜きを区別する。④ 変更が実装詳細でなく**要件レベル**（受け入れ基準そのものが変わる）の場合は、Mainが変更後の要件を一行で再言語化しユーザーに確認を取る（独立エージェントによる再検証ではなくMain自身の軽量確認に留める）。
```

- [ ] **Edit 3: trivial/small誤判定対応（比例ルール節への追記）**

変更前:
```
- **substantial**（新規ロジック・複数ファイル横断・公開IF変更・非自明なバグ修正）: CP-A〜D をフルで通す。CP-B（計画品質レビュー）・CP-D（最終スコアカード）は省略不可（唯一の実レビュー層のため）。

数値基準の正典はグローバル CLAUDE.md 作業ルーティング表 small 行。
```

変更後:
```
- **substantial**（新規ロジック・複数ファイル横断・公開IF変更・非自明なバグ修正）: CP-A〜D をフルで通す。CP-B（計画品質レビュー）・CP-D（最終スコアカード）は省略不可（唯一の実レビュー層のため）。

**trivial/small判定に迷う場合**: グローバル CLAUDE.md「変更規模で工程の深さを変えよ。迷えば substantial 扱いにせよ」の原則をそのまま適用する。trivial誤判定はbrainstorming自体のスキップ＝CP-Aの要件ギャップレビューが丸ごと素通りされることを意味するため、この原則の遵守は特に重要である。

数値基準の正典はグローバル CLAUDE.md 作業ルーティング表 small 行。
```

- [ ] **Step 4: 検証**

```bash
grep -n "brainstormingを経由せず既存のspec/plan文書\|要件レベル\|trivial/small判定に迷う場合" ~/.claude/skills/tdd-gates/SKILL.md
```

期待結果: 3件（各追記見出しが1件ずつヒット）。

---

## 実行方式（Execution Handoff）

標準のwriting-plansは「Subagent-Driven（SDD）」「Inline Execution（executing-plans）」の二択を提示するが、本計画には適用しない。理由（`docs/plans/2026-08-02-tdd-gates-lightweight-plan.md`・`docs/plans/2026-08-09-tdd-gates-cp-d-baseline-reduction-plan.md`と同じ前例に従う）:

1. 対象がMarkdown指示文書の追記のみであり、コード・自動テストが存在しない。
2. `~/.claude`はgitリポジトリではないため、SDDの前提（各タスクがgit commitを生み、ledgerがコミットハッシュを記録して復旧する）が機能しない。
3. 全編集は本計画内で完全に事前確定されている（探索・判断の余地がない「内容が事前確定したexact-edit」に該当）。

**推奨する実行方式**: Main（またはMainが直接委任する一括実行）が、Task 1の3 EditをEditツールで適用する。検証ステップ（grep）で確認する。完了後、本リポジトリから`scripts/sync.sh`を実行して`~/.claude`の変更を`my-claude`へ同期・commit・pushする。
