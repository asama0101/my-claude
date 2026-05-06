# README.md レビュー結果

対象ファイル: `/home/asama/notebook/traffic-shaper/traffic-reports-db/README.md`

---

## 総評

README の構成は全体的に充実しており、ディレクトリ構成・コマンド例・環境変数表など主要な情報を網羅している。ただし、以下の問題点が確認された。

---

## 指摘一覧

### 1. [重要度: 高] サンプルデータ生成コメントの日数誤り（行 205）

**問題**: コメントに「1 日分」と記載されているが、実際の `--days` デフォルト値は `7`（7日分）。

```bash
# デフォルト（1 日分・60 subport・各 5 flow・1 装置）を ./incoming/ に生成
.venv/bin/python scripts/gen_sample_data.py
```

**実態** (`scripts/gen_sample_data.py` 行 145):
```python
"--days", type=int, default=7, help="生成日数 (default: 7)  --start/--end 未指定時のみ有効"
```

**修正案**: コメントを「7 日分」に変更する。

---

### 2. [重要度: 高] 開発ルールの関数名が実際のコードと不一致（行 347）

**問題**: 「commit の位置」の説明で `load_rows` / `load_subport_rows` という関数名を挙げているが、これらの関数は存在しない。実際の関数名は `copy_flow_rows` / `upsert_subport_rows`。

```markdown
- **commit の位置**: `load_rows` / `load_subport_rows` は `session.commit()` を呼ばない。commit は `worker._ingest_job` が `ingest_log` INSERT と同一トランザクションで行う。
```

**実態** (`src/ingest/loader.py`):
- `copy_flow_rows(df, conn)` — FLOW データの書き込み
- `upsert_subport_rows(df, conn)` — SUBPORT データの書き込み

**実態** (`src/ingest/worker.py`): commit は `_ingest_job` ではなく `_process_one` 内の `conn.transaction()` ブロックで実行される。`session.commit()` ではなく asyncpg の `conn.transaction()` コンテキストマネージャが使われている（SQLAlchemy セッションは使用していない）。

**修正案**: 関数名を `copy_flow_rows` / `upsert_subport_rows` に、commit の場所を `_process_one` に、セッションの記述を asyncpg トランザクションに修正する。

---

### 3. [重要度: 中] SQL クエリ例のテーブル名が不適切（行 237）

**問題**: 「直近 1 時間の subport トップトーカー」クエリが `subport_stats`（生データ・31日保持）を参照しているが、設計上の外部公開用テーブルは `subport_stats_5min`（5分集計・全装置合算・93日保持）。

```sql
SELECT subport, avg(mbps_in), max(mbps_in)
FROM subport_stats
WHERE time_stamp >= now() - INTERVAL '1 hour'
GROUP BY subport
ORDER BY avg(mbps_in) DESC
LIMIT 10;
```

README 自体の別箇所（行 15）でも「外部システムは `subport_stats_5min` を参照する想定」と記載している。生データテーブルを直接クエリするとホスト名ごとに重複行が現れ、集計結果が誤った値になる可能性がある。

**修正案**: `FROM subport_stats` を `FROM subport_stats_5min` に変更し、クエリを 5min CA に合わせる。

---

### 4. [重要度: 中] `INGEST_ERROR_THRESHOLD` の説明が不正確（行 322）

**問題**: README には「ファイル数がこの値以上に達した場合にバックログアラートを送信する」と記述されているが、実際の条件は `backlog >= threshold AND backlog > last_count`（前回より増加したときのみ）。

**実態** (`src/ingest/worker.py` 行 285):
```python
should_alert = failed_now > 0 or (backlog >= _ERROR_FILE_THRESHOLD and backlog > last_count)
```

単に閾値を超えるだけでなく、**前回よりバックログが増加したとき**にのみアラートが発火する。

**修正案**: 説明を「`incoming/error/` のファイル数がこの値以上かつ前回より増加した場合にバックログアラートを送信する。」に修正する。

---

### 5. [重要度: 低] ディレクトリ構成に `src/db/_alembic_filters.py` が未記載（行 47〜49）

**問題**: 実際の `src/db/` には `_alembic_filters.py` が存在するが、README のディレクトリ構成ツリーには記載がない。

**実態**:
```
src/db/
├── _alembic_filters.py   ← 未記載
├── models.py
└── session.py
```

**修正案**: ディレクトリ構成に `_alembic_filters.py` を追加する（例: `# Alembic 自動生成フィルタ` のコメント付きで）。

---

### 6. [重要度: 低] `--end` オプションの説明が「省略時は現在時刻」のみ（行 220）

**問題**: README の `--end` オプション説明は「省略時は現在時刻」と記載しているが、実際には `--start` が指定されていない場合に `--end` を単独使用するとエラー (`parser.error`) になる。この制約が README に明記されていない。

**実態** (`scripts/gen_sample_data.py` 行 191-192):
```python
elif args.end is not None:
    parser.error("--end を単独で指定する場合は --start も指定してください")
```

**修正案**: `--end` の説明に「`--start` が必須（単独使用不可）」の注記を追加する。

---

## ファイル・コマンド照合サマリー

| 確認項目 | README 記載 | 実態 | 結果 |
|---|---|---|---|
| マイグレーションファイル (0001〜0011) | 一覧記載 | 全て存在 | OK |
| scripts/ スクリプト一覧 | 全て記載 | 全て存在 | OK |
| tests/ テスト件数 (parser: 57, loader: 15, worker: 50, alerts: 3, session: 3) | 各件数記載 | 実数と一致 | OK |
| tests/integration/ テスト件数 | 各件数記載 | 全て一致 | OK |
| docs/ ドキュメント一覧 | 6ファイル記載 | 全て存在 | OK |
| config/ ファイル一覧 | alembic.ini, app.env.example, app.env, logrotate.conf | 全て存在 | OK |
| 環境変数一覧 | 11変数記載 | app.env.example と一致 | OK |
| `--days` デフォルト値 (表) | `7` | `7` | OK |
| コメント「1 日分」 | 1日 | 実際は7日 | **NG** |
| `load_rows` / `load_subport_rows` 関数名 | 記載あり | 存在しない | **NG** |
| `_ingest_job` が commit | 記載あり | 実際は `_process_one` | **NG** |
| SQL 例のテーブル名 `subport_stats` | 記載あり | 外部公開用は `subport_stats_5min` | **NG** |
| `INGEST_ERROR_THRESHOLD` 発火条件 | 閾値以上 | 閾値以上かつ増加時 | **NG** |
| `_alembic_filters.py` の記載 | 未記載 | 存在する | **NG** |
| incoming/ サブディレクトリ (processing/, error/) | 記載あり | 両方存在 | OK |
| `.ingest.lock` の記載 | cron 例のみ | worker.py で `incoming/.ingest.lock` を生成 | 軽微 |

---

## 評点

| 観点 | 評点 | コメント |
|---|---|---|
| 内容の正確性 | 3/5 | 関数名・コメント・SQL テーブル名に誤りあり |
| 構成・網羅性 | 4/5 | 主要情報は揃っているが `_alembic_filters.py` が抜け |
| 記述の明瞭さ | 4/5 | 概ね分かりやすいが INGEST_ERROR_THRESHOLD の条件が不正確 |
| コマンド例の正確性 | 4/5 | alembic / pytest 等は正確。サンプルデータのコメントに誤り |

**総合: 4件の高〜中重要度の指摘あり。修正を推奨する。**
