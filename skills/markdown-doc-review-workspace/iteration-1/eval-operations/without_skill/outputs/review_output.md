# docs/operations.md レビュー結果

レビュー対象: `/home/asama/notebook/traffic-shaper/traffic-reports-db/docs/operations.md`
レビュー実施日: 2026-05-02

---

## 総評

全体的に網羅性が高く、運用者視点で必要な情報（起動・停止・監視・障害対応・FAQ・未確認事項）が揃っている。しかし以下の点で**内容の誤り・実装との不整合・記述の矛盾**が確認された。

---

## 指摘一覧

### [高] 内容の正確性

#### 1. §5-2 の「正常な files 数」計算が矛盾している（重大な誤り）

**該当箇所**: §5-2 の表（正常な状態列）

> `files` | 600 ファイル/時間（300 装置 × 2 種 × 12 区間/時間 ÷ 12 × ??）= **約 7,200 ファイル/時間**を期待。

- 計算式が「× 12 区間/時間 ÷ 12」となっており、意味不明な計算が括弧内に残留している。
- 正しくは「300 装置 × 2 種（FLOW/SUBPORT）× 12 区間/時間 = **7,200 ファイル/時間**」と明記すべき。
- さらに同じセルに「1 時間に **3,600 ファイル未満**は装置側転送異常の疑い」とあるが、期待値 7,200 に対して異常閾値が 3,600（50%）というのは実運用上アラートが遅れるリスクがある点も補足すべき。

#### 2. §2-4 のネットワーク節で Syslog のデフォルトポートが実装と矛盾

**該当箇所**: §2-4 ネットワーク

> `app` コンテナはホストの **Syslog ポート（既定 514/UDP）** へ通知を送る

- `config/app.env.example` では `SYSLOG_PORT=5514`、`src/alerts.py` のコード上も `os.getenv("SYSLOG_PORT", "5514")` でデフォルト 5514 を使用している。
- ドキュメントの「既定 514/UDP」は誤り。正しくは「既定 **5514**/UDP（`app.env.example` の初期値）。本番環境で IANA 規定の 514 を使う場合は `app.env` で上書き」と記述すべき。
- §10-2 の環境変数表では `SYSLOG_PORT` の説明に「既定 `5514`（example）／`514`（実環境）」と正確に記載されており、§2-4 の記述と矛盾している。

#### 3. §6-1 の Syslog アラート欄でもデフォルトポートが 514 と誤記

**該当箇所**: §6-1 ログ表（Syslog アラート行）

> `SYSLOG_HOST:SYSLOG_PORT`（既定 `localhost:514` UDP、...）

- 上記と同様に `app.env.example` の実デフォルトは `5514` であり `514` は誤り。

#### 4. §4-2 の compression policy 表に `subport_stats_5min` の compression が記載されていない

**該当箇所**: §4-2 TimescaleDB 内部ジョブ表

- `migration/versions/0005_add_compression.py` を確認した限り、`subport_stats_5min` の compression policy は migration 0005 には含まれていない（`flow_stats`・`subport_stats`・`flow_stats_hourly` の 3 つのみ）。
- ただし §2-5 用語集の compression policy 説明には「`flow_stats` 7 日経過後、`subport_stats` / `flow_stats_hourly` 14 日経過後」とあり、`subport_stats_5min` は記載なし。この記述は正確だが、§4-2 の表も合わせて `subport_stats_5min` に compression が設定されていないことを明示すると親切。

#### 5. §7 のタイムスタンプ過去チェックのエラーメッセージが実装と異なる

**該当箇所**: §7 エラー一覧

> `ingest failed for <file>: time_stamp ... is too far in the past ...` | CSV のタイムスタンプが現在時刻 - **30 日**超

- `src/ingest/parser.py` では `_MAX_PAST_DELTA = timedelta(days=30)` だが、`_validate_timestamp_range` が送出するエラーメッセージは `"time_stamp {ts} is too far in the past (now={now}); data may have already been deleted by retention policy"` であり、数値「30 日」は含まれない。
- 対応説明には「30 日以内のデータなら時刻補正の上で再投入」とある。仕様として「現在時刻 - 30 日」という閾値でよいが、エラーメッセージパターンとして表に掲載するなら実際のメッセージと合わせた方が検索性が高い。

#### 6. §7 の「取り込みスキップ」時のログに `ingest_log` チェックのエラーパターンが欠けている

**該当箇所**: §7 エラー一覧

