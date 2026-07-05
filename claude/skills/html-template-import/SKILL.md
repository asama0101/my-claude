---
name: html-template-import
description: |
  既存の HTML ドキュメントを流用元ライブラリ（~/.claude/assets/html-templates/）へ取り込む。HTML を解析してトーン・レイアウト種別を要約し、規約名でコピーし、カタログ INDEX.md に1行登録する。

  以下のような発言・状況で起動すること:「このHTMLをテンプレとして保存」「既存のHTMLを流用元に取り込んで」「html-template-import」「作った HTML を再利用できるように登録」。取り込み対象の HTML ファイルパスを伴って呼ばれる。
---

# HTML テンプレート取り込み

過去に作成した HTML デザインを流用元ライブラリに登録し、次回以降 doc-updater が構造・CSS を土台に再利用できるようにする。ライブラリの場所とカタログ：

- 保存先: `~/.claude/assets/html-templates/`
- カタログ（単一ソース）: `~/.claude/assets/html-templates/INDEX.md`
- 判断フロー・流用側の使い方: `~/.claude/agents/references/doc-html.md`

## 手順

1. **対象を受け取る**: 取り込む既存 HTML のファイルパスを確認する（指定がなければ聞く）。

2. **解析する**: HTML を Read し、次を要約する。
   - **トーン**: dark / light（背景・配色から判断）
   - **レイアウト種別**: report / card / topology / slide / dashboard 等
   - **主要な構造・CSS の特徴**: 再利用価値のある骨格（グリッド・カード・ヘッダ・カラーパレット等）を1〜2行で

3. **正規化名を決める**: ファイル名規約 `<内容>-<トーン>.html`（例 `report-dark.html`）。`INDEX.md` の既存エントリと衝突する場合は末尾に連番（`report-dark-2.html`）。

4. **コピーする**: `~/.claude/assets/html-templates/<正規化名>.html` へ**そのままコピー**する（内容は原則いじらない。プロジェクト固有の中身が残るが、流用時に doc-updater が骨格＋CSS だけを抽出するため問題ない）。
   - 汎用スケルトンへ一般化してから保存したい場合のみ、コピー前に固有コンテンツをプレースホルダへ置換する（既定はしない）。

5. **カタログに登録する**: `INDEX.md` の表に `name / 特徴（トーン・レイアウト種別）/ 用途 / path` を1行追記する。seed のプレースホルダ行（「まだテンプレはありません」）が残っていれば置き換える。

6. **報告する**: 登録した name・特徴・path を1行で返す。

## 注意

- ライブラリは `~/.claude/assets/` 配下で、`sync.sh`/`install.sh` の同期対象（全環境へ配布される）。実ファイルの source of truth は `~/.claude/` 側。`claude/` ミラーは直接編集しない。
- 取り込み後、設定を他環境へ反映するには `scripts/sync.sh` の実行が必要（push を伴うためユーザーに依頼する）。
