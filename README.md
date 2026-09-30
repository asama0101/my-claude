# my-claude

Claude Code のユーザーグローバル設定（`%USERPROFILE%\.claude\`）をバージョン管理し、**別の Windows 環境（別ユーザー・別マシン）でクローンして再現**するためのリポジトリ。Windows 専用で、Linux/macOS は対象外。

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `windows/claude/` | `%USERPROFILE%\.claude\` のミラー（hooks / skills / rules / settings.json / CLAUDE.md / statusline-command.sh） |
| `.claude/skills/my-claude-pull/` | `%USERPROFILE%\.claude\` → `windows/claude/` への同期スキル（`scripts/sync-windows.ps1`。コピーのみで commit・push は行わない） |
| `.claude/skills/my-claude-push/` | `windows/claude/` → 実機 `$CLAUDE_HOME` への反映スキル（`my-claude-pull` の逆方向。commit・push は行わない） |

## windows/claude/ フォルダについて

`windows/claude/` は `%USERPROFILE%\.claude\` のミラーであり、以下を含む：

| パス | 概要 |
|---|---|
| `windows/claude/hooks/` | ツール呼び出しを検査する PreToolUse フックスクリプトとそのテスト（詳細は後述「hooks」を参照） |
| `windows/claude/skills/` | スキル定義（詳細は後述「スキル」を参照） |
| `windows/claude/rules/` | ルールファイルの置き場所（`hooks.md`＝Hooks の enforcement 正典） |
| `windows/claude/settings.json` | Claude Code の設定ファイル（詳細は後述「settings.json」を参照） |
| `windows/claude/CLAUDE.md` | リポジトリ直下の `CLAUDE.md` とは別物。`%USERPROFILE%\.claude\CLAUDE.md`（ユーザーのグローバル指示ファイル）のミラー |
| `windows/claude/statusline-command.sh` | ステータスライン表示用スクリプト（コンテキスト使用率・モデル名・ブランチ名などを色分け表示） |

## スキル

`windows/claude/skills/` 配下のスキル：

| 名前 | 役割 |
|---|---|
| `grilling` | 計画・決定・アイデアをユーザーに徹底的に質問して詰めるスキル |

> `skills/synced/` は claude.ai から自動同期されるスキル群（実機の環境固有資産）。手動管理の対象ではない。

## hooks

| Hook | 効果 |
|---|---|
| `venv-guard.sh` | venv 外への `pip install`/`pip uninstall`（`pip`/`pip3`/`python -m pip` 経由）・`uv add`/`uv pip install` をブロック（文字列一致で誤検知しうるが例外は認めない方針） |
| `branch-guard.sh` | main/master ブランチ上での Write/Edit/MultiEdit/NotebookEdit、および Bash の削除・変更系コマンドをブロック。読み取り専用コマンドは対象外。`.git`書込み権限が無い環境は自動検知し警告のみで許容(監査ログ記録) |

- 補助スクリプトとして `hooks/lib/json-field.sh`（フック入力 JSON の項目抽出）を持つ。
- いずれのスクリプトも node が無い環境では判定不能として fail-close（安全側にブロック）する。
- 詳細は各スクリプト内のコメント、または `rules/hooks.md`（Hooks の enforcement 正典）を参照。
- `system-guard.sh`・`workspace-guard.sh` は廃止済み。破壊的コマンドや作業ディレクトリ外への書き込みは auto モードの分類器が判定し、認証情報・秘密鍵の Read/Edit は `settings.json` の `permissions.deny` が拒否する。

## rules

`windows/claude/rules/` はルールファイルの置き場所。現状は `hooks.md`（Hooks の enforcement 正典）のみ。

## settings.json

| キー | 説明 |
|---|---|
| `$schema` | 設定ファイルの JSON Schema 参照 URL（バリデーション用） |
| `env` | Claude Code に渡す環境変数（本リポジトリでは `CLAUDE_CODE_DISABLE_MOUSE=1`） |
| `permissions` | ツール呼び出しの許可（allow）・拒否（deny）・確認要求（ask）ルールと `defaultMode`・`disableBypassPermissionsMode` を定義 |
| `model` | デフォルトで使用するモデルの上書き指定（本リポジトリでは `"sonnet"`） |
| `theme` | 配色テーマ（本リポジトリでは `"dark"`） |
| `hooks` | ライフサイクルイベントで実行するフックスクリプトの登録。本リポジトリでは `PreToolUse`（Bash 用の `venv-guard.sh` と、Write/Edit/MultiEdit/NotebookEdit/Bash 用の `branch-guard.sh`）のみ登録 |
| `statusLine` | ステータスライン表示のカスタムコマンド設定（`statusline-command.sh` を呼び出す） |
| `enabledPlugins` | 有効化するプラグインを `プラグインID@マーケットプレイスID: true` 形式で列挙（skill-creator・superpowers・claude-md-management・frontend-design・code-review・playwright） |
| `effortLevel` | セッションをまたいで持続する推論努力レベルの指定（`low`/`medium`/`high`/`xhigh`。本リポジトリでは `"high"`） |
| `tui` | ターミナル UI の描画モード（`fullscreen`=ちらつきのない代替画面レンダラー／`default`=従来のメイン画面レンダラー。本リポジトリでは `"fullscreen"`） |
| `skipWorkflowUsageWarning` | 値は `true`。schemastore の公開スキーマには未収録のため詳細は未規定。キー名からはワークフロー利用時の使用方法警告表示に関する設定と推測されるに留まる |
| `remoteControlAtStartup` | 対話セッション開始時に Remote Control を自動接続するかどうか（`true`=常時／`false`=無効／未設定=組織既定値。本リポジトリでは `true`） |
| `inputNeededNotifEnabled` | Remote Control 接続時、権限確認や質問への入力待ちが発生した際にスマートフォンへプッシュ通知するかどうか |
| `agentPushNotifEnabled` | Remote Control 接続時、長時間タスク完了時などに Claude から能動的にプッシュ通知を送ることを許可するかどうか |
| `skipAutoPermissionPrompt` | 値は `true`。schemastore の公開スキーマには未収録のため詳細は未規定。キー名からは自動権限確認プロンプトのスキップに関する設定と推測されるに留まる |
| `autoMode` | auto モードの分類器に渡す環境情報（信頼するリポジトリ・機密データの所在・本リポジトリ固有の定型作業など） |

## 別環境でのセットアップ（初回）

```powershell
git clone <repo-url>
```

クローン後、Claude Code で `my-claude-push` スキルを使い（「my-claude-pushして」と依頼）、`windows/claude/` の内容を `%USERPROFILE%\.claude\` へ反映する。スキルは以下の条件を満たして動作する：

- **ホワイトリスト方式**: `settings.local.json`（ローカルオーバーライド）・`projects/`（会話をまたぐ自動メモリ含む）・`logs/`・`sessions/`・`daemon/`・`plugins/` など環境固有資産には一切触れない
- **バックアップ**: 差分のある既存ファイルは上書き前に `%USERPROFILE%\.claude\backup\` 配下へ退避してから上書きする
- **プレースホルダ実体化**: `settings.json` 内の `__CLAUDE_HOME__` は git-bash 形式の絶対パス（例: `/c/Users/<user>/.claude`）へ置換してから配置する
- 反映後、Claude Code を再起動すると新しい設定が読み込まれる

## 設定を更新したら（既存環境）

`%USERPROFILE%\.claude\` 側で設定を変更した後、`my-claude-pull` スキルでリポジトリへ同期する。Claude Code に「設定を同期して」と伝える。内部で以下のスクリプトが実行される（自分で直接実行することも可能）：

```powershell
powershell -File .claude/skills/my-claude-pull/scripts/sync-windows.ps1   # %USERPROFILE%\.claude\ -> windows/claude/ へコピー（commit・push は行わない）
```

> `my-claude-pull` スキルはコピーのみ行う。commit・push が必要なら `git status` で差分を確認し、`git` と `gh` で行うこと。

## 移植性の仕組み

ハードコードされた絶対パス（`C:\Users\<user>\` など）を排除している：

- **hooks・skill スクリプト**: `$HOME` を直書き。シェルが実行時に展開するため変換不要。
- **settings.json**: Claude Code は settings.json 内で `$HOME` を展開しないため、repo 上は プレースホルダ `__CLAUDE_HOME__` を置く。反映時に `my-claude-push` スキルが git-bash 形式の絶対パスへ実体化し、`my-claude-pull` スキルの同期スクリプトが逆変換でプレースホルダへ戻す。
- **rules など**: ハードコードされた絶対パスを含まないため、パス変換処理は不要。

この順変換（反映時）と逆変換（同期時）は対になっている。そのため、反映と同期を繰り返してもパス表現はブレない。

## Gotchas（運用上の注意点）

- **`windows/claude/` フォルダを直接編集しない**：`my-claude-pull` スキル実行時に `%USERPROFILE%\.claude\` の内容で上書きされる。設定変更は必ず `%USERPROFILE%\.claude\` 側で行い、その後 Claude Code に「設定を同期して」と依頼するか、`sync-windows.ps1` を直接実行して同期する。

- **`my-claude-pull` スキルはコピーのみ行う**：commit・push は自動実行しない。同期後は `git status` で差分を確認し、必要なら `git` と `gh` で行うこと。実機側で削除したディレクトリはコピー元が無いと `Skip` になり、ミラー側に残る（ミラー側の削除は手動）。

- **別環境セットアップ・実機反映は `my-claude-push` スキルで行う**：展開時は `projects/`・`sessions/`・`logs/`・`settings.local.json` 等の環境固有資産に一切触れないホワイトリスト方式を守り、差分のある既存ファイルは上書き前にバックアップへ退避する。

- **`my-claude-push` は robocopy に依存しない**：Claude Code が Read/Write ツールで直接ファイル操作するため、展開先に robocopy が無くても実行できる。一方 `my-claude-pull` の `sync-windows.ps1` は robocopy を使用する。反映方向と同期方向でツールが異なる非対称設計。

- **`git status` の `M` 件数を鵜呑みにしない**：`my-claude-pull` 実行後は CRLF/LF 差分で `M` が多発することがある。実質差分は `git diff --stat` で確認する。
