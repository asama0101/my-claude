# my-claude

Claude Code のユーザーグローバル設定（`~/.claude/`）をバージョン管理し、**別環境（別ユーザー・別マシン）でクローンして再現**するためのリポジトリ。

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `linux/claude/` | `~/.claude/` のミラー（hooks / skills / agents / rules / assets / commands / settings.json / CLAUDE.md / statusline-command.sh） |
| `.claude/skills/sync-config/` | `~/.claude/` → `linux/claude/` への同期スキル（コピーのみ、commit + push は行わない） |
| `.claude/skills/diff-sync/` | `linux/claude/` と `windows/claude/` の差分を検出・解消するスキル。意図的なOS差分を台帳（`ledger.json`）に記録して以後自動的に許容し、未記録の差分だけ対話的に解消する。実機には一切触れない |
| `windows/` | Windows 版設定の置き場所（`windows/claude/` は `%USERPROFILE%\.claude\` の完全なミラー） |

## linux/claude/ フォルダについて

`linux/claude/` は `~/.claude/` のミラーであり、以下を含む：

| パス | 概要 |
|---|---|
| `linux/claude/agents/` | サブエージェント定義（詳細は後述「サブエージェント」を参照） |
| `linux/claude/skills/` | スキル定義（詳細は後述「スキル」を参照） |
| `linux/claude/hooks/` | ツール呼び出しを検査する PreToolUse フックスクリプト（詳細は後述「hooks」を参照） |
| `linux/claude/assets/` | HTML 成果物の流用元テンプレート置き場（詳細は後述「assets」を参照。現状ディレクトリ自体が存在しない） |
| `linux/claude/rules/` | ルールファイルの置き場所（詳細は後述「rules」を参照） |
| `linux/claude/commands/` | カスタムスラッシュコマンド定義（`pr-create.md`＝コミット→push→PR作成を一括実行、`pr-cleanup.md`＝マージ済みPRのブランチ片付け） |
| `linux/claude/settings.json` | Claude Code の設定ファイル（詳細は後述「settings.json」を参照） |
| `linux/claude/CLAUDE.md` | リポジトリ直下の `CLAUDE.md` とは別物。`~/.claude/CLAUDE.md`（ユーザーのグローバル指示ファイル）のミラー |
| `linux/claude/statusline-command.sh` | ステータスライン表示用スクリプト（コンテキスト使用率・モデル名・ブランチ名などを色分け表示） |

## サブエージェント

`linux/claude/agents/*.md` が定義するサブエージェント（`references/` 配下は実装の詳細参照用で対象外）：

| 名前 | 役割 |
|---|---|
| `dev-python` | Python コードのスタイル・設計パターン・イディオムを担当する実装専門家 |
| `doc-updater` | ドキュメントの新規作成・構成設計、および既存ドキュメントのソースコードとの同期更新 |
| `doc-verifier` | ドキュメントの記載事実とソースコードの整合を、執筆者と別コンテキストで確認（採点専用・自身では修正しない） |
| `planner` | 機能実装・アーキテクチャ変更・複雑なリファクタリングの実装計画を作成 |
| `review-correctness` | バグ・論理エラー・エラーハンドリング・境界値・冪等性のレビュー |
| `review-doc-readability` | 人間向けMarkdown文書の構成・可読性を、執筆者と別コンテキストで採点（記載事実の照合はdoc-verifierの担当） |
| `review-maintainability` | 保守性（命名・構造・複雑さ・DRY/YAGNI）とドキュメント整合性のレビュー |
| `review-performance` | アルゴリズム計算量・メモリ効率・DB/並列処理最適化のレビュー |
| `review-security` | インジェクション・認証・機密情報漏洩・パストラバーサルのレビュー |
| `review-test` | テストのカバレッジ・品質・仕様適合性のレビュー |
| `tdd-evaluator` | `tdd-gates` の採点役。実装者と別コンテキストで証拠に基づき合否判定する |
| `tdd-implementer` | TDD 規律（RED→GREEN→REFACTOR）に従いテストと実装を書く実行者 |
| `trivial-executor` | 数行程度の trivial 変更（設定/ドキュメント/コメント/誤記）を軽量実行（haiku） |

## スキル

`linux/claude/skills/*/` が定義するスキル：

| 名前 | 役割 |
|---|---|
| `tdd-gates` | superpowers のスキルチェーンに品質規律を上乗せする TDD 品質ゲート（チェックポイント CP-A〜F・証拠主義・Critical 即 FAIL） |

## hooks

| Hook | 効果 |
|---|---|
| `system-guard.sh` | 場所を問わずシステム全体を破壊しうるコマンドのみを無条件ブロック（`dd`/`mkfs`/`shred`・`chown -R .../`・`chmod 000`/`chmod -R 777 /`・`kill -9 -1`・フォーク爆弾・`shutdown`等・`curl\|bash`等・`/etc/hosts`等への書込・DB破壊・グローバルパッケージ導入/削除・システムパッケージのupdate/upgrade・`truncate -s 0`・`git clean -fd`(パス無し)・`crontab -r`）。機密ファイル読取・任意ファイルへの書込み(リダイレクト/cp/tee/mv/curl -o)は意図的に無防備（ゾーン判定が必要でこのフックの「場所非依存」という設計軸に合わないため。詳細は`docs/specs/2026-08-29-hooks-redesign-design.md`） |
| `workspace-guard.sh` | Write/Edit/MultiEdit/NotebookEdit の書込み先が、プロジェクト配下／`~/.claude` 配下／`/tmp/claude-*/` 配下のいずれでもない場合にブロック。Bashコマンド経由の書込み・削除はこのフックの対象外（2026-08-29再設計でスコープ縮小） |
| `venv-guard.sh` | venv 外への `pip install`/`pip uninstall`（`pip`/`pip3`/`python -m pip` 経由）・`uv add`/`uv pip install` をブロック（文字列一致で誤検知しうるが例外は認めない方針） |
| `branch-guard.sh` | main/master ブランチ上での Write/Edit/MultiEdit/NotebookEdit、および Bash の削除・変更系コマンドをブロック。読み取り専用コマンドは対象外。`.git`書込み権限が無い環境は自動検知し警告のみで許容(監査ログ記録) |

> いずれのスクリプトも jq が無い環境では判定不能として fail-close（安全側にブロック）する。詳細は各スクリプト内のコメント、またはリポジトリ直下 `CLAUDE.md` の「Hooks（enforcement の正典）」表を参照。

## assets

`linux/claude/assets/` は現状ディレクトリ自体が存在しない（`windows/claude/assets/`・`~/.claude/assets/` も同様）。かつては `html-template-import` スキルが HTML 成果物の流用元テンプレート（カタログ `INDEX.md`・テンプレート本体 `report-light.html`）を保管していたが、同スキルの廃止（2026-08-24, commit `13f23f2`）に伴いディレクトリごと削除された。

## rules

`linux/claude/rules/` はルールファイルの置き場所。`hooks.md`（Hooks の enforcement 正典）・`skills.md`（スキル使用判断の索引）を含む。

## settings.json

| キー | 説明 |
|---|---|
| `$schema` | 設定ファイルの JSON Schema 参照 URL（バリデーション用） |
| `permissions` | ツール呼び出しの許可（allow）・拒否（deny）・確認要求（ask）ルールと `defaultMode`・`disableBypassPermissionsMode` を定義 |
| `model` | デフォルトで使用するモデルの上書き指定（本リポジトリでは `"sonnet"`） |
| `hooks` | ライフサイクルイベントで実行するフックスクリプトの登録。本リポジトリでは `PreToolUse`（Bash 用と Write/Edit/MultiEdit/NotebookEdit/Bash 用）のみ登録 |
| `statusLine` | ステータスライン表示のカスタムコマンド設定（`statusline-command.sh` を呼び出す） |
| `enabledPlugins` | 有効化するプラグインを `プラグインID@マーケットプレイスID: true` 形式で列挙（skill-creator・superpowers・context7・claude-md-management・frontend-design） |
| `effortLevel` | セッションをまたいで持続する推論努力レベルの指定（`low`/`medium`/`high`/`xhigh`。本リポジトリでは `"high"`） |
| `tui` | ターミナル UI の描画モード（`fullscreen`=ちらつきのない代替画面レンダラー／`default`=従来のメイン画面レンダラー。本リポジトリでは `"fullscreen"`） |
| `skipWorkflowUsageWarning` | 値は `true`。schemastore の公開スキーマ（`https://www.schemastore.org/claude-code-settings.json`）には未収録のため詳細は未規定。キー名からはワークフロー利用時の使用方法警告表示に関する設定と推測されるに留まる |
| `remoteControlAtStartup` | 対話セッション開始時に Remote Control を自動接続するかどうか（`true`=常時／`false`=無効／未設定=組織既定値。本リポジトリでは `true`） |
| `inputNeededNotifEnabled` | Remote Control 接続時、権限確認や質問への入力待ちが発生した際にスマートフォンへプッシュ通知するかどうか |
| `agentPushNotifEnabled` | Remote Control 接続時、長時間タスク完了時などに Claude から能動的にプッシュ通知を送ることを許可するかどうか |
| `skipAutoPermissionPrompt` | 値は `true`。schemastore の公開スキーマには未収録のため詳細は未規定。キー名からは自動権限確認プロンプトのスキップに関する設定と推測されるに留まる |

