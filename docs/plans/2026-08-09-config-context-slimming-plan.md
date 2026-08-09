# グローバルCLAUDE.md・自作skills・agentsのコンテキスト圧縮 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: 本計画はコード・テストを持たないMarkdown指示文書の監査・編集のみで構成される。標準のsubagent-driven-development/executing-plansの二択は適用しない。詳細は末尾「実行方式（Execution Handoff）」を参照。

**Goal:** 設計書`docs/specs/2026-08-09-config-context-slimming-design.md`に基づき、`~/.claude/CLAUDE.md`・`~/.claude/skills/{tdd-gates,codemap,html-template-import}/SKILL.md`・`~/.claude/agents/*.md`（13ファイル）を対象に、成果物種別ごとの基準（CLAUDE.mdは削除、skills/agentsはreferences外出し）でコンテキスト圧縮を行う。

**Architecture:** 2段階。Phase 1（監査）は読み取り専用サブエージェント（Explore）を並列起動し、各対象ファイルに対して「削除候補」または「references外出し候補」を具体的な行範囲・移動先・本文に残す参照文とともに返させる。Phase 2（適用）はMainが監査結果を集約し、過剰な圧縮がないか確認したうえで`~/.claude/`側に直接Editを適用する。

**Tech Stack:** Markdown。対象ファイルの実体はすべて`~/.claude/`配下。`my-claude/claude/`はミラーのため直接編集しない。

## Global Constraints

- 対象: `~/.claude/CLAUDE.md`（1件）／`~/.claude/skills/{tdd-gates,codemap,html-template-import}/SKILL.md`（3件）／`~/.claude/agents/*.md`（13件: dev-python, doc-updater, doc-verifier, planner, review-correctness, review-doc-readability, review-maintainability, review-performance, review-security, review-test, tdd-evaluator, tdd-implementer, trivial-executor）。
- 対象外: プロジェクトCLAUDE.md、plugin提供skills（superpowers/context7/frontend-design等）、`references/`配下ファイルの中身（監査でリンク整合は確認するが、内容そのものの圧縮はしない）。
- 各editorは`references/`の既存命名規約に従う: agentsは`~/.claude/agents/references/{doc/,python/,review.md,planner.md}`のようにトピック別サブディレクトリ+裸名詞。skillsは各skill配下の`references/`。新規ファイルを作る場合もこの規約に揃える。
- `~/.claude`はgitリポジトリではないため、各タスクに`git commit`ステップは含めない。全タスク完了後、本リポジトリから`scripts/sync.sh`を実行して同期・commit・push（実行前にユーザー確認）。
- CLAUDE.mdの削除基準は「この行を消したらClaudeがミスするか？しないなら消せ」。skills/agents本文の外出し基準は「この記述は発火／起動の都度必要か？」（都度必要なら本文残置、稀にしか要らない詳細はreferences化）。
- frontmatter（skillの`name`/`description`、agentの`name`/`description`/`tools`/`model`）は圧縮対象外。トリガー精度に関わるため一切変更しない。
- 迷う削減候補（手順の欠落やトリガー精度低下の恐れがあるもの）は適用せず、ユーザーに提示して判断を仰ぐ。

---

## Task 1: 監査ディスパッチ（Explore 16件並列 + Main自己監査1件）

**Files:** なし（読み取りのみ、既存ファイルを変更しない）

**Interfaces:**
- Produces: 各監査エージェントの返答は次の構造化フォーマットに従う（Task 2がこの形式を集約する）:
  ```
  ## <対象ファイルパス>
  ### 現状維持（都度必要）
  - <行範囲>: <一言理由>
  ### 外出し候補
  - <行範囲>: 移動先=<references/内の既存 or 新規ファイルパス>
    本文に残す参照文: "<正確な文面>"
    元の抜粋: "<該当箇所の引用>"
  ### 要確認（判断が割れる境界）
  - <行範囲>: <なぜ判断が割れるか>
  ```

- [ ] **Step 0: 適用後の突合用に、対象16ファイルのfrontmatterを退避しておく**

```bash
mkdir -p /tmp/claude-1001/-home-asama-my-claude/*/scratchpad/frontmatter-baseline 2>/dev/null || true
for f in ~/.claude/skills/tdd-gates/SKILL.md ~/.claude/skills/codemap/SKILL.md ~/.claude/skills/html-template-import/SKILL.md ~/.claude/agents/*.md; do
  sed -n '1,/^---$/p' "$f" | tail -n +2 | head -n -1
done > /tmp/claude-1001/-home-asama-my-claude/*/scratchpad/frontmatter-baseline/before.txt
```

（実際のパスはセッションのスクラッチパッドディレクトリに合わせる。Task 4 Step 1でこのファイルと適用後の値を突合する。）

- [ ] **Step 1: skills 3件・agents 13件を対象に、Exploreを1メッセージ内で16並列起動する**

各Exploreエージェントへの共通プロンプトテンプレート（`<TARGET_FILE>`を実ファイルパスに置換して使う）:

```
以下のMarkdown指示文書を監査してください。あなたは読み取り専用で、編集は行いません。

対象ファイル: <TARGET_FILE>

対象ファイルが属するディレクトリの references/ 配下（存在する場合）も併せて読み、
どのトピックが既にどのファイルに外出しされているかを把握してください。

判定基準: 「この記述はスキル発火／エージェント起動の都度必要か？」
- 都度必要な手順・チェックリスト・分岐条件・制約文は本文に残す対象（削らない）。
- 発火/起動の都度は不要な背景説明・非自明だが稀にしか要らない詳細情報・長い例示は
  references/ へ外出しする候補とする。既存の references/ ファイルにトピックが一致すれば
  そこへの追記を提案し、一致しなければ新規ファイル名を提案する（命名規約:
  トピック別サブディレクトリ + 裸名詞、例 references/doc/xxx.md）。
- frontmatter（name/description/tools/model）は対象外。一切変更を提案しない。
- 判断が割れる境界（削ってよいか自信が持てない）は「外出し候補」に入れず
  「要確認」に分類し、理由を書く。

出力は次の形式に厳密に従ってください（他の文章を前後に付けない）:

## <TARGET_FILE>
### 現状維持（都度必要）
- <行範囲>: <一言理由>
### 外出し候補
- <行範囲>: 移動先=<references/内の既存 or 新規ファイルパス>
  本文に残す参照文: "<正確な文面>"
  元の抜粋: "<該当箇所の引用>"
### 要確認（判断が割れる境界）
- <行範囲>: <なぜ判断が割れるか>
```

対象16ファイル（それぞれ上記テンプレートの`<TARGET_FILE>`に代入し、1メッセージ内でAgentツールを16回並列呼び出しする）:

1. `~/.claude/skills/tdd-gates/SKILL.md`
2. `~/.claude/skills/codemap/SKILL.md`
3. `~/.claude/skills/html-template-import/SKILL.md`
4. `~/.claude/agents/dev-python.md`
5. `~/.claude/agents/doc-updater.md`
6. `~/.claude/agents/doc-verifier.md`
7. `~/.claude/agents/planner.md`
8. `~/.claude/agents/review-correctness.md`
9. `~/.claude/agents/review-doc-readability.md`
10. `~/.claude/agents/review-maintainability.md`
11. `~/.claude/agents/review-performance.md`
12. `~/.claude/agents/review-security.md`
13. `~/.claude/agents/review-test.md`
14. `~/.claude/agents/tdd-evaluator.md`
15. `~/.claude/agents/tdd-implementer.md`
16. `~/.claude/agents/trivial-executor.md`

- [ ] **Step 2: Main自身が`~/.claude/CLAUDE.md`を同一プロセスで自己監査する**

判定基準: 「この行を消したらClaudeがミスするか？しないなら消せ」。以下を削除候補とする。
- Claudeがコードやfrontmatterから推論できる自明な事項。
- 発火頻度が低くskill化すべき知識で、該当skillが既に存在する場合（Step 1の16監査結果と突き合わせ、重複記述があればCLAUDE.md側を削り、skillへの言及のみ残す）。
- 実質的な強制力がなくフックで代替可能なリマインダー文。

出力形式はStep 1と同じ（「外出し候補」は「削除候補」に読み替え、移動先の代わりに削除理由を書く）。

---

## Task 2: 集約とユーザー確認

**Files:** なし

**Interfaces:**
- Consumes: Task 1の17件の監査結果（構造化フォーマット）。
- Produces: 適用可否が確定した差分リスト（Task 3が使う）。

- [ ] **Step 1: 17件の監査結果をMainが集約する**

各ファイルの「外出し候補／削除候補」と「要確認」を一覧化する。この際、以下を確認する:
- 移動先として提案された`references/`ファイルが実在するか（実在しなければ新規作成が必要と記録）。
- 同じ内容が複数ファイルから同じ移動先に提案されていないか（重複があれば1箇所に統合するよう調整）。
- CLAUDE.mdの削除候補のうち「skill化すべき」に分類されたものが、対応するskillの監査結果（現状維持または外出し候補）と整合しているか。

- [ ] **Step 2: 「要確認」項目と、過剰な圧縮の疑いがある「外出し候補／削除候補」をユーザーに提示する**

各項目について、削る/外出しする場合の影響（手順欠落・トリガー精度低下の可能性）を一言で添えて提示し、適用可否をユーザーに確認する。ユーザーが不採用と判断した項目は適用対象から除外する。

- [ ] **Step 3: 確定した差分リストを次タスクへ引き渡す**

「現状維持」項目には触れない。「外出し候補／削除候補」のうち承認されたものだけを、ファイルごとに（元の抜粋 → 削除 or 参照文への置換、および移動先ファイルへの追記内容）のペアとして確定する。

---

## Task 3: 適用

