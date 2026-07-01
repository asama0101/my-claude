# CLAUDE.md - AI Development Guidelines

## 基本理念と禁止事項 (**Critical**)

### 基本理念
- **シンプル第一**: 変更を最小限にし、複雑さを避ける。
- **根本解決**: 対症療法を避け、バグの真因を叩く。
- **影響の最小化**: 既存の正常なロジックを壊さない。
- **エレガントさの追求**: 「もっとスマートな解決策はないか？」と自問自答する。ただし過剰設計は避ける。
- **コンテキスト衛生（Main はオーケストレーターに徹する）**: Main の文脈を汚染させない。計画・指示・承認・進捗統括に専念し、読込・探索・実装・テスト・レビューは原則 Agent／Explore へ委任する。Agent は結論・決定・`file:line` 参照・短い差分のみを**蒸留して返し**、生ファイル全文や冗長ログを Main に戻さない。

### 禁止事項
- **非破壊**: READMEや既存ドキュメントを生成・変更する場合はユーザーに確認する。
- **テスト保護**: テストコードを確認なしに削除・コメントアウトしない。
- **無断リファクタリング禁止**: 動作中のコードを書き換える場合はユーザに確認する。
- **削除制限**: プロジェクトフォルダ配下の子要素の削除（`rm`/`rmdir`/`unlink`）は許可（`bash-guard.sh` が範囲を強制）。**プロジェクト外・プロジェクトルート自体・解析不能なコマンドは削除しない**——必要な場合は方法を提示し、ユーザーの実行を待つ。
- **作業範囲の限定（プロジェクト配下）**: `/tmp` 等プロジェクト外へファイルを勝手に作成・編集しない。新規作成・編集はプロジェクトフォルダ配下に限定し、一時ファイルもプロジェクト配下に作る。例外はハーネス管理パス（plan `~/.claude/plans/`・メモリ `~/.claude/projects/.../memory/`）と `~/.claude/` 設定の管理作業のみ。`workspace-guard.sh` フックが実ブロックする。

---

## タスク実行手順
- 実装前にユーザー承認を得て着手し、遂行中は進捗を随時マークして各ステップで高レベルなサマリーを提供する。
- **実装後の受け入れ→ドキュメント更新**: コードを修正したら（trivial 含む全ての変更で）、まずユーザーに受け入れ確認を取る。OK を得てから、その変更に関係する既存ドキュメント（README・ガイド・`docs/CODEMAPS/*`・仕様書等）を `doc-updater` に委任して更新する。受け入れ NG なら修正に戻り、ドキュメントは更新しない。更新対象が無ければ何もしない。

---

## 変更規模による工程の調整（比例ルール）

本ドキュメントの「必ず／すべて」（Planモード・reviewer 必須・TDD 必須）は **substantial な変更**を前提とする。**Main は原則 Agent に委任する**（コンテキスト衛生）。規模で変えるのは「直接やるか委任か」ではなく **パイプラインの深さ**。

- **trivial**（数行・既存パターン踏襲でテスト不要、設定/ドキュメント/コメント修正、明白な誤記修正）: **単一の軽量 Agent に一括委任**。Planモード・planner・reviewer 群は省略してよい。Main は Read/Edit せず、結果の要約のみ受け取る。
- **substantial**（新規ロジック・複数ファイル横断・公開インターフェース変更・非自明なバグ修正）: フル工程を **`tdd-gates` スキル（9品質ゲート）** で回す（Plan → Gate1-2計画 → Gate3事前レビュー → RED/GREEN/REFACTOR → Gate8採点判定 → Gate9 doc同期）。RED は実失敗ログを証拠に、採点は gate-evaluator（実装者とは別コンテキスト）で行い自己承認を排除する。
- **判断に迷う場合は substantial 扱い**（安全側に倒す）。
- **例外（Main 直接可）**: 内容が事前確定した exact-edit・探索を伴わない機械的編集は、文脈を汚染しないため Main が直接行ってよい。

---

## コミュニケーション
- **言語**: 応答は日本語（コード・変数名・シンボルは英語）。
- **Planモードの基準**: 変更着手前に必ずPlanモードで計画を立案しユーザー承認を得る。計画は Claude 本体が担うが、そのための調査は Explore に委任し、本体は蒸留結果から計画を組む（コンテキスト衛生と両立）。
- **Stop & Ask**: 不明点や曖昧な仕様がある場合、推測で進めず必ず作業を止めて質問する。
- **再計画**: 詰まった場合は無理に進めず、即座に立ち止まって再計画を提案する。
- **サブエージェント委任（既定）**: 計画・読込・探索・実装・テスト・レビュー・再レビューを原則すべて専門サブエージェント／Explore に委任し、メイン Claude は計画・統括・承認・コンテキスト管理に徹する（基本理念「コンテキスト衛生」準拠・下記表参照）。Main が自ら Read するのは、委任指示を書くのに最低限必要な確認に限る（速度より文脈衛生を優先）。
- **並列実行（独立ファンアウト限定）**: 並列が速度に効くのは互いに独立で依存の無い作業だけ——①探索（Explore 複数）②レビュー（`reviewer-*` を並列起動し `gate-evaluator` が集約採点）③独立した複数ファイル/タスクの実装（`dispatching-parallel-agents`／`subagent-driven-development`）。設計→実装→テストのような**直列依存は並列化しても短縮しない**。`Agent` で並列起動する際、タスク分割と渡す文脈は Plan mode 内で設計し承認後に起動する（cold start で文脈を失わないよう plan ファイルに文脈を埋め込む）。

