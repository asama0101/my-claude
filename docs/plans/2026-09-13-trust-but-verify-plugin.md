# trust-but-verify プラグイン化 実装計画

> **For agentic workers:** この計画の主対象 `~/.claude/` は git リポジトリではないため、SDD／executing-plans のコミット単位タスクループは使わない。各タスクは事前確定した exact-edit の列であり、Main が Edit／Write／Bash（mv・mkdir のみ）ツールで直接適用する（グローバル CLAUDE.md「例外（Main直接可）: 内容が事前確定した exact-edit」）。チェックボックス（`- [ ]`）で進捗を追跡する。
>
> **安全指示**: 安全装置（hooks）にブロックされたら、別の技術的手段で回避せず即座に停止し、BLOCKED として報告する。同一リポジトリ・同一ブランチで複数のBash権限サブエージェントを並行起動する場合は、作業ツリーを破棄する操作（`git checkout --`／`git reset --hard`等）を行わない。

**Goal:** `~/.claude/skills/tdd-gates/` を `trust-but-verify` プラグイン（`~/.claude/skills/trust-but-verify/`）へ改名・再構成し、CP-A〜Dを独立スキルに分割する。

**Architecture:** live側`~/.claude/skills/tdd-gates/`で新ディレクトリ構造を構築し、変更不要な参照ファイルはそのまま移設、CP対応部分は5つの新規SKILL.md（オーケストレーター1＋CP-A〜D相当4）に分割・改名して作成する。旧ディレクトリ削除後、外部から`tdd-gates`を参照する9ファイルのパス・名称を更新し、最後に`my-claude-pull`でこのリポジトリへ同期する。

**Tech Stack:** Markdown（Claude Code の skill／agent 定義）、JSON（plugin.json）、Bash（mv/mkdir）、Edit/Write ツール、grep。

**Spec:** `docs/specs/2026-09-13-trust-but-verify-design.md`

## Global Constraints

- 編集対象は live 版 `~/.claude/skills/tdd-gates/`（→`trust-but-verify/`）、および `~/.claude/agents/{tdd-evaluator,tdd-implementer,doc-updater,trivial-executor}.md`・`~/.claude/agents/references/{doc/design,python/rest-api,python/testing}.md`・`~/.claude/rules/skills.md`・`~/.claude/CLAUDE.md`。`linux/claude/`・`windows/claude/` は直接編集しない（Task 10 の `my-claude-pull` で同期する）。
- 各 Edit の `old_string` は本計画に記した現行テキストと一字一句一致させる。一致しなければ止めて報告する（推測で近い行を編集しない）。
- `superpowers`（`~/.claude/plugins/cache/.../subagent-driven-development/`）・`~/.claude/agents/{tdd-evaluator,tdd-implementer,review-*}.md` の**振る舞い**は変更しない。変更するのは `tdd-gates` という文字列（パス・名称）への参照のみ。
- `review-maintainability`の判定基準変更（ponytailラダー化）は本計画の対象外。
- Markdown はハードラップしない。1文・1箇条書き項目は1行で書く。
- タスク順序は Task 1→11 を守る（Task 9 は Task 1〜8 完了後のパスを前提にする）。

---

### Task 1: ディレクトリ構造の構築とplugin.json作成

**Files:**
- Create: `~/.claude/skills/tdd-gates/.claude-plugin/plugin.json`
- Create: `~/.claude/skills/tdd-gates/skills/`（ディレクトリ）

- [ ] **Step 1: `.claude-plugin/`ディレクトリと`skills/`ディレクトリを作成**

Bash:
```bash
mkdir -p ~/.claude/skills/tdd-gates/.claude-plugin
mkdir -p ~/.claude/skills/tdd-gates/skills
```

- [ ] **Step 2: plugin.jsonを作成**

Write: `~/.claude/skills/tdd-gates/.claude-plugin/plugin.json`
```json
{
  "name": "trust-but-verify",
  "version": "0.1.0",
  "description": "superpowers標準チェーンに自己承認を防ぐ独立検証を差し込む品質規律レイヤー（旧tdd-gates）"
}
```

- [ ] **Step 3: 検証**

Run: `cat ~/.claude/skills/tdd-gates/.claude-plugin/plugin.json | python3 -m json.tool`
Expected: JSONパースエラー無く整形出力される。

---

### Task 2: 変更不要な参照ファイル群の移設

**Files:**
- Move: `~/.claude/skills/tdd-gates/references/` → `~/.claude/skills/tdd-gates/references/`（変更なし、パスは同じ階層のまま親ディレクトリごと後でリネームされる。Task 8で親ディレクトリ名を変える）
- Move: `~/.claude/skills/tdd-gates/templates/` → 同上

このタスクでは中身の変更は無い。`references/`（checkpoints.md・scoring.md・profiles/8ファイル）と`templates/`（6ファイル）は既にプラグインルート直下に正しく存在しており、Task 8で親ディレクトリ`tdd-gates/`が`trust-but-verify/`にリネームされれば自動的に正しい位置になる。**このタスクは Step なし（確認のみ）。**

- [ ] **Step 1: 現状確認（移設不要であることの確認）**

Run: `ls ~/.claude/skills/tdd-gates/references/ ~/.claude/skills/tdd-gates/templates/`
Expected: `references/`に`checkpoints.md`・`scoring.md`・`profiles/`、`templates/`に6ファイルが存在する。

---

### Task 3: skills/trust-but-verify/SKILL.md（オーケストレーター）の作成

**Files:**
- Create: `~/.claude/skills/tdd-gates/skills/trust-but-verify/SKILL.md`

- [ ] **Step 1: ディレクトリを作成**

Bash: `mkdir -p ~/.claude/skills/tdd-gates/skills/trust-but-verify`

- [ ] **Step 2: SKILL.mdを作成**

