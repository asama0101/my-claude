# CP-F タスク雛形（doc-sync-task-template）

**土台**: `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.2.0/skills/writing-plans/SKILL.md`「## Task Structure」形式。

writing-plans が CP-F の条件（ドキュメント影響がある変更）を満たすと判定した場合、CP-E タスクの後（CI を運用しないプロジェクトでは CP-C の実装タスク群の後）に、計画書の末尾タスクとして以下の雛形をそのまま追加する。実装タスクとしては CP-C と同じ SDD の通常タスクループに乗るが、**レビュー役だけが `tdd-evaluator` ではなく `doc-verifier` になる**（執筆者と検証者の分離を保つため）。

**ドキュメント影響があるタスクの後にのみ追加される**（リファクタのみ等、ドキュメント影響が無ければスキップする。`checkpoints.md` CP-F「スキップ条件」参照）。

---

## タスク雛形

````markdown
### Task N: ドキュメント同期

**Files:**
- Modify: `<影響を受けるREADME/ガイド/API仕様のパス>`

**Interfaces:**
- Consumes: 本タスクより前の実装タスクが確定した挙動・数値・コマンド・スキーマ（推測・発明は禁止）
- Produces: 更新済みドキュメント（後続の受け入れ確認で参照される）

**実装役**: `doc-updater`
**レビュー役**: `doc-verifier`（別コンテキストで記載事実とソースを照合する）

- [ ] **Step 1: 影響範囲の洗い出し**

`doc-updater` が実装差分（`git diff`）を確認し、同期が必要なドキュメント箇所を洗い出す。

- [ ] **Step 2: ドキュメント執筆・更新**

`doc-updater` が該当箇所を更新する。**不発明制約**: ソースに根拠の無い数値・目標値・事実を発明しない。導出できる事実のみ記載し、根拠が無い項目は「未規定」と明示する。AI 臭い定型表現があれば検出・修正する。

- [ ] **Step 3: 整合確認（doc-verifier）**

Main が別コンテキストで `doc-verifier` を起動する。記載事実（数値・コマンド・スキーマ・挙動）をソースと照合し、文書に新規登場した数値・事実の裏取り（発明された値の検出）を照合観点に含める。不一致は✓/不一致の表で報告する。

- [ ] **Step 4: 差し戻し・再検証**

不一致があれば `doc-updater` に差し戻して修正させる。再検証では前回不一致を1件ずつ解消／部分解消／未解消で判定する。Critical（`checkpoints.md` CP-F の Critical 行: 裏付けの無い事実主張が未解消のまま残っている）が解消するまで繰り返す。

- [ ] **Step 5: Commit**

```bash
git add <影響を受けるドキュメントのパス>
git commit -m "docs: sync with implementation changes"
```
````

---

## 埋めるプレースホルダ

- `<影響を受けるREADME/ガイド/API仕様のパス>`: `doc-updater` が Step 1 で洗い出した具体パス
- `doc-updater` への委任プロンプトには「ソースに根拠の無い数値・目標値・事実を発明しない。導出できる事実のみ記載し、根拠が無い項目は『未規定』と明示する」を必ず含める（`checkpoints.md` CP-F「不発明制約」）
- `doc-verifier` への委任プロンプトには「文書に新規登場した数値・事実の裏取り（発明された値の検出）」を照合観点として指示する
