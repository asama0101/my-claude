# docs/testing_manual.md レビュー結果

レビュー対象: `/home/asama/notebook/traffic-shaper/traffic-reports-db/docs/testing_manual.md`
レビュー実施日: 2026-05-02

---

## 総合評価

**評点: B+（良好・軽微〜中程度の問題あり）**

ドキュメントの完成度は高く、正常系から性能計測・運用監査まで網羅した実践的な手順書になっている。発見した問題点は1件の重大なファクト誤りと、複数の軽微な不整合・改善提案である。

---

## 発見した問題点

### 重大度: 高（ファクト誤り）

#### 問題1: §5.7-B の `downgrade base` 後期待値が誤っている

**場所**: §5.7-B. 連続 downgrade（1501〜1502行目）

**現状の記述**:
```bash
.venv/bin/alembic -c config/alembic.ini downgrade base
# 期待: flow_stats / subport_stats だけが残る（0002 状態）
```
および
```
# 期待: flow_stats / subport_stats のみ（ingest_log・CA なし）
```

**問題の内容**:
`alembic downgrade base` は **全マイグレーション（0001 を含む）を逆順に適用する**。migration 0001 の `downgrade()` は `op.drop_table("flow_stats")` を実行し、0002 の `downgrade()` は `op.drop_table("subport_stats")` を実行するため、base 到達後は **テーブルが1件も存在しない状態** になる。「flow_stats / subport_stats だけが残る」という期待値は誤り。

**正しい期待値**:
```bash
.venv/bin/alembic -c config/alembic.ini downgrade base
# 期待: テーブルが一切存在しない状態（base = migration 0001 より前の状態）
```

補足：「0002 状態（flow_stats + subport_stats のみ）」にしたい場合は `downgrade 0002` と明示すること。

---

### 重大度: 中（コマンドが失敗または動作不一致）

#### 問題2: §1.5 / §5.7-D の `docker compose run` に `--profile worker` が欠落している

**場所**:
- §1.5 Docker Compose 経由取り込み（293行目）
- §5.7-D ダウングレード確認（1538行目）

**現状の記述**:
```bash
docker compose run --rm app uv run python -m src.ingest.worker   # §1.5
docker compose run --rm app python -m src.ingest.worker          # §5.7-D
```

**問題の内容**:
`docker-compose.yml` の `app` サービスは `profiles: ["worker"]` を持つ。Docker Compose v2 では `run` コマンドはターゲットサービスのプロファイルを自動活性化するため、`docker compose run --rm app` は動作する場合があるが、実際のプロダクション cron コマンド（`config/logrotate.conf` および `docs/operations.md` 行230）は `--profile worker` を明示している:

```bash
docker compose --profile worker run --rm app    # operations.md での正式記法
```

一貫性・明示性のため、手順書内でも `--profile worker` を付与すべきである。

**追加の問題（§5.7-D のみ）**:
`docker compose run --rm app python -m src.ingest.worker` は CMD を `python -m ...` で上書きする。Dockerfile の `uv sync --no-dev` は uv の仮想環境（`.venv/`）に依存パッケージをインストールするため、システムの `python` から直接起動すると `asyncpg` 等が見つからずインポートエラーになる可能性がある。§1.5 と同様に `uv run python -m src.ingest.worker` とすべき。

---

### 重大度: 低（記述と実装の軽微な不一致）

#### 問題3: §2.3 / §3.2 の worker.py 行番号参照がずれている可能性

**場所**:
- §2.3「worker.py:189-209 参照」（451行目）
- §3.2「worker.py:125-133 参照」（553行目）
- §5.6「worker.py:245-261 参照」（1466行目）

**現状**:
現時点では以下のとおり確認できる:
- `_ingest_job` の stable check ループは 190〜208行に存在 → `189-209` はほぼ正確
- `processing/` への rename は 125〜133行 → `125-133` は正確
- `_cleanup_error_dir` の glob ループは 257〜263行 → `245-261` は若干ずれている（248行〜264行が実際の関数範囲）

行番号参照はコードの変更に追従しないため、将来のリファクタリング時に陳腐化しやすい。ラベルとして行番号よりも関数名（`_ingest_job`、`_process_one`、`_cleanup_error_dir`）を参照することを推奨する。

---

#### 問題4: §4.2 の「測定基準値 20,013 rows/sec（フルスケール1区間）」との不整合表記

**場所**: §4.2 持続スループット判定基準（749行目）

**現状の記述**:
> 全サイクルでスループットが必要値（`20,013 rows/sec`、フルスケール 1 区間）を超えていること

