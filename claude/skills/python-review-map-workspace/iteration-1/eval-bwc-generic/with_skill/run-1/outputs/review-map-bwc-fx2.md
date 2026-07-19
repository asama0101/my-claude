# 対象範囲

`/home/asama/notebook/bwc-api-tool/src/bwc_provisioner/fx2/` 配下（読み取り専用、変更禁止）。

- `client.py`（264行）— FitelNet FX2 REST API クライアント本体
- `__init__.py`（0行）— 空ファイル。パッケージマーカーのみ。対象外扱い（触れる内容なし）

このパッケージ自体は 2 ファイルのみで小さいため絞り込みは行っていない。ただし `fx2/client.py` は
`core/` 配下の複数モジュールから呼ばれるため、地図には「呼ばれ方」として呼び出し元（1 hop）も含めた。

## 仕様書の探索結果

自動探索の結果、以下を仕様の正典として採用した（プロジェクトルートの `CLAUDE.md` に明記されている）。

- `docs/requirements/spec.html` — 要件定義書 v1.0（機能要件 F-01〜F-14、FX2 REST API 仕様〔セクション12〕、
  非機能要件〔リトライ回数・タイムアウト〕）
- `docs/requirements/business-flow.html` — 業務フロー設計書 v1.0（セクション6「共通サブフロー — FX2
  3ステップ コミットプロトコル」に `fx2/client.py` の `apply_subport_config` と一対一に対応する図解あり）
- `CLAUDE.md`（プロジェクトルート）— 実装済みファイル構成表、非自明な Gotchas 一覧（`traffic-manger`
  のタイポ風表記、PATCH の差分送信方式など）

`REQ-`/`NFR-` 形式の ID は無く、代わりに `F-01`〜`F-14`（機能要件）と `FR-ERR-005`（エラー処理、本文中の
参照のみで独立した定義セクションは見当たらなかった）という ID 体系だった。仕様書は実際に Read してから
対応付けている。

# 全体構成図

```
   api/devices.py ──┐
                     │ show_version()
core/subport_orchestrator.py ──┐
core/sync_engine.py ───────────┼─→ core/orchestrator_utils.py ──→ fx2/client.py (FX2Client)
core/rollback_engine.py ───────┤   (make_fx2_client: Device/AppConfig → FX2Client 生成)
core/flow_id_orchestrator.py ──┘
```

`fx2/client.py` は `core/orchestrator_utils.py:make_fx2_client()`（`orchestrator_utils.py:13-21`）を
唯一の生成経路として使われている。呼び出し元は `api/devices.py`・`subport_orchestrator.py`・
`sync_engine.py`・`rollback_engine.py`・`flow_id_orchestrator.py` の 5 箇所。

# モジュール地図

## `fx2/__init__.py`

**平たく言うと:** 空ファイル。パッケージマーカーのみで役割なし。対象外。

## `fx2/client.py`

**平たく言うと:** FX2 装置への REST API 通信を一手に引き受けるクライアント。subport 設定の
3-step commit（PATCH → refresh → save、失敗時は discard）、flow_id の JSONL 登録/削除/取得、
稼働確認（show version）を提供する。

**なぜ要るか:** `core/` 配下の複数オーケストレーター（subport・flow_id・sync・rollback）が
同じ FX2 通信プロトコル（3-step commit・リトライ・エラー判定）を共有する必要があり、これを
1箇所に集約することで各オーケストレーターは「差分 CLI テキストを渡す」だけで済むようにしている。

**呼ばれ方:**
- `core/orchestrator_utils.py:16` `make_fx2_client()` が唯一のインスタンス生成箇所
- `core/subport_orchestrator.py:62,66,234` `apply_subport_config()`
- `core/rollback_engine.py:71,97,120,137,139` `get_subports_raw()` / `apply_subport_config()` /
  `get_flow_ids_raw()` / `delete_flow_ids()` / `apply_flow_ids()`
- `core/sync_engine.py:40,41,80,97,103` 同上のメソッド群
- `core/flow_id_orchestrator.py:86,118` `apply_flow_ids()` / `delete_flow_ids()`
- `api/devices.py:199` `show_version()`

**主な関数:**

### 例外クラス — `client.py:40-45`

```
FX2CommitError      # PATCH（Step 1）失敗 — discard 送信済み
FX2PostCommitError  # refresh/save（Step 2/3）失敗 — PATCH は適用済み
```

