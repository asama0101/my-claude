---
name: sync-config
description: ~/.claude/（Linux/macOS）または %USERPROFILE%\.claude\（Windows）の設定を、このmy-claudeリポジトリのミラーディレクトリ（linux/claude/ または windows/claude/）へ同期する。ユーザーが「設定を同期して」「syncして」「claude設定をリポジトリに反映して」と言ったときや、~/.claude/配下のhooks・skills・agents・rules・settings.json等を編集した後にリポジトリへ反映したい場面で必ず使う。commit・pushは行わない（同期のみ）。
---

# sync-config

`~/.claude/`（実環境の設定）が真実の源で、リポジトリの`linux/claude/`・`windows/claude/`はそのミラー。このスキルはミラーを最新化するだけで、commit・pushは行わない。反映後にコミット・PR作成が必要なら`/pr-create`を使う。

## 実行手順

1. 実行環境のOSを判定する。
   - `uname`が使えればLinux/macOS。
   - PowerShell環境（`$IsWindows`が真、またはOS自体がWindows）ならWindows。
2. 対応するスクリプトを実行する（`<スキルディレクトリ>`はこのSKILL.mdが置かれているディレクトリ）。
   - Linux/macOS: `bash <スキルディレクトリ>/scripts/sync-linux.sh`
   - Windows: `powershell -File <スキルディレクトリ>/scripts/sync-windows.ps1`
3. 出力（`Done(file): ...` / `Done(dir): ...` / `Skip: ...`）をそのままユーザーに見せ、スキップされた項目があれば理由（source側に存在しない等）を添えて報告する。
4. リポジトリのミラー側で`git status`を確認する。差分があれば「commit・pushが必要なら`/pr-create`を使ってください」と伝えて終了する。差分が無ければ「変更なし」と報告して終了する。**このスキル自身はcommit・pushを行わない。**

## 注意

- 空ディレクトリ（例: `assets`が空の場合）はコピー元自体が存在しないと`Skip`になる。ミラー側に残った空ディレクトリの掃除はこのスキルの対象外。
- `settings.json`は絶対パスを`__CLAUDE_HOME__`プレースホルダに変換して保存する（別環境での再現性のため）。中身を確認する際はこの変換を踏まえて読むこと。
- Windows版はLinux実機が無い環境では動作確認ができない。変更時はコメントで理由を明記し、次にWindows機で実行されたときに検証されることを前提にする。