Write: `~/.claude/skills/tdd-gates/skills/trust-but-verify/SKILL.md`
```markdown
---
name: trust-but-verify
description: |
  superpowers のスキルチェーン（brainstorming → writing-plans → subagent-driven-development → finishing-a-development-branch）に上乗せする品質規律レイヤー。AI駆動開発の品質問題（動くように見えて中身がバグだらけ・テストの形骸化・RED未確認・自己承認）を、superpowers の各ステップに差し込むチェックポイント（design-audit・plan-audit・evidence-check・review-aggregate）と、Critical即FAIL＋証拠要求の採点語彙で構造的に潰す。substantial な実装（新機能・バグ修正・非自明な変更）で使う。

  以下のような発言・状況で起動すること:「TDDで実装して」「テストファーストで」「品質ゲートを回して」「チェックポイントを回して」「新機能を実装して（テスト付きで）」「バグを直して（回帰テスト付きで）」。substantial なコード変更の着手時に積極的に起動する。trivial（数行・設定/ドキュメント）は使わず単一軽量 Agent に委任する（比例ルール）。
---

# trust-but-verify — 品質規律オーケストレーター（superpowers 拡張）

あなた（Main）は、superpowers のスキルチェーンを背骨として使う。trust-but-verify は自前の駆動ループを持たない。チェーンの各ステップに寄生してチェックポイント（`trust-but-verify:design-audit`・`trust-but-verify:plan-audit`・`trust-but-verify:evidence-check`・`trust-but-verify:review-aggregate`）を差し込み、「証拠不信の原則」「専門レビュアーによる多次元評価」「0–3点採点語彙・Critical即FAIL」を、そのステップの担当エージェントに上乗せするだけの薄いレイヤーである。

**中核原則**: superpowers の Iron Law「NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST」を規律の根拠とする（`superpowers:test-driven-development` が実行手順の正典）。trust-but-verify はこれを**検証**する層——特に `evidence-check` では、SDD の `task-reviewer-prompt.md` にある "Do not re-run the suite to confirm their report." を明示的に上書きし、evaluator が実装者の報告を鵜呑みにせず自ら再実行する（詳細は `evidence-check` および `~/.claude/skills/trust-but-verify/references/checkpoints.md`）。

## 起動時にやること（チェックリスト）

各項目をtodo化して順に実施する。

1. **プロファイル確定**: 対象言語のプロファイルを1つ選ぶ（Python は `~/.claude/skills/trust-but-verify/references/profiles/pytest.md`）。パス→テスト種別の対応表を読み、対象ファイルのテスト種別（unit/integration/e2e）を判定して**ユーザーに確認**する。**CI品質ゲート整備を回すなら、プロファイルの「CI ステージ」定義（lint/typecheck/build/unit/integration/主要E2E の具体コマンド）も確認する**。
   - **対象言語のプロファイルが無い場合**（現状は pytest／browser-manual-e2e の2本）は、`~/.claude/skills/trust-but-verify/references/profiles/_template.md` から新規プロファイルを起草する。テスト実行コマンドと合格ログ形式を**ユーザーに承認してもらってから**開始する（未定義のまま pytest 前提で進めない。停止時は `~/.claude/skills/trust-but-verify/references/scoring.md`「停止シグナル」の `profile_undefined` 形式で提示する）。
   - **確定したプロファイルのパスは、各サブスキルを起動するたびにプロンプトへ必ず明記して渡す**（エージェント側での推測は禁止）。
   - **文書同期タスクを回すなら、ドキュメントプロファイルも確定する**: プロジェクトの `CLAUDE.md` に宣言があればそれに従う（例「ドキュメントプロファイル: docs-network-tool」）。宣言が無ければ既定の `~/.claude/skills/trust-but-verify/references/profiles/docs-generic.md` を使ってよいかユーザーに一言確認する（言語プロファイルと異なり`docs-generic`は安全な既定値のため `profile_undefined` 停止は発火しない）。プロファイルが無いドメインは `~/.claude/skills/trust-but-verify/references/profiles/_template-docs.md` から起草しユーザー承認を得る。
2. **証拠の記録先（成果物は必ずファイル化する）**: `design-audit`・`plan-audit` は独自の PASS/CONDITIONAL/FAIL（最大2回の再評価）で完結し、専用の台帳は持たない。ただし `tdd-evaluator` は Bash 書き込みを持たないため、**Main が Quality Gate Report を対象 spec/plan 文書の末尾に追記してから git commit する**（brainstorming/writing-plans が既に commit する文書に相乗りし、新規の台帳ファイルは作らない）。チャット報告のみで終わらせない。**`evidence-check` 以降は SDD（`subagent-driven-development`）の `progress.md` に証拠行（RED／GREEN コミット SHA、RED/GREEN コマンドと出力）を追記する形に統一**し、**`review-aggregate` の集約スコアカードも Main が `progress.md` に書き出す**。**タスクループ開始前に Main がプロファイルの全体実行コマンドを1回実行し、その結果をベースラインとして `progress.md` に記録する**（`review-aggregate` 手順0 の比較基準。`evidence-check` の各タスクではフルスイートを再実行しない）。trust-but-verify 独自の台帳（旧 `.tdd-gates/ledger-*.md`）は作らない。
3. **superpowers チェーンを起動**: `superpowers:using-superpowers` の案内どおり `brainstorming` から入り、下記対応表に従って各ステップのレビュアーを差し替える。`evidence-check` 以降のタスク単位の todo は SDD が自前で作成するため、trust-but-verify 側で重複して作らない。**brainstormingを経由せず既存のspec/plan文書から再開する場合**（別セッションで`design-audit`承認済みの場合等）は、対象spec文書のcommit日時以降に参照範囲のコードへ変更が入っていないか`git log`で確認し、変更があれば一言ユーザーに確認する（`design-audit`再実行ではなく差分有無の軽量チェック）。

## チェックポイント対応表（superpowers チェーンへの寄生地図）

| サブスキル | 内容（旧名） | 上乗せ先 | 担当 | リトライ機構 |
|---|---|---|---|---|
| `trust-but-verify:design-audit` | 要件ギャップレビュー（旧CP-A） | brainstorming の Spec Self-Review 後・User Review Gate 前に独立エージェントの敵対的検査を挿入 | `tdd-evaluator` | 独自 PASS/CONDITIONAL/FAIL・最大2回 |
| `trust-but-verify:plan-audit` | 計画品質レビュー（旧CP-B） | writing-plans の Self-Review 後・Execution Handoff 前 | `tdd-evaluator` | 同上・最大2回 |
| `trust-but-verify:evidence-check` | タスク証拠検証（旧CP-C） | SDD の task-reviewer ディスパッチを差し替え（汎用reviewerでなく`tdd-evaluator`）。UI/UX・security/perfは条件付き追加 | `tdd-evaluator` | SDD純正の5ラウンドfix loopをそのまま使用（独自カウンタは持たない） |
| `trust-but-verify:review-aggregate` | 最終スコアカード（旧CP-D） | SDD Final Review の `code-reviewer.md` を差し替え | Mainがフルスイート1回（手順0）→`review-*`条件付き2〜5本並列→`tdd-evaluator`集約（徴候時はミューテーション検証必須） | SDD純正のFinal Review（1修正波+1 scoped re-review） |
| （CI品質ゲート整備、条件付き） | 旧CP-E | writing-plans が条件を満たせば末尾タスクとして自動追加 | 実装=`doc-updater`、レビュー=`tdd-evaluator` | SDD純正の5ラウンドloop |
| （ドキュメント同期、条件付き） | 旧CP-F | 同上、CI整備タスクの後。選択したドキュメントプロファイルのカテゴリ表を参照し、トリガー条件該当カテゴリのみ対象 | 実装=`doc-updater`、レビュー=`doc-verifier` | SDD純正の5ラウンドloop |

各チェックポイントの目的・Critical基準・証拠要件の正典は `~/.claude/skills/trust-but-verify/references/checkpoints.md`。採点形式（design-audit/plan-audit用とevidence-check以降用の2モード）の正典は `~/.claude/skills/trust-but-verify/references/scoring.md`。モデル選定（どのロールをどのモデル階層で起動するか）は `superpowers:subagent-driven-development` 本体の Model Selection 節を参照する（trust-but-verify独自のモデル階層化ルールは持たない）。

## 比例ルール（trivial / small / substantial）

- **trivial**（数行・既存パターン踏襲・テスト不要）: trust-but-verify を使わず単一の軽量 Agent（`trivial-executor`）に一括委任する。
- **small**（数値基準の正典はグローバル CLAUDE.md 作業ルーティング表 small 行）: **判定主体は `plan-audit`**（writing-plans の計画品質レビュー時に `tdd-evaluator` が `git diff --stat` 見込みと既存テスト一覧で4条件を照合する）。該当すれば `evidence-check` のうち RED→GREEN 相当だけの簡略ルートを取ってよいが、`evidence-check` の Critical（実失敗ログ）はいかなる場合も省略しない。
- **substantial**（新規ロジック・複数ファイル横断・公開IF変更・非自明なバグ修正）: `design-audit`〜`review-aggregate` をフルで通す。`plan-audit`（計画品質レビュー）・`review-aggregate`（最終スコアカード）は省略不可（唯一の実レビュー層のため）。

**trivial/small判定に迷う場合**: グローバル CLAUDE.md「変更規模で工程の深さを変えよ。迷えば substantial 扱いにせよ」の原則をそのまま適用する。trivial誤判定はbrainstorming自体のスキップ＝`design-audit`の要件ギャップレビューが丸ごと素通りされることを意味するため、この原則の遵守は特に重要である。

数値基準の正典はグローバル CLAUDE.md 作業ルーティング表 small 行。

## 重要ルール

- **証拠主義**: 「テストは通るはず」「多分失敗する」は無効。RED/GREEN は必ず実行ログを証拠として `progress.md`（`evidence-check`以降）またはスコアカード（`design-audit`/`plan-audit`）に残す（`~/.claude/skills/trust-but-verify/references/scoring.md` の証拠フォーマット）。
- **Critical即FAIL**: スコアが高くても Critical 未達なら即 FAIL。特に `evidence-check` の RED は「実際に失敗したログ」が無ければ通さない。
- **Main のコンテキスト衛生**: Main は生ログ全文を抱えない。各サブエージェントには結論・スコア・証拠スニペット・`file:line` だけを蒸留して返させる。
- **並列実装・worktree分離**: SDD の Setup（`superpowers:using-git-worktrees`）にそのまま従う。trust-but-verify 独自の追加要求はない。
- **仕様変更時の巻き戻し**: ユーザー起因の仕様変更が入ったら、① `evidence-check`以降なら `progress.md` に「仕様変更」エントリ（日時・変更内容・ユーザー指示の要旨）を記録し、② 影響するテストは `evidence-check` の RED からやり直す。③ `tdd-evaluator` はこのエントリと照合し、正当なテスト変更と assert 骨抜きを区別する。④ 変更が実装詳細でなく**要件レベル**（受け入れ基準そのものが変わる）の場合は、Mainが変更後の要件を一行で再言語化しユーザーに確認を取る（独立エージェントによる再検証ではなくMain自身の軽量確認に留める）。
- **チェックポイントを1サイクルとして自動で通し、受け入れ確認は最後に一度だけ**: `design-audit`→`plan-audit`→`evidence-check`→`review-aggregate`→CI整備→文書同期まで、CONDITIONAL再評価や SDD の fix loop を正規工程として自動で回し、人間の都度承認を挟まない（正常系の停止点はここにしかない）。文書同期完了後に一度だけユーザーの受け入れ確認を取る（グローバル CLAUDE.md「実装後の受け入れ→ドキュメント更新」準拠）。この受け入れ確認の際、`tdd-evaluator` が受け入れチェックリスト（受入基準＋`review-aggregate`の実施次元（2〜5本）＋CI整備/文書同期の整備状況＋例外処理・権限漏れ・変更影響範囲）と、`review-aggregate`で修正済みの「スコープ外の既存問題」一覧（`~/.claude/skills/trust-but-verify/references/checkpoints.md`「CP-D」参照）を生成する。NG なら該当チェックポイントへ差し戻す。
  - **止まるのはガードレール発動時のみ**: 非自明な要件の抜け漏れ（`design-audit`/`plan-audit`）・再評価/fix loop 上限到達による FAIL 確定・仕様の曖昧化。構造化フォーマットは `~/.claude/skills/trust-but-verify/references/scoring.md`「停止シグナル（GUARDRAIL_HALT）」参照。これは「都度の承認待ち」とは別物であり正常系フローを止めない。複数マイルストーン計画では、マイルストーン単位で文書同期まで自動通しし、各マイルストーンの文書同期後 1 回の受け入れ確認に一本化する（マイルストーン間の中間確認はしない）。

## 参照ファイル

- `~/.claude/skills/trust-but-verify/references/checkpoints.md` — 旧CP-A〜F の目的・上乗せ先・担当・Critical・証拠要件。
- `~/.claude/skills/trust-but-verify/references/scoring.md` — 0–3採点・80%/60–79%・Critical即FAIL・CONDITIONAL上限・design-audit/plan-audit用とevidence-check以降用の2モードのスコアカード形式。
- `~/.claude/skills/trust-but-verify/templates/*.md` — 各サブスキルが差分追記／差し替えるプロンプトテンプレート。
- `~/.claude/skills/trust-but-verify/references/profiles/pytest.md` — Python/pytest のパス判定・実行コマンド・合格ログ形式（深い作法は agents/references/python/testing.md へ委譲）。
- `~/.claude/skills/trust-but-verify/references/profiles/browser-manual-e2e.md` — ビルド/自動テストランナーを持たない単一HTMLファイルアプリ向け。全レイヤーをe2eとして扱い、claude-in-chromeで手動E2Eの証拠を取る。
- `~/.claude/skills/trust-but-verify/references/profiles/_template.md` — 新言語追加用スケルトン。
- `~/.claude/skills/trust-but-verify/references/profiles/docs-generic.md` — 文書同期タスクが対象とするドキュメントカテゴリの既定セットと生成条件（README/ガイド/API仕様[+データスキーマ・IF定義書]は常時、セキュリティ設計書・リリースノートは条件付き）。
- `~/.claude/skills/trust-but-verify/references/profiles/docs-network-tool.md` — SSH/Telnet通信・ネットワーク機器連携等のドメイン向け追加カテゴリ（検証環境トポロジー・差分マップ／監視・アラート定義書／ランブック、すべて条件付き）。`docs-generic.md`を継承。
- `~/.claude/skills/trust-but-verify/references/profiles/_template-docs.md` — 新規ドキュメントプロファイル追加用スケルトン。
```

- [ ] **Step 3: 検証**

Run: `head -8 ~/.claude/skills/tdd-gates/skills/trust-but-verify/SKILL.md`
Expected: frontmatterに`name: trust-but-verify`が含まれる。

---

### Task 4: skills/design-audit/SKILL.md の作成

**Files:**
- Create: `~/.claude/skills/tdd-gates/skills/design-audit/SKILL.md`

- [ ] **Step 1: ディレクトリを作成**

Bash: `mkdir -p ~/.claude/skills/tdd-gates/skills/design-audit`

- [ ] **Step 2: SKILL.mdを作成**

Write: `~/.claude/skills/tdd-gates/skills/design-audit/SKILL.md`
```markdown
---
name: design-audit
description: |
  brainstorming の Spec Self-Review 後・User Review Gate 前に独立エージェントの敵対的検査を挿入し、要件ギャップを検出する（trust-but-verify チェーンの旧CP-A相当）。`tdd-evaluator` が担当し、独自PASS/CONDITIONAL/FAIL（最大2回の再評価）で完結する。決定ツリーを一問一答で詰め、各分岐に推奨回答を示したかも監査基準に含む。

  `trust-but-verify:trust-but-verify` チェーンの一部として自動組込で使うのが基本。設計文書単体の敵対的レビューが独立して欲しい場合のみ単体起動する。
---

# trust-but-verify:design-audit — 要件ギャップレビュー

`trust-but-verify:trust-but-verify` チェーンの design-audit ステップ（旧CP-A）。superpowers `brainstorming` の Spec Self-Review 後・User Review Gate 前に、`tdd-evaluator` による独立の敵対的検査を挿入する。

土台は `~/.claude/skills/trust-but-verify/templates/spec-gap-review-addendum.md`（`spec-document-reviewer-prompt.md`への差分追記）。

**監査基準**: 抜け漏れ検出時は `~/.claude/skills/trust-but-verify/references/scoring.md`「停止シグナル（GUARDRAIL_HALT）」形式で提示する。加えて、決定ツリーを依存順に一問一答で詰め、各分岐に推奨回答を示したか（grillingスキル相当の徹底度）も監査項目に含める。

**再開時の軽量チェック**: brainstormingを経由せず既存のspec文書から再開する場合（別セッションでdesign-audit承認済みの場合等）は、対象spec文書のcommit日時以降に参照範囲のコードへ変更が入っていないか`git log`で確認し、変更があれば一言ユーザーに確認する（design-audit再実行ではなく差分有無の軽量チェック）。

目的・Critical基準・証拠要件の正典は `~/.claude/skills/trust-but-verify/references/checkpoints.md`「CP-A」節。採点形式の正典は `~/.claude/skills/trust-but-verify/references/scoring.md`「スコアカード出力形式（design-audit/plan-audit用）」。
```

- [ ] **Step 3: 検証**

Run: `head -8 ~/.claude/skills/tdd-gates/skills/design-audit/SKILL.md`
Expected: frontmatterに`name: design-audit`が含まれる。

---

### Task 5: skills/plan-audit/SKILL.md の作成

**Files:**
- Create: `~/.claude/skills/tdd-gates/skills/plan-audit/SKILL.md`

- [ ] **Step 1: ディレクトリを作成**

Bash: `mkdir -p ~/.claude/skills/tdd-gates/skills/plan-audit`

- [ ] **Step 2: SKILL.mdを作成**

Write: `~/.claude/skills/tdd-gates/skills/plan-audit/SKILL.md`
```markdown
---
name: plan-audit
description: |
  writing-plans の Self-Review 後・Execution Handoff 前に独立エージェントの計画品質レビューを挿入する（trust-but-verify チェーンの旧CP-B相当）。`tdd-evaluator` が担当し、独自PASS/CONDITIONAL/FAIL（最大2回の再評価）で完結する。small/substantial判定の実施場所でもある。

  `trust-but-verify:trust-but-verify` チェーンの一部として自動組込で使うのが基本。
---

# trust-but-verify:plan-audit — 計画品質レビュー

`trust-but-verify:trust-but-verify` チェーンの plan-audit ステップ（旧CP-B）。superpowers `writing-plans` の Self-Review 後・Execution Handoff 前に、`tdd-evaluator` による独立の計画品質レビューを挿入する。

土台は `~/.claude/skills/trust-but-verify/templates/plan-quality-review-addendum.md`（`plan-document-reviewer-prompt.md`への差分追記。トレーサビリティ表・3層戦略・small/substantial判定・業務ロジック分離監査を追加）。

**small/substantial判定**: 判定主体は本ステップ。`git diff --stat` 見込みと既存テスト一覧でグローバル CLAUDE.md 作業ルーティング表 small 行の4条件を照合する。該当すれば `trust-but-verify:evidence-check` はRED→GREEN相当だけの簡略ルートを取ってよい。

目的・Critical基準・証拠要件の正典は `~/.claude/skills/trust-but-verify/references/checkpoints.md`「CP-B」節。採点形式の正典は `~/.claude/skills/trust-but-verify/references/scoring.md`「スコアカード出力形式（design-audit/plan-audit用）」。

> **実効性メモ（2026-09-13）**: design-audit（旧CP-A）ほどの実効性実証記録が無い。今後の運用実績を見て要否を再判断する対象として注記しておく。
```

- [ ] **Step 3: 検証**

Run: `grep -n "実効性メモ" ~/.claude/skills/tdd-gates/skills/plan-audit/SKILL.md`
Expected: 該当行がヒットする。

---

### Task 6: skills/evidence-check/SKILL.md の作成

**Files:**
- Create: `~/.claude/skills/tdd-gates/skills/evidence-check/SKILL.md`

- [ ] **Step 1: ディレクトリを作成**

Bash: `mkdir -p ~/.claude/skills/tdd-gates/skills/evidence-check`

- [ ] **Step 2: SKILL.mdを作成**

Write: `~/.claude/skills/tdd-gates/skills/evidence-check/SKILL.md`
```markdown
---
name: evidence-check
description: |
  superpowers subagent-driven-development の task-reviewer ディスパッチを差し替え、実装者の申告を信じず`tdd-evaluator`が自ら再実行して検証する（trust-but-verify チェーンの旧CP-C相当）。UI/UX・security/perfは条件付き追加。SDD純正の5ラウンドfix loopをそのまま使う。

  `trust-but-verify:trust-but-verify` チェーンのタスクレビュー段階に必ず自動組込で使う。単体で呼び出し可能なスキルとしても存在するが、`evidence-check`自体を単体運用の起点にはしない（専門レビュアー群だけを単発利用したい場合は`trust-but-verify:review-aggregate`を使う）。
---

# trust-but-verify:evidence-check — タスク証拠検証

`trust-but-verify:trust-but-verify` チェーンの evidence-check ステップ（旧CP-C）。superpowers `subagent-driven-development` の task-reviewer ディスパッチを差し替える（汎用reviewerでなく`tdd-evaluator`）。

**中核原則**: SDD の `task-reviewer-prompt.md` には既定で "Do not re-run the suite to confirm their report."（実装者の報告を信頼し再実行しない）とあるが、evidence-check が乗る場面ではこれを**明示的に上書きする**。RED/GREEN のテスト実行結果は実装者の報告のまま信用せず、必ず自ら再実行して確認する。上書きの適用手順は `~/.claude/skills/trust-but-verify/templates/task-evidence-addendum.md` が正典（Main がディスパッチプロンプトを組み立てる際に適用する差分であり、`tdd-evaluator`はその結果として渡されたプロンプトに従って再実行する）。

**証拠の記録先**: タスク単位のtodoはSDDが自前で作成するため重複して作らない。証拠行（RED／GREEN コミット SHA、RED/GREEN コマンドと出力）は SDD の `progress.md` に追記する形に統一する。

**証拠主義**: 「テストは通るはず」「多分失敗する」は無効。RED/GREEN は必ず実行ログを証拠として `progress.md` に残す（`~/.claude/skills/trust-but-verify/references/scoring.md` の証拠フォーマット）。特にRED は「実際に失敗したログ」が無ければ通さない（Critical即FAIL）。

**仕様変更時の巻き戻し**: ユーザー起因の仕様変更が入ったら、① `progress.md` に「仕様変更」エントリ（日時・変更内容・ユーザー指示の要旨）を記録し、② 影響するテストはRED からやり直す。③ `tdd-evaluator` はこのエントリと照合し、正当なテスト変更と assert 骨抜きを区別する。④ 変更が実装詳細でなく要件レベルの場合は、Mainが変更後の要件を一行で再言語化しユーザーに確認を取る。

**small判定時の簡略ルート**: `trust-but-verify:plan-audit` でsmall判定された場合、RED→GREEN 中心の簡略パイプに降格してよいが、Critical（実失敗ログ）はいかなる場合も省略しない。

リトライ機構はSDD純正の5ラウンドfix loopをそのまま使用する（独自カウンタは持たない）。目的・Critical基準・証拠要件の正典は `~/.claude/skills/trust-but-verify/references/checkpoints.md`「CP-C」節。採点形式の正典は `~/.claude/skills/trust-but-verify/references/scoring.md`「スコアカード出力形式（evidence-check以降用）」。
```

- [ ] **Step 3: 検証**

Run: `grep -n "Do not re-run" ~/.claude/skills/tdd-gates/skills/evidence-check/SKILL.md`
Expected: 該当行がヒットする。

---

### Task 7: skills/review-aggregate/SKILL.md の作成

**Files:**
- Create: `~/.claude/skills/tdd-gates/skills/review-aggregate/SKILL.md`

- [ ] **Step 1: ディレクトリを作成**

Bash: `mkdir -p ~/.claude/skills/tdd-gates/skills/review-aggregate`

- [ ] **Step 2: SKILL.mdを作成**

Write: `~/.claude/skills/tdd-gates/skills/review-aggregate/SKILL.md`
```markdown
---
name: review-aggregate
description: |
  superpowers subagent-driven-development の Final Review（`code-reviewer.md`）を差し替え、Mainのフルスイート実行1回→`review-*`条件付き2〜5本並列→`tdd-evaluator`集約という最終スコアカード化を行う（trust-but-verify チェーンの旧CP-D相当）。徴候があればミューテーション検証を加える。

  `trust-but-verify:trust-but-verify` チェーンの一部として自動組込で使うのが基本。専門レビュアー群（`review-*`）だけを単発利用したい場合はこのスキルを起点にする（「レビュー単独」経路）。
---

# trust-but-verify:review-aggregate — 最終スコアカード

`trust-but-verify:trust-but-verify` チェーンの review-aggregate ステップ（旧CP-D）。superpowers `subagent-driven-development` の Final Review にある `code-reviewer.md` 単独ディスパッチを、Main のフルスイート実行1回（手順0）→`review-*`条件付き2〜5本並列→`tdd-evaluator`集約に丸ごと差し替える。土台は `~/.claude/skills/trust-but-verify/templates/final-scorecard-review-prompt.md`。

**モデル選定**: どの `review-*` をどのモデル階層（haiku/sonnet等）で起動するかは、このスキル独自のルールを持たず、superpowers `subagent-driven-development` 本体の Model Selection 節を参照する。

**手順0**: タスクループ開始前に Main が記録したプロファイル全体実行コマンドのベースライン結果（`progress.md`）と比較する。`evidence-check`の各タスクではフルスイートを再実行しないため、この手順0が唯一のフルスイート再実行点になる。

**集約スコアカード**: Main が `progress.md` に書き出す。Critical: 偽装テスト検出・ミューテーション検証条件（徴候があれば必須）。

**受け入れチェックリストへの組込**: チェーン完了後の受け入れ確認時、`tdd-evaluator` が受け入れチェックリスト（受入基準＋本ステップの実施次元（2〜5本）＋CI整備/文書同期の整備状況＋例外処理・権限漏れ・変更影響範囲）と、本ステップで修正済みの「スコープ外の既存問題」一覧を生成する。

リトライ機構はSDD純正のFinal Review（1修正波+1 scoped re-review）。目的・Critical基準・証拠要件の正典は `~/.claude/skills/trust-but-verify/references/checkpoints.md`「CP-D」節。採点形式の正典は `~/.claude/skills/trust-but-verify/references/scoring.md`「スコアカード出力形式（evidence-check以降用）」。

> **スコープメモ（2026-09-13）**: `review-maintainability`の判定基準をponytailのラダー式に差し替える案は本タスクの対象外。前提事実（「プロファイル階層」は`checkpoints.md`に実在しない）を洗い直した上で別タスクとして扱う。
```

- [ ] **Step 3: 検証**

Run: `grep -n "スコープメモ" ~/.claude/skills/tdd-gates/skills/review-aggregate/SKILL.md`
Expected: 該当行がヒットする。

---

### Task 8: 旧SKILL.mdの削除とディレクトリの改名

**Files:**
- Delete: `~/.claude/skills/tdd-gates/SKILL.md`（内容はTask 3〜7で分割済み）
- Rename: `~/.claude/skills/tdd-gates/` → `~/.claude/skills/trust-but-verify/`

- [ ] **Step 1: 旧SKILL.mdを削除**

Bash: `rm ~/.claude/skills/tdd-gates/SKILL.md`

- [ ] **Step 2: ディレクトリ全体を改名**

Bash: `mv ~/.claude/skills/tdd-gates ~/.claude/skills/trust-but-verify`

- [ ] **Step 3: 検証**

Run: `find ~/.claude/skills/trust-but-verify -maxdepth 2 | sort`
Expected: `.claude-plugin/plugin.json`・`references/`・`templates/`・`skills/design-audit`・`skills/evidence-check`・`skills/plan-audit`・`skills/review-aggregate`・`skills/trust-but-verify` が全て存在し、`~/.claude/skills/tdd-gates`は存在しない（`ls ~/.claude/skills/tdd-gates`が`No such file or directory`を返す）。

---

### Task 9: 外部参照ファイル9件のパス・名称更新

**Files:**
- Modify: `~/.claude/agents/tdd-evaluator.md`
- Modify: `~/.claude/rules/skills.md`
- Modify: `~/.claude/agents/trivial-executor.md`
- Modify: `~/.claude/agents/tdd-implementer.md`
- Modify: `~/.claude/agents/doc-updater.md`
- Modify: `~/.claude/agents/references/doc/design.md`
- Modify: `~/.claude/agents/references/python/rest-api.md`
- Modify: `~/.claude/agents/references/python/testing.md`
- Modify: `~/.claude/CLAUDE.md`

これらのファイルの`tdd-gates`という文字列は、いずれも本タスクの対象外（変更しない）と定めた superpowers本体・`review-*`エージェントの**振る舞い**ではなく、Task 8で移動した先へのパス参照、または旧プラグイン名の呼称にすぎない。放置すると存在しないパスを指し続けるため、機械的な文字列置換として更新する。

- [ ] **Step 1: tdd-evaluator.md を更新（`.tdd-gates/ledger-*.md`という旧台帳名は変更しない）**

Edit: `~/.claude/agents/tdd-evaluator.md`

old_string:
```
description: tdd-gates（superpowers 拡張の品質規律レイヤー）の Evaluator ロール（採点役）。
```
new_string:
```
description: trust-but-verify（superpowers 拡張の品質規律レイヤー）の Evaluator ロール（採点役）。
```

old_string:
```
あなたは tdd-gates（superpowers 拡張の品質規律レイヤー）の **Evaluator（採点役）** です。
```
new_string:
```
あなたは trust-but-verify（superpowers 拡張の品質規律レイヤー）の **Evaluator（採点役）** です。
```

old_string:
```
採点は必ず `~/.claude/skills/tdd-gates/references/scoring.md` に従う。各CPの目的・Critical・証拠要件は `~/.claude/skills/tdd-gates/references/checkpoints.md` を単一ソースとする。
```
new_string:
```
採点は必ず `~/.claude/skills/trust-but-verify/references/scoring.md` に従う。各CPの目的・Critical・証拠要件は `~/.claude/skills/trust-but-verify/references/checkpoints.md` を単一ソースとする。
```

old_string:
```
**CP-C での明示的な上書き（tdd-gates 最大の付加価値）**: SDD の `task-reviewer-prompt.md` には既定で "Do not re-run the suite to confirm their report."（実装者の報告を信頼し再実行しない）とあるが、tdd-gates が乗る場面ではこれを**明示的に上書きする**。RED/GREEN のテスト実行結果は実装者の報告のまま信用せず、必ず自ら再実行して確認する。上書きの適用手順は `~/.claude/skills/tdd-gates/templates/task-evidence-addendum.md` が正典（Main がディスパッチプロンプトを組み立てる際に適用する差分であり、あなたはその結果として渡されたプロンプトに従って再実行する）。
```
new_string:
```
**CP-C での明示的な上書き（trust-but-verify 最大の付加価値）**: SDD の `task-reviewer-prompt.md` には既定で "Do not re-run the suite to confirm their report."（実装者の報告を信頼し再実行しない）とあるが、trust-but-verify が乗る場面ではこれを**明示的に上書きする**。RED/GREEN のテスト実行結果は実装者の報告のまま信用せず、必ず自ら再実行して確認する。上書きの適用手順は `~/.claude/skills/trust-but-verify/templates/task-evidence-addendum.md` が正典（Main がディスパッチプロンプトを組み立てる際に適用する差分であり、あなたはその結果として渡されたプロンプトに従って再実行する）。
```

old_string:
```
CP-A〜Eのどの段階で呼ばれているかにより、受け取るものと振る舞いが異なる。各CPの目的・上乗せ先・Critical・証拠要件は `~/.claude/skills/tdd-gates/references/checkpoints.md` を単一ソースとする。
```
new_string:
```
CP-A〜Eのどの段階で呼ばれているかにより、受け取るものと振る舞いが異なる。各CPの目的・上乗せ先・Critical・証拠要件は `~/.claude/skills/trust-but-verify/references/checkpoints.md` を単一ソースとする。
```

old_string:
```
- **証拠の記録先**: CP-A・CP-B は専用台帳を持たない——直近のスコアカード応答自体が記録（再評価カウンタも同様）。CP-C以降は SDD の `progress.md`（ワークスペース配下のプラン専用台帳）が記録の正典であり、tdd-gates 独自の `.tdd-gates/ledger-*.md` は使わない。CP-C以降で過去の履歴（fix round・仕様変更エントリ）を確認する必要があれば、Main から渡された `progress.md` のパスを Read する。
```
new_string:
```
- **証拠の記録先**: CP-A・CP-B は専用台帳を持たない——直近のスコアカード応答自体が記録（再評価カウンタも同様）。CP-C以降は SDD の `progress.md`（ワークスペース配下のプラン専用台帳）が記録の正典であり、trust-but-verify 独自の `.tdd-gates/ledger-*.md` は使わない。CP-C以降で過去の履歴（fix round・仕様変更エントリ）を確認する必要があれば、Main から渡された `progress.md` のパスを Read する。
```

old_string:
```
2. 対象CPの Critical 項目を `~/.claude/skills/tdd-gates/references/checkpoints.md` で確認。
```
new_string:
```
2. 対象CPの Critical 項目を `~/.claude/skills/trust-but-verify/references/checkpoints.md` で確認。
```

old_string:
```
**CP-A/B用**: `~/.claude/skills/tdd-gates/references/scoring.md`「スコアカード出力形式（CP-A/B用）」（**Quality Gate Report** 形式）に**厳密に従う**（採点プロセス step1 で Read 済み。フォーマットをここで再掲しない＝単一ソース化）。ヘッダ（`Quality Gate Report: CP-<A/B> - <CP名>`）・評価項目表（証拠つき）・スコア率・判定（PASS/CONDITIONAL/FAIL）・Critical違反・指摘事項・**次のアクション**の順で返す。
```
new_string:
```
**CP-A/B用**: `~/.claude/skills/trust-but-verify/references/scoring.md`「スコアカード出力形式（CP-A/B用）」（**Quality Gate Report** 形式）に**厳密に従う**（採点プロセス step1 で Read 済み。フォーマットをここで再掲しない＝単一ソース化）。ヘッダ（`Quality Gate Report: CP-<A/B> - <CP名>`）・評価項目表（証拠つき）・スコア率・判定（PASS/CONDITIONAL/FAIL）・Critical違反・指摘事項・**次のアクション**の順で返す。
```

- [ ] **Step 2: rules/skills.md を更新**

Edit: `~/.claude/rules/skills.md`

old_string:
```
ローカルスキル: tdd-gates（詳細は SKILL.md）。プラグイン群は有効化済み。
```
new_string:
```
ローカルスキル: trust-but-verify（詳細は SKILL.md）。プラグイン群は有効化済み。
```

- [ ] **Step 3: trivial-executor.md を更新**

Edit: `~/.claude/agents/trivial-executor.md`

old_string:
```
これらは比例ルール上 `tdd-gates`（substantial）へ回すべきもの。
```
new_string:
```
これらは比例ルール上 `trust-but-verify`（substantial）へ回すべきもの。
```

- [ ] **Step 4: tdd-implementer.md を更新**

Edit: `~/.claude/agents/tdd-implementer.md`

old_string:
```
description: superpowers:subagent-driven-development（または executing-plans）から起動される implementer サブエージェント。TDD 規律（superpowers:test-driven-development の RED→GREEN→REFACTOR）を強制するペルソナとして、1タスク分のテストと実装を書く。tdd-gates の CP-C（タスク証拠検証）で `tdd-evaluator` が検証する対象。汎用 general-purpose subagent の代わりに implementer 役として使う。
```
new_string:
```
description: superpowers:subagent-driven-development（または executing-plans）から起動される implementer サブエージェント。TDD 規律（superpowers:test-driven-development の RED→GREEN→REFACTOR）を強制するペルソナとして、1タスク分のテストと実装を書く。trust-but-verify の evidence-check（タスク証拠検証、旧CP-C）で `tdd-evaluator` が検証する対象。汎用 general-purpose subagent の代わりに implementer 役として使う。
```

old_string:
```
**コミット粒度（tdd-gates 固有）**: 1タスクにつき RED コミット（テストファイルのみ。実装ファイルを含めない）→ GREEN コミット（実装）→ REFACTOR コミット（差分がある場合のみ）の順に分けて切る。RED コミットは `tdd-evaluator` が隔離 worktree で RED を再現する基点になるため、GREEN と混ぜない。
```
new_string:
```
**コミット粒度（trust-but-verify 固有）**: 1タスクにつき RED コミット（テストファイルのみ。実装ファイルを含めない）→ GREEN コミット（実装）→ REFACTOR コミット（差分がある場合のみ）の順に分けて切る。RED コミットは `tdd-evaluator` が隔離 worktree で RED を再現する基点になるため、GREEN と混ぜない。
```

old_string:
```
- ディスパッチ元が指定した言語プロファイル（`~/.claude/skills/tdd-gates/references/profiles/` 配下）を Read（パス→テスト種別・実行コマンド・合格ログ形式の対応表）。**指定が無ければ推測せず、ディスパッチ元に要求する**。テスト実行は常にそのプロファイル定義の実行コマンドを使う。
```
new_string:
```
- ディスパッチ元が指定した言語プロファイル（`~/.claude/skills/trust-but-verify/references/profiles/` 配下）を Read（パス→テスト種別・実行コマンド・合格ログ形式の対応表）。**指定が無ければ推測せず、ディスパッチ元に要求する**。テスト実行は常にそのプロファイル定義の実行コマンドを使う。
```

old_string:
```
**Review Findings 後のフォローアップ**: task review で指摘が返ってきたら、修正し、修正対象コードを被覆するテストを再実行し、同じレポートファイルに fix report を追記する（何を直したか・実行した被覆テスト・コマンド・出力）。レビュアーはテストを再実行しない前提の SDD 標準とは異なり、tdd-gates の `tdd-evaluator` は自ら再実行して検証するため、fix report の RED/GREEN 抜粋は省略しない。
```
new_string:
```
**Review Findings 後のフォローアップ**: task review で指摘が返ってきたら、修正し、修正対象コードを被覆するテストを再実行し、同じレポートファイルに fix report を追記する（何を直したか・実行した被覆テスト・コマンド・出力）。レビュアーはテストを再実行しない前提の SDD 標準とは異なり、trust-but-verify の `tdd-evaluator` は自ら再実行して検証するため、fix report の RED/GREEN 抜粋は省略しない。
```

- [ ] **Step 5: doc-updater.md を更新**

Edit: `~/.claude/agents/doc-updater.md`

old_string:
```
| CI ワークフロー定義の生成・更新（CP-E） | `~/.claude/skills/tdd-gates/references/profiles/`（CIステージ定義）・`~/.claude/skills/tdd-gates/templates/ci-gate-task-template.md` |
| ドキュメント同期（CP-F、プロファイル対象カテゴリ） | `~/.claude/skills/tdd-gates/references/profiles/docs-*.md`（対象カテゴリ・生成条件）→ 新規カテゴリの初回生成は `~/.claude/agents/references/doc/design.md`「文書カテゴリ別 目次テンプレート」節、既存更新は `doc/verify.md` 更新モードA/B |
```
new_string:
```
| CI ワークフロー定義の生成・更新（CP-E） | `~/.claude/skills/trust-but-verify/references/profiles/`（CIステージ定義）・`~/.claude/skills/trust-but-verify/templates/ci-gate-task-template.md` |
| ドキュメント同期（CP-F、プロファイル対象カテゴリ） | `~/.claude/skills/trust-but-verify/references/profiles/docs-*.md`（対象カテゴリ・生成条件）→ 新規カテゴリの初回生成は `~/.claude/agents/references/doc/design.md`「文書カテゴリ別 目次テンプレート」節、既存更新は `doc/verify.md` 更新モードA/B |
```

- [ ] **Step 6: references/doc/design.md を更新**

Edit: `~/.claude/agents/references/doc/design.md`

old_string:
```
> 以下は `~/.claude/skills/tdd-gates/references/profiles/docs-*.md` が条件付きで対象とする
```
new_string:
```
> 以下は `~/.claude/skills/trust-but-verify/references/profiles/docs-*.md` が条件付きで対象とする
```

- [ ] **Step 7: references/python/rest-api.md を更新**

Edit: `~/.claude/agents/references/python/rest-api.md`

old_string:
```
- `tdd-gates` スキル — API エンドポイントのテストを品質ゲートで検証する（ゲート数は `tdd-gates` スキル側を単一ソースとする。`~/.claude/agents/references/python/testing.md` に pytest 詳細パターン）
```
new_string:
```
- `trust-but-verify` スキル — API エンドポイントのテストを品質ゲートで検証する（ゲート数は `trust-but-verify` スキル側を単一ソースとする。`~/.claude/agents/references/python/testing.md` に pytest 詳細パターン）
```

- [ ] **Step 8: references/python/testing.md を更新**

Edit: `~/.claude/agents/references/python/testing.md`

old_string:
```
> 参照元: `tdd-gates` の `profiles/pytest.md`（CP用グルーが深い作法をここへ委譲）／`tdd-implementer` エージェント／`dev-python` の API・FastAPI パターン。
```
new_string:
```
> 参照元: `trust-but-verify` の `profiles/pytest.md`（CP用グルーが深い作法をここへ委譲）／`tdd-implementer` エージェント／`dev-python` の API・FastAPI パターン。
```

- [ ] **Step 9: CLAUDE.md を更新**

Edit: `~/.claude/CLAUDE.md`

old_string:
```
| small | 次を**すべて**満たす: 差分 ≤2ファイル。実装差分 ≤50行（テスト除く）。公開 IF 不変。既存テストが対象を被覆。<br>1つでも外れたら substantial | 着手前は substantial と仮置きして `tdd-gates` に入れ。<br>small 該当判定は CP-B で `tdd-evaluator` が行う。<br>該当なら CP-C（RED→GREEN 中心）の簡略パイプに降格して進めよ |
| substantial | 新規ロジック・複数ファイル横断・公開 IF 変更・非自明なバグ修正 | Plan モード → `tdd-gates` フル工程で進めよ。<br>採点は実装者と別コンテキストで行え |
```
new_string:
```
| small | 次を**すべて**満たす: 差分 ≤2ファイル。実装差分 ≤50行（テスト除く）。公開 IF 不変。既存テストが対象を被覆。<br>1つでも外れたら substantial | 着手前は substantial と仮置きして `trust-but-verify:trust-but-verify` に入れ。<br>small 該当判定は plan-audit で `tdd-evaluator` が行う。<br>該当なら evidence-check（RED→GREEN 中心）の簡略パイプに降格して進めよ |
| substantial | 新規ロジック・複数ファイル横断・公開 IF 変更・非自明なバグ修正 | Plan モード → `trust-but-verify:trust-but-verify` フル工程で進めよ。<br>採点は実装者と別コンテキストで行え |
```

Edit: `~/.claude/CLAUDE.md`

old_string:
```
  - reviewer構成・本数の正典は`~/.claude/skills/tdd-gates/references/checkpoints.md`。
```
new_string:
```
  - reviewer構成・本数の正典は`~/.claude/skills/trust-but-verify/references/checkpoints.md`。
```

- [ ] **Step 10: 検証**

Run: `grep -rln "tdd-gates" ~/.claude/agents/ ~/.claude/rules/ ~/.claude/CLAUDE.md 2>/dev/null | grep -v '.tdd-gates/ledger'`
Expected: `~/.claude/agents/tdd-evaluator.md`（`.tdd-gates/ledger-*.md`という意図的に残す旧台帳名のみ）以外はヒットしない。念のため`grep -n "tdd-gates" ~/.claude/agents/tdd-evaluator.md`を実行し、唯一の残存が`.tdd-gates/ledger-*.md`の行であることを目視確認する。

---

### Task 10: my-claude-pullでミラー同期

**Files:**
- Sync: `~/.claude/skills/trust-but-verify/` → `linux/claude/skills/trust-but-verify/`（このリポジトリ内）
- Sync: `~/.claude/agents/`・`~/.claude/rules/`・`~/.claude/CLAUDE.md` の変更分 → `linux/claude/`配下

- [ ] **Step 1: my-claude-pullスキルを実行**

`my-claude-pull`スキルを起動する（`~/.claude/`をリポジトリのミラーへ同期。commit・pushは行わない）。

- [ ] **Step 2: 検証**

Run: `cd /home/asama/my-claude && git status`
Expected: `linux/claude/skills/tdd-gates/`が削除され`linux/claude/skills/trust-but-verify/`が追加、および`linux/claude/agents/*`・`linux/claude/rules/skills.md`・`linux/claude/CLAUDE.md`に変更が反映されている。

Run: `cd /home/asama/my-claude && git diff --stat`
Expected: Task 9で編集した9ファイル＋新規`trust-but-verify/`ディレクトリの変更が表示される（CRLF/LF起因の無関係な`M`が紛れていないか目視確認、[[reference-sync-file-behavior]]参照）。

---

### Task 11: 最終検証

- [ ] **Step 1: プラグイン構造の妥当性確認**

Run:
```bash
find /home/asama/my-claude/linux/claude/skills/trust-but-verify -maxdepth 2 | sort
cat /home/asama/my-claude/linux/claude/skills/trust-but-verify/.claude-plugin/plugin.json | python3 -m json.tool
```
Expected: Task 8のディレクトリ構造と一致し、JSONが妥当。

- [ ] **Step 2: 残存参照の最終grep**

Run: `grep -rn "tdd-gates" /home/asama/my-claude/linux/claude/ 2>/dev/null | grep -v '.tdd-gates/ledger'`
Expected: ヒット無し（`.tdd-gates/ledger-*.md`の意図的な残存を除く）。

- [ ] **Step 3: スキル一覧への登場確認（次回セッションで確認）**

次回このリポジトリで新規セッションを開始した際、システムが提示するスキル一覧に`trust-but-verify:trust-but-verify`・`trust-but-verify:design-audit`・`trust-but-verify:plan-audit`・`trust-but-verify:evidence-check`・`trust-but-verify:review-aggregate`が現れ、`tdd-gates`が消えていることを確認する（現行セッション内ではスキル一覧が再走査されないため、この場では確認できない旨をユーザーに明記する）。

- [ ] **Step 4: ユーザーへの受け入れ確認**

Task 1〜10の完了をユーザーに報告し、受け入れ確認を取る。OKなら、`docs/specs/2026-09-13-trust-but-verify-design.md`と本計画ファイルをgit commitするかどうかをユーザーに確認する（本計画のGlobal Constraintsどおりcommitは自動で行わない）。
