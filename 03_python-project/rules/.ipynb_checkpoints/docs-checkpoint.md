---
paths:
  - "docs/**"
  - "**/*.html"
---
# ドキュメント作成ルール

ドキュメント作成・設計レビュー時に参照する。

## ドキュメント形式

`docs/` 配下は HTML。外部仕様書（`docs/spec.md` 等）のみ Markdown。`.claude/` は Markdown（本ガイドライン対象外）。

## 作成の指針

- 前提知識に依存せずドキュメント単体で伝わるよう記述する
- What だけでなく Why（採用理由・却下した代替案）を書く
- 略語は初出時に正式名称を併記、ドメイン固有概念は説明を付ける
- 用語集を `docs/glossary.html` に集約し各ドキュメントから参照する
- 要件 → 設計 → 実装の各段階で前段への参照を明示する

## プロジェクトドキュメント

全ドキュメント共通の必須セクション: 対象読者・前提知識 / 本ドキュメントの目的 / 関連ドキュメントへのリンク / 改訂履歴

| ドキュメント | 役割 | 配置先 | タイミング |
|---|---|---|---|
| 用語集 | 専門用語・略語の定義 | docs/glossary.html | 要件定義 |
| 要件定義書 | 機能要件（FR-xxx）・非機能要件 | docs/requirements/*.html | 要件定義 |
| アーキテクチャ設計書 | コンポーネント構成・責任分界・要件トレース | docs/design/architecture.html | 基本設計 |
| データモデル設計書 | テーブル定義・ER図・制約・インデックス | docs/design/data_model.html | 基本設計 |
| インターフェース設計書 | コンポーネント間 I/F 定義 | docs/design/interfaces.html | 基本設計 |
| セキュリティ設計書 | 認証・認可・暗号化・監査ログ設計 | docs/design/security.html | 基本設計 |
| 環境構成書 | 開発/ステージング/本番の構成・Docker・ネットワーク | docs/design/infrastructure.html | 基本設計 |
| 監視・アラート設計書 | 監視メトリクス・アラート条件・通知先 | docs/design/monitoring.html | 基本設計 |
| 外部仕様書 | 外部 I/F の詳細仕様 | docs/spec.md | 基本設計 |
| 性能しきい値 | Load/Stress Test の基準値 | docs/performance_thresholds.html | 基本設計 |
| テスト計画書 | テスト範囲・合格基準・スケジュール | docs/test_plan.html | 基本設計完了時 |
| 内部 API 設計書 | エンドポイント・リクエスト/レスポンス・認証 | docs/design/api.html | 詳細設計 |
| エラーコード定義書 | エラーコード・メッセージ・HTTP ステータス対応表 | docs/design/error_codes.html | 詳細設計 |
| 処理フロー設計 | 機能ごとの処理フロー図 | docs/design/flows/*.html | 詳細設計 |
| テストケース一覧 | 機能別テストケース・合否基準 | docs/test_cases.html | 詳細設計〜実装 |
| シナリオテスト手順書 | 受け入れテストの手動手順 | docs/scenario/*.html | 詳細設計〜実装 |
| テスト結果報告書 | テスト実施結果・リリース判定の根拠 | docs/test_report.html | 実装完了時 |
| 運用手順書 | 構築・日常・障害対応・バックアップ | docs/operations/*.html | 実装中盤〜完了 |
| ADR | 設計判断の記録 | docs/design/decisions/*.html | 設計判断発生時 |

## 図示・視覚化ガイドライン

Mermaid を基準とし、表現困難な場合のみ draw.io（`.drawio.svg` 形式）を使用する。

### Mermaid で使える図種

`flowchart` / `sequenceDiagram`（`par` で並列）/ `stateDiagram-v2` / `classDiagram` / `erDiagram` / `gantt`

### 図作成の注意

- 15要素超は分割する
- タイトル・凡例・読み取りポイントを必ず添える
- Mermaid コードブロックには ` ```mermaid ` を付ける

### HTML での Mermaid 実装

`mermaid.min.js` をローカルに保存して参照する（CDN 直参照禁止）。

```bash
curl -o docs/assets/mermaid.min.js https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js
```

```html
<script src="../assets/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true });</script>

<pre class="mermaid">
flowchart TD
    A[開始] --> B[処理]
</pre>
```

## 処理フロー設計

詳細設計フェーズで機能ごとに `docs/design/flows/[機能名].html` を作成する。

### 3階層構成

| 粒度 | 配置 | 内容 |
|---|---|---|
| システム全体 | アーキテクチャ書（基本設計） | コンポーネント間のやりとり |
| 機能単位の概略（必須） | `flows/[機能名].html` の §1 | 入力・出力と主要分岐を1枚で俯瞰 |
| サブ処理単位（複雑な処理に必須） | §2 以降 | リトライ・並列・状態遷移を詳細化 |

### ファイル構成例

```
# [機能名]の処理フロー
## 対象読者・前提知識・関連ドキュメント
## 1. 全体フロー（概略）
## 2. [サブ処理1]
## 3. [サブ処理2: 並列処理]
## 4. [サブ処理3: リトライ]
## 5. [サブ処理4: エラー通知]
```

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

### Markdown（.claude/）

注意ボックス（各章1〜2個まで）。GitHub Flavored Markdown の記法:

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

コードブロック: 言語指定必須。`docs/` HTML内でMkDocs利用時は `linenums="1"` / `hl_lines="3 5"` で行強調可。