**意図:** business-flow.html セクション6の「PATCH 失敗時のみ discard 可能、refresh/save 失敗時は
discard 不可（自動ロールバック対象）」という区別（`business-flow.html:1621-1622`）を型で表現している。

**確認ポイント:** 呼び出し側（`subport_orchestrator.py`）がこの2つの例外を区別してロールバック要否を
判定しているかは `fx2/` の対象外なので、呼び出し元側での分岐を実際に確認する？

---

### `FX2Client.__init__(device_id, host, username, password, timeout=30) -> None` — `client.py:56-70`

**意図:** 装置ごとのクライアントを構築する。ベース URL は通常 `https://{host}`（spec.html:1560 の
共通仕様と一致）。

**実装の要点:**
- `FX2_BASE_URL_PATTERN` 環境変数が設定されている場合、`host` を無視して全クライアントを同一 URL に
  向ける（`client.py:67-68`、コメントで「ST用の完全URL上書き」と明記）。システムテスト用のフック。
- `timeout` のデフォルトは 30 秒（`client.py:62`）。NFR「1台あたりの FX2 API タイムアウト（デフォルト:
  30秒）」（`spec.html:1405`）と一致。

**確認ポイント:** `FX2_BASE_URL_PATTERN` はテスト用フックとして本体コードに残っている。本番経路では
未設定である前提だが、誤設定時に気づける仕組み（ログ等）は無い。運用上のガードは足りているか確認する？

---

### `_make_patch_body(cli_lines) -> str` — `client.py:76-79`

**平たく言うと:** 差分 CLI 行をテンプレート（`PATCH_WRAPPER`, `client.py:22-28`）に埋め込み、各行に
2スペースインデントを付与する。`spec.html:1580-1590` の PATCH ボディ形式（`traffic-manger accelerator`
〜 `end`）と対応。

**実装の要点:**
- `cli_lines` が空文字列でも例外にはならず、インデント済み空行だけが挿入される（`client.py:78`）。
  呼び出し元が空の差分を渡すケースがあるかは対象外（`core/` 側の確認事項）。

---

### `async apply_subport_config(cli_lines) -> None` — `client.py:81-110`

**意図:** subport 設定を 3-step commit で適用する。`business-flow.html` セクション6の図解
（`business-flow.html:1611-1679`）と、`spec.html:1566-1578`（3ステップ順次実行の表）に一対一で対応。

**実装の要点（制御フロー）:**

```
apply_subport_config(cli_lines)
├─ patch_body 組み立て（_make_patch_body）
├─ Step1: PATCH /api/v1/config（最大3回リトライ）
│  ├─ 失敗 → discard moff 送信（best-effort） → FX2CommitError 送出（client.py:91-96）
│  └─ 成功 →
├─ Step2: POST /api/v1/cli {"command": "refresh moff"}（最大3回リトライ）
│  └─ 失敗 → FX2PostCommitError 送出（client.py:100-103、discard は送らない）
└─ Step3: POST /api/v1/cli {"command": "save moff"}（最大3回リトライ）
   └─ 失敗 → FX2PostCommitError 送出（client.py:107-110）
```

- Step1 失敗時のみ discard を送る点は `business-flow.html:1598`「discard moff — PATCH（Step 1）失敗時
  のみ実行」と一致。
- 3ステップとも同一の `aiohttp.ClientSession`（`async with self._make_session()`）内で実行される
  （`client.py:88`）。セッション生成は1回のみ。

**確認ポイント:** Step2（refresh）が成功し Step3（save）だけ失敗した場合も `FX2PostCommitError` で
一律扱われる（`client.py:107-110`）。呼び出し元が「refresh 済みだが save 未了」という状態をどう扱うかは
`rollback_engine.py`/`subport_orchestrator.py` 側の対象。ここでは区別できない設計だが、それでよいか
確認する？

---

### `async get_subports_raw() -> str` — `client.py:112-123`

**平たく言うと:** `POST /api/v1/cli {"command": "show running | grep subport"}` で現在の subport 設定を
取得する。`spec.html:1607-1614` の「subport 取得」と対応。

**実装の要点:** HTTP 200 以外は `RuntimeError` を送出（リトライなし、`client.py:119-122`）。
`apply_subport_config` の内部ステップと異なり、こちらは `FX2CommitError`/`FX2PostCommitError` ではなく
汎用の `RuntimeError` を使っている。

**確認ポイント:** 取得系（`get_subports_raw`/`get_flow_ids_raw`/`show_version`）はリトライなしの
単発呼び出しだが、書き込み系（`_patch_config`/`_cli_command`）は3回リトライする。この非対称は意図的か
（読み取り失敗は呼び出し元でリトライ判断する設計か）確認する？

---

### `async apply_flow_ids(flow_ids) -> None` — `client.py:125-135`

**平たく言うと:** `POST /api/v1/dynamic-queueing/flows`（`Content-Type: application/jsonl`）で flow_id を
一括登録する。`spec.html:1625-1630` の flow_id プロビジョニングと対応。subport の3-step commit とは
異なり単発 POST のみ（CLAUDE.md の Gotchas 節「flow_id の FX2 API は3-step commit なし」と一致）。

**実装の要点:**
- `flow_ids` が空リストの場合、`body` は空文字列になり、それでも POST は送信される（`client.py:127-131`）。
  空リストで呼ばれるケースを想定しているか、対応するテストが無いため未確認。

---

### `async delete_flow_ids(flow_ids) -> None` — `client.py:137-147`

**平たく言うと:** `DELETE /api/v1/dynamic-queueing/flows` で flow_id を一括削除する。`apply_flow_ids` と
対称的な実装。

**実装の要点:** `apply_flow_ids` 同様、失敗時は個別ステータスに応じた分岐は無く一律 `FX2CommitError`
（`client.py:144-147`）。

---

### `async get_flow_ids_raw() -> str` — `client.py:149-159`

**平たく言うと:** `GET /api/v1/dynamic-queueing/flows` で現在の flow_id 一覧（JSONL）を取得する。
`get_subports_raw` と対になる読み取り系メソッド。HTTP 200 以外は `RuntimeError`。

---

### `async show_version(self) -> dict[str, Any]` — `client.py:161-179`

**意図:** `POST /api/v1/cli {"command": "show version"}` で疎通確認する（F-11「装置の稼働状態・疎通確認」
`spec.html:586`、`/devices/{hostname}/status` `spec.html:1105-1108` に対応）。

**実装の要点:**
- `time.monotonic()` でレイテンシを計測し `{"status": "online", "latency_ms": int}` を返す
  （`client.py:169,178-179`）。
- HTTP 200 以外は `RuntimeError`（`client.py:174-177`）。呼び出し元 `api/devices.py:199-206` は
  この `RuntimeError` を捕捉して `logger.warning` にしている（offline 扱いへの変換は `fx2/` の対象外）。

---

### `_make_session() -> aiohttp.ClientSession` — `client.py:185-191`

**平たく言うと:** 各メソッド呼び出しのたびに新しい `ClientSession`（`TCPConnector(ssl=False)`）を
生成するファクトリ。

**難所: TLS 証明書検証を無効化している**

**何が問題か:** `aiohttp.TCPConnector(ssl=False)`（`client.py:186`）は TLS 証明書検証を行わない。
中間者攻撃に対して脆弱になりうる設定。

**どう解決しているか:** FX2 装置は自己署名証明書を使う社内/閉域網の装置という前提であれば妥当な判断だが、
コード上にその前提を説明するコメントは無い。

**ハマりどころ:** レビュアーがここを見落とすと「TLS 検証なしの HTTPS 通信」に気づかないまま通り過ぎる
可能性がある。意図的な設計判断か、見落としかを確認する必要がある（セキュリティ観点チェックリストにも
再掲）。

---

### `_patch_config(session, body) -> bool` / `_cli_command(session, command) -> bool` — `client.py:193-249`

**平たく言うと:** どちらも同型のリトライループ（最大 `_MAX_RETRIES`=3回、`client.py:30`）。HTTP 200 なら
`True`、それ以外または `aiohttp.ClientError` なら `logger.warning` してリトライ、上限到達で `False` を
返す（例外は送出しない。呼び出し元の `apply_subport_config` が bool を見て例外に変換する）。

**難所: リトライ間隔がプロセス起動時に1回だけ評価される**

**何が問題か:** `_RETRY_INTERVAL = float(os.environ.get("FX2_RETRY_INTERVAL", "1"))`（`client.py:33`）は
モジュール import 時に評価されるモジュールレベル定数。テストで待ち時間をゼロにしたい場合、実行中に
環境変数を変更しても反映されない。

