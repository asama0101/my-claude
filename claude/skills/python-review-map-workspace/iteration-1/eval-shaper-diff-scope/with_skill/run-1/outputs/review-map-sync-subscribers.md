# レビュー地図: shaper-db コミット 0253fe0 (sync/subscribers.py 加入者同期エントリ)

## 対象範囲

`git diff 0253fe0^ 0253fe0` で変更された3ファイル(すべて新規追加、差分 +409/-0)を中心に、
その直接の呼び出し元/呼び出し先(1 hop)を含めた diff スコープの地図。

- `src/shaper_db/sync/subscribers.py`(+111、本体)
- `tests/unit/test_sync_subscribers.py`(+90)
- `tests/system/test_sync_subscribers_system.py`(+208)

1 hop として以下を含める(いずれも変更なし、参照のみ):

- 呼び出し元: `src/shaper_db/sync/pipeline.py`(`run_cli`/`run_sync`/`_sync_one_device` が
  `make_fetch_and_transform`/`read_current`/`apply` を注入して呼ぶ)
- 呼び出し先: `src/shaper_db/diff.py`(`DiffResult`)、`src/shaper_db/fetch/db.py`(`fetch_db`)、
  `src/shaper_db/fetch/csv_source.py`(`fetch_subscribers`)、
  `src/shaper_db/transform/subscribers.py`(`Subscriber`/`build_subscribers`)、
  `src/shaper_db/fx2/client.py`(`FX2Client.get_flows`/`post_flows`/`delete_flows`)
- 兄弟モジュール(非対称性の比較対象として参照): `src/shaper_db/sync/rules.py`(変更なし。
  コミットメッセージが「rules と非対称」と明記しているため、地図・チェックリストで対比する)

仕様書は `CLAUDE.md`(プロジェクトルート)の「仕様書の参照順」節が `docs/spec/` 配下6文書を
正典と明記しており、実際に `docs/spec/04_fx2-api.md`・`docs/spec/05_sync-spec.md` に
`REQ-`/`NFR-` ID 形式の要件が確認できたため、これを正典として対応表を作成した。

## 全体構成図

```
        ┌────────────────────┐
        │ sync/pipeline.py    │  (変更なし。呼び出し元)
        │ run_cli/run_sync/   │
        │ _sync_one_device    │
        └─────────┬───────────┘
                   │ 3ステップ注入(make_fetch_and_transform/read_current/apply)
                   ▼
        ┌════════════════════════════════════┐
        ║ sync/subscribers.py  ← 今回の変更   ║
        ║ (新規, +111行)                      ║
        └───┬───────────┬───────────┬─────────┘
            │            │           │
            ▼            ▼           ▼
   fetch/db.py    fetch/csv_source.py   fx2/client.py
   fetch_db()     fetch_subscribers()   get_flows/post_flows/
            │            │              delete_flows
            ▼            ▼
        transform/subscribers.py
        build_subscribers() → Subscriber

   diff.py (DiffResult, diff_rows) は pipeline.py 側から呼ばれ、
   結果が apply() に渡される。

   (対比参照・変更なし)
   sync/rules.py ─ 同型の3ステップだが commit_config(PATCH→refresh→save)
                    を使う点が subscribers.py の即時反映と非対称
```

## モジュールブロック

#### `src/shaper_db/sync/subscribers.py`(新規)

**平たく言うと:** `sync-subscribers` バッチの「変換・事前読取・適用」3ステップを実装し、
`pipeline.run_cli` に注入するエントリポイント。

**なぜ要るか:** 加入者(flow)の望ましい状態を外部DB+CSVから組み立て、装置現状との差分を
`DELETE`/`POST /dynamic-queueing/flows` で適用する処理を1箇所に集約する。`sync/rules.py`
と同じ3ステップの型(`make_fetch_and_transform`/`read_current`/`apply`)を踏襲しつつ、
flow 特有の非対称性(PIR概念なし・即時反映でcommit不要・削除先行必須)を吸収する。

