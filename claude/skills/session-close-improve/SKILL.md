---
name: session-close-improve
description: |
  セッション終了時の改善ワークフロー。実装・作業セッションを締め括る際に使う。サブエージェント使用を振り返り、使った agent/skill 定義の改善要否（汎用は更新・固有は CLAUDE.md/project-local へ振分け）もチェックし、必要最小限の更新のみ実施し、メモリを保存する。

  以下のような発言で起動すること:「終了します」「振り返りをしたい」「セッションを終える前に」「学びをまとめたい」「session ending」「wrap up」「このセッションの改善をしたい」「CLAUDE.mdを更新したい」「今回の学びを反映させたい」

  実装後・大きな機能追加後・長い作業セッションの終わりに積極的に起動する。
---

# セッション終了改善フロー

軽量ワークフロー。過剰な更新はしない。**今やる価値がある改善だけ**実施し、それ以外は追跡せず捨てる（本当に重要なら次回また出る）。

---

## Step 1: 振り返り（改善の種を拾う）

今セッションを以下の順（上が高優先）で点検し、定義に恒久反映すべき種を拾う:

1. **ユーザーの指摘・依頼（最優先の種）**: セッション中にユーザーが訂正・要望したことを洗い出す。自己観察由来の先回りより優先（[[feedback-user-input-drives-definitions]]）。
2. **必須エージェントの使用漏れ**: tdd-guide / reviewer-*（run-reviewers）/ python-dev が必要場面で使われたか。汎用 `claude` で代替した・並列化できた場面を逐次実行した、も拾う。
3. **使った agent/skill の実害**: 今回実際に困った具体例 — 誤誘導した／古い参照・存在しないファイルを指した／期待した出力形式でなかった。

各種を1行で **今やる / 捨てる** に二分する:

- **今やる** = 実害が起きた、または ユーザー指摘で対策が1行で言える → Step 2 へ。
- **捨てる** = それ以外（様子見・判断保留・あれば便利程度）→ 追跡しない（バックログは持たない）。

今やる種が無ければ Step 2 を飛ばして Step 3 へ。

---

## Step 2: 最小更新（今やる種だけ）

拾った種を、ユーザー承認を得てから最小限に反映する。**新しい入れ物（agent/skill 新設）は最終手段**。

**反映先の決め方:**

- **固有**（その repo だけ有用）→ 対象 repo の CLAUDE.md / spec。
- **汎用**（他プロジェクトでも有用）→ 既存 agent/skill 定義 or `~/.claude/agents/references/*.md` へ1〜数行追記。足す先が無い時だけ新規 reference、それも無理な時だけ新規 agent/skill（却下理由を1行で言えること）。

**実装ルール:**

- **CLAUDE.md を変える時は2段**: `/claude-md-management:revise-claude-md` で取り込み → `/claude-md-management:claude-md-improver` でレビュー。（フォールバック: revise が使えない時のみ直接 Read→Edit。CLAUDE.md は直接 Edit 可＝[[hard-block-workarounds]]。）
- agent/skill/reference 定義は 提示→承認→直接 Edit/Write（HARD BLOCK はサブエージェントのみ）。
- Hook を足したら `settings.json` 登録 ＋ CLAUDE.md「アクティブなHooks」表に記載（両方必須）。
- 変更案は表で提示→承認→実装:

| # | 種類 | 反映先パス | 汎用/固有 | 解決する問題 |
|---|------|----------|---------|------------|
| 1 | agent定義更新 | ~/.claude/agents/reviewer-correctness.md | 汎用 | 古い参照 |

**棚卸（今セッションで agent/skill/reference を触った時だけ）:** 触ったものに孤立 reference（被参照ゼロ）・重複・肥大が無いか軽く点検し、整理候補を承認のうえ処理（非破壊・CLAUDE.md「削除制限」に従い方法提示＋承認必須）。

---

## Step 3: spec/plan アーカイブ（docs/superpowers/ がある時のみ）

cwd に `docs/superpowers/specs/` も `plans/` も無ければ本ステップ全体をスキップ。他 STEP と独立した housekeeping。

1. **状態判定**: spec はファイル存在で ✅。plan はチェックボックス集計:
   ```bash
   done=$(grep -cE '^[[:space:]]*- \[x\]' <plan.md>); todo=$(grep -cE '^[[:space:]]*- \[ \]' <plan.md>)
   # todo==0 かつ done>0 → ✅完全完了 / todo>0 → 🔄進行中（据え置き）
   ```
2. **アーカイブ（承認必須・非破壊）**: 100% 完了の plan を候補提示し、承認を得てから `git mv <file> docs/superpowers/plans/done/`。対応 spec も完了なら同様に移動。未完了ファイルは絶対に動かさない。

---

## Step 4: クローズ

メモリ保存: `~/.claude/projects/<project-sanitized-path>/memory/` に、次セッションで要る状態変化だけ最小限に記録する:

- プロジェクトのフェーズ変化・次のステップ
- 次セッションで注意すべき非自明な制約

---

## 終了宣言前チェックリスト

- [ ] Step 1: 3観点（ユーザー指摘／使用漏れ／実害）で種を拾い、各々「今やる／捨てる」に二分
- [ ] Step 2: 今やる種だけ承認のうえ反映（固有/汎用でルーティング・新設は最終手段）。**CLAUDE.md 変更は revise-claude-md→improver で実施・レビュー済み**。棚卸は今セッションでインベントリを触った時のみ
- [ ] Step 3: docs/superpowers がある場合のみ完了分を承認のうえ done/ へ移動（無ければスキップ）
- [ ] Step 4: メモリ保存完了