- 実装（`worker.py` 119 行目）では `"already ingested (hash match), skipping: %s"` が INFO ログとして出力されるが、これはエラーではなく正常動作。ただし運用者が「ファイルが消えたのに DB に入っていない」と誤解する可能性があるため、§8 FAQ に追記するか §7 の NOTE として補足するとよい（現状は記載なし）。

---

### [中] 構成・記述漏れ

#### 7. §3-1 の起動確認コマンドで psql ユーザ名がハードコード

**該当箇所**: §3-1

```bash
docker compose exec db pg_isready -U user -d traffic
```

- `user` は `app.env.example` のデフォルト値であり、本番環境では異なる可能性がある。
- `docker compose exec db pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}` のように環境変数参照形式で記述するか、「`user` は `POSTGRES_USER` の値に置き換えること」と注記すべき。

#### 8. §9-2 の pg_dump コマンドが `-f` オプションでコンテナ内パスに書き出している

**該当箇所**: §9-2

```bash
docker compose exec -T db pg_dump -U user -F c -f /tmp/traffic.dump traffic
docker compose cp db:/tmp/traffic.dump ./backup/traffic-$(date +%Y%m%d).dump
```

- `-f /tmp/traffic.dump` はコンテナ内の `/tmp` に書き出す（コンテナ再起動で消える）。
- より確実な方法は `docker compose exec -T db pg_dump -U user -F c traffic > ./backup/traffic-$(date +%Y%m%d).dump` のように stdout を直接ホスト側ファイルにリダイレクトすること。
- また `date` コマンドはホストのタイムゾーンに依存するため、`date -u +%Y%m%d`（UTC 統一）が推奨される（メモリファイル `feedback_docker_timezone.md` の方針と整合）。

#### 9. §4-1 の cron 例に `-f` フラグが記載されているが §3-3 の手動実行例と形式が異なる

**該当箇所**: §4-1 vs §3-3

- §4-1: `docker compose -f /path/to/.../docker-compose.yml --profile worker run --rm -T app`
- §3-3: `docker compose --profile worker run --rm app`

- `-f` の有無、`-T` の有無が異なる。cron からは標準入力が存在しないため `-T`（疑似 TTY 無効）は必要だが、§3-3 の手動実行では TTY が利用可能なので省略可能。この違いを注記すれば混乱を防げる。

#### 10. §8-5 の手動再集計コマンドの日付がハードコード

**該当箇所**: §8-5

```bash
-c "CALL refresh_continuous_aggregate('flow_stats_hourly', '2026-04-29 00:00', '2026-04-29 12:00');"
```

- 実例として特定日付を記載しているが、「例として 2026-04-29 00:00〜12:00 を指定。実際の対象期間に合わせて変更すること」と注記を追加すべき。現状では注記がなく、初見の運用者がそのままコピーして実行するリスクがある。

---

### [低] リンク・参照

#### 11. §2-3 のディレクトリ構成で `docs/operations/` の記述が残留

**該当箇所**: §2-3

- 変更履歴（§13）に「`docs/operations/handover.md` → `docs/operations.md` に移動」「空になった `docs/operations/` ディレクトリを削除」とあるが、§2-3 のディレクトリツリーには `docs/operations/` は表示されておらず整合している。問題なし（確認済み）。

#### 12. §5-5 の参照先 `docs/consistency_audit.md` は実在する

- `docs/consistency_audit.md` の存在を `ls` で確認済み。リンク切れなし。

#### 13. §4-2 の参照「`5-4` で確認する」が正しい節番号

- 本文中「これらの動作状況は `5-4` で確認する」→ §5-4 が確かに「TimescaleDB バックグラウンドジョブの実行状況」を確認する節であり整合している。

---

## まとめ

| 重要度 | 件数 | 内容 |
|---|---|---|
| 高（内容の誤り） | 3件 | §5-2 の計算式混乱、§2-4 と §6-1 の Syslog デフォルトポート誤記（514 vs 実装の 5514） |
| 中（記述漏れ・改善） | 4件 | pg_isready のハードコード、pg_dump の安全性、cron と手動コマンドの差異未記述、再集計コマンドの日付ハードコード |
| 低（確認済み・問題なし） | 3件 | リンク切れなし、参照節番号整合 |

最優先で修正すべきは **Syslog デフォルトポートの誤記（§2-4 と §6-1）** と **§5-2 の計算式の整理**。前者は運用者がアラート設定を誤る直接原因になる。