**呼ばれ方:** `main()` が `pipeline.run_cli("subscribers", make_fetch_and_transform,
read_current, apply, argv)` を呼ぶ(`src/shaper_db/sync/subscribers.py:110`)。
`pipeline._sync_one_device`(`src/shaper_db/sync/pipeline.py:98-108`)が
`read_current`→`diff_rows`→`apply` の順で呼び出す。

**主な関数:** 下記参照。

##### `_chunks(seq: tuple, size: int) -> Iterator[tuple]` — `src/shaper_db/sync/subscribers.py:20-23`

**意図:** `seq` を `size` 件ずつに分割する(docstring: 04_fx2-api.md §2.4/2.5 の
1リクエスト最大1,000,000件制約への対応)。

**実装の要点:**
- `range(0, len(seq), size)` で先頭インデックスを刻み、スライスをそのまま yield する単純な
  ジェネレータ。
- `size` が 0 の場合は無限ループにならず `range(0, len, 0)` が即座に `ValueError` を送出する
  (Python 標準動作。呼び出し元は `_CHUNK = 1_000_000` 固定のため通常到達しない)。

**確認ポイント:** テスト `test_apply_chunks_both_sides`(`tests/system/test_sync_subscribers_system.py:118-150`)
は `_CHUNK` を `monkeypatch` で `2` に差し替え、5件を2+2+1に分割した際の off-by-one を、
件数だけでなく送信された `flow_id` の和集合の完全一致まで検証している。

##### `_flow_to_row(flow: dict) -> tuple` — `src/shaper_db/sync/subscribers.py:31-39`

**意図:** `GET /flows` 応答の1行(`{flow_id, subport, address, count_id}`)を
`(flow_id, subport, address)` の3-tupleへ変換する。docstring が明記する理由:
`count_id` は管理対象外であり、4-tupleのままだと desired(3列)との列数不一致で
`diff_rows`(`src/shaper_db/diff.py:47`)がクラッシュするため。

**実装の要点:**
- 単純な dict→tuple 変換。`count_id` キーには触れない(読まずに捨てる)。
- キー欠落時の挙動は書かれていない。`flow["flow_id"]` は `KeyError` を送出しうるが、
  この関数内では捕捉していない。

**確認ポイント:** `test_read_current_drops_count_id`(`tests/system/test_sync_subscribers_system.py:60-74`)
と `test_read_current_output_survives_diff_rows`(同77-88行)が、まさにこの「4列→3列」変換が
`diff_rows` のクラッシュを防ぐという回帰シナリオを直接検証している。

##### `make_fetch_and_transform(config: Config) -> FetchAndTransform` — `src/shaper_db/sync/subscribers.py:46-64`

**意図:** 外部DBのエリア表+顧客CSVを取得し `build_subscribers` で `Subscriber` 集合に変換した後、
`group_name` 別に正準タプルへ集約したクロージャを返す(design §5 手順1)。

**実装の要点:**
- `_fetch()` 内で `fetch_db(config.db)` → `fetch_subscribers(config.csv)` →
  `build_subscribers(customer_rows, db_rows.areas, config.groups)` の順に呼ぶ。
- `db_rows.rules` は使わない(`db_rows.areas` のみ参照。`rules` フィールドは
  `sync/rules.py` 側が使う共有の戻り値型であることが読み取れる)。
- `build_subscribers` には `pir_max_kbps` に相当する第4引数を渡さない
  (コミットメッセージが明記する「rules との非対称」)。
- `by_group: dict[str, list[tuple]]` へ `setdefault` で集約する単純なループ。例外処理なし
  (`fetch_db`/`fetch_subscribers`/`build_subscribers` からの例外はそのまま伝播)。

**確認ポイント:** `test_make_fetch_and_transform_groups_by_group_name`
(`tests/unit/test_sync_subscribers.py:15-62`)は `fetch_db`/`fetch_subscribers` を
monkeypatch し、`config.db`/`config.csv` がそれぞれ正しい引数に渡ることを恒等性
(`is`)まで検証し、group 別集約の並び順も確認している。

