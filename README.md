# my-claude

Claude Code のユーザーグローバル設定（`~/.claude/`）をバージョン管理し、**別環境（別ユーザー・別マシン）でクローンして再現**するためのリポジトリ。

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `claude/` | `~/.claude/` のミラー（hooks / skills / agents / rules / assets / settings.json / CLAUDE.md / statusline-command.sh） |
| `scripts/sync.sh` | `~/.claude/` → `claude/` への同期（commit + push 自動） |
| `scripts/install.sh` | `claude/` → `~/.claude/` への展開（別環境セットアップ） |
| `docs/` | 過去の計画・仕様の記録 |

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
