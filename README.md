# my-claude

Claude Code のユーザーグローバル設定（`~/.claude/`）をバージョン管理し、**別環境（別ユーザー・別マシン）でクローンして再現**するためのリポジトリ。

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `claude/` | `~/.claude/` のミラー（hooks / skills / agents / rules / assets / settings.json / CLAUDE.md / statusline-command.sh） |
| `scripts/sync.sh` | `~/.claude/` → `claude/` への同期（commit + push 自動） |
| `scripts/install.sh` | `claude/` → `~/.claude/` への展開（別環境セットアップ） |
| `docs/` | 過去の計画・仕様の記録 |

## サブエージェント

`claude/agents/*.md` が定義するサブエージェント（`references/` 配下は実装の詳細参照用で対象外）：

| 名前 | 役割 |
|---|---|
| `dev-python` | Python コードのスタイル・設計パターン・イディオムを担当する実装専門家 |
| `doc-updater` | ドキュメントの新規作成・構成設計、および既存ドキュメントのソースコードとの同期更新 |
| `doc-verifier` | ドキュメントの記載事実とソースコードの整合を、執筆者と別コンテキストで確認（採点専用・自身では修正しない） |
| `planner` | 機能実装・アーキテクチャ変更・複雑なリファクタリングの実装計画を作成 |
| `review-correctness` | バグ・論理エラー・エラーハンドリング・境界値・冪等性のレビュー |
| `review-maintainability` | 保守性（命名・構造・複雑さ・DRY/YAGNI）とドキュメント整合性のレビュー |
| `review-performance` | アルゴリズム計算量・メモリ効率・DB/並列処理最適化のレビュー |
| `review-security` | インジェクション・認証・機密情報漏洩・パストラバーサルのレビュー |
| `review-test` | テストのカバレッジ・品質・仕様適合性のレビュー |
| `tdd-evaluator` | `tdd-gates` の採点役。実装者と別コンテキストで証拠に基づき合否判定する |
| `tdd-implementer` | TDD 規律（RED→GREEN→REFACTOR）に従いテストと実装を書く実行者 |
| `trivial-executor` | 数行程度の trivial 変更（設定/ドキュメント/コメント/誤記）を軽量実行（haiku） |

## スキル

`claude/skills/*/` が定義するスキル：

| 名前 | 役割 |
|---|---|
| `codemap-python` | Python コードの処理フローを一本道で読み下せる HTML レビュー地図（インデックス＋フローページ）を生成する |
| `html-template-import` | 既存の HTML ドキュメントをテンプレートライブラリ（`~/.claude/assets/html-templates/`）へ取り込み、カタログに登録する |
| `tdd-gates` | superpowers のスキルチェーンに品質規律を上乗せする TDD 品質ゲート（チェックポイント CP-A〜F・証拠主義・Critical 即 FAIL） |

## claude/ 配下のその他のファイル

`claude/agents/`・`claude/skills/` 以外の主なファイル・ディレクトリ：

| パス | 内容 |
|---|---|
| `claude/hooks/` | Claude Code のツール呼び出しを検査する PreToolUse フックスクリプト（4本。詳細は下表） |
| `claude/assets/html-templates/` | 過去に作成した HTML 成果物の流用元テンプレート・ライブラリ。`INDEX.md` がカタログ（name・特徴・用途・path の表）、`report-light.html` が現在唯一登録済みのテンプレート。登録は `html-template-import` スキルが担う |
| `claude/rules/` | 現状空のディレクトリ。将来ルールファイルを置く想定の場所 |
| `claude/settings.json` | Claude Code の設定ファイル（permissions・hooks 登録・model 等） |
| `claude/CLAUDE.md` | リポジトリ直下の `CLAUDE.md` とは別物。`~/.claude/CLAUDE.md`（ユーザーのグローバル指示ファイル）のミラー |
| `claude/statusline-command.sh` | ステータスライン表示用スクリプト（コンテキスト使用率・モデル名・ブランチ名などを色分け表示） |

### hooks の一覧

