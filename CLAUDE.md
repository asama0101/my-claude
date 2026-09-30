# CLAUDE.md — my-claude（Claude Code 設定管理リポジトリ）

目的・セットアップ・ディレクトリ構成は `README.md` を参照。Windows 専用。

## コマンド

- 実機 → リポジトリ: `my-claude-pull` スキル（`.claude/skills/my-claude-pull/`）。`scripts/sync-windows.ps1` が `%USERPROFILE%\.claude\` の内容を `windows/claude/` へコピーする（commit・pushは行わない）。
- リポジトリ → 実機（別環境の初回セットアップも同じ）: `my-claude-push` スキル（`.claude/skills/my-claude-push/`）。手順は `README.md` のセットアップを参照。

## 日常運用（実機の設定を変更したとき）

1. `%USERPROFILE%\.claude\` を直接編集する
2. `my-claude-pull` スキルで `windows/claude/` へ同期する
3. `git status` で変更を確認し、`git`・`gh` で作業ブランチへ commit・push して PR を作成する

## 移植性の仕組み（パス変数化）

別環境でも動くよう、ハードコードされた絶対パスを排除している。

- **hooks・skill スクリプト**: `$HOME` を直書き（シェルが実行時に展開）。ユーザー名入りの絶対パスを書かない。
- **settings.json**: Claude Code は settings.json 内で `$HOME` を展開しないため、repo 上は **プレースホルダ `__CLAUDE_HOME__`** を置く。別環境セットアップ時に `my-claude-push` が絶対パスへ実体化し、`my-claude-pull` の同期スクリプトが逆変換でプレースホルダへ戻す（順変換と逆変換が対）。

## Gotchas

- **`windows/claude/` を直接編集しない**: `my-claude-pull` 実行時に上書きされる。設定変更は `%USERPROFILE%\.claude\` 側で行い、その後 `my-claude-pull` で同期する
- **`my-claude-pull` はコピーのみ行う**: 同期後の変更は `git status` で確認し、commit・push は `git`・`gh` で行うこと
- **ディレクトリごと削除した場合だけ、ミラー側に残る**: `hooks`・`skills`・`rules` は `robocopy /MIR` で同期するため、ディレクトリ内のファイル削除はミラーへ伝播する。実機側でディレクトリ自体を削除するとコピー元が無く `Skip` になり、ミラー側のディレクトリは残るので手動で削除する
- **`skills/synced/` と `skills/grilling/` は同期しない**: `synced/` は claude.ai が自動同期する環境固有の資産、`grilling/` は第三者（mattpocock/skills, MIT）のスキルで再配布しないため。どちらも `sync-windows.ps1` で除外し `.gitignore` にも登録している
- **`my-claude-push` は環境固有資産に触れない**: `projects/`・`sessions/`・`logs/`・`settings.local.json` 等には一切触れないホワイトリスト方式で、差分のある既存ファイルは上書き前にバックアップへ退避する
- **`my-claude-push` は Read/Write ツールで直接ファイル操作する**: 展開先に robocopy が無くても実行できる
- **`my-claude-push`実行時、`$CLAUDE_HOME`へのBash書き込み（mkdir/cp/リダイレクト等）はbranch-guardにブロックされる**: mainブランチ上のBash変更系コマンドは「対象パスが全てプロジェクト外かつ`$CLAUDE_HOME`外」の場合のみ除外されるが、`$CLAUDE_HOME`自体はこの条件を満たさない。バックアップ退避・書き込みはWrite/Editツールで行うこと
- **`my-claude-pull`実行後の`git status`はCRLF/LF差分で`M`が多発することがある**: 実質差分は`git diff --stat`で確認し、`git status`の`M`件数を鵜呑みにしない。`.sh`は`.gitattributes`でLFに固定している