##### `read_current(client: FX2Client, group_name: str, desired_rows: list[tuple]) -> list[tuple]` — `src/shaper_db/sync/subscribers.py:67-81`

**意図:** 装置の現状 flow を読み `(flow_id, subport, address)` の list で返す(design §5 手順2、
05_sync-spec.md §3.3)。

**実装の要点:**
- `group_name`/`desired_rows` 引数は**受け取るが使わない**。docstring はその理由を明記:
  `client.get_flows([])`(空リスト=subports 未指定=全件取得)で常に装置上の全 flow を返す設計。
  subport 絞り込みだと 04_fx2-api.md §2.3 の「最大10件」制約に抵触するうえ desired に
  無い subport 上の残存 flow を取りこぼす、という2つの理由がコメントされている。
- `Fx2Error` を捕捉しない設計(fail-loud)。docstring が `pipeline._sync_one_device` の契約
  (装置単位の失敗捕捉はそちらの責務)であることを明記。
- `desired_rows`/`group_name` を関数シグネチャに残しつつ本体で無視するのは、
  `pipeline.ReadCurrent` という共通の関数型シグネチャ(`sync/rules.py:read_current` と揃える)
  を満たすため(型の対称性)。

**確認ポイント:** `test_read_current_full_fetch_no_subport_query`
(`tests/system/test_sync_subscribers_system.py:49-57`)が「無関係な `group_name`/`desired_rows`
を渡しても常にクエリ文字列なしの全件 GET になる」ことを明示的に回帰テストしている
(AC-4 とコメントあり)。

##### `apply(client: FX2Client, group_name: str, diff: DiffResult) -> None` — `src/shaper_db/sync/subscribers.py:84-107`

**意図:** 差分を装置へ適用する(design §5 手順3、04_fx2-api.md §2.4/2.5、05_sync-spec.md §3.5)。

**実装の要点:**
- `diff.to_add`/`diff.to_delete` が両方空なら即 `return`(no-op、装置に触れない)。
- **削除を先に行ってから追加する**(`to_delete` の `_chunks` ループが `to_add` より先)。
  docstring 曰く `flow_id`/`address` はいずれも装置全体で一意制約があり、値変更は
  「削除→再登録」でしか行えないため、追加が先だと一意制約違反になりうる。
  (04_fx2-api.md §2.4 の一意制約記述と整合。05_sync-spec.md §3.4 も
  「`address` が変更された加入者は削除→再登録の対象として扱う」と明記)。
- `to_delete`/`to_add` それぞれを `_CHUNK`(1,000,000)件単位で `_chunks` に通し、
  `client.delete_flows(flow_ids=[row[0] for row in chunk])` /
  `client.post_flows(flows=[_row_to_flow(row) for row in chunk])` を呼ぶ。
- **`commit_config`(PATCH /config → refresh moff → save moff)を一切呼ばない**。
  `sync/rules.py:apply`(下記対比参照)との最大の非対称点。docstring は「flows は即時反映のため」
  と理由を明記。
- 分割送信の途中で失敗した場合の巻き戻しは行わない。次周期の事前読取 diff による
  自己修復に委ねる、と docstring が明記(05_sync-spec.md §7 を参照)。
- `Fx2Error` を捕捉しない(fail-loud、`read_current` と同じ契約)。
- `post_flows`/`delete_flows` の戻り値 `FlowResult`(`total`/`exist`/`confirmed`)は
  **受け取るが一切使わない**(呼び出すだけで結果を捨てている)。

**確認ポイント:**
- 削除先行の順序は `test_apply_delete_before_post`(`tests/system/test_sync_subscribers_system.py:104-115`)
  が `methods.index("DELETE") < methods.index("POST")` で検証。