| Hook | 効果 |
|---|---|
| `bash-guard.sh` | 破壊的コマンドをブロック。`rm`/`rmdir`/`unlink`/`git rm` はプロジェクト配下／`$CLAUDE_HOME` 配下／`/tmp` 配下の子要素のみ許可（各ゾーンのルート自体は不可）。非 rm 削除（`find -delete`・`shutil.rmtree`・`rsync --delete`）は無条件ブロック。機密ファイル（`.env`/`.ssh`/鍵）の読取/持ち出しもブロック |
| `workspace-guard.sh` | プロジェクト配下／`~/.claude` 配下／`/tmp` 配下以外への Write/Edit をブロック。`~/.claude/hooks/` とハーネス設定（`settings.json`）は許可。Bash の `/var/tmp` リダイレクト・プロジェクト外宛先の cp/tee/mv も保守的にブロック |
| `venv-guard.sh` | venv 外への `pip install` 等をブロック（文字列一致で誤検知しうる） |
| `main-branch-guard.sh` | main/master ブランチ上での Write/Edit/MultiEdit/NotebookEdit、および Bash の削除・変更系コマンド（`rm`/`mv`/`cp`/`tee`/`touch`/リダイレクト/`sed -i`/`git commit`/`git rm` 等）をブロック。読み取り専用コマンドは対象外 |

> いずれのスクリプトも jq が無い環境では判定不能として fail-close（安全側にブロック）する。詳細は各スクリプト内のコメント、またはリポジトリ直下 `CLAUDE.md` の「Hooks（enforcement の正典）」表を参照。

## 別環境でのセットアップ（初回）

```bash
git clone <repo-url> ~/my-claude
bash ~/my-claude/scripts/install.sh            # claude/ → ~/.claude/ へ展開
```

- 実行時に展開先パスを表示して確認する（新規作成・既存いずれの場合も `[y/N]` プロンプトが出る）。`CLAUDE_HOME` の指定ミスによる誤展開を防ぐためで、`--force` / `--yes` / 非対話（非TTY）実行では確認を省略する
- `--dry-run` で実際の変更なしに差分を確認できる：`bash scripts/install.sh --dry-run`
- 展開先を変えたい場合は `CLAUDE_HOME` を指定：`CLAUDE_HOME=/path/to/dest bash scripts/install.sh`
- 既存の `~/.claude/` の対象ファイルは `~/.claude/backups/install-<timestamp>/` へ退避してから上書きされる
- 展開後、Claude Code を再起動すると新しい設定が読み込まれる

### 移植されないもの（環境固有）

`install.sh` はホワイトリスト方式で、以下には**一切触れない**：

- `~/.claude/settings.local.json`（ローカルオーバーライド）
- `~/.claude/projects/.../memory/`（会話をまたぐ自動メモリ）
- `~/.claude/logs/`・`~/.claude/sessions/`・`~/.claude/daemon/`・`~/.claude/plugins/` など

## 設定を更新したら（既存環境）

`~/.claude/` 側で設定を変更した後、リポジトリへ同期する：

```bash
bash scripts/sync.sh   # ~/.claude/ → claude/ へ同期し commit + push（自動）
```

> `scripts/sync.sh` は commit + push まで自動実行する。実行前に余計な差分がないか確認すること。

## 移植性の仕組み

ハードコードされた絶対パス（`/home/<user>/`）を排除している：

- **hooks・skill スクリプト**: `$HOME` を直書き。シェル/Python が実行時に展開するため変換不要。
- **settings.json**: Claude Code は settings.json 内で `$HOME` を展開しないため、repo 上は プレースホルダ `__CLAUDE_HOME__` を置く。`install.sh` が展開先の絶対パスへ実体化し、`sync.sh` が逆変換で戻す。

この順変換（install）と逆変換（sync）が対になっているため、`install` ↔ `sync` を繰り返してもパス表現はブレない。

- **agents・rules・assets など**: ハードコードされた絶対パスを含まないため、パス変換処理は不要。

## Gotchas（運用上の注意点）

- **`claude/` フォルダを直接編集しない**：`sync.sh` で `~/.claude/` 内容が上書きされる。設定変更は必ず `~/.claude/` 側で行い、その後 `bash scripts/sync.sh` で同期する。
  
- **`scripts/sync.sh` は commit + push まで自動実行する**：実行前に余計な差分がないか確認すること。

- **`install.sh` は環境固有資産に触れない**：`projects/`・`sessions/`・`logs/`・`settings.local.json` 等はホワイトリスト方式で展開対象外。差分のある既存ファイルのみ `~/.claude/backups/install-<timestamp>/` へ退避してから上書きされる（差分がなければバックアップは作られない）。

- **`install.sh` は rsync に依存しない**：別環境での依存を最小化するため `cp`・`cmp`・`find` のみで実装。一方 `sync.sh` は rsync を使用する非対称設計。
