---
paths:
  - "tests/**"
---
# テスト方針

テストコード作成・CI設定時に参照する。

## TDD

新規機能は失敗するテストを先に書く（Red → Green → Refactor）。
テストなしで実装コードを書き始めない。

## テスト方針

- pytest 使用
- 外部サービス・HTTP 通信は HTTP クライアント層でモック化
- サブプロセス呼び出し（`subprocess`, `docker run` 等）はサブプロセス層でモック化
- 外部応答サンプルは `tests/fixtures/` 配下に保存
- 自動化（CI）: Unit / Integration / E2E / Smoke / Load・Stress（例: Locust）
- 手動: Scenario（Acceptance）。手順書は `docs/testing/scenario/` に配置

## テスト粒度と命名

- テスト関数名は `test_<状況>_<期待結果>` 形式: `test_create_order_returns_201`
- 1テスト関数で1つのアサーション（複数を検証する場合は `pytest.approx` 等でまとめる）
- テストは Arrange（準備）→ Act（実行）→ Assert（検証）の3段階で書く

## CI 種別と定義

| 種別 | 定義 | 実行タイミング |
|---|---|---|
| Unit | 外部依存を排除した単一関数・クラスのテスト | PR ごと |
| Integration | 実 DB・実キューを使った複数コンポーネントの結合テスト | PR ごと |
| E2E | 実際の HTTP クライアントからエンドポイントを叩く | PR ごと |
| Smoke | 本番/ステージングで最小限の疎通確認 | デプロイ後 |
| Load/Stress | Locust 等で同時接続・スループットを計測 | リリース前 |