## 別環境でのセットアップ（初回）

```bash
git clone <repo-url> ~/my-claude
```

展開スクリプトは廃止済み。クローン後、Claude Code に「`linux/claude/` の内容を `~/.claude/` へ展開して」と直接依頼する運用に変更した。依頼時は以下をClaude Codeが満たすべき条件として明示する：

- **ホワイトリスト方式**: `~/.claude/settings.local.json`（ローカルオーバーライド）・`~/.claude/projects/.../memory/`（会話をまたぐ自動メモリ）・`~/.claude/logs/`・`~/.claude/sessions/`・`~/.claude/daemon/`・`~/.claude/plugins/` など環境固有資産には一切触れない
- **バックアップ**: 差分のある既存ファイルは上書き前に `~/.claude/backups/` 配下など退避先へコピーしてから上書きする
- **プレースホルダ実体化**: `settings.json` 内の `__CLAUDE_HOME__` は展開先の絶対パス（通常 `$HOME/.claude`）へ置換してから配置する
- 展開後、Claude Code を再起動すると新しい設定が読み込まれる

## 設定を更新したら（既存環境）

`~/.claude/` 側で設定を変更した後、`sync-config` スキルでリポジトリへ同期する。Claude Code に「設定を同期して」と伝える。Claude Code が OS を判定し、内部で以下のスクリプトを実行する（自分で直接実行することも可能）：

