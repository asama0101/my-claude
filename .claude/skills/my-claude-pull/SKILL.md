---
name: my-claude-pull
description: %USERPROFILE%\.claude\（Windows）の設定を、このmy-claudeリポジトリのミラーディレクトリ（windows/claude/）へ同期する。ユーザーが「設定を同期して」「syncして」「claude設定をリポジトリに反映して」と言ったときや、%USERPROFILE%\.claude\配下のhooks・skills・rules・settings.json等を編集した後にリポジトリへ反映したい場面で必ず使う。commit・pushは行わない（同期のみ）。
---

# my-claude-pull

`%USERPROFILE%\.claude\`（実環境の設定）が真実の源で、リポジトリの`windows/claude/`はそのミラー。このスキルはミラーを最新化するだけで、commit・pushは行わない。反映後にコミット・PR作成が必要なら`git`と`gh`で行う。

## 実行手順

1. スクリプトを実行する（`<スキルディレクトリ>`はこのSKILL.mdが置かれているディレクトリ）。
   - `powershell -File <スキルディレクトリ>/scripts/sync-windows.ps1`
2. 出力（`Done(file): ...` / `Done(dir): ...` / `Skip: ...`）をそのままユーザーに見せ、スキップされた項目があれば理由（source側に存在しない等）を添えて報告する。
3. リポジトリのミラー側で`git status`を確認する。差分があれば「commit・pushが必要なら`git`と`gh`で行ってください」と伝えて終了する。差分が無ければ「変更なし」と報告して終了する。**このスキル自身はcommit・pushを行わない。**

## 注意

- コピー元に存在しないディレクトリ（実機側で削除済みのもの等）は`Skip`になり、ミラー側に残る。ミラー側の掃除はこのスキルの対象外で、手動で行う。
- `settings.json`は絶対パスを`__CLAUDE_HOME__`プレースホルダに変換して保存する（別環境での再現性のため）。中身を確認する際はこの変換を踏まえて読むこと。
- 実行後の`git status`はCRLF/LF差分で`M`が多発することがある。実質差分は`git diff --stat`で確認する。
