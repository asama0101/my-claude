---
name: tdd-gates
description: |
  superpowers のスキルチェーン（brainstorming → writing-plans → subagent-driven-development → finishing-a-development-branch）に上乗せする品質規律レイヤー。AI駆動開発の品質問題（動くように見えて中身がバグだらけ・テストの形骸化・RED未確認・自己承認）を、superpowers の各ステップに差し込むチェックポイント（CP-A〜F）と、Critical即FAIL＋証拠要求の採点語彙で構造的に潰す。substantial な実装（新機能・バグ修正・非自明な変更）で使う。

  以下のような発言・状況で起動すること:「TDDで実装して」「テストファーストで」「品質ゲートを回して」「チェックポイントを回して」「新機能を実装して（テスト付きで）」「バグを直して（回帰テスト付きで）」。substantial なコード変更の着手時に積極的に起動する。trivial（数行・設定/ドキュメント）は使わず単一軽量 Agent に委任する（比例ルール）。
---

# TDD 品質規律レイヤー（superpowers 拡張）

あなた（Main）は、superpowers のスキルチェーンを背骨として使う。tdd-gates は自前の駆動ループを持たない。チェーンの各ステップに寄生してチェックポイント（CP-A〜F）を差し込み、「証拠不信の原則」「専門レビュアーによる多次元評価」「0–3点採点語彙・Critical即FAIL」を、そのステップの担当エージェントに上乗せするだけの薄いレイヤーである。

**中核原則**: superpowers の Iron Law「NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST」を規律の根拠とする（`superpowers:test-driven-development` が実行手順の正典）。tdd-gates はこれを**検証**する層——特に CP-C では、SDD の `task-reviewer-prompt.md` にある "Do not re-run the suite to confirm their report." を明示的に上書きし、evaluator が実装者の報告を鵜呑みにせず自ら再実行する（詳細は `references/checkpoints.md` CP-C節）。

## 起動時にやること（チェックリスト）

各項目をtodo化して順に実施する。

1. **プロファイル確定**: 対象言語のプロファイルを1つ選ぶ（Python は `references/profiles/pytest.md`）。パス→テスト種別の対応表を読み、対象ファイルのテスト種別（unit/integration/e2e）を判定して**ユーザーに確認**する。**CP-E（CI）を回すなら、プロファイルの「CI ステージ」定義（lint/typecheck/build/unit/integration/主要E2E の具体コマンド）も確認する**。
   - **対象言語のプロファイルが無い場合**（現状は pytest／browser-manual-e2e の2本）は、`references/profiles/_template.md` から新規プロファイルを起草する。テスト実行コマンドと合格ログ形式を**ユーザーに承認してもらってから**開始する（未定義のまま pytest 前提で進めない。停止時は `references/scoring.md`「停止シグナル」の `profile_undefined` 形式で提示する）。
   - **確定したプロファイルのパスは、各チェックポイントのレビュアーを起動するたびにプロンプトへ必ず明記して渡す**（エージェント側での推測は禁止）。
   - **CP-F（ドキュメント同期）を回すなら、ドキュメントプロファイルも確定する**: プロジェクトの `CLAUDE.md` に宣言があればそれに従う（例「ドキュメントプロファイル: docs-network-tool」）。宣言が無ければ既定の `references/profiles/docs-generic.md` を使ってよいかユーザーに一言確認する（言語プロファイルと異なり`docs-generic`は安全な既定値のため `profile_undefined` 停止は発火しない）。プロファイルが無いドメインは `references/profiles/_template-docs.md` から起草しユーザー承認を得る。
2. **証拠の記録先（成果物は必ずファイル化する）**: CP-A・CP-B は独自の PASS/CONDITIONAL/FAIL（最大2回の再評価）で完結し、専用の台帳は持たない。ただし `tdd-evaluator` は Bash 書き込みを持たないため、**Main が Quality Gate Report を対象 spec/plan 文書の末尾に追記してから git commit する**（brainstorming/writing-plans が既に commit する文書に相乗りし、新規の台帳ファイルは作らない）。チャット報告のみで終わらせない。**CP-C 以降は SDD（`subagent-driven-development`）の `progress.md` に証拠行（RED/GREEN コマンドと出力）を追記する形に統一**し、**CP-D の集約スコアカードも Main が `progress.md` に書き出す**。tdd-gates 独自の台帳（旧 `.tdd-gates/ledger-*.md`）は作らない。
3. **superpowers チェーンを起動**: `superpowers:using-superpowers` の案内どおり `brainstorming` から入り、下記 CP対応表に従って各ステップのレビュアーを差し替える。CP-C 以降のタスク単位の todo は SDD が自前で作成するため、tdd-gates 側で重複して作らない。**brainstormingを経由せず既存のspec/plan文書から再開する場合**（別セッションでCP-A承認済みの場合等）は、対象spec文書のcommit日時以降に参照範囲のコードへ変更が入っていないか`git log`で確認し、変更があれば一言ユーザーに確認する（CP-A再実行ではなく差分有無の軽量チェック）。

