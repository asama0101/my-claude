# CLAUDE.md — my-claude（Claude Code 設定管理リポジトリ）

## リポジトリの目的

`~/.claude/` の Claude Code 設定をバージョン管理し、**別環境（別ユーザー・別マシン）でクローンして再現**できるようにするリポジトリ。

## コマンド

設定の同期は `my-claude-pull` スキル（`.claude/skills/my-claude-pull/`）を使う。OSを判定し、Linux/macOSでは`scripts/sync-linux.sh`、Windowsでは`scripts/sync-windows.ps1`を実行して `~/.claude/`（または`%USERPROFILE%\.claude\`）の内容をミラーディレクトリへコピーのみ行う（commit・pushは行わない）。

実機への反映（逆方向の同期）は `my-claude-push` スキル（`.claude/skills/my-claude-push/`）を使う。リポジトリの `linux/claude/`・`windows/claude/` の内容を、実行環境の `$CLAUDE_HOME` へ差分確認・バックアップを経て書き込む。真っさらな別環境の初回セットアップにも使える（バックアップ対象が単に存在しないだけで、同一マシン内での反映と同じ手順で動作する）。

## 典型的な作業フロー

### A. 実機の設定を変更したとき（このマシン → リポジトリ）
1. `~/.claude/`（Windows: `%USERPROFILE%\.claude\`）を直接編集する
2. `my-claude-pull` スキルでミラー（`linux/claude/` または `windows/claude/`）へ同期する
3. 両OSのミラーに差分が出た場合のみ `my-claude-mirrors` で意図的差分か確認・整理する
4. `git status` で変更を確認し、`/pr-create` で commit・push する

### B. リポジトリの変更を実機へ反映するとき（リポジトリ → このマシン。別環境の初回セットアップも同じ手順）
1. `git pull` 等でリポジトリを最新化する
2. `my-claude-push` スキルで対応OSのミラー内容を実機 `$CLAUDE_HOME` へ反映する

## ディレクトリ構成

| パス | 内容 |
|-----|------|
| `linux/claude/` | `~/.claude/` のミラー（hooks / skills / agents / rules / assets / commands / settings.json / CLAUDE.md / statusline-command.sh） |
| `windows/claude/` | `%USERPROFILE%\.claude\` のミラー（hooks / skills / agents / rules / assets / commands / settings.json / CLAUDE.md / statusline-command.sh） |
| `.claude/skills/my-claude-pull/` | 上記2つのミラーへの同期スキル（`scripts/sync-linux.sh` / `scripts/sync-windows.ps1`）。コピーのみでcommit・pushは行わない |
| `.claude/skills/my-claude-mirrors/` | `linux/claude/` と `windows/claude/` の間の差分を検出・解消するスキル（`scripts/detect-diffs.sh` / `scripts/show-ledger.sh` / `ledger.json`）。実機には一切触れず、意図的なOS差分を台帳に記録して以後自動許容し、未記録の差分だけ対話的に解消する |
| `.claude/skills/my-claude-push/` | リポジトリのミラー内容（`linux/claude/`または`windows/claude/`）を実機の`$CLAUDE_HOME`へ反映するスキル。`my-claude-pull`の逆方向。commit・pushは行わない |

## 移植性の仕組み（パス変数化）

別環境でも動くよう、ハードコードされた絶対パスを排除している。

- **hooks・skill スクリプト**: `$HOME` を直書き（シェル/Python が実行時に展開）。`/home/<user>/` を書かない。
- **settings.json**: Claude Code は settings.json 内で `$HOME` を展開しないため、repo 上は **プレースホルダ `__CLAUDE_HOME__`** を置く。別環境セットアップ時に Claude Code が展開先の絶対パスへ実体化し、`my-claude-pull` スキルの同期スクリプトが逆変換でプレースホルダへ戻す（順変換と逆変換が対）。

## Gotchas

- **`linux/claude/`・`windows/claude/` を直接編集しない**: `my-claude-pull` スキル実行時に上書きされる。設定変更は `~/.claude/`（または`%USERPROFILE%\.claude\`）側で行い、その後 `my-claude-pull` スキルで同期する
  - 例外: `my-claude-mirrors` スキルは両ミラー間の差分を解消することが目的のスキルであり、両ミラーを直接編集してよい（実機には一切触れない）。上記の禁止は `my-claude-pull` による上書きを想定したものであり、`my-claude-mirrors` には適用されない
- **`my-claude-pull` スキルはコピーのみ行う**: 同期後の変更内容は `git status` で確認し、commit・push が必要なら `/pr-create` を使うこと
- **別環境セットアップ・実機反映は `my-claude-push` スキルで行う**（`install.sh` は廃止）: 展開時は `projects/`・`sessions/`・`logs/`・`settings.local.json` 等の環境固有資産に一切触れないホワイトリスト方式を守り、差分のある既存ファイルは上書き前にバックアップへ退避する
- **`my-claude-push` は rsync/robocopy に依存しない**: Claude Code が Read/Write ツールで直接ファイル操作するため、展開先環境に rsync/robocopy が無くても実行できる。`my-claude-pull` スキルの `sync-linux.sh` は引き続き rsync を使用する非対称設計
