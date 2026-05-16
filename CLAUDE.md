# CLAUDE.md — my-claude（Claude Code 設定管理リポジトリ）

## リポジトリの目的

`~/.claude/` の Claude Code 設定をバージョン管理し、Python バックエンド開発テンプレートを保管するリポジトリ。

## コマンド

```bash
bash sync_file.sh   # ~/.claude/ → 01_setup/ へ同期して git push（commit まで自動実行）
```

## ディレクトリ構成

| パス | 内容 |
|-----|------|
| `01_setup/` | `~/.claude/` のミラー（hooks / skills / agents / rules / settings.json / CLAUDE.md） |
| `02_private-skills/` | プライベートカスタムスキル（superpowers プラグイン外） |
| `03_python-project/` | Python バックエンド開発テンプレート（CLAUDE.md + rules/） |
| `sync_file.sh` | 同期スクリプト |

## Gotchas

- **`01_setup/` を直接編集しない**: `sync_file.sh` で上書きされる。設定変更は `~/.claude/` 側で行い、その後 `sync_file.sh` で同期する
- **`sync_file.sh` は commit + push まで自動実行する**: 実行前に余計な差分がないか確認すること
- **新規 Python プロジェクトへの適用**: `03_python-project/CLAUDE.md` と `rules/` を新プロジェクトにコピーし、プレースホルダーを置き換える
- **venv-guard.sh の誤検知**: bash コマンド内に `pip install` が文字列として含まれると誤ブロックされる場合がある（例: `grep "pip install" file`）。回避策は Read ツールで読む