- チャンク分割は `test_apply_chunks_both_sides`(同118-150行)。
- フィールド対応(取り違え検知)は `test_apply_sends_exact_field_mapping`(同153-172行)。
- commit 非呼び出しは `test_apply_no_commit`(同175-190行)。
- no-op は `test_apply_noop_empty`(同193-197行)。
- fail-loud 伝播は `test_apply_propagates_fx2error`(同200-208行)。
- `FlowResult` を使わない点(`total`/`exist`/`confirmed` を読まない)に対応するテストは
  見当たらない。04_fx2-api.md §4.2「部分適用の検出」は `PATCH /config`(rules 側)の
  `400` 応答本文の話であり、flows 系(`POST`/`DELETE`)の部分適用検出については
  04_fx2-api.md に明記が無い(`POST` は「オールオアナッシング」と05_sync-spec.md §3.5に
  明記があるため、`200` 応答なら全件成功と解釈できる可能性はある)。この解釈が正しいか、
  `FlowResult` を無視してよいという設計判断がどこかに明文化されているか確認する価値がある。

##### `main(argv: list[str] | None = None) -> int` — `src/shaper_db/sync/subscribers.py:109-111`

**平たく言うと:** `pipeline.run_cli` に3ステップを注入して委譲する1行の CLI エントリ。
自明なため関数ブロックは省略(`test_main_delegates_to_run_cli`
(`tests/unit/test_sync_subscribers.py:70-90`)が委譲先の恒等性まで検証済み)。

---

#### `sync/rules.py`(対比参照、変更なし)

**平たく言うと:** 同じ3ステップの型を持つ `sync-rules` エントリ。今回の `subscribers.py` と
構造は同型だが、対象が subport 定義(CLI コンフィグ経由)である点が異なる。

**非対称点(コミットメッセージが明記、地図として対比表化):**

| 観点 | `sync/rules.py` | `sync/subscribers.py` |
|---|---|---|
| `make_fetch_and_transform` の変換引数 | `build_rules(..., config.sync.pir_max_kbps)` (4引数) | `build_subscribers(...)` (3引数、PIR概念なし) |
| `read_current` の取得経路 | `POST /cli`(`show current.cfg`)をパース | `GET /flows`(NDJSON) |
| `apply` の適用経路 | `client.commit_config(cli_text)`(PATCH→refresh moff→save moff) | `delete_flows`→`post_flows` を直接呼ぶ(commit不要) |
| 適用順序 | CLI本文1回投入(追加/削除が同一ブロック内) | 削除先行→追加(一意制約のため必須) |
| チャンク分割 | なし(CLIコンフィグに件数上限の言及なし) | `_CHUNK=1,000,000` で両側分割 |

`sync/rules.py` 自体は今回のコミットで変更されていないため、地図としてはこの対比表のみに
とどめる(詳細な関数ブロックは対象外)。

---

#### `src/shaper_db/sync/pipeline.py`(呼び出し元、変更なし)

**平たく言うと:** `read_current`/`apply` を関数注入として受け取り、装置単位の構築→読取→差分→適用と、
失敗分離・指紋ゲート・並列実行を担う共通オーケストレータ。

**呼ばれ方との整合性:** `_sync_one_device`(`src/shaper_db/sync/pipeline.py:83-109`)が
`Fx2Error` のみを捕捉し `DeviceOutcome("failure", ...)` に写像する契約になっている
(`src/shaper_db/sync/pipeline.py:108-109`)。`subscribers.py` の `read_current`/`apply` が
`Fx2Error` を握らない設計は、この契約と整合している。

---

#### `src/shaper_db/diff.py`(呼び出し先、変更なし)

**平たく言うと:** `desired`/`current` の行集合を一時 SQLite で `EXCEPT` し `DiffResult` を返す
汎用リーフ。列数は先頭行から動的に決定するため(`src/shaper_db/diff.py:47`)、
`_flow_to_row` が3列を保証していないと `desired`(3列)との列数不一致でクラッシュする
(`subscribers.py` の docstring が言及する点そのもの)。

---

#### `src/shaper_db/fetch/db.py` / `src/shaper_db/fetch/csv_source.py`(呼び出し先、変更なし)

**平たく言うと:** それぞれ `fetch_db(config.db) -> DbRows(areas, rules)`、
`fetch_subscribers(config.csv) -> tuple[tuple[str, ...], ...]`(顧客CSV行)を返す取得関数。
`make_fetch_and_transform._fetch()` から呼ばれる(1行呼び出しのみで、内部実装(SSH/SFTP)は
今回のdiffスコープ外)。

