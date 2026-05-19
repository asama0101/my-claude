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
   - **修正・指示変更を受けたとき**: 即座に自動メモリ（feedback タイプ）として保存する。セッション終了時に `session-close-improve` を実行して CLAUDE.md に反映する（`session-close-remind.sh` フックがリマインドする）。

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

### go/（*.go ファイル対象）

| Rule File | Contents |
|-----------|----------|
| coding-style.md | Effective Go・gofmt・命名規則・エラーハンドリング・panic 禁止 |
| testing.md | testify・テーブル駆動テスト・TDD・80%カバレッジ・t.Parallel |
| patterns.md | インターフェース・エラーラッピング・goroutine・Functional Options |
| gin.md | ルーター設計・ハンドラー DI・ShouldBindJSON・ミドルウェア・セキュリティ |

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
| go-patterns | Go コードの型・インターフェース・エラーハンドリング・goroutine パターンを適用するとき |
| go-testing | testify フィクスチャ・テーブル駆動テスト・モック・カバレッジを書くとき |
| gin-patterns | Gin ハンドラー・ミドルウェア・DI・バリデーション・テストを書くとき |

> **役割分担**: superpowers = 汎用プロセス（計画・TDDサイクル・デバッグ手順）、ローカルスキル = ドメイン知識 + プロジェクト固有プロセス（実装パターン・コード規約・セッション終了フロー）。

### プラグインスキル（superpowers / claude-md-management / skill-creator）

`settings.json` の `enabledPlugins` で有効化済み。セッション開始時に `superpowers:using-superpowers` が自動読み込みされ、利用可能な全スキル（TDD・デバッグ・レビュー・計画等）が提示される。

### context7（MCP サーバー）

`settings.json` の `enabledPlugins` と `SessionStart` フックで自動読込済み。ライブラリ・フレームワーク・SDK・API に関する質問では**必ず**使用すること。トレーニングデータに頼らず `resolve-library-id` → `query-docs` の順で呼び出す。

**計画フェーズ（`writing-plans` 実行前）でも使用すること。** 実装で使うライブラリの型制約・API の破壊的変更・依存関係の制限は、実装中ではなく計画時に確認する。

### スキル使用時の注意

