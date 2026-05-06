## ドキュメントレビュー: README.md

### 総合スコア

| 観点 | スコア | 概要 |
|---|---|---|
| 内容の正確性 | ★★★☆☆ | コマンド例に3件の誤り・不整合あり（デフォルト値誤記、コマンド省略、SQLのテーブル選択） |
| 構成・読みやすさ | ★★★★★ | 目次とセクション見出しが対応しており、章立て・見出し階層も論理的。重複なし。 |
| 記述漏れ・抜け穴 | ★★★★☆ | `docker/` ディレクトリと `_alembic_filters.py` がディレクトリ構成に未掲載。致命的ではないが漏れ。 |
| リンク・参照 | ★★★★★ | 相対リンクはすべて実在ファイルに対応。TOCアンカーも正しい。外部URLなし。 |

**指摘件数**: 🔴 重要 2件 / 🟡 中程度 1件 / 🟢 軽微 2件

---

### 指摘事項

#### 🔴 重要（誤り・手順不能・参照不能）

**#1 [内容の正確性]** 場所: L205（サンプルデータ生成コードブロック直上のコメント）

コメントに「デフォルト（**1 日分**・60 subport・各 5 flow・1 装置）を ./incoming/ に生成」とあるが、`gen_sample_data.py` の `--days` 引数のデフォルト値は `7`（7日分）であり、直後のオプション表にも `--days | 7` と正しく記載されている。コメントと実装・表が矛盾している。

→ 修正案: コメントを「デフォルト（**7 日分**・60 subport・各 5 flow・1 装置）を ./incoming/ に生成」に変更する。

---

**#2 [内容の正確性]** 場所: L344（コントリビューション > 開発上のルール「スキーマ変更」）

```
.venv/bin/alembic revision --autogenerate
```

`alembic.ini` はプロジェクトルートではなく `config/alembic.ini` に配置されており、`-c config/alembic.ini` を省略すると alembic がファイルを見つけられずエラーになる。他のコマンド例（L165, L296, L299）では `-c config/alembic.ini` を正しく付与しているのに、この箇所だけ省略している。

→ 修正案:
```
.venv/bin/alembic -c config/alembic.ini revision --autogenerate -m "説明文"
```

---

#### 🟡 中程度（抜け穴・混乱の原因）

**#3 [内容の正確性]** 場所: L234–L242（使い方 > DB へクエリ（外部システム）の SQL サンプル）

```sql
FROM subport_stats
```

CLAUDE.md は「外部システムは集計済の Continuous Aggregate（`flow_stats_hourly` / `subport_stats_5min`）を参照する想定」と明記しているが、SQL サンプルは生データの hypertable `subport_stats` を直接クエリしている。`subport_stats` は `hostname` 列を含む装置単位の生データ（保持期間31日）であり、GROUP BY なしでは複数装置の行が重複して返る。外部システム向けの用途であれば `subport_stats_5min`（全装置合算済・5分バケット・保持期間93日）を参照するほうが適切。

→ 修正案: SQL サンプルを以下に変更するか、または「生データを直接参照する例」であることを明記する注記を追加する。

```sql
-- 直近 1 時間の subport トップトーカー（全装置合算）
SELECT subport, avg(mbps_in), max(mbps_in)
FROM subport_stats_5min
WHERE bucket >= now() - INTERVAL '1 hour'
GROUP BY subport
ORDER BY avg(mbps_in) DESC
LIMIT 10;
```

---

#### 🟢 軽微（改善提案・スタイル）

**#4 [記述漏れ・抜け穴]** 場所: L34–L120（ディレクトリ構成のツリー図）

実際には `docker/Dockerfile` が存在するが、ディレクトリ構成のツリー図には掲載されていない。`docker-compose.yml` が `docker/Dockerfile` を参照しており（`dockerfile: docker/Dockerfile`）、開発者がビルドを理解するうえで有用な情報が省かれている。

→ 修正案: `docker-compose.yml` の行の下に以下を追加する。

```
├── docker/
│   └── Dockerfile                  # app コンテナイメージ定義
```

---

**#5 [記述漏れ・抜け穴]** 場所: L46–L49（ディレクトリ構成 `src/db/` の項目）

`src/db/` に実際には `_alembic_filters.py` が存在するが、ツリー図に記載がない。Alembic autogenerate の挙動（hypertable 等の TimescaleDB オブジェクトを誤検出しないようフィルタリング）を理解する際に重要なファイルである。

→ 修正案: `src/db/` のツリーに以下を追加する。

```
│       └── _alembic_filters.py     # Alembic autogenerate フィルタ（TimescaleDB 対応）
```

---

**手動確認が必要な外部リンク**: なし（README内の外部URLは存在しない）

---
修正を適用しますか？
番号を指定（例: 1,3,5）、「全部」、または「スキップ」を入力してください。