**Files:**
- Modify: Task 2で確定した対象ファイル（`~/.claude/CLAUDE.md`、対象skillsのSKILL.md、対象agentsの本体）
- Modify or Create: Task 2で確定した移動先の`references/`ファイル

**Interfaces:**
- Consumes: Task 2で確定した差分リスト（元の抜粋・置換後の参照文・移動先ファイルと追記内容）。

- [ ] **Step 1: 適用前に、確定した各「元の抜粋」が対象ファイルに現在も存在するか確認する**

Task 1の監査からTask 2のユーザー確認までの間に対象ファイルが変更されていないことを前提とするが、Editツール実行前に該当箇所をReadし、文字列が完全一致しない場合は推測で適用せず、その項目をスキップして報告する。

- [ ] **Step 2: skills/agentsの外出し候補を適用する**

各項目について、移動先の`references/`ファイル（既存なら追記、新規ならファイル作成）に元の抜粋の内容を移し、本文の該当箇所をTask 2で確定した参照文に置き換える。

- [ ] **Step 3: CLAUDE.mdの削除候補を適用する**

各項目について、該当行を削除する（skill化に伴う削除の場合、既存の該当skillへの言及が本文中に残っていることを確認し、なければ短い言及を1行追加する）。

- [ ] **Step 4: 全対象ファイルへの適用が完了したことを確認する**

Task 2で確定した差分リストの全項目が適用済み（またはStep 1でスキップと明記）であることをチェックする。

---

## Task 4: 検証

**Files:** なし（読み取りのみ）

- [ ] **Step 1: frontmatterが変更されていないことを確認する**

```bash
for f in ~/.claude/skills/tdd-gates/SKILL.md ~/.claude/skills/codemap/SKILL.md ~/.claude/skills/html-template-import/SKILL.md ~/.claude/agents/*.md; do
  echo "== $f =="; sed -n '1,/^---$/p' "$f" | tail -n +2 | head -n -1
done
```

期待結果: Task 1着手前に記録したfrontmatter（name/description/tools/model）と一字一句一致していること（Step 1実行前に`git diff`等で変更前の値を控えておき、目視突合する）。

- [ ] **Step 2: 外出し先ファイルへのリンクが実在することを確認する**

```bash
grep -rn "references/" ~/.claude/skills/tdd-gates/SKILL.md ~/.claude/skills/codemap/SKILL.md ~/.claude/skills/html-template-import/SKILL.md ~/.claude/agents/*.md
```

出力された各`references/...`パスについて、対象ファイルからの相対パスまたは絶対パスでファイルが実在することを`ls`で確認する。

- [ ] **Step 3: 正典との矛盾がないことを確認する**

プロジェクトメモリが正典と定めている箇所（`project-claude-config-inventory.md`の「reviewer本数/分離原則=gates.md・フロー図=SKILL.md・enforcement=Hooks表」、`project-agents-restructure.md`の命名規約）と、適用後の記述に矛盾がないか目視確認する。矛盾があれば修正する。

---

## Task 5: 同期確認

**Files:** なし

- [ ] **Step 1: 全タスク完了後、ユーザーに`scripts/sync.sh`の実行可否を確認する**

Task 1〜4の完了サマリー（各カテゴリでの削減・外出し件数、ユーザーが不採用とした項目）を提示し、`scripts/sync.sh`（commit+push自動）の実行可否を確認する。

- [ ] **Step 2: 承認後、本リポジトリから`scripts/sync.sh`を実行する**

```bash
bash scripts/sync.sh
```

期待結果: `~/.claude/CLAUDE.md`・`~/.claude/skills/`・`~/.claude/agents/`の変更が`my-claude/claude/`側に反映され、commit+pushが完了する。

---

## 実行方式（Execution Handoff）

標準のwriting-plansは「Subagent-Driven（SDD）」「Inline Execution（executing-plans）」の二択を提示するが、本計画には適用しない。理由（`docs/plans/2026-08-09-tdd-gates-cp-d-baseline-reduction-plan.md`と同じ前例に従う）:

1. 対象はすべてMarkdown指示文書の監査・編集であり、コード・自動テストが存在しない。
2. `~/.claude`はgitリポジトリではないため、SDDの前提（各タスクがgit commitを生み、ledgerがコミットハッシュを記録して復旧する）が機能しない。
3. Task 1（監査）は探索・判断を要するため「内容が事前確定したexact-edit」ではないが、監査自体は読み取り専用サブエージェントへの並列委任として完全に事前確定されている。Task 3（適用）はTask 2で確定した差分リストに基づく機械的な置換であり、事前確定済みとなる。

**推奨する実行方式**: Mainが本計画のTask 1〜5を順に直接実行する。Task 1はAgentツール（Explore）を1メッセージ内で16並列起動し、Main自身がCLAUDE.mdを自己監査する。Task 2〜3はMainが集約・確認・適用する。Task 4はMainが検証する。Task 5はユーザー確認後にMainが`scripts/sync.sh`を実行する。
