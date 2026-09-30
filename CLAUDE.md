# CLAUDE.md — my-claude（Claude Code 設定管理リポジトリ）

## リポジトリの目的

`%USERPROFILE%\.claude\` の Claude Code 設定をバージョン管理し、**別の Windows 環境（別ユーザー・別マシン）でクローンして再現**できるようにするリポジトリ。Windows 専用で、Linux/macOS は対象外。

## コマンド

設定の同期は `my-claude-pull` スキル（`.claude/skills/my-claude-pull/`）を使う。`scripts/sync-windows.ps1` を実行して `%USERPROFILE%\.claude\` の内容を `windows/claude/` へコピーする（commit・pushは行わない）。

実機への反映（逆方向の同期）は `my-claude-push` スキル（`.claude/skills/my-claude-push/`）を使う。`windows/claude/` の内容を、実行環境の `$CLAUDE_HOME` へ差分確認・バックアップを経て書き込む。真っさらな別環境の初回セットアップにも使える（バックアップ対象が単に存在しないだけで、同一マシン内での反映と同じ手順で動作する）。

## 典型的な作業フロー

### A. 実機の設定を変更したとき（このマシン → リポジトリ）
1. `%USERPROFILE%\.claude\` を直接編集する
2. `my-claude-pull` スキルで `windows/claude/` へ同期する
3. `git status` で変更を確認し、`git`・`gh` で作業ブランチへ commit・push して PR を作成する

### B. リポジトリの変更を実機へ反映するとき（リポジトリ → このマシン。別環境の初回セットアップも同じ手順）
1. `git pull` 等でリポジトリを最新化する
2. `my-claude-push` スキルで `windows/claude/` の内容を実機 `$CLAUDE_HOME` へ反映する

## ディレクトリ構成

| パス | 内容 |
|-----|------|
| `windows/claude/` | `%USERPROFILE%\.claude\` のミラー（hooks / skills / rules / settings.json / CLAUDE.md / statusline-command.sh） |
| `.claude/skills/my-claude-pull/` | ミラーへの同期スキル（`scripts/sync-windows.ps1`）。コピーのみでcommit・pushは行わない |
| `.claude/skills/my-claude-push/` | ミラーの内容を実機の`$CLAUDE_HOME`へ反映するスキル。`my-claude-pull`の逆方向。commit・pushは行わない |

## 移植性の仕組み（パス変数化）

別環境でも動くよう、ハードコードされた絶対パスを排除している。

- **hooks・skill スクリプト**: `$HOME` を直書き（シェルが実行時に展開）。ユーザー名入りの絶対パスを書かない。
- **settings.json**: Claude Code は settings.json 内で `$HOME` を展開しないため、repo 上は **プレースホルダ `__CLAUDE_HOME__`** を置く。別環境セットアップ時に Claude Code が展開先の絶対パスへ実体化し、`my-claude-pull` スキルの同期スクリプトが逆変換でプレースホルダへ戻す（順変換と逆変換が対）。

## Gotchas

- **`windows/claude/` を直接編集しない**: `my-claude-pull` スキル実行時に上書きされる。設定変更は `%USERPROFILE%\.claude\` 側で行い、その後 `my-claude-pull` スキルで同期する
- **`my-claude-pull` スキルはコピーのみ行う**: 同期後の変更内容は `git status` で確認し、commit・push は `git`・`gh` で行うこと。実機側で削除したディレクトリは、コピー元が無いと `Skip` になり、ミラー側に残る。ミラー側の削除は手動で行う
- **別環境セットアップ・実機反映は `my-claude-push` スキルで行う**: 展開時は `projects/`・`sessions/`・`logs/`・`settings.local.json` 等の環境固有資産に一切触れないホワイトリスト方式を守り、差分のある既存ファイルは上書き前にバックアップへ退避する
- **`my-claude-push` は Claude Code が Read/Write ツールで直接ファイル操作する**: 展開先に rsync/robocopy が無くても実行できる
- **`my-claude-push`実行時、`$CLAUDE_HOME`へのBash書き込み（mkdir/cp/リダイレクト等）はbranch-guardにブロックされる**: mainブランチ上のBash変更系コマンドは「対象パスが全てプロジェクト外かつ`$CLAUDE_HOME`外」の場合のみ除外されるが、`$CLAUDE_HOME`自体はこの条件を満たさない。バックアップ退避・書き込みはWrite/Editツールで行うこと
- **`my-claude-pull`実行後の`git status`はCRLF/LF差分で`M`が多発することがある**: 実質差分は`git diff --stat`で確認し、`git status`の`M`件数を鵜呑みにしない