---

#### `src/shaper_db/transform/subscribers.py`(呼び出し先、変更なし)

**平たく言うと:** `build_subscribers(customer_rows, area_rows, groups) -> SubscribersResult`。
顧客CSV+エリア表からロンゲストマッチで `Subscriber(flow_id, subport, address, group_name)` を
構築する。`make_fetch_and_transform` はこの戻り値の `.subscribers` を `group_name` でグループ化
するだけで、ロンゲストマッチ等のロジック自体には関与しない。

---

#### `src/shaper_db/fx2/client.py`(呼び出し先、変更なし)

**平たく言うと:** `get_flows`/`post_flows`/`delete_flows` の3メソッドが今回のdiffスコープから
呼ばれる。`post_flows`/`delete_flows` は `FlowResult(total, exist, confirmed)` を返すが、
`subscribers.py:apply` はこの戻り値を受け取らずに捨てている(上記「確認ポイント」参照)。

## レビューチェックリスト

#### 命名/可読性/複雑度

- [ ] `src/shaper_db/sync/subscribers.py:67` `read_current(client, group_name, desired_rows, ...)` は
  `group_name`/`desired_rows` を受け取るが本体で一切使わない。`sync/rules.py:read_current` と
  シグネチャを揃えるための意図的な設計と読めるが、未使用引数であることを示す命名・コメント
  (例: `_group_name`)を付けるかどうか確認する？
- [ ] `src/shaper_db/sync/subscribers.py:84` `apply(client, group_name, diff)` も同様に
  `group_name` を一切使わない。同上。

#### 例外処理/境界値

- [ ] `src/shaper_db/sync/subscribers.py:31-39` `_flow_to_row` は `flow["flow_id"]` などの
  dict アクセスをそのまま行い、キー欠落時の `KeyError` を捕捉していない。装置応答の NDJSON が
  仕様(04_fx2-api.md §2.3)通り `{flow_id, subport, address, count_id}` を常に含む前提で
  問題ないか確認する？
- [ ] `src/shaper_db/sync/subscribers.py:84-107` `apply` は `client.post_flows`/`delete_flows`
  の戻り値 `FlowResult`(`total`/`exist`/`confirmed`)を一切参照していない。04_fx2-api.md §2.4
  は「`POST` はオールオアナッシング」と明記されており `200` なら全件成功と解釈できそうだが、
  `exist`/`confirmed` が期待件数と一致するかまでは検証していない。この設計判断(戻り値を
  検証しない)が意図通りか確認する？
- [ ] `src/shaper_db/sync/subscribers.py:20-23` `_chunks(seq, size)` は `size<=0` のガードが
  無い(`_CHUNK` 定数以外から呼ばれる想定は無いため実害は薄いが、念のため確認する？)。

#### テストカバレッジ/テスタビリティ

- [ ] `src/shaper_db/sync/subscribers.py:84-107` `apply` の「削除チャンク送信中に例外が起きた場合、
  追加チャンクは一切送信されない」という部分成功シナリオ(削除は一部成功・追加は未送信)を
  直接検証するテストが `tests/system/test_sync_subscribers_system.py` に見当たらない
  (`test_apply_propagates_fx2error` は削除0件目で即失敗するケースのみ)。分割送信の中間で
  失敗した場合の挙動確認は不要か(docstring は「巻き戻しは行わない、次周期に委ねる」と明記
  しているため設計上は正しいが、テストで固定化する価値があるか)確認する？
- [ ] `src/shaper_db/sync/subscribers.py:46-64` `make_fetch_and_transform` 内で
  `fetch_db`/`fetch_subscribers`/`build_subscribers` のいずれかが例外を送出した場合の
  挙動を直接検証するテストが `tests/unit/test_sync_subscribers.py` に見当たらない
  (正常系のみ)。`pipeline.run_sync` 側が非捕捉で伝播させる契約(`FetchError`/`IntegrityError`
  等)であるため単体テスト不要という判断か確認する？

