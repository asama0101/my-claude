# CLAUDE.md — my-claude（Claude Code 設定管理リポジトリ）

## リポジトリの目的

`~/.claude/` の Claude Code 設定をバージョン管理し、**別環境（別ユーザー・別マシン）でクローンして再現**できるようにするリポジトリ。

## コマンド

```bash
bash linux/sync.sh      # ~/.claude/ → linux/claude/ へ同期（commit + push 自動）
```

```powershell
.\windows\sync.ps1      # %USERPROFILE%\.claude\ → windows/claude/ へ同期（commit + push 自動）
```

別環境セットアップは専用スクリプトを持たない。Claude Code に `linux/claude/` の内容を `~/.claude/` へ展開するよう依頼する運用とする。

## ディレクトリ構成

| パス | 内容 |
|-----|------|
| `linux/claude/` | `~/.claude/` のミラー（hooks / skills / agents / rules / assets / settings.json / CLAUDE.md / statusline-command.sh） |
| `linux/sync.sh` | `~/.claude/` → `linux/claude/` 同期スクリプト（commit + push 自動） |
| `windows/claude/` | `%USERPROFILE%\.claude\` のミラー（hooks / skills / agents / rules / assets / settings.json / CLAUDE.md / statusline-command.sh） |
| `windows/sync.ps1` | `%USERPROFILE%\.claude\` → `windows/claude/` 同期スクリプト（commit + push 自動、PowerShell 版） |

## 移植性の仕組み（パス変数化）

別環境でも動くよう、ハードコードされた絶対パスを排除している。

- **hooks・skill スクリプト**: `$HOME` を直書き（シェル/Python が実行時に展開）。`/home/<user>/` を書かない。
- **settings.json**: Claude Code は settings.json 内で `$HOME` を展開しないため、repo 上は **プレースホルダ `__CLAUDE_HOME__`** を置く。別環境セットアップ時に Claude Code が展開先の絶対パスへ実体化し、`sync.sh` が逆変換でプレースホルダへ戻す（順変換と逆変換が対）。

## Gotchas

- **`linux/claude/` を直接編集しない**: `sync.sh` で上書きされる。設定変更は `~/.claude/` 側で行い、その後 `linux/sync.sh` で同期する
- **`linux/sync.sh` は commit + push まで自動実行する**: 実行前に余計な差分がないか確認すること
- **別環境セットアップは Claude Code への依頼で行う**（`install.sh` は廃止）: 展開時は `projects/`・`sessions/`・`logs/`・`settings.local.json` 等の環境固有資産に一切触れないホワイトリスト方式を守り、差分のある既存ファイルは上書き前にバックアップへ退避する
- **展開時は rsync に依存しない**: Claude Code が Read/Write ツールで直接ファイル操作するため、展開先環境に rsync が無くても実行できる。sync.sh は引き続き rsync を使用する非対称設計