# CLAUDE.md - AI Development Guidelines

## 基本理念と禁止事項 (**Critical**)

### 基本理念
- **シンプル第一**: 変更を最小限にし、複雑さを避ける。
- **根本解決**: 対症療法を避け、バグの真因を叩く。
- **影響の最小化**: 既存の正常なロジックを壊さない。
- **エレガントさの追求**: 「もっとスマートな解決策はないか？」と自問自答する。ただし過剰設計は避ける。

### 禁止事項
- **非破壊**: READMEや既存ドキュメントを勝手に生成・変更しない。生成・変更すべき場合はユーザーに確認する。
- **テスト保護**: テストコードを確認なしに削除・コメントアウトしない。
- **無断リファクタリング禁止**: 動作中のコードを理由なく書き換えない。
- **削除制限**: ファイルを勝手に削除しない。削除が必要な場合は方法を提示し、ユーザーの承認を待つ。

---

## タスク実行手順
1. **確認**: 実装前に必ずユーザーの承認を得る。
2. **遂行**: 進捗を随時マークし、各ステップで高レベルなサマリーを提供する。
3. **記録**: 完了後、プロジェクトの `.claude/lessons.md` に学びを蓄積する（ファイルがなければ新規作成）。予期しなかった問題・回避策・次回役立つ非自明な知見のみ記録する。
   - **使い分け**: `lessons.md`はプロジェクト固有の技術的知見。会話をまたいで保持すべきユーザー嗜好・フィードバックは自動メモリシステム（`memory/MEMORY.md`）に保存する。
   - **修正・指示変更を受けたとき**: 即座に自動メモリ（feedback タイプ）として保存する。Stop フックがこれを検出し、`/claude-md-management:claude-md-improver` の実行を促す。

---

## コミュニケーション
- **言語**: 応答は日本語（コード・変数名・シンボルは英語）。
- **Planモードの基準**: 変更着手前に必ずPlanモードで計画を立案しユーザー承認を得る（計画フェーズは Claude 本体が担う）。`settings.json` の `defaultMode: "plan"` で自動設定済み。
- **Stop & Ask**: 不明点や曖昧な仕様がある場合、推測で進めず必ず作業を止めて質問する。
- **透明性**: Bash実行を確認する際、コマンドの意図を説明する。
- **再計画**: 詰まった場合は無理に進めず、即座に立ち止まって再計画を提案する。
- **エージェント優先**: 複雑な作業は専門のエージェントに委任する（タイミングは下記「利用可能なエージェント」表を参照）。計画承認後の実装・レビュー・テストフェーズで使用する。
- **並列実行**: 可能な場合は、`Agent` ツールで複数のサブエージェントを並列起動する。

---

## モジュール式ルール

詳細なガイドラインは`~/.claude/rules/`にあります。

> ルールファイルのフロントマター `paths:` に一致するファイルを Claude が読んだ時のみ
> そのルールがロードされます（コンテキストを節約するため）。
> `paths:` フロントマターがないファイルは **常時ロード** されます（common/ ルールはこれに該当）。

### common/（常時ロード）

| Rule File | Contents |
|-----------|----------|
| agents.md | エージェントオーケストレーション、どのエージェントをいつ使用するか |
| code-review.md | コードレビュー基準（CRITICAL/HIGH/MEDIUM/LOW）、セキュリティチェック |
| planning-checklist.md | writing-plans 前・subagent-driven-development 中・実装完了後のチェックリスト |

### python/（*.py ファイル対象）

| Rule File | Contents |
|-----------|----------|
| coding-style.md | PEP 8、型アノテーション、KISS/DRY/YAGNI、命名規則、black/isort/ruff |
| testing.md | pytest、TDDワークフロー、80%カバレッジ、AAAパターン |
| patterns.md | Protocol/dataclass DTO、リポジトリパターン、APIレスポンス形式 |
| fastapi.md | create_app()、薄いルーター、DI、非同期、セキュリティ |

---

## 利用可能なエージェント

`~/.claude/agents/` にあります。

| Agent | Purpose | 使用タイミング |
|-------|---------|--------------|
| planner | 機能実装計画 | 複雑な機能・リファクタリング着手前 |
| architect | システム設計・アーキテクチャ | 設計判断・スケーラビリティ検討時 |
| tdd-guide | テスト駆動開発 | **新機能・バグ修正時は必須**（テストファースト）。汎用 `claude` エージェントで代替しない |
| code-reviewer | 品質/セキュリティレビュー | コード作成・変更後に必ず使用 |
| e2e-runner | Playwright E2E テスト | 重要ユーザーフローの動作確認時 |
| refactor-cleaner | デッドコードのクリーンアップ | 未使用コード削除・コードメンテ時 |
| doc-updater | ドキュメント更新 | README・ガイド・コードマップ更新時 |