**問題の内容**:
§4.2 の PERF_SUSTAIN_SUBPORTS の既定値は 80、PERF_SUSTAIN_CYCLES は 12 であり、これは「1区間フルスケール（6,004,000行）」にはほど遠い小規模テストである。判定基準に「フルスケール 1 区間」の必要値 20,013 rows/sec を適用することは文脈として妥当だが、「既定パラメータ（小規模）での測定値が 20,013 rows/sec を超えること」を要件とするのは実態と乖離している可能性がある。

既定パラメータでの期待スループット目安を別途記載するか、「フルスケールパラメータで実施する場合の判定基準」であることを明記することを推奨する。

---

### 重大度: 低（用語・一貫性）

#### 問題5: parser.py の docstring との不整合（情報提供）

**場所**: §4.2（753行目）

**現状**: 手順書は `parser の許容範囲（-30 日 〜 +10 分）` と正しく記載している。

**関連する注意事項**: `src/ingest/parser.py` 冒頭の docstring には `time_stamp 範囲チェック（未来 +10分 / 過去 -35日）` と記載されているが、実際のコードは `_MAX_PAST_DELTA = timedelta(days=30)`（30日）である。手順書の記述（30日）は実装と一致しており正しいが、参照先の parser.py 自体に誤った docstring が存在する点を認識しておくこと。

---

## 正確性の確認ができた事項

以下の事項はコードと照合して正確であることを確認した:

| 確認事項 | 結果 |
|---|---|
| `gen_sample_data.py:216` のシード式参照 | 正確（`rng = random.Random(42 + i * len(device_names) + dev_idx)` が216行目に存在）|
| `test_ingest.sh` パターン 4 の存在 | 正確（200行目に「パターン 4: 同 hash 再投入の冪等 skip」）|
| `tests/test_gen_sample_data_determinism.py` の `GOLDEN_HASHES` | 正確（ファイル存在・定数存在確認）|
| `tests/integration/test_db_e2e_propagation.py` 参照 | 正確（ファイル存在）|
| `tests/integration/test_db_retention.py::test_policy_retention_actually_drops_old_chunks` 参照 | 正確（関数名存在確認）|
| 圧縮ポリシー（flow_stats=7日 / subport_stats=14日 / flow_stats_hourly=14日）| 正確（migration 0005 と一致）|
| `subport_stats_5min` に圧縮ポリシーなし | 正確（migration 0009 に add_compression_policy なし）|
| retention ポリシー（flow_stats/subport_stats=31日、その他=93日）| 正確（CLAUDE.md・migration と一致）|
| CA refresh policy の設定値（flow_stats_hourly: start=3h/end=1h/interval=1h）| §5.2 の記述は実装と一致（migration より）|
| `docs/perf-results/<timestamp>.json` の出力先 | 正確（ファイル存在確認）|
| `docs/perf-results/resources/<timestamp>_summary.txt` の出力先 | 正確（ファイル存在確認）|
| §1.2 の 7 タイムスタンプ計算（00:00〜00:30 の 5 分刻み）| 正確（`_build_timestamps_range` の実装と一致）|
| `test_plan.md §6` / `§7.5` の存在 | 正確（それぞれ「試験スケジュール」「環境変数・設定値早見表」として存在）|
| 参照されている全スクリプト（18件）の存在 | 全て `scripts/` 直下に存在 |
| worker DELETE 文 `WHERE hostname = $1 AND time_stamp BETWEEN $2 AND $3` | 正確（worker.py 138-139行）|
| `_cleanup_error_dir` の glob 仕様（*.csv.gz のみ）| 正確（worker.py 257行）|

---

## 改善提案（問題点以外）

1. **§1.5 の目的記述**: 現在「cron実行の模擬」と書かれているが、実際の cron コマンドとは `--profile worker` の有無・環境変数注入方法が異なる。「cron に近い環境でのコンテナ実行確認」程度の表現にとどめ、完全な再現ではないことを補記する。

2. **§3.2 の免責事項**: ディスク満杯テストの loop device 手順は `root` 権限が必要だが、それについての説明が不足している。`sudo` の前提となる権限要件を冒頭に明示することを推奨する。

3. **§4 全体**: 各性能スクリプトの「既定パラメータでの期待スループット（小規模）」と「仕様スケールでの期待スループット」を明確に分離して記載すると、判定基準が明確になる。

---

## まとめ

| 重大度 | 件数 | 主な内容 |
|---|---|---|
| 高（ファクト誤り） | 1件 | §5.7-B `downgrade base` 後の期待テーブル状態が誤り |
| 中（コマンドミス） | 1件 | §1.5 / §5.7-D で `--profile worker` 欠落および §5.7-D で `uv run` 未使用 |
| 低（軽微不一致） | 3件 | 行番号参照のずれ、性能判定基準の文脈説明不足、parser.py docstring との差異（情報提供）|