## CP対応表（superpowers チェーンへの寄生地図）

| CP | 内容（旧ゲート） | 上乗せ先 | 担当 | リトライ機構 |
|---|---|---|---|---|
| CP-A 要件ギャップレビュー（旧1） | brainstorming の Spec Self-Review 後・User Review Gate 前に独立エージェントの敵対的検査を挿入。土台は `spec-document-reviewer-prompt.md` への差分追記 | `tdd-evaluator` | tdd-gates独自 PASS/CONDITIONAL/FAIL・最大2回 |
| CP-B 計画品質レビュー（旧2+3） | writing-plans の Self-Review 後・Execution Handoff 前。土台は `plan-document-reviewer-prompt.md` への差分追記（トレーサビリティ表・3層戦略・small/substantial判定・業務ロジック分離監査を追加） | `tdd-evaluator` | 同上・最大2回 |
| CP-C タスク証拠検証（旧4-7） | SDD の task-reviewer ディスパッチを差し替え（汎用reviewerでなく`tdd-evaluator`）。UI/UX・security/perfは条件付き追加 | `tdd-evaluator` | SDD純正の5ラウンドfix loopをそのまま使用（独自カウンタは持たない） |
| CP-D 最終スコアカード（旧8） | SDD Final Review の `code-reviewer.md` を差し替え | `review-*`条件付き2〜5本並列→`tdd-evaluator`集約（ミューテーション検証必須） | SDD純正のFinal Review（1修正波+1 scoped re-review） |
| CP-E CI品質ゲート整備（旧9・条件付き） | writing-plans が条件を満たせば末尾タスクとして自動追加 | 実装=`doc-updater`、レビュー=`tdd-evaluator` | SDD純正の5ラウンドloop |
| CP-F ドキュメント同期（旧10・条件付き） | 同上、CI整備タスクの後。選択したドキュメントプロファイルのカテゴリ表を参照し、トリガー条件該当カテゴリのみ対象 | 実装=`doc-updater`、レビュー=`doc-verifier` | SDD純正の5ラウンドloop |

各CPの目的・Critical基準・証拠要件の正典は `references/checkpoints.md`。採点形式（CP-A/B用と CP-C〜F用の2モード）の正典は `references/scoring.md`。

## 比例ルール（trivial / small / substantial）

- **trivial**（数行・既存パターン踏襲・テスト不要）: tdd-gates を使わず単一の軽量 Agent（`trivial-executor`）に一括委任する。
- **small**（数値基準の正典はグローバル CLAUDE.md 作業ルーティング表 small 行）: **判定主体は CP-B**（writing-plans の計画品質レビュー時に `tdd-evaluator` が `git diff --stat` 見込みと既存テスト一覧で4条件を照合する）。該当すれば CP-C のうち RED→GREEN 相当だけの簡略ルートを取ってよいが、CP-C の Critical（実失敗ログ）はいかなる場合も省略しない。
- **substantial**（新規ロジック・複数ファイル横断・公開IF変更・非自明なバグ修正）: CP-A〜D をフルで通す。CP-B（計画品質レビュー）・CP-D（最終スコアカード）は省略不可（唯一の実レビュー層のため）。

**trivial/small判定に迷う場合**: グローバル CLAUDE.md「変更規模で工程の深さを変えよ。迷えば substantial 扱いにせよ」の原則をそのまま適用する。trivial誤判定はbrainstorming自体のスキップ＝CP-Aの要件ギャップレビューが丸ごと素通りされることを意味するため、この原則の遵守は特に重要である。

数値基準の正典はグローバル CLAUDE.md 作業ルーティング表 small 行。

## 重要ルール