---

## 利用可能なスキル

### ローカルスキル（`~/.claude/skills/`）

ドメイン固有の実装パターンとプロジェクト固有のプロセスを提供する。superpowers のプロセススキル（brainstorming・writing-plans 等）と**組み合わせて**使う。

| Skill | 使用タイミング |
|-------|--------------|
| session-close-improve | 実装完了後・長い作業セッション終了時に積極的に使用。CLAUDE.md 更新・Hook/Rule/Skill 提案・メモリ保存を行う |
| api-design | REST エンドポイントのURL設計・HTTPステータスコード・ページネーション・エラー形式を決めるとき |
| fastapi-patterns | FastAPI のルーター・Pydanticスキーマ・DI・非同期実装・テストを書くとき |
| python-patterns | Python コードの型ヒント・イディオム・dataclass・非同期パターンを適用するとき |
| python-testing | pytest フィクスチャ・モック・パラメトライズ・非同期テストを書くとき |

> **役割分担**: superpowers = 作業プロセス（計画・TDDサイクル・デバッグ手順）、ローカルスキル = ドメイン知識（実装パターン・コード規約）。

### プラグインスキル（superpowers / claude-md-management / skill-creator）

`settings.json` の `enabledPlugins` で有効化済み。セッション開始時に `superpowers:using-superpowers` が自動読み込みされ、利用可能な全スキル（TDD・デバッグ・レビュー・計画等）が提示される。

### context7（MCP サーバー）

`settings.json` の `enabledPlugins` と `SessionStart` フックで自動読込済み。ライブラリ・フレームワーク・SDK・API に関する質問では**必ず**使用すること。トレーニングデータに頼らず `resolve-library-id` → `query-docs` の順で呼び出す。

**計画フェーズ（`writing-plans` 実行前）でも使用すること。** 実装で使うライブラリの型制約・API の破壊的変更・依存関係の制限は、実装中ではなく計画時に確認する。

### スキル使用時の注意

| スキル | よくある逸脱 | 守るべきこと |
|--------|------------|------------|
| `brainstorming` | 既存ドキュメントがあるとき設計ドキュメント作成ステップをスキップ | 仕様書があっても `docs/superpowers/specs/` に実装アプローチの簡易ドキュメントを作る |
| `subagent-driven-development` | タスク数が多いとき spec/quality レビューを省略 | タスクごとに必ず 2 段階レビューを実施。「テストが通った」はレビュー省略の正当化にならない |
| `writing-plans` | ライブラリ API をトレーニングデータで推定して計画に書く | context7 で確認済みの API のみプランに記載する |

---

## 自動メモリシステム

`~/.claude/projects/*/memory/MEMORY.md` に会話をまたいだ記憶が蓄積される。
セッション中に `#` キーを押すと、現在の学びを `memory/MEMORY.md` に保存できる。

---

## アクティブなHooks

`settings.json` で以下のフックが常時動作中:

| Hook | トリガー | 効果 |
|------|---------|------|
| bash-guard.sh | Bash実行前 | `rm` 等の破壊的コマンドをブロック。ブロック時は **自分で実行せず、ユーザーへ `! <コマンド>` の形式で実行を依頼**すること |
| venv-guard.sh | Bash実行前 | venv外での `pip install` / `pip uninstall` / `uv add` をブロック（venv パス直接指定は許可） |
| tdd-guard.sh | Write/Edit後（*.py） | `tests/` 外の Python ファイル編集時に tdd-guide 使用を促す。汎用エージェントでの代替防止 |
| context7-remind.sh | セッション開始時 | context7 使用指示を自動注入 |
| task-finish-suggest-review.sh | TaskUpdate（status=completed） | Task 完了時に code-reviewer または security-review の実施を提案。レビュー漏れ防止 |
| skill-logger.sh | Skill/Agent/context7 ツール使用後 | 使用スキル・エージェント・プラグインを `~/.claude/logs/session-usage-<日付>.log` に追記 |
| session-summary.sh | セッション終了時（Stop） | セッション中に使用したスキル一覧を出力 |
| session-close-remind.sh | Stop（活性セッションのみ） | `session-close-improve` 未実施の場合にリマインドを表示 |

### Python 開発の必須要件

- `pip install` / `pip uninstall` は必ずプロジェクトのvenv内で実行すること
- セットアップ例: `python -m venv .venv && source .venv/bin/activate`（uvを使う場合: `uv venv && source .venv/bin/activate`）

PostToolUse フックの追加設定が必要な場合は `/update-config` スキルを使用。
