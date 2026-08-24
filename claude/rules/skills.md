# スキル使用判断

ローカルスキル: tdd-gates／self-improvement-loop（詳細は各 SKILL.md）。プラグイン群は有効化済み。

- **context7 は必ず使用せよ**: ライブラリ・SDK・API の質問時（`resolve-library-id` → `query-docs` の順）。
- **frontend-design は必ず使用せよ**: UI・Web ページ・HTML 成果物・スライド等をデザイン・生成・変更するとき。
- **専用レビュー機構（`review-*`・`doc-verifier`等）が無い成果物**（設定ファイル・HTML等）: 独立サブエージェントで敵対的クロスレビュー→修正→再レビューを通せ。HTMLでブラウザ不可なら静的解析で代替せよ。
