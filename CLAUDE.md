# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 目的とスコープ

このリポジトリは、Claude Code の個人設定を一元管理する。

管理対象:
- ユーザレベルの `CLAUDE.md`
- `settings.json`
- 汎用的なサブエージェント定義
- ステータスラインの設定

管理対象外: スキルとプラグインの本体。追加しない。自作以外のスキル・プラグインは、名前と入手元だけを `skills-manifest.md` に記録する。

## ディレクトリ構成と CLAUDE.md の役割分担

- ルートの `CLAUDE.md`（このファイル）は、このリポジトリで作業するための指示。`~/.claude\` には反映しない。
- `user\` は `~/.claude\` に反映する設定の実体。`user\CLAUDE.md` がユーザレベルの指示、`user\settings.json`、`user\statusline.py` などを置く。
- ユーザレベルの指示を変えるときは `user\CLAUDE.md` を編集する。ルートの `CLAUDE.md` に書かない。

## 配置方式

`user\` 内のファイルを、コピーで `C:\Users\<ユーザー名>\.claude\` に反映する。シンボリックリンクは使わない。

- 理由: 公式ドキュメントに、`~/.claude\` 直下のファイルをリンクにした場合の動作（読み込み、`settings.json` の書き込み）の記載がなく、動作が保証されないため。
- 反映は `sync.ps1` で行う（`user\` → `~\.claude\` の一方向）。`pwsh .\sync.ps1`
  - 内容が同一のファイルは何もしない。
  - 反映先のほうが新しいファイルはスキップして警告する。`-Force` で上書きする。
- 常に `user\` を編集して、`sync.ps1` を実行する。`~\.claude\` 側を直接編集しない。
- `/model` や `/config` などで Claude Code が `~\.claude\settings.json` を書き換えた場合、その変更は `user\settings.json` に自動では戻らない。`sync.ps1` が警告したら、差分を確認して `user\` に取り込む。
- 対象環境は Windows のみ。`sync.ps1` は macOS や Linux では動かない。
- `user\` 内のテキストファイルでは、環境依存のパスをプレースホルダで書く。`sync.ps1` が反映時に、実行環境の値へ置換する。
  - `{{HOME}}`: `C:/Users/<ユーザ名>`（スラッシュ区切り）
  - `{{HOME_JSON}}`: `C:\\Users\\<ユーザ名>`（JSON 文字列内用）
  - 差分の判定は、置換後の内容で比べる。`~\.claude\` に反映される内容は置換後の絶対パスになる。
- `settings.json` の `statusLine.command` は `py {{HOME}}/.claude/statusline.py`。反映先に `statusline.py` と Python が必要。
  - `python` コマンドは使わない。この環境では Microsoft Store のエイリアス（`WindowsApps\python.exe` のスタブ）が先に解決され、スクリプトが実行されない（2026-10-10 確認）。`py` ランチャー経由なら実行できる。
  - `~/.claude/statusline.py` の形は未検証。直前に `python` と組み合わせて表示されなかったが、原因は `~` ではなく `python` だった可能性が高い。
- 自作の `guild`（プラグイン兼ローカルマーケットプレイス）は、`settings.json` に含めない。`extraKnownMarketplaces` と `enabledPlugins` から外してある。

## 秘密情報

- `settings.local.json` や認証情報ファイルは管理対象外にして、`.gitignore` で除外する。
- `settings.json` に環境変数を書く場合は、トークンやキーを含めない。

## 現状

ビルドやテストのコマンドはない。コマンドは `sync.ps1` のみ。