- **証拠主義**: 「テストは通るはず」「多分失敗する」は無効。RED/GREEN は必ず実行ログを証拠として `progress.md`（CP-C以降）またはスコアカード（CP-A/B）に残す（`references/scoring.md` の証拠フォーマット）。
- **Critical即FAIL**: スコアが高くても Critical 未達なら即 FAIL。特に CP-C の RED は「実際に失敗したログ」が無ければ通さない。
- **Main のコンテキスト衛生**: Main は生ログ全文を抱えない。各サブエージェントには結論・スコア・証拠スニペット・`file:line` だけを蒸留して返させる。
- **並列実装・worktree分離**: SDD の Setup（`superpowers:using-git-worktrees`）にそのまま従う。tdd-gates 独自の追加要求はない。
- **仕様変更時の巻き戻し**: ユーザー起因の仕様変更が入ったら、① CP-C以降なら `progress.md` に「仕様変更」エントリ（日時・変更内容・ユーザー指示の要旨）を記録し、② 影響するテストは CP-C の RED からやり直す。③ `tdd-evaluator` はこのエントリと照合し、正当なテスト変更と assert 骨抜きを区別する。④ 変更が実装詳細でなく**要件レベル**（受け入れ基準そのものが変わる）の場合は、Mainが変更後の要件を一行で再言語化しユーザーに確認を取る（独立エージェントによる再検証ではなくMain自身の軽量確認に留める）。
- **CP-A〜Fを1サイクルとして自動で通し、受け入れ確認は最後に一度だけ**: CP-A→B→C→D→E→F まで、CONDITIONAL再評価や SDD の fix loop を正規工程として自動で回し、人間の都度承認を挟まない（正常系の停止点はここにしかない）。CP-F 完了後に一度だけユーザーの受け入れ確認を取る（グローバル CLAUDE.md「実装後の受け入れ→ドキュメント更新」準拠）。この受け入れ確認の際、`tdd-evaluator` が受け入れチェックリスト（受入基準＋CP-Dの実施次元（2〜5本）＋CP-E/Fの整備状況＋例外処理・権限漏れ・変更影響範囲）と、CP-Dで修正済みの「スコープ外の既存問題」一覧（`references/checkpoints.md`「CP-D」参照）を生成する。NG なら該当CPへ差し戻す。
  - **止まるのはガードレール発動時のみ**: 非自明な要件の抜け漏れ（CP-A/B）・再評価/fix loop 上限到達による FAIL 確定・仕様の曖昧化。構造化フォーマットは `references/scoring.md`「停止シグナル（GUARDRAIL_HALT）」参照。これは「都度の承認待ち」とは別物であり正常系フローを止めない。複数マイルストーン計画では、マイルストーン単位で CP-F まで自動通しし、各マイルストーンの CP-F 後 1 回の受け入れ確認に一本化する（マイルストーン間の中間確認はしない）。

## 参照ファイル

- `references/checkpoints.md` — CP-A〜F の目的・上乗せ先・担当・Critical・証拠要件。
- `references/scoring.md` — 0–3採点・80%/60–79%・Critical即FAIL・CONDITIONAL上限・CP-A/B用とCP-C〜F用の2モードのスコアカード形式。
- `templates/*.md` — 各CPが差分追記／差し替えるプロンプトテンプレート（`spec-gap-review-addendum.md`・`plan-quality-review-addendum.md`・`task-evidence-addendum.md`・`final-scorecard-review-prompt.md`・`ci-gate-task-template.md`・`doc-sync-task-template.md`）。
- `references/profiles/pytest.md` — Python/pytest のパス判定・実行コマンド・合格ログ形式（深い作法は agents/references/python/testing.md へ委譲）。
- `references/profiles/browser-manual-e2e.md` — ビルド/自動テストランナーを持たない単一HTMLファイルアプリ向け。全レイヤーをe2eとして扱い、claude-in-chromeで手動E2Eの証拠を取る。
- `references/profiles/_template.md` — 新言語追加用スケルトン。
- `references/profiles/docs-generic.md` — CP-Fが対象とするドキュメントカテゴリの既定セットと生成条件（README/ガイド/API仕様[+データスキーマ・IF定義書]は常時、セキュリティ設計書・リリースノートは条件付き）。
- `references/profiles/docs-network-tool.md` — SSH/Telnet通信・ネットワーク機器連携等のドメイン向け追加カテゴリ（検証環境トポロジー・差分マップ／監視・アラート定義書／ランブック、すべて条件付き）。`docs-generic.md`を継承。
- `references/profiles/_template-docs.md` — 新規ドキュメントプロファイル追加用スケルトン。
