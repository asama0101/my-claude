---
paths:
  - "tests/**"
---
# テスト方針

テストコード作成・CI設定時に参照する。

## テスト方針

- pytest 使用
- 外部サービス・HTTP 通信は HTTP クライアント層でモック化
- サブプロセス呼び出し（`subprocess`, `docker run` 等）はサブプロセス層でモック化
- 外部応答サンプルは tests/fixtures/ 配下に保存
- 自動化（CI）: Unit / Integration / E2E / Smoke / Load・Stress（例: Locust）
- 手動: Scenario（Acceptance）。手順書は docs/scenario/ に配置
