# my-claude

Claude Code のユーザーグローバル設定（`~/.claude/`）をバージョン管理し、**別環境（別ユーザー・別マシン）でクローンして再現**するためのリポジトリ。

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `claude/` | `~/.claude/` のミラー（hooks / skills / agents / settings.json / CLAUDE.md / statusline-command.sh） |
| `anzen/` | プロジェクト用バンドル（ネットワーク手順書レビュー／パラメータ自動入力）。**`sync.sh`/`install.sh` の同期対象外**。詳細は `anzen/README.md` |
| `scripts/sync.sh` | `~/.claude/` → `claude/` への同期（commit + push 自動） |
| `scripts/install.sh` | `claude/` → `~/.claude/` への展開（別環境セットアップ） |
| `docs/` | 過去の計画・仕様の記録 |

## 別環境でのセットアップ（初回）

```bash
git clone <repo-url> ~/my-claude
bash ~/my-claude/scripts/install.sh            # claude/ → ~/.claude/ へ展開
```

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
