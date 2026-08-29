# CLAUDE.md — my-claude（Claude Code 設定管理リポジトリ）

## リポジトリの目的

`~/.claude/` の Claude Code 設定をバージョン管理し、**別環境（別ユーザー・別マシン）でクローンして再現**できるようにするリポジトリ。

## コマンド

設定の同期は `sync-config` スキル（`.claude/skills/sync-config/`）を使う。OSを判定し、Linux/macOSでは`scripts/sync-linux.sh`、Windowsでは`scripts/sync-windows.ps1`を実行して `~/.claude/`（または`%USERPROFILE%\.claude\`）の内容をミラーディレクトリへコピーのみ行う（commit・pushは行わない）。

別環境セットアップは専用スクリプトを持たない。Claude Code に `linux/claude/` の内容を `~/.claude/` へ展開するよう依頼する運用とする。

## ディレクトリ構成

| パス | 内容 |
|-----|------|
| `linux/claude/` | `~/.claude/` のミラー（hooks / skills / agents / rules / assets / commands / settings.json / CLAUDE.md / statusline-command.sh） |
| `windows/claude/` | `%USERPROFILE%\.claude\` のミラー（hooks / skills / agents / rules / assets / commands / settings.json / CLAUDE.md / statusline-command.sh） |
| `.claude/skills/sync-config/` | 上記2つのミラーへの同期スキル（`scripts/sync-linux.sh` / `scripts/sync-windows.ps1`）。コピーのみでcommit・pushは行わない |

## 移植性の仕組み（パス変数化）

別環境でも動くよう、ハードコードされた絶対パスを排除している。

- **hooks・skill スクリプト**: `$HOME` を直書き（シェル/Python が実行時に展開）。`/home/<user>/` を書かない。
- **settings.json**: Claude Code は settings.json 内で `$HOME` を展開しないため、repo 上は **プレースホルダ `__CLAUDE_HOME__`** を置く。別環境セットアップ時に Claude Code が展開先の絶対パスへ実体化し、`sync-config` スキルの同期スクリプトが逆変換でプレースホルダへ戻す（順変換と逆変換が対）。

## Gotchas

- **`linux/claude/`・`windows/claude/` を直接編集しない**: `sync-config` スキル実行時に上書きされる。設定変更は `~/.claude/`（または`%USERPROFILE%\.claude\`）側で行い、その後 `sync-config` スキルで同期する
- **`sync-config` スキルはコピーのみ行う**: 同期後の変更内容は `git status` で確認し、commit・push が必要なら `/pr-create` を使うこと
- **別環境セットアップは Claude Code への依頼で行う**（`install.sh` は廃止）: 展開時は `projects/`・`sessions/`・`logs/`・`settings.local.json` 等の環境固有資産に一切触れないホワイトリスト方式を守り、差分のある既存ファイルは上書き前にバックアップへ退避する
- **展開時は rsync に依存しない**: Claude Code が Read/Write ツールで直接ファイル操作するため、展開先環境に rsync が無くても実行できる。`sync-config` スキルの `sync-linux.sh` は引き続き rsync を使用する非対称設計