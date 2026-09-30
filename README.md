# my-claude

Windows 版 Claude Code のユーザー設定（`%USERPROFILE%\.claude\`）をバージョン管理し、別の Windows 環境で再現するためのリポジトリ。Windows 専用。

コンテキスト消費を抑えるため、サブエージェント・自作スキル・カスタムコマンドを持たない最小構成にしている。

## セットアップ

前提: Claude Code と Git for Windows（Git Bash）がインストールされていること。

1. このリポジトリをクローンする。
2. クローンしたディレクトリで Claude Code を起動し、`my-claude-push` スキルでの反映を依頼する（例:「my-claude-pushして」）。
3. 提示された差分一覧を確認して承認する。上書きされる既存ファイルは `%USERPROFILE%\.claude\backup\` へ退避される。
4. 実行中の設定が書き換わるため、反映後は Claude Code を再起動する。
5. `/login` で Claude Code にログインする。認証情報はリポジトリに含まれない。
6. プラグインを導入する。対象は `settings.json` の `enabledPlugins` に列挙されたプラグイン。`/plugin` でインストール状況を確認し、未導入のものは `claude plugin install <名前>@claude-plugins-official` で導入する。
7. context7（MCP）を登録する。ユーザースコープの MCP は `~/.claude.json` に保存され、リポジトリでは共有されないため、手動で登録する。

   ```
   claude mcp add --scope user --transport http context7 https://mcp.context7.com/mcp
   ```
8. `grilling` スキルを導入する。第三者（Matt Pocock 氏、MIT ライセンス）のスキルのため、このリポジトリには含めていない。[mattpocock/skills](https://github.com/mattpocock/skills) の `skills/productivity/grilling/` を、`%USERPROFILE%\.claude\skills\grilling\` へコピーする。

## ディレクトリ構成

`my-claude-push` は、`windows/claude/` の内容を `%USERPROFILE%\.claude\`（環境変数 `CLAUDE_HOME` で変更可）へ反映する。

| `windows/claude/` 内 | 内容 |
|---|---|
| `CLAUDE.md` | グローバルな行動指示 |
| `settings.json` | 権限・フック配線・プラグイン。パスは `__CLAUDE_HOME__` プレースホルダで保存され、反映時に実環境のパスへ変換される |
| `statusline-command.sh` | ステータスライン表示 |
| `hooks/` | PreToolUse フック（`branch-guard.sh`、`venv-guard.sh`）と、共通ライブラリ・テスト |
| `rules/` | フックの効果一覧（`hooks.md`） |

上記以外（`projects/`、`sessions/`、`logs/`、`settings.local.json` など環境固有の資産）には触れない。

`docs/` は過去の設計記録で、現行構成とは一致しない。反映の対象外。
