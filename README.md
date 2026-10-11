# my-claude

Claude Code の個人設定を一元管理するリポジトリ。`user\` の内容を `C:\Users\<ユーザ名>\.claude\` に反映する（Windows のみ）。

作業時の規則は [CLAUDE.md](CLAUDE.md) を参照。

## 構成

| 場所 | 内容 | 反映先 |
|---|---|---|
| `user\CLAUDE.md` | ユーザレベルの指示 | `~\.claude\CLAUDE.md` |
| `user\settings.json` | 設定（権限、プラグインの有効化、Hooks、ステータスライン） | `~\.claude\settings.json` |
| `user\statusline.py` | ステータスライン | `~\.claude\statusline.py` |
| `user\hooks\` | Hooks のスクリプト | `~\.claude\hooks\` |
| `user\mcp-servers.json` | MCP サーバー定義 | `~\.claude.json`（`claude mcp add-json` で登録） |
| `skills-manifest.md` | 自作以外のスキル・プラグインの入手元の記録 | 反映しない |
| `docs\` | SPEC | 反映しない |

## 反映方法

```
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync.ps1
```

- `user\` から `~\.claude\` への一方向のコピー。`user\` を編集して実行する。`~\.claude\` 側は直接編集しない。
- 反映先のほうが新しいファイルはスキップして警告する。`-Force` で上書きする。
- `{{HOME}}` などのプレースホルダは、反映時に実行環境のパスへ置換される。

## プラグイン

`user\settings.json` の `enabledPlugins` で有効にしている。すべて `claude-plugins-official` から導入している。

| プラグイン | 用途 |
|---|---|
| skill-creator | スキルの作成・改善・評価 |
| frontend-design | UI のデザイン |
| superpowers | 開発ワークフローのスキル群（ブレインストーミング、デバッグ、TDD など） |
| code-review | コードレビュー |
| claude-md-management | CLAUDE.md の監査・更新 |

導入元と手順は [skills-manifest.md](skills-manifest.md) を参照。プラグインの本体はこのリポジトリで管理しない。

## スキル

| スキル | 配置先 | 管理 |
|---|---|---|
| grilling | `~\.claude\skills\grilling` | 手動コピー（入手元は [skills-manifest.md](skills-manifest.md)） |
| roundtable | `~\.claude\skills\roundtable` | 自作。このリポジトリでは管理しない |
| synced | `~\.claude\skills\synced` | Claude Code が自動で管理する |

## MCP サーバー

`user\mcp-servers.json` に定義し、`sync.ps1` がユーザースコープに登録する。同名で内容が違うサーバーは警告してスキップし（`-Force` で上書き）、定義にないサーバーは触らない。

| サーバー | 種類 | 内容 |
|---|---|---|
| playwright | stdio | `npx @playwright/mcp@latest`（Chrome。ファイルへのアクセス制限を解除し、出力先は `~\.playwright-mcp`） |

トークンが必要なサーバーは定義に書かず、手動で `claude mcp add` する。

## Hooks

`user\settings.json` の `hooks` に定義し、スクリプトは `user\hooks\` に置く。コマンドは `py` 経由で実行する（`python` は Microsoft Store のスタブに解決されて動かない）。

| イベント | 対象 | 動作 |
|---|---|---|
| PostToolUse | `Edit\|Write` | 編集したファイルを、セッションごとに一時ファイルへ記録する |
| Stop | すべて | プロジェクト直下に README.md があり、README を更新せずにソース／設定ファイルを編集していれば、1回だけ block して更新要否の確認を促す |
| Stop | すべて | Git リポジトリに未コミットの変更があれば、`systemMessage` で件数とファイル（最大 10 件、`git status --porcelain` の形式）を警告する（block しない） |
| UserPromptSubmit | すべて | 応答の開始時刻を、セッションごとに一時ファイルへ記録する |
| Stop | すべて | 開始から 30 秒以上かかっていれば、トースト通知と音で完了を知らせる |
| Notification | すべて | 許可待ち（`permission_prompt`）と入力待ち（`elicitation_dialog`）のとき、トースト通知と音で知らせる |

- スクリプト: `user\hooks\readme_guard.py`（`record` と `check`）。仕様は [docs\readme-update-hook-spec.md](docs/readme-update-hook-spec.md)。
- 対象外の編集: `.md` などの文書、docs・テスト、ロックファイル。プロジェクト外のファイル。
- 対象ファイルの編集後に README を編集すると、確認済みとして扱う。block 後に続けて応答を終えようとしても、再度は block しない。
- 一時ファイルは `%TEMP%\claude-readme-guard\` に置き、7 日で削除する。
- 未コミットの警告: `user\hooks\uncommitted_warn.py`。Stop は応答のたびに走るため、同じ変更内容では同じセッション中に1回しか警告しない（状態は `%TEMP%\claude-commit-warn\` に置き、7 日で削除する）。
- 通知: `user\hooks\notify.py`（`start`・`done`・`attention`）と `notify.ps1`。しきい値は `notify.py` の `THRESHOLD_SEC`。サブエージェントの完了（SubagentStop）には hook を付けないので通知しない。状態は `%TEMP%\claude-notify\` に置き、7 日で削除する。

## 秘密情報

`settings.local.json` や認証情報ファイルは管理対象外で、`.gitignore` で除外している。`settings.json` や MCP 定義にトークンやキーを書かない。