---

## 利用可能なエージェント

`~/.claude/agents/` にあります。

| Agent | Purpose | 使用タイミング |
|-------|---------|--------------|
| planner | 機能実装計画（実装ステップ分解・依存関係・順序） | 複雑な機能・リファクタリング着手前 |
| architect | システム設計・アーキテクチャ（全体設計・トレードオフ・ADR） | 設計判断・スケーラビリティ検討時 |
| gate-generator | TDD Generator（RED→GREEN→REFACTOR・実行ログを証拠に） | **新機能・バグ修正時**、`tdd-gates` から段階起動。汎用 `claude` で代替しない |
| gate-evaluator | TDD Evaluator（採点役・Critical即FAIL・reviewer-* を集約） | `tdd-gates` の Gate3/Gate8。単独起動で汎用スコアードレビューにも使える |
| reviewer-correctness | 正確性レビュー（バグ・冪等性・エラーハンドリング） | コード変更後に **必ず** 使用（Gate3/8 で gate-evaluator が並列集約） |
| reviewer-performance | 性能レビュー（メモリ・DB/I/O最適化・並列処理） | コード変更後に **必ず** 使用（同上） |
| reviewer-security | セキュリティレビュー（SQL injection・認証・機密情報） | コード変更後に **必ず** 使用（同上） |
| reviewer-test | テスト品質・要件適合レビュー（カバレッジ・フィクスチャ・信頼性＋仕様書要件・スキーマ適合・冪等性） | コード変更後に **必ず** 使用（同上） |
| reviewer-maintainability | 保守性・ドキュメント整合性レビュー（命名・構造・DRY・YAGNI＋docstring・CLAUDE.md・仕様書整合性） | コード変更後に **必ず** 使用（同上） |
| business-acceptance | 業務受け入れ検査（業務フローが過不足なく回るか・受け入れ可否判定） | 新システムの受け入れ判定・設計妥当性確認時 |
| python-dev | Python実装（スタイル・設計パターン・イディオム） | Python コードを書くとき（FastAPI/REST 設計は `references/` 参照） |
| python-refactor-cleaner | Python デッドコードのクリーンアップ | 未使用コード削除・コードメンテ時 |
| doc-updater | ドキュメント更新 | README・ガイド・コードマップ更新時 |

> **比例ルール優先**: 上表の gate-generator「必須」・reviewer-*「必ず」（＝`tdd-gates` の 9 ゲート）は **substantial 前提**。trivial は単一軽量 Agent に委任し、ゲート・reviewer 群を省略してよい。

---

## スキル

ローカル: `~/.claude/skills/tdd-gates`（TDD × 9品質ゲートのオーケストレータ。substantial 実装で使用）・`session-close-improve`（セッション終了時の改善ワークフロー専用）。プラグイン（superpowers / context7 / frontend-design 等）は `enabledPlugins` で有効化済み。  
context7 はライブラリ・SDK・API 質問で**必ず**使用（context7 MCP の instructions が常時注入される）。`resolve-library-id` → `query-docs` の順。  
frontend-design は UI・Web ページ・HTML 成果物（レポート/構成図等）・スライド等の資料をデザイン・生成・変更するときに**必ず**使用（スキル自体の description は Web アプリ寄りで資料系に自動発火しないため、ここで明示）。  
HTML 成果物は提出前に独立サブエージェントで**敵対的クロスレビュー → 修正 → 再レビュー**を通す（ブラウザ不可環境では `node --check` ＋ JS ロジック追跡等の静的解析で代替）。

---

## アクティブなHooks

| Hook | 効果 |
|------|------|
| bash-guard.sh | 破壊的コマンドをブロック。`rm`/`rmdir`/`unlink` はプロジェクト配下の子要素のみ許可し、配下外・ルート自体・解析不能なものはブロック。ブロック時はユーザーへ `! <コマンド>` 形式で依頼すること |
| workspace-guard.sh | プロジェクト配下／`~/.claude` 配下以外への Write/Edit と `/tmp` への Bash リダイレクトをブロック（`exit 2`）。誤検知時は Read ツールで回避 |
| tdd-gates-nudge.sh | `tests/` 外の Python 実装ファイル編集時に `tdd-gates` スキル使用を非ブロッキングで促す（言語追加は profile 用意後に拡張） |
| session-stop.sh | 統合 Stop フック。(1) 新規 feedback メモリを検出してパッシブ通知（revise→improver 案内）。(2) 最後のユーザー入力（transcript の `last-prompt`）に終了意図がある時だけ `session-close-improve` を**1セッション1回 decision:block** で促す。スキップはセッション単位（reason 内の `touch` パス）・実施済み判定は空白許容・stop_hook_active でループ防止 |
| venv-guard.sh | venv 外への `pip install` 等をブロック。bash コマンド内に `pip install` が文字列として含まれると誤検知する場合あり（回避は Read ツール） |
| context7-plan-remind.sh | Skill 実行前（PreToolUse→Skill）にライブラリ/SDK 質問で context7 使用を促す |

