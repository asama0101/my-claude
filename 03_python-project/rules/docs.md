---
paths:
  - "docs/**"
  - "**/*.html"
---
# ドキュメント作成ルール

ドキュメント作成・設計レビュー時に参照する。

## ドキュメント形式

`docs/` 配下は HTML。外部仕様書（`docs/spec.md` 等）のみ Markdown。`.claude/` は Markdown（本ガイドライン対象外）。

新規ドキュメント作成時は `docs/templates/base.html` をコピーして使用する。
処理フロー設計書は `docs/templates/flow.html` をコピーして使用する。
Mermaid（`mermaid.min.js`）は `docs/assets/mermaid.min.js` にローカル保存する（CDN 直参照禁止）。
インストール: `curl -o docs/assets/mermaid.min.js https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js`

## 作成の指針

- What だけでなく Why（採用理由・却下した代替案）を書く
- 用語集を `docs/glossary.html` に集約し各ドキュメントから参照する

> レビュー時のチェック観点（対象読者の明記・専門用語の定義・前フェーズへのトレース等）は `.claude/rules/design-review.md` を参照する。

## ドキュメント更新・廃止

### 更新タイミング

- 機能追加・変更・削除 PR には、対応するドキュメント更新を同梱する（後回し禁止）
- 実装中に仕様が変わった場合は、コードをマージする前に `docs/` を更新する
- 更新対象の判断基準: 変更が外部 I/F・データモデル・セキュリティ要件・処理フローに影響する場合は必ず更新する

### 廃止・削除

廃止されたドキュメントはすぐに削除せず、以下の手順を踏む:

1. ファイル先頭の `<header>` 内に廃止バナーを追加する:
   ```html
   <p class="deprecated">【廃止】このドキュメントは廃止されました。後継: <a href="./新ドキュメント.html">新ドキュメント名</a></p>
   ```
2. 後継ドキュメントが確定し、参照元のリンクをすべて更新してから削除する
3. 削除は単独コミットとし、コミットメッセージに廃止理由を記載する

## プロジェクトドキュメント

全ドキュメント共通の必須セクション: 対象読者・前提知識 / 本ドキュメントの目的 / 関連ドキュメントへのリンク / 改訂履歴

