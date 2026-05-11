# my-claude

Claude Code の個人設定ファイルと Python バックエンド開発テンプレートをバージョン管理するリポジトリ。
`~/.claude/` の設定を `01_setup/` に保存し、`03_python-project/` を新規プロジェクトの雛形として使う。

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `01_setup/` | Claude Code グローバル設定（hooks, skills, settings, CLAUDE.md） |
| `02_private-skills/` | プライベートカスタムスキル |
| `03_python-project/` | Python バックエンド開発テンプレート（CLAUDE.md + rules/） |
| `sync_file.sh` | `~/.claude/` → `01_setup/` への同期スクリプト（git 管理外） |

## セットアップ（更新時）

Claude Code の設定を更新した後、`01_setup/` へ同期してコミットする。

```bash
bash sync_file.sh
git add 01_setup/
git commit -m "chore(setup): Claude Code 設定を同期"
```

## 新規 Python プロジェクトの開始方法

1. `03_python-project/CLAUDE.md` を新プロジェクトの `CLAUDE.md`（または `.claude/CLAUDE.md`）にコピー
2. `03_python-project/rules/` を新プロジェクトの `.claude/rules/` にコピー
3. CLAUDE.md のプレースホルダーを実際の値に置き換える
