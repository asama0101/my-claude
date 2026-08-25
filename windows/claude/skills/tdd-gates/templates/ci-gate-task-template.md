# CP-E タスク雛形（ci-gate-task-template）

**土台**: `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.2.0/skills/writing-plans/SKILL.md`「## Task Structure」形式。

writing-plans が CP-E の条件（CI を運用するプロジェクト）を満たすと判定した場合、計画書の末尾タスクとして以下の雛形をそのまま追加する。追加後は CP-C と同じ SDD の通常タスクループに乗る——CP-E は「タスクの中身」を規定するだけで、独自のディスパッチ・リトライ機構は持たない。

**CI 運用時のみ条件付きで追加されるタスクである**（CI を運用しないプロジェクトは plan 文書にスキップ理由を記して丸ごとスキップする。`checkpoints.md` CP-E「スキップ条件」参照）。

---

## タスク雛形

````markdown
### Task N: CI 品質ゲート整備

**Files:**
- Create/Modify: `.github/workflows/<ci-workflow>.yml`（CI プロバイダは GitHub Actions が既定。プロファイルで差し替え可）
- Reference: `~/.claude/skills/tdd-gates/references/profiles/<lang>.md`「CI ステージ」節（ステージごとの具体コマンドの正典）

**Interfaces:**
- Consumes: 対象言語プロファイルが供給する各ステージの実行コマンド（lint/typecheck/build/unit/integration/主要E2E）
- Produces: CI ワークフロー定義（後続タスク・レビューが被覆確認に使う）

**実装役**: `doc-updater`
**レビュー役**: `tdd-evaluator`（CP-C の仕組みに乗り、必須ステージの被覆を採点する。ディスパッチモデルはCP-Cと同じ階層化ルール[`checkpoints.md`CP-C「evaluatorモデル階層化」]に従う）

- [ ] **Step 1: 対象言語プロファイルの CI ステージ定義を確認**

`~/.claude/skills/tdd-gates/references/profiles/<lang>.md` の「CI ステージ」表を Read し、lint／typecheck／build／unit test／integration test／主要E2E の具体コマンドを確認する。

- [ ] **Step 2: CI ワークフローを作成/更新**

必須ステージ（lint／typecheck／build／unit test／integration test／主要E2E）をすべて実行するようワークフローを書く。任意ステージ（preview環境デプロイ）は既定 off。

- [ ] **Step 3: ワークフロー定義を検証**

`yamllint` 等でワークフロー定義の構文を検証する（実際の push・CI 実行はしない——同期性の限界。`checkpoints.md` CP-E「同期性の限界」参照）。

- [ ] **Step 4: レビュー（tdd-evaluator）**

`tdd-evaluator` が必須ステージの被覆を、ワークフロー定義の該当行と照合して採点する。欠落があれば Critical（`checkpoints.md` CP-E の Critical 行: 必須ステージのいずれかが CI 定義から欠落している）。

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/<ci-workflow>.yml
git commit -m "ci: add quality gate stages"
```
````

---

## 埋めるプレースホルダ

- `<ci-workflow>`: プロジェクトの CI ワークフローファイル名
- `<lang>`: 対象言語プロファイル名（例 `pytest`）
- 必須ステージの具体コマンドは、上記プロファイルの「CI ステージ」表から writing-plans が転記する（ここでの新規発明・推測は禁止）