| スキル / コンテキスト | よくある逸脱 | 守るべきこと |
|----------------------|------------|------------|
| `brainstorming` | 既存ドキュメントがあるとき設計ドキュメント作成ステップをスキップ | 仕様書があっても `docs/superpowers/specs/` に実装アプローチの簡易ドキュメントを作る |
| `subagent-driven-development` | タスク数が多いとき spec/quality レビューを省略 | タスクごとに必ず 2 段階レビューを実施。「テストが通った」はレビュー省略の正当化にならない |
| `writing-plans` | ライブラリ API をトレーニングデータで推定して計画に書く | context7 で確認済みの API のみプランに記載する |
| `tdd-guide` | OOM・メモリリーク等のバグ修正で「小さい変更だから」と省略 | バグ修正でも tdd-guide を使う。修正後にテスト全件が通ることを確認してからコミット |
| `tdd-guide` / `code-reviewer` | 「小さな変更・数行の修正」と判断して両者をスキップし、手書き pytest + 手動確認で完結させる | 変更規模に関わらず tdd-guide（新機能・バグ修正）・code-reviewer（コード変更後）は必須。「テストが通った」は省略の正当化にならない |
| `tdd-guide` | 「既存テストを修正するだけ」と判断してスキップ | 既存テストに新アサーション（新動作の検証）を追加する作業は新機能追加と同等。tdd-guide を起動してから修正する |
| `brainstorming` | Plan mode 中に writing-plans を呼ばず ExitPlanMode で移行し、その後も spec ファイルを作らない | Plan mode 中は `ExitPlanMode` が writing-plans の代替。**ExitPlanMode 後の実装フェーズ最初のステップ**として `docs/superpowers/specs/` に spec ファイルを作成しコミットする |
| `context7` | リファクタリング作業で「API を変更しないから不要」とスキップ | リファクタリングでも新記法・関数（例: `polars.DataFrame.pipe()`）を追加する場合は context7 で確認する |
| `impl-doc-builder` | 設計背景を What（何をするか）から書いて反復修正が発生する | 設計理由・判断背景は必ず Why（なぜそうするか）を先に書く。What は補足に留める |
| `impl-doc-builder` | 「targeted な変更だから」と直接 HTML 編集して省略する | `.html` ドキュメントの既存セクション修正・追記でも impl-doc-builder を使う。「小さい変更」は省略の理由にならない |
| `impl-doc-builder` | ドキュメントに件数・数値を記述するとき記憶や推測で書く | テスト件数・カバレッジ・実測値は必ずソースから取得してから書く（`grep -c 'def test_'`・pytest 実行等）。code-reviewer 頼りではなく自分で先に検証する |
| `impl-doc-builder` | 設計判断カードの「リカバリ手順・CLI フラグ」を記憶で書く | CLI フラグ（`--retry-failed` vs `--hour` 等）は該当コードの WARNING ログ文字列や実装を先に読んでから書く。code-reviewer が検出する前に自分で確認する |
| `impl-doc-builder` | ログメッセージのサンプルに含まれる datetime 文字列を `datetime` フォーマット関数の確認なしに記憶で書く | `.isoformat()` は T 区切り（`2026-05-15T14:00:00+09:00`）、`str()` / `strftime('%Y-%m-%d %H:%M:%S')` はスペース区切り。サンプルを書く前に該当 Python 式をソースで確認する（例: `bucket_str = ....isoformat()` → T 区切りが確定） |
| `impl-doc-builder` | UAT シナリオの SQL サンプルにバケットのタイムゾーンを記憶で書く（`+00` と `+09:00` を混同） | `+00`（UTC 14:00）と `+09:00`（JST 14:00）は指す時刻が9時間異なる。CLAUDE.md の「手動リカバリ」セクションの SQL サンプルと照合して書く。JST 環境では `WHERE bucket = '2026-05-15 14:00:00+09:00'` が正しい |
| `impl-doc-builder` | 運用ドキュメントのコマンド例に具体的なパスワード値（`traffic123` 等）を直書きする | `source .env` 形式かプレースホルダー（`<DB_PASSWORD>`）を使う。パスワード文字列は運用ドキュメントに記載しない |
| `brainstorming` (Visual Companion) | Plan モード中にビジュアルコンパニオンサーバーを起動しようとする | Plan モードでは Bash ツールが使えないためサーバー起動不可。Plan モード中はテキストのみで進め、実装フェーズに入ってから起動する |
| `code-reviewer` | HTML / SVG / ドキュメントの変更を「コード変更ではない」と判断してスキップ。または「前回呼んだから後続の小さな修正は不要」と判断して省略する | `.html` / `.svg` の編集もコード変更に該当。**連続する小さな修正でも毎回呼ぶ**。前回呼んだことは省略の理由にならない |
| `code-reviewer` | Dockerfile / docker-compose.yml の変更を「設定ファイルのバージョン番号書き換えだから不要」と判断してスキップ | インフラ設定ファイルの変更もコード変更に該当。バージョン固定・環境変数追加・イメージタグ変更でも code-reviewer を呼ぶ |
| `tdd-guide` / `code-reviewer` | ドキュメント整備セッション中に Python スクリプトも変更した場合、「ドキュメント作業のついで」と判断して省略する | セッションの主目的がドキュメントでも、Python ファイルを変更したら tdd-guide・code-reviewer は必須。脇役扱いは省略の正当化にならない |
| HTML ダイアグラム要素追加 | 矢印の向きを「データフロー」と「接続起点」で混同し逆方向に設計する。隣接要素と CSS クラスが揃わない | 矢印は「接続起点（クライアント）→ 接続先（サーバー）」の方向で描く。追加する要素は隣接する既存要素と同じ CSS クラス（`arch-box` 等）を使っているか確認する |
| `code-reviewer` 指摘の実装 | 「MEDIUM = 要対応」と機械的に実装し、テスト用デフォルト値など文脈依存の設定を変更してテスト全滅 | `conftest.py` 等のテスト基盤ファイルへの変更は実装前に既存テストを実行して影響を確認する。「テスト用デフォルト認証情報」は本番ハードコードではなく必須のローカルDB接続設定であることが多い |
| `code-reviewer` | 「TDD で全テスト GREEN になった」「大規模リライトで時間がかかった」を理由に省略する | **テストが通ることとコードレビューは別**。大規模リライト（関数全面書き替え・新しい外部ライブラリ追加等）ほど、意図しない設計上の問題が潜みやすい。変更量が多いほど code-reviewer を呼ぶ必要がある |
| `tdd-guide` / `code-reviewer` | ETL の「冗長な変換を1行削除する」程度の簡素化を「リファクタリングだから tdd-guide 不要」「2行だから code-reviewer 不要」と判断してスキップ | `.dt.convert_time_zone()` 削除のような ETL ロジック変更は動作に影響する可能性がある。変更の種類（バグ修正・新機能・簡素化）に関わらず Python ファイルを変更したら tdd-guide・code-reviewer は必須 |
| `brainstorming` | ボトルネック分析・探索作業を会話でこなし「分析済みだから brainstorming は不要」と判断して writing-plans に直行する | 分析が済んでいても brainstorming を呼ぶ。spec ファイル（`docs/superpowers/specs/`）が未作成になることを防ぐために必要 |
| `writing-plans` + `context7` | 「探索ベンチマークで API の動作を確認済み」「このライブラリは十分知っている」という理由で context7 をスキップして計画を書く | 探索コードで動作確認した API でも、計画に記載する前に context7 で正式ドキュメントを確認する。`context7-plan-remind.sh` フックが writing-plans 実行前にリマインドする |
| `go-patterns` / `go-testing` / `gin-patterns` スキル作成・更新時 | 「Gin/testify は十分知っている」という理由で context7 をスキップしてコード例を書く | go-patterns・go-testing・gin-patterns を作成・更新する際も、コード例に使う API（`c.ShouldBindJSON`・`assert.Equal`・`t.Parallel()` 等）を context7 で確認してから書く |
| rule/skill/agent の markdown 作成後 | 「設定ファイル・ドキュメントだから code-reviewer は不要」と判断してスキップする | `.md` ファイルであっても rule/skill/agent は実際の動作に影響する設定。作成・変更後は必ず code-reviewer を呼ぶ |
| rule/skill/agent を新規作成するとき | 「要件が明確だから brainstorming は不要」と判断して Plan モードに直行する | rule/skill/agent の新規作成は機能追加に該当するため brainstorming が必要。Claude-md-improver 経由でも同様 |
| `impl-doc-builder`（HTML セクション番号変更） | セクションを移動したとき「移動元番号への参照」を見落とし、事後 grep で修正する羽目になる | 変更前に `grep -n 'Section [0-9]'` で全テキスト参照を列挙し「参照先が移動するもの」と「参照元番号が変わるもの」の両方を網羅する。変更後にも同じ grep で確認する |
| `impl-doc-builder`（Write ツールで大規模書き直し） | 1,000行超の HTML を Write ツールで一括書き直したとき、新たなミスが混入しても自分では気づけない | 大規模書き直し後は必ず code-reviewer を呼ぶ。Write ツールは既存の誤りを直す一方で新たな誤りを生む可能性がある（今回の例: `_detect_late_files` 戻り値型・`logging.DEBUG` vs `logging.INFO`・カラム順序の3件が混入 → code-reviewer で全検出）。「Write 後の code-reviewer は必須」のパターン |

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
| tdd-guard-go.sh | Write/Edit後（*.go） | `*_test.go` 以外の Go ファイル編集時に tdd-guide 使用を促す |
| context7-remind.sh | セッション開始時 | context7 使用指示を自動注入 |
| task-finish-suggest-review.sh | TaskUpdate（status=completed） | Task 完了時に code-reviewer または security-review の実施を提案。レビュー漏れ防止 |
| skill-logger.sh | Skill/Agent/context7 ツール使用後 | 使用スキル・エージェント・プラグインを `~/.claude/logs/session-usage-<日付>.log` に追記 |
| session-summary.sh | セッション終了時（Stop） | セッション中に使用したスキル一覧を出力 |
| session-close-remind.sh | Stop（活性セッションのみ） | `session-close-improve` 未実施の場合にリマインドを表示 |
| context7-plan-remind.sh | Skill 実行前（writing-plans） | context7 でライブラリ API を確認済みかをリマインド。トレーニングデータ推定による計画記載を防止 |

### Python 開発の必須要件

- `pip install` / `pip uninstall` は必ずプロジェクトのvenv内で実行すること
- セットアップ例: `python -m venv .venv && source .venv/bin/activate`（uvを使う場合: `uv venv && source .venv/bin/activate`）

PostToolUse フックの追加設定が必要な場合は `/update-config` スキルを使用。
