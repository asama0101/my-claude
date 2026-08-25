# windows/

Windows 版 Claude Code 設定の置き場所。`linux/` と対称的な構成（`claude/` ミラー + 同期スクリプト）。

## 構成

| パス | 内容 |
|-----|------|
| `windows/claude/` | `%USERPROFILE%\.claude\` のミラー（hooks / skills / agents / rules / assets / settings.json / CLAUDE.md / statusline-command.sh） |
| `windows/sync.ps1` | `%USERPROFILE%\.claude\` → `windows/claude/` 同期スクリプト（commit + push 自動、PowerShell 版） |

## 同期方式

- ファイル: `Copy-Item` で `windows/claude/` 直下へコピー（上書き）
- ディレクトリ: `robocopy /MIR` で完全同期（source に無いファイルはミラーからも削除）
- `settings.json`: `$CLAUDE_HOME` の絶対パスを git-bash 形式（`/c/Users/...`）に変換した上でプレースホルダ `__CLAUDE_HOME__` へ逆変換して保存（linux 側と同じ仕組み。詳細はリポジトリ直下 `CLAUDE.md` を参照）

別環境セットアップ（repo → `%USERPROFILE%\.claude` への展開）は専用スクリプトを持たない。Claude Code に `windows/claude/` の内容を展開するよう依頼する運用とする。