**どう解決しているか:** コメント（`client.py:31-32`）に「STでは subprocess の環境変数に "0" をセットして
起動することでリトライ待機をゼロにする」と明記。プロセスを新規起動するテストでのみ有効な手法。

**ハマりどころ:** 同一プロセス内でのユニットテスト（`aioresponses` を使う `tests/unit/test_fx2_client.py`
など）ではこの環境変数上書きは効かない。実際、`test_fx2_client.py` の3回リトライ系テスト
（`test_apply_subport_config_patch_failure_sends_discard` 等）は `_RETRY_INTERVAL`（デフォルト1秒）分
待つ実装になっているように見える。テスト実行時間への影響は確認したか？

**例外処理/境界値の要点:** `except aiohttp.ClientError as exc`（`client.py:210,239`）で接続エラー系のみを
捕捉しており、`except Exception` のような broad catch ではない。個別ステータスコード分岐は無く
「200以外は一律エラー」という `spec.html:1562`（「エラー判定：HTTP 200以外は一律エラー」）と一致する
実装になっている。

---

### `_discard(session) -> None` — `client.py:251-264`

**平たく言うと:** `discard moff` を best-effort で送信する。失敗しても `logger.warning` のみで例外は
送出しない（呼び出し元は既に `FX2CommitError` を送出する流れのため、discard 自体の失敗で追加の例外は
出さない設計）。`business-flow.html:1621-1622` の「discard moff を実行（refresh 前の状態に戻す）」に
対応。

# レビューチェックリスト

#### 命名/可読性/複雑度

- [ ] `client.py:193-219`（`_patch_config`）と `client.py:221-249`（`_cli_command`）はリトライループの
  構造がほぼ同一（ループ・ログ・sleep）。共通化の余地があるか確認する？（意図的に分けている可能性もある
  ので判定はしない）
- [ ] `client.py:76` `_make_patch_body` の `cli_lines` という引数名は「複数行の文字列」を指しているが、
  型は `str`（リストではない）。呼び出し元での命名との整合を確認する？

#### 例外処理/境界値

- [ ] `client.py:107-110` refresh 成功・save 失敗時と、refresh 失敗時（`client.py:100-103`）が同じ
  `FX2PostCommitError` で区別されない。呼び出し元（`rollback_engine.py`/`subport_orchestrator.py`）で
  「どこまで反映済みか」を判定する必要があるか確認する？
- [ ] `client.py:125-135`（`apply_flow_ids`）・`client.py:137-147`（`delete_flow_ids`）は空リストで
  呼ばれた場合の早期 return が無く、空ボディで POST/DELETE が送信される。空リスト呼び出しが実際に
  発生しうるか呼び出し元を確認する？
- [ ] `client.py:112-123`（`get_subports_raw`）・`client.py:149-159`（`get_flow_ids_raw`）はリトライなし
  の単発呼び出し。`_patch_config`/`_cli_command`（書き込み系）は3回リトライする非対称設計。読み取り系も
  リトライすべきか、意図的な非対称か確認する？

#### テストカバレッジ/テスタビリティ

- [ ] `tests/unit/test_fx2_client.py` には `apply_flow_ids`（69-79行）・`delete_flow_ids`（82-88行）の
  成功パスのテストはあるが、HTTP 200 以外を返す失敗パス（`FX2CommitError` 送出、`client.py:132-135` /
  `client.py:144-147`）のテストが見当たらない。`apply_subport_config`（成功/PATCH失敗/refresh失敗/
  save失敗の4パターン、27-101行）と比べてカバレッジに差がある。追加が必要か確認する？
- [ ] `client.py:185-191`（`_make_session`）は毎回新規セッションを作るため、`tests/unit/test_fx2_client.py`
  は `aioresponses` でモックできている（テスタビリティは確保されている）。一方 `tests/system/stub_fx2.py`
  （実サーバースタブ）を使ったシステムテストが `fx2/client.py` に対して存在するかは確認していない
  （`tests/system/` 配下で `FX2Client` を直接使うテストの有無を確認する？）。
- [ ] `client.py:67`（`FX2_BASE_URL_PATTERN`）・`client.py:33`（`FX2_RETRY_INTERVAL`）はテスト専用の
  環境変数フックが本体コードに直接埋め込まれている。DI（コンストラクタ引数化）ではなく環境変数分岐に
  なっている設計判断について、テスタビリティ上の意図を確認する？

#### セキュリティ/外部入力

- [ ] `client.py:186` `TCPConnector(ssl=False)` は TLS 証明書検証を無効化している。FX2 装置が自己署名
  証明書を使う閉域網前提だとしても、コード上にその根拠のコメントが無い。意図的な設計か確認する？
- [ ] `client.py:69` `aiohttp.BasicAuth(username, password)` で認証情報を保持する。ログ出力
  （`client.py:204-209,211-216,232-238,240-246,258-262`）にリクエスト/レスポンスボディを含めていない点は
  確認できたが、`aiohttp` 自体が Basic 認証ヘッダをデバッグログに出す設定（`aiohttp` の内部ログレベル）に
  なっていないか、呼び出し元のロガー設定と合わせて確認する？
- [ ] `client.py:81`（`apply_subport_config`）が受け取る `cli_lines` は `core/` 側の diff エンジンが
  組み立てた CLI テキストであり、`fx2/` パッケージ自体には入力検証が無い。ISP から受け取った
  subport 名・帯域値がそのまま CLI コマンド文字列に埋め込まれる経路（`spec.html` の
  `downstream_kbps → pir 変換` 節）でエスケープ/検証がどこで行われているか、`fx2/` の対象外のため
  `core/diff_engine.py` 側を確認する？

# 仕様書との対応表

| コード (file:line) | 対応する要件/仕様 | 備考 |
|---|---|---|
| `client.py:81-110 apply_subport_config` | spec.html §12「subport操作」表（1566-1578行）、business-flow.html §6（1553-1686行） | 3-step commit（PATCH→refresh→save、失敗時discard）の手順・エラー判定が一致 |
| `client.py:22-28 PATCH_WRAPPER` | spec.html:1580-1590「PATCH /api/v1/config ボディ形式」 | `traffic-manger accelerator`〜`end` のテンプレートが一致（`traffic-manger`表記はCLAUDE.mdのGotchasで意図的と明記） |
| `client.py:30 _MAX_RETRIES = 3` | spec.html:1484「FX2接続失敗時: リトライ3回後にエラー記録」 | 一致 |
| `client.py:62 timeout: int = 30` | spec.html:1405「FX2 APIタイムアウト（デフォルト: 30秒）」 | 一致 |
| `client.py:112-123 get_subports_raw` | spec.html:1607-1614「subport取得」 | `show running | grep subport` コマンドが一致 |
| `client.py:125-135 apply_flow_ids` / `client.py:137-147 delete_flow_ids` | spec.html:1625-1630「flow_idプロビジョニング」 | POST/DELETE + application/jsonl が一致 |
| `client.py:161-179 show_version` | spec.html:586 F-11「装置の稼働状態・疎通確認」、spec.html:1105-1108 `GET /devices/{hostname}/status` | `show version` コマンド自体はspec.htmlの当該箇所に明記が無く、`{"command": "show version"}` というCLIコマンド名の対応はコードのみが情報源。呼び出し元 `api/devices.py` 側の実装で確認する？ |
| `client.py:251-264 _discard` | business-flow.html:1598,1621-1622「discard moff — PATCH（Step 1）失敗時のみ実行」 | 一致。best-effort（失敗してもwarningのみ）という実装判断はbusiness-flow.html上に明記が見当たらず、コード側の独自判断の可能性がある |
| （対応する仕様記述が見当たらない） `client.py:67-68 FX2_BASE_URL_PATTERN` / `client.py:31-33 FX2_RETRY_INTERVAL` | — | テスト用の環境変数フック。spec.html/business-flow.htmlに記載なし。CLAUDE.mdにも明記なし（コード内コメントのみが情報源） |
| spec.html:1562「エラー判定: HTTP 200以外は一律エラー。個別ステータスコードによる分岐は行わない」 | `client.py:119,155,174,202,230` 各所 | 一致（全メソッドで`resp.status != 200`のみ判定） |

`FR-ERR-005`（spec.html:1568 で参照されているエラー処理方針）は本文中に参照のみで独立した定義セクションが
見当たらなかった。業務フロー設計書側（business-flow.html §6）の記述で実質的な内容を確認した。
