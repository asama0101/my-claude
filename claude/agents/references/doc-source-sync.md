# ソース同期（詳細リファレンス）

> doc-updater エージェント用のオンデマンド参照ファイル（エージェント定義ではない）。
> コードから生成するドキュメント（README・ガイド・API ドキュメント）を、実際のコードの状態に同期する手順。
> 人間向けドキュメントの新規整備は [doc-design.md] → [doc-writing.md]、整合確認は [doc-verify.md] を参照。

---

## 原則

- **実行可能性** — 実際に動作するセットアップ/生成コマンドを含める。
- **コードから生成** — 記載内容は手書きで捏造せず、実際のコードから生成・抽出する。

---

## 解析コマンド

**Python プロジェクト:**
```bash
pdoc --output-dir docs/api src/         # Python API ドキュメント生成
sphinx-apidoc -o docs/source src/      # Sphinx 向け API ドキュメント
python -m pytest --collect-only -q     # テスト対象の確認
ruff check . --statistics              # コード品質の統計
```

**JavaScript/TypeScript プロジェクト:**
```bash
npx madge --image graph.svg src/        # 依存関係グラフ
npx jsdoc2md src/**/*.ts                # JSDoc を抽出
```

## ドキュメント更新ワークフロー

1. **抽出** — docstring/JSDoc・README セクション・環境変数・API エンドポイントを読み取る
2. **更新** — README.md・docs/GUIDES/*.md・pyproject.toml/package.json・API ドキュメント
3. **検証** — ファイルの存在確認・リンクの動作確認・サンプルの実行・スニペットのコンパイル

## 品質チェックリスト

- [ ] 実際のコードから記載内容を生成
- [ ] すべてのファイルパスが存在することを確認
- [ ] コード例がコンパイル/実行できる
- [ ] リンクのテスト
- [ ] 鮮度タイムスタンプの更新
- [ ] 廃止された参照がない

## 更新すべき時期

**必須:** 新しい主要機能、API ルートの変更、依存関係の追加/削除、アーキテクチャの変更、セットアップ手順の変更。

**任意:** 軽微なバグ修正、外観の変更、内部リファクタリング。
