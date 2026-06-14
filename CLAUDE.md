# CLAUDE.md — my-claude（Claude Code 設定管理リポジトリ）

## リポジトリの目的

`~/.claude/` の Claude Code 設定をバージョン管理し、**別環境（別ユーザー・別マシン）でクローンして再現**できるようにするリポジトリ。

## コマンド

```bash
bash scripts/sync.sh      # ~/.claude/ → claude/ へ同期（commit + push 自動）
bash scripts/install.sh   # claude/ → ~/.claude/ へ展開（別環境セットアップ用）
```

## ディレクトリ構成

| パス | 内容 |
|-----|------|
| `claude/` | `~/.claude/` のミラー（hooks / skills / agents / settings.json / CLAUDE.md / statusline-command.sh） |
| `anzen/` | プロジェクト用バンドル（ネットワーク手順書レビュー／パラメータ自動入力スキル `anzen` ＋ `ops-*` エージェント）。**`sync.sh`/`install.sh` の同期対象外**。詳細は `anzen/README.md` |
| `scripts/sync.sh` | `~/.claude/` → `claude/` 同期スクリプト（commit + push 自動） |
| `scripts/install.sh` | `claude/` → `~/.claude/` 展開スクリプト（別環境セットアップ） |
| `docs/` | 過去の計画・仕様の記録 |

## 移植性の仕組み（パス変数化）

別環境でも動くよう、ハードコードされた絶対パスを排除している。

- **hooks・skill スクリプト**: `$HOME` を直書き（シェル/Python が実行時に展開）。`/home/<user>/` を書かない。
- **settings.json**: Claude Code は settings.json 内で `$HOME` を展開しないため、repo 上は **プレースホルダ `__CLAUDE_HOME__`** を置く。`install.sh` が展開先の絶対パスへ実体化し、`sync.sh` が逆変換でプレースホルダへ戻す（順変換と逆変換が対）。

## Gotchas

- **`claude/` を直接編集しない**: `sync.sh` で上書きされる。設定変更は `~/.claude/` 側で行い、その後 `scripts/sync.sh` で同期する
- **`settings.json` に絶対パスを書かない**: repo 側はプレースホルダ `__CLAUDE_HOME__`。`install.sh`/`sync.sh` が変換する
- **hooks・skill のパスは `$HOME` 直書き**: `/home/<user>/` を書かない
- **`scripts/sync.sh` は commit + push まで自動実行する**: 実行前に余計な差分がないか確認すること
- **install.sh は環境固有資産に触れない**: `projects/`・`sessions/`・`logs/`・`settings.local.json` 等は展開対象外（ホワイトリスト方式）。既存ファイルは `~/.claude/backups/` へ退避してから上書き
- **venv-guard.sh の誤検知**: bash コマンド内に `pip install` が文字列として含まれると誤ブロックされる場合がある（例: `grep "pip install" file`）。回避策は Read ツールで読む
- **`anzen/` は同期対象外のプロジェクト資産**: `claude/` ミラーには含めない。利用するネットワーク作業プロジェクトの `.claude/` へコピーして使う（導入手順は `anzen/README.md`）