```bash
bash .claude/skills/sync-config/scripts/sync-linux.sh   # ~/.claude/ → linux/claude/ へコピー（commit・push は行わない）
```

> `sync-config` スキルはコピーのみ行う。commit・push が必要なら `git status` で差分を確認し `/pr-create` を使うこと。

## 移植性の仕組み

ハードコードされた絶対パス（`/home/<user>/`）を排除している：

- **hooks・skill スクリプト**: `$HOME` を直書き。シェル/Python が実行時に展開するため変換不要。
- **settings.json**: Claude Code は settings.json 内で `$HOME` を展開しないため、repo 上は プレースホルダ `__CLAUDE_HOME__` を置く。別環境セットアップ時に Claude Code が展開先の絶対パスへ実体化し、`sync-config` スキルの同期スクリプトが逆変換でプレースホルダへ戻す。

この順変換（展開時）と逆変換（`sync-config` スキルの同期スクリプト）は対になっている。そのため、展開と同期を繰り返してもパス表現はブレない。

- **agents・rules・assets など**: ハードコードされた絶対パスを含まないため、パス変換処理は不要。

## Gotchas（運用上の注意点）

- **`linux/claude/` フォルダを直接編集しない**：`sync-config` スキル実行時に `~/.claude/` 内容で上書きされる。設定変更は必ず `~/.claude/` 側で行い、その後 Claude Code に「設定を同期して」と依頼するか、`sync-linux.sh` を直接実行して同期する。
  - 例外：`diff-sync` スキルは `linux/claude/` と `windows/claude/` の差分を解消することが目的のスキルであり、両ミラーを直接編集してよい（実機には一切触れない）。この禁止は `sync-config` による上書きを想定したものであり、`diff-sync` には適用されない。
  
- **`sync-config` スキルはコピーのみ行う**：commit・push は自動実行しない。同期後は `git status` で差分を確認し、必要なら `/pr-create` を使うこと。

- **別環境セットアップは Claude Code への依頼で行う（`install.sh` は廃止）**：展開時は `projects/`・`sessions/`・`logs/`・`settings.local.json` 等の環境固有資産に一切触れないホワイトリスト方式を守り、差分のある既存ファイルは上書き前にバックアップへ退避する。

- **展開時は rsync に依存しない**：Claude Code が Read/Write ツールで直接ファイル操作するため、展開先環境に rsync が無くても実行できる。一方 `sync-config` スキルの `sync-linux.sh`（`~/.claude/` → repo 方向）は引き続き rsync を使用する。展開方向と同期方向でツールが異なる非対称設計。