| ドキュメント | 役割 | 配置先 | タイミング |
|---|---|---|---|
| 要求整理書 | システムの目的・背景・スコープ・ステークホルダー | docs/requirements/01_overview.html | 要求整理 |
| 用語集 | 専門用語・略語の定義 | docs/glossary.html | 要求整理〜要件定義 |
| 要件定義書 | 機能要件（FR-xxx）・非機能要件 | docs/requirements/*.html | 要件定義 |
| アーキテクチャ設計書 | コンポーネント構成・責任分界・要件トレース | docs/design/architecture.html | 基本設計 |
| データモデル設計書 | テーブル定義・ER図・制約・インデックス | docs/design/data_model.html | 基本設計 |
| セキュリティ設計書 | 認証・認可・暗号化・監査ログ設計 | docs/design/security.html | 基本設計 |
| 環境構成書 | 開発/ステージング/本番の構成・Docker・ネットワーク | docs/design/infrastructure.html | 基本設計 |
| 監視・アラート設計書 | 監視メトリクス・アラート条件・通知先 | docs/design/monitoring.html | 基本設計 |
| 外部仕様書 | 外部 I/F の詳細仕様 | docs/spec.md | 基本設計 |
| テスト計画書 | テスト範囲・合格基準（性能しきい値含む）・スケジュール | docs/testing/plan.html | 基本設計完了時 |
| 内部 API 設計書 | エンドポイント・リクエスト/レスポンス・認証 | docs/design/api.html | 詳細設計 |
| エラーコード定義書 | エラーコード・メッセージ・HTTP ステータス対応表 | docs/design/error_codes.html | 詳細設計 |
| 処理フロー設計 | 機能ごとの処理フロー図 | docs/design/flows/*.html | 詳細設計 |
| バッチ処理設計書（任意） | バッチ処理のフロー・スケジュール・エラー処理 | docs/design/batch.html | 詳細設計 |
| テストケース一覧 | 機能別テストケース・合否基準 | docs/testing/cases.html | 詳細設計〜実装 |
| シナリオテスト手順書 | 受け入れテストの手動手順 | docs/testing/scenario/*.html | 詳細設計〜実装 |
| コードの解説書（任意） | モジュール構成・主要クラスの役割・実装上の判断根拠 | docs/design/code_guide.html | 実装 |
| テスト結果報告書 | テスト実施結果・リリース判定の根拠 | docs/testing/report.html | テスト完了時 |
| デプロイ手順書 | リリース手順・ロールバック手順・ダウンタイム見積もり | docs/operations/deploy.html | リリース・運用 |
| 運用手順書 | 構築・日常運用・障害対応・バックアップ・DBマイグレーション | docs/operations/*.html | リリース・運用 |
| CHANGELOG | リリースごとの変更内容・バージョン履歴 | CHANGELOG | リリース |
| ADR | 設計判断の記録 | docs/design/decisions/*.html | 全フェーズ |

### ADR（アーキテクチャ決定記録）

重要な設計判断を `docs/design/decisions/ADR-NNN-<タイトル>.html` に記録する。
番号 NNN は連番（001, 002, …）。

**必須セクション:**

| セクション | 内容 |
|---|---|
| ステータス | `Proposed` / `Accepted` / `Deprecated` / `Superseded by ADR-NNN` のいずれか |
| コンテキスト | この決定が必要になった背景・制約・問題 |
| 決定 | 何を採用したか（1文で明言する） |
| 影響 | この決定がもたらすトレードオフ・副作用 |
| 代替案 | 検討したが採用しなかった案と却下理由 |

ステータスが `Superseded` の場合、後継 ADR へのリンクを本文先頭に置く。

### CHANGELOG

[Keep a Changelog](https://keepachangelog.com/ja/) 形式を採用する。
バージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従う。

**セクション構造:**

```
## [Unreleased]
### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [1.0.0] - YYYY-MM-DD
### Added
- 初回リリース
```

**ルール:**
- リリース前の変更はすべて `[Unreleased]` に追記する
- リリース時に `[Unreleased]` を `[x.y.z] - YYYY-MM-DD` に変更し、新しい `[Unreleased]` セクションを追加する
- 各変更は動詞（過去形）で始める: 「〇〇を追加した」「〇〇を修正した」
- Breaking Change は `### Changed` に `**破壊的変更:**` プレフィックスを付ける

## 図示・視覚化ガイドライン

Mermaid を基準とし、表現困難な場合のみ draw.io（`.drawio.svg` 形式）を使用する。

### Mermaid で使える図種

`flowchart` / `sequenceDiagram`（`par` で並列）/ `stateDiagram-v2` / `classDiagram` / `erDiagram` / `gantt`

### 図作成の注意

- 15要素超は分割する
- タイトル・凡例・読み取りポイントを必ず添える
- Mermaid コードブロックには ` ```mermaid ` を付ける

## 処理フロー設計

詳細設計フェーズで機能ごとに `docs/design/flows/[機能名].html` を作成する。

### 3階層構成

| 粒度 | 配置 | 内容 |
|---|---|---|
| システム全体 | アーキテクチャ書（基本設計） | コンポーネント間のやりとり |
| 機能単位の概略（必須） | `flows/[機能名].html` の §1 | 入力・出力と主要分岐を1枚で俯瞰 |
| サブ処理単位（複雑な処理に必須） | §2 以降 | リトライ・並列・状態遷移を詳細化 |

新規作成時は `docs/templates/flow.html` を使用する。

### フロー図の必須要素

タイトル / 入力・出力 / 分岐条件 / 外部呼び出し / エラーハンドリング / 凡例 / 対応コード位置（ファイル・関数名）

各節には「§1 のどのステップを詳細化するか」を明記する。

### 図の種類

| 内容 | 図種 |
|---|---|
| 単一機能の流れ | `flowchart` |
| コンポーネント間のやりとり | `sequenceDiagram` |
| 状態遷移 | `stateDiagram-v2` |
| 並列処理 | `sequenceDiagram` の `par` |
| 複雑な分岐・スイムレーン | `subgraph` または draw.io |

## ドキュメント記法

### HTML（docs/）

- 改行: `<br>`
- 表のセル内改行: `<br>`、4列超または長文セルは箇条書きに変更

### Markdown（`.claude/`・`docs/spec.md` 等）

**見出し:**
- H1（`#`）はファイルごとに1つ、ドキュメントタイトルのみ
- H2（`##`）で主要章、H3（`###`）で節。H4以下は原則使わない
- 見出しの前後に空行を置く

**リスト:**
- 箇条書きは `-` を使用（`*` は禁止）
- 番号付きリストは手順・順序に意味がある場合のみ
- ネストは2段階以内

**テーブル:**
- ヘッダー行は必須
- セル内改行は `<br>` で代替（Markdown テーブルは改行不可）
- 4列超・長文セルは箇条書きへの変換を検討する

**注意ボックス**（各章1〜2個まで）。GitHub Flavored Markdown の記法:

```markdown
> [!NOTE]
> 補足情報

> [!TIP]
> 推奨事項

> [!WARNING]
> 注意喚起

> [!CAUTION]
> 重大な警告・不可逆操作
```

**コードブロック:** 言語指定必須。