#### セキュリティ/外部入力

- [ ] `src/shaper_db/sync/subscribers.py:41-44` `_row_to_flow(row)` は diff 結果由来の
  `(flow_id, subport, address)` をそのまま `POST /flows` の JSON body に埋め込む。この時点で
  値は `transform/subscribers.py` の `FLOW_ID_PATTERN`/`SUBPORT_NAME_PATTERN` 等で既に検証済み
  という前提(05_sync-spec.md §3.5「適用前に検証規則を満たすことを確認済みのデータのみを送信する」)
  で問題ないか、`apply` 側で二重検証していないことを確認する？
- [ ] このスコープでは他に該当箇所なし(認証情報・ログ出力・パス構築は今回の変更に含まれない)。

## 仕様書との対応表

正典: `docs/spec/04_fx2-api.md`(FX2 REST API アダプタ仕様)・`docs/spec/05_sync-spec.md`
(ルール同期/加入者同期の処理仕様)。`CLAUDE.md` の「仕様書の参照順」節が明記する6文書のうち
今回のdiffスコープに対応する2文書。

| コード (file:line) | 対応する要件/仕様 | 備考 |
|---|---|---|
| `sync/subscribers.py:46 make_fetch_and_transform` | 05_sync-spec.md §3.1/3.2(取得・望ましい状態生成) | `build_subscribers` への委譲のみで、ロンゲストマッチ等の検証ロジック自体は `transform/subscribers.py` 側の対応表(スコープ外)を参照 |
| `sync/subscribers.py:67 read_current` | 05_sync-spec.md §3.3(装置現状読取)、04_fx2-api.md §2.3(`GET /flows`) | 「全件取得(subports 未指定)」が仕様に明記されているか: 05_sync-spec.md §3.3 は「対象装置ごとに `GET /dynamic-queueing/flows` で現在の flow 定義を1回取得する」とのみ記載し、subports絞り込みの是非には言及していない。全件取得の判断根拠は docstring 内のコメント(04_fx2-api.md §2.3 の最大10件制約)によるものであり、05_sync-spec.md 本文には全件取得を明示する記述が見当たらない |
| `sync/subscribers.py:84 apply`(削除先行) | 05_sync-spec.md §3.4「`address` が変更された加入者は…削除→再登録の対象として扱う」、04_fx2-api.md §2.4 一意制約 | 一致 |
| `sync/subscribers.py:84 apply`(チャンク分割 `_CHUNK=1_000_000`) | 05_sync-spec.md §3.5「いずれも1,000,000件単位に分割してリクエストする」、04_fx2-api.md §2.4/2.5「1リクエスト最大1,000,000件」 | 一致 |
| `sync/subscribers.py:84 apply`(commit_config 不呼び出し) | 05_sync-spec.md §3.6「適用後の再読取による一致確認は行わない」 | flows が即時反映でありcommit手順(§2.5節・rules側)自体が不要という設計は、05_sync-spec.md 3節に rules 相当の commit 手順への言及が無いことと整合(消極的な整合であり、明示的に「flowsはcommit不要」と書いた一文は見当たらない) |
| `sync/subscribers.py:84 apply`(`Fx2Error` 非捕捉) | 05_sync-spec.md §3.6「HTTP応答…のみで判定し、いずれかが失敗した場合はエラーログを記録し当該装置を失敗として扱う」 | `pipeline._sync_one_device` が装置単位で捕捉する設計と整合 |
| `sync/subscribers.py:84 apply`(FlowResult 未使用) | 04_fx2-api.md §4.2「部分適用の検出」 | §4.2 は `PATCH /config`(400応答)限定の記述であり、`POST`/`DELETE /flows` の部分適用検出については 04_fx2-api.md に明示規定が見当たらない。05_sync-spec.md §3.5 の「オールオアナッシング」という記述のみを根拠にしている可能性があり、`FlowResult.exist`/`confirmed` を未使用のままでよいという判断がどこかに明文化されているか確認する価値がある |
