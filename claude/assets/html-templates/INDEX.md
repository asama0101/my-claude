# HTML テンプレート・ライブラリ カタログ

過去に作成した HTML デザインの流用元。新しい HTML 成果物を作るとき、doc-updater はまずこのカタログを見て流用できるテンプレがあるか判断する（判断フローは `~/.claude/agents/references/doc-html.md`）。

- **登録**: `html-template-import` スキルが既存 HTML をこのディレクトリへコピーし、下表に1行追記する（手作業で編集しない）。
- **ファイル名規約**: `<内容>-<トーン>.html`（例 `report-dark.html`・`topology-light.html`）
- **流用**: 該当 `.html` を Read し、構造・CSS を土台に内容を差し替える（frontend-design 不要・Skill 非依存で完結）。

## カタログ

| name | 特徴（トーン・レイアウト種別） | 用途 | path |
|------|------------------------------|------|------|
| report-light | light・report（和風監査台帳）。明朝体見出し＋「第一条」縦ラベル＋朱の検印スタンプ。カードグリッド／スクロール表／2枚組の凡例つき SVG 関係図／縦ライン式タイムライン＋各段アコーディオン（details）／末尾に用語集（dl・2カラム） | 構造監査・設計解説・多章立ての長文レポート | `report-light.html` |
