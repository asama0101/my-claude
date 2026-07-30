# CP-F タスク雛形（doc-sync-task-template）

**土台**: `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.2.0/skills/writing-plans/SKILL.md`「## Task Structure」形式。

writing-plans が CP-F の条件（選択したドキュメントプロファイルのいずれかのカテゴリがトリガーに該当する変更）を満たすと判定した場合、CP-E タスクの後（CI を運用しないプロジェクトでは CP-C の実装タスク群の後）に、計画書の末尾タスクとして以下の雛形をそのまま追加する。実装タスクとしては CP-C と同じ SDD の通常タスクループに乗るが、**レビュー役だけが `tdd-evaluator` ではなく `doc-verifier` になる**（執筆者と検証者の分離を保つため）。

**ドキュメント影響があるタスクの後にのみ追加される**（リファクタのみ等、ドキュメント影響が無ければスキップする。`checkpoints.md` CP-F「スキップ条件」参照）。

---

## タスク雛形

````markdown
### Task N: ドキュメント同期

**Files:**
- Modify: `<Step 1で特定した該当カテゴリの文書パス>`
- Reference: `~/.claude/skills/tdd-gates/references/profiles/<docs-profile>.md`「対象カテゴリ」節（カテゴリと生成条件の正典）

**Interfaces:**
- Consumes: 本タスクより前の実装タスクが確定した挙動・数値・コマンド・スキーマ（推測・発明は禁止）
- Produces: 更新済みドキュメント（後続の受け入れ確認で参照される）

**実装役**: `doc-updater`
**レビュー役**: `doc-verifier`（別コンテキストで記載事実とソースを照合する）

- [ ] **Step 1: 対象ドキュメントプロファイルの確認とカテゴリ選定**

`~/.claude/skills/tdd-gates/references/profiles/<docs-profile>.md` の「対象カテゴリ」表を Read し、
各カテゴリの生成条件（常時 / 条件付きトリガー）を確認する。`doc-updater` が実装差分（`git diff`）を
確認し、条件付きカテゴリはトリガーに該当する根拠（`file:line`）があるものだけを選定する
（根拠を示せないカテゴリは生成しない。無条件生成の禁止は `checkpoints.md` CP-F 参照）。
選定結果（該当カテゴリ一覧＋各カテゴリの該当根拠）をタスク実行記録に残す。

- [ ] **Step 2: ドキュメント執筆・更新**

`doc-updater` が該当箇所を更新する。**不発明制約**: ソースに根拠の無い数値・目標値・事実を発明しない。導出できる事実のみ記載し、根拠が無い項目は「未規定」と明示する。AI 臭い定型表現があれば検出・修正する。
（新規カテゴリを初めて生成する場合は、目次構成として
`~/.claude/agents/references/doc/design.md`「文書カテゴリ別 目次テンプレート」節の該当見出しを
起草の土台に使う。既存文書の更新は従来どおり `doc/verify.md` 更新モードA/Bに従う。）

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

- `<docs-profile>`: 対象ドキュメントプロファイル名（例 `docs-generic`／`docs-network-tool`）
- `<Step 1で特定した該当カテゴリの文書パス>`: `doc-updater` が Step 1 でトリガー該当と判定した具体パス（根拠が無いカテゴリは含めない）
- `doc-updater` への委任プロンプトには「ソースに根拠の無い数値・目標値・事実を発明しない。導出できる事実のみ記載し、根拠が無い項目は『未規定』と明示する」を必ず含める（`checkpoints.md` CP-F「不発明制約」）
- `doc-verifier` への委任プロンプトには「文書に新規登場した数値・事実の裏取り（発明された値の検出）」を照合観点として指示する
