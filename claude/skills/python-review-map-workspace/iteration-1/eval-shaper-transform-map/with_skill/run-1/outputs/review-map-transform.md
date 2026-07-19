# shaper-db `src/shaper_db/transform/` レビュー地図

## 対象範囲

- スコープ: `/home/asama/shaper-db/src/shaper_db/transform/` 配下 4 ファイル(全体スコープ、絞り込みなし)。
  - `common.py`(120行)・`rules.py`(115行)・`subscribers.py`(178行)・`__init__.py`(空)。
- 仕様書: `/home/asama/shaper-db/docs/spec/` 配下 6 文書のうち、主に
  [03_data-spec.md](../../shaper-db/docs/spec/03_data-spec.md)(変換規則・検証規則の正典)と
  [01_requirements.md](../../shaper-db/docs/spec/01_requirements.md)(REQ-xx/NFR-xx)を対応付けに用いた。
  プロジェクトの `CLAUDE.md`「仕様書の参照順」節に明記された正典であることを確認済み。
- 補助資料: コード docstring 中の `P1-VAL-xx`・`P1-RUL-xx`・`P1-SUB-xx`・`ASK-2a/2b`・`design §n` は
  `docs/spec/` ではなく `docs/superpowers/specs/2026-07-18-phase1-transform-diff-design.md`
  (実装設計時の内部設計文書、以下「フェーズ1設計文書」)を指す。これは `docs/spec/` の下位に位置する
  実装決定の記録であり、`docs/spec/03_data-spec.md` 自体を上書きするものではない。対応表では両方を
  併記する。

## 全体構成図

```
        ┌──────────────┐        ┌──────────────────┐
        │  sync/rules.py│        │ sync/subscribers.py│
        └──────┬───────┘        └─────────┬─────────┘
               │ build_rules()             │ build_subscribers()
               ▼                           ▼
        ┌──────────────┐        ┌──────────────────┐
        │transform/rules│        │transform/         │
        │    .py        │        │  subscribers.py   │
        └──────┬───────┘        └─────────┬─────────┘
               │            共通import          │
               └───────────────┬────────────────┘
                                ▼
                      ┌──────────────────┐
                      │ transform/common.py│
                      │ (定数・SkipReason・ │
                      │ TransformSummary・  │
                      │ 共通ヘルパ)          │
                      └──────────────────┘
                                ▲
                                │ Group(config.py)
                      ┌──────────────────┐
                      │     config.py     │
                      └──────────────────┘
```

`rules.py`・`subscribers.py` はいずれも `common.py` の定数・`SkipReason`・`TransformSummary`・
`build_area_group_index`/`new_skip_counts`/`finalize_summary` を import する(DRY)。両者の間に
直接の依存関係はない(独立した純粋関数)。

## モジュール地図

### `src/shaper_db/transform/__init__.py`

**平たく言うと:** 空ファイル。パッケージマーカーのみ。対象外扱いはせず一応触れておく。

### `src/shaper_db/transform/common.py`

**平たく言うと:** `rules.py`・`subscribers.py` が共通で使う識別子/subport/flow_id の検証用正規表現、
スキップ理由 `SkipReason`(enum)、結果サマリ `TransformSummary`(frozen dataclass)、およびそれらを
組み立てる共通ヘルパ関数を集約したモジュール。ロジックらしいロジックは持たない
(`transform/common.py:1-7` の docstring どおり)。

**なぜ要るか:** 識別子の正規表現やスキップ集計ロジックを `rules.py`/`subscribers.py` の両方に
書くと二重管理になる(DRY, docstring 内 `P1-VAL-06`)。1箇所に定義することで、仕様変更時の修正漏れを防ぐ。

**呼ばれ方:** `rules.py:12-21`・`subscribers.py:14-25` の import 文から利用される。

**主な関数:**

##### `new_skip_counts() -> dict[str, int]` — `common.py:73-79`

**意図:** `SkipReason` 5種すべてを0で事前初期化する(フェーズ1設計文書 §「スキップ理由キーは5種」)。

**実装の要点:**
- `{reason.value: 0 for reason in SkipReason}` の辞書内包表記のみ。分岐なし。
- 事前に全キーを用意しておくことで、呼び出し側は `skip_counts[SkipReason.XXX.value] += 1` を
  `KeyError` なく書ける。

##### `freeze_skip_counts(skip_counts: dict[str, int]) -> Mapping[str, int]` — `common.py:82-89`

**意図:** 集計済み辞書を読み取り専用ビューに包む。

**実装の要点:**
- `types.MappingProxyType(skip_counts)` を返すのみ。
- **確認ポイント:** docstring(`common.py:86-88`)に明記の通り、返り値は元の `dict` への「ビュー」であり
  コピーではない。呼び出し元が凍結後に元の `skip_counts` を変更すると、凍結したはずの
  `TransformSummary.skipped_by_reason` も変化しうる。`rules.py`/`subscribers.py` の呼び出しパターン
  (ループ終了後に一度だけ `finalize_summary` を呼ぶ)では実害はなさそうだが、将来的な呼び出し順序の
  変更に注意が要る箇所。

##### `finalize_summary(total_input, emitted, skip_counts, clamped=0) -> TransformSummary` — `common.py:92-106`

**意図:** `skipped = total_input - emitted` という不変条件(フェーズ1設計文書「サマリ不変条件」、
config の area_ids 互いに素検証 `P1-CFG-01` に依存)で `TransformSummary` を組み立てる。

**実装の要点:**
- 分岐なし。`skipped` は `skip_counts` の合計ではなく `total_input - emitted` の引き算で求めている点に注意。
- **確認ポイント:** `skip_counts` の合計と `total_input - emitted` が一致することは、コード上では
  検証(assert)されていない。単一グループ割当の前提(`config.py` 側の検証)が崩れた場合に静かに
  不整合な値になる可能性があるかどうか、確認する価値がある(後述チェックリストにも記載)。

##### `build_area_group_index(groups: Sequence[Group]) -> dict[str, str]` — `common.py:109-120`

**意図:** `poi_id`(4桁ゼロ埋め文字列) → 所属グループ名 の索引を構築する
(`03_data-spec.md` §2.4、QA決定事項 #32 の4桁ゼロ埋め正規化)。

**実装の要点:**
- 2重ループ(`groups` × `group.area_ids`)。`f"{area_id:04d}"` で整数を4桁ゼロ埋め文字列化してから
  index のキーにする。
- 各 `poi_id` が高々1グループに属するという前提(`P1-CFG-01`、config側で重複を検証済み)に依存しており、
  本関数自体は重複時の後勝ち上書きに関するチェックを行っていない(前提が破られた場合は後勝ちで
  上書きされる)。

## `src/shaper_db/transform/rules.py`

**平たく言うと:** 外部DBのルール表(4フィールドの行)から FX2 の subport に相当する `Rule` を構築する。
`03_data-spec.md` §1.1・§2.2 に対応。

**なぜ要るか:** 装置に投入する「望ましい状態」のうちルール(subport)部分を、生のDB行から検証・変換して
組み立てる、変換ロジックの中核の一つ。

**呼ばれ方:** `sync/rules.py` から `build_rules(...)` として呼ばれる(想定。`sync/rules.py` は
本タスクのスコープ外だが呼び出し元として存在を確認: `grep -rn "build_rules" src/shaper_db/sync/rules.py`)。

**主な関数:**

##### `build_rules(rule_rows, groups, pir_max_kbps) -> RulesResult` — `rules.py:44-115`

**意図:** ルール表の各行を検証・変換して `Rule` のタプルとサマリを返す。処理順序は docstring
(`rules.py:50-57`)に明記: arity→識別子形式→型変換→グループ割当→subport形式検証→pirクランプ、という
順で、仕様書 `03_data-spec.md` §2.2・§3.1・§5、REQ-09・REQ-10・REQ-04 に対応。

**実装の要点(制御フロー):**
```
build_rules(rule_rows, groups, pir_max_kbps)
├─ area_group_index を事前構築(ループ外, common.build_area_group_index)
└─ 各行について:
   ├─ arity != 4 → type_error でスキップ (rules.py:71-73)
   ├─ isp_code/poi_id が識別子形式regex不一致 → identifier_format でスキップ (rules.py:76-78)
   ├─ pipe_band が int変換不能(ValueError) → type_error でスキップ (rules.py:80-84)
   ├─ fair_use_flg が "t"/"f" 以外 → type_error でスキップ (rules.py:86-92)
   ├─ poi_id に対応するグループが無い → no_group でスキップ (rules.py:94-97)
   ├─ 生成したルール名がsubport形式regex不一致 → identifier_format でスキップ (rules.py:99-102)
   │  (docstring注記: "常に満たすが DRY検証実施" = 03_data-spec.md §3.1 の
   │   「サービスコード7字+地域エリアID4字=12字固定は常にsubport上限15字を満たす」という
   │   仕様上の保証を、コード側でも再検証している防御的な二重チェック)
   ├─ pipe_band > pir_max_kbps → pir_max_kbps にクランプ + clamped カウント (rules.py:104-107、
   │  スキップにはしない。QA決定事項#22どおり)
   └─ 上記すべて通過 → Rule を追加、emitted += 1
```

**確認ポイント:** `fair_use_flg` の分岐(`rules.py:86-92`)は `t`/`f` 以外を全て `type_error` に
分類しているが、`03_data-spec.md` の記述上も「psql の真偽値表現 t/f」以外は型不正相当という理解で
一致しているか確認する価値がある(スキップ理由の分類自体は妥当に見える)。

## `src/shaper_db/transform/subscribers.py`

**平たく言うと:** 顧客CSV・エリア表(いずれも文字列フィールド行)から、ロンゲストマッチで所属エリアを
決定し、FX2 の flow に相当する `Subscriber` を構築する。`03_data-spec.md` §1.2・§1.3・§2.1・§2.3 に対応。
4ファイル中もっとも複雑なモジュール(178行、非自明な分岐が最多)。

**なぜ要るか:** 「望ましい状態」のうち加入者(flow)部分の構築ロジック。ロンゲストマッチという
非自明なアルゴリズムを含む。

**呼ばれ方:** `sync/subscribers.py` から `build_subscribers(...)` として呼ばれる想定
(本タスクのスコープ外だが呼び出し元として存在を確認)。

**主な関数:**

##### `_build_area_index(area_rows) -> dict[int, dict[int, str]]` — `subscribers.py:53-73`

**意図:** エリア表から `{prefix_len: {正規化ネットワークアドレス(int): poi_id}}` の索引を構築する。
`03_data-spec.md` §2.1「プレフィックス長ごとにハッシュテーブル化」に対応。ビルド毎に1回だけ構築し、
顧客ループ内では再構築しない(フェーズ1設計文書 `R8`、性能上の意図)。

**実装の要点:**
- arity != 2 → 索引に入れずスキップ(`subscribers.py:62-63`。ここではカウントされず、単に索引に
  含まれないだけ。行スキップのサマリ計上は無い)。
- `poi_id` が `^[0-9]{4}$` 不一致 → 索引に入れない(`subscribers.py:65-66`)。
- `ipaddress.IPv6Network(poi_prefix, strict=False)` がパース不能(ValueError) → 索引に入れない
  (`subscribers.py:67-70`)。
- **確認ポイント:** エリア表側の不正行(arity不一致・poi_id形式違反・パース不能)は
  `SkipReason` によるカウントが一切行われない(フェーズ1設計文書「エリア表の不正行は索引構築時
  スキップ(ASK-2)」「エリア表の完全性検証は fetch(フェーズ2)の責務」という設計判断どおり)。
  `03_data-spec.md` §4 のスキップ対象一覧(顧客CSV由来の行スキップ)とは別扱いになっている点は
  仕様上の意図的な区別かどうか、レビュー時に読み比べる価値がある。

##### `_truncate_to_length(addr_int, length) -> int` — `subscribers.py:76-83`

**意図:** IPv6アドレス整数値を上位 `length` ビットへビットマスクで切り詰める。`ipaddress.IPv6Network`
オブジェクト生成のオーバーヘッドを避け、整数演算のみで行う(NFR-01のスケール要件、フェーズ1設計文書 `R1`)。

**実装の要点:** `mask = (~((1 << (128 - length)) - 1)) & _IPV6_FULL_MASK` というビット演算。分岐なし。

##### 難所: IPv6ロンゲストマッチのビットマスク実装

**何が問題か:** `ipaddress` モジュールの高レベルAPI(`IPv6Network` オブジェクトを毎回生成して
`subnet_of`等で判定)は顧客最大600万件(NFR-01)の規模では低速になりうる。

**どう解決しているか:** エリア索引をプレフィックス長ごとに分割し、各長さについて「顧客アドレスを
その長さに切り詰めた整数値」でハッシュ引き(`dict.get`)するだけの O(1) 判定に落とし込んでいる
(`_longest_match`)。

**コード抜粋:** `subscribers.py:82` `mask = (~((1 << (_IPV6_BIT_LENGTH - length)) - 1)) & _IPV6_FULL_MASK`

**ハマりどころ:** ビットマスク演算は一見して正しさが分かりにくい。`length=128`(ホストアドレス
そのもの)や `length=0`(全アドレス一致)の境界でオーバーフロー/アンダーフローしないか、単体テストで
境界値が押さえられているか確認する価値がある(下記チェックリストにも記載)。

##### `_longest_match(area_index, sorted_area_lengths, addr_int, client_len) -> str | None` — `subscribers.py:86-102`

**意図:** 顧客ネットワークに最長一致するエリアの `poi_id` を返す。`03_data-spec.md` §2.1「照合対象は
顧客プレフィックス長以下のエリア長に限り、長い順に走査する」に対応。

**実装の要点(制御フロー):**
```
_longest_match(area_index, sorted_area_lengths, addr_int, client_len)
└─ sorted_area_lengths(降順)を順に走査
   ├─ length > client_len → 照合対象外としてスキップ (subscribers.py:96-97、
   │  03_data-spec.md §2.1「顧客プレフィックスより長いエリアプレフィックスは照合対象としない」)
   ├─ 切り詰めたaddr_intでarea_index[length]を引く
   │  ├─ 一致あり → その poi_id を即return(最初に一致した=最長一致)
   │  └─ 一致なし → 次の長さへ
   └─ 全長さで不一致 → None を返す(呼び出し側で no_area スキップ)
```

**確認ポイント:** `sorted_area_lengths` は呼び出し側(`build_subscribers`)がループ外で1回だけ
ソート済みのものを渡す設計(`subscribers.py:92-93` docstring、フェーズ1設計文書 `R8`)。この関数自体は
引数として受け取った `sorted_area_lengths` が本当に降順ソート済みかを検証していない(呼び出し側の
契約に依存)。呼び出し元が1箇所(`build_subscribers`)のみなら実害は小さいが、契約が暗黙である点は
留意。

##### `build_subscribers(customer_rows, area_rows, groups) -> SubscribersResult` — `subscribers.py:105-178`

**意図:** 顧客CSV・エリア表から `Subscriber` を構築する。処理順序は docstring
(`subscribers.py:112-117`)に明記: arity→識別子/UserPrefix形式→ロンゲストマッチ→
subport/flow_id生成・形式検証→グループ割当。`03_data-spec.md` §1.3・§2.1・§2.3・§2.4・§3 に対応。

**実装の要点(制御フロー):**
```
build_subscribers(customer_rows, area_rows, groups)
├─ area_index を事前構築(_build_area_index、ループ外)
├─ sorted_area_lengths を事前ソート(ループ外)
├─ area_group_index を事前構築(common.build_area_group_index、ループ外)
└─ 各顧客行について:
   ├─ arity != 3 → type_error でスキップ (subscribers.py:132-134)
   ├─ isp_code/customer_no が識別子形式regex不一致 → identifier_format でスキップ (:137-139)
   ├─ UserPrefix が IPv6Network としてパース不能(ValueError) → address_format でスキップ (:141-145)
   ├─ prefixlen が {56, 64} 以外 → address_format でスキップ (:146-148)
   ├─ ロンゲストマッチ失敗(_longest_match が None) → no_area でスキップ (:150-155)
   ├─ 生成したsubportがsubport形式regex不一致 → identifier_format でスキップ (:157-160)
   ├─ 生成したflow_idがflow_id形式regex不一致 → identifier_format でスキップ (:162-165)
   ├─ poi_idに対応するグループが無い → no_group でスキップ (:167-170)
   └─ 上記すべて通過 → Subscriber を追加、emitted += 1
```

**確認ポイント:** `flow_id` は `f"{customer_no}@{user_prefix}@{subport}"`(`subscribers.py:162`)で
組み立てられる。`user_prefix` はCSVから受け取った生の文字列(パース前の表記)をそのまま埋め込んでいる
(`ipaddress.IPv6Network` でパースし直した正規化後の文字列ではない)。`03_data-spec.md` §2.3の
「顧客IPv6プレフィックス」がCSV表記そのものを指すのか正規化後を指すのか、仕様と実装の表記揺れ
(大文字/小文字・省略形の違い等)の余地がないか確認する価値がある。

## レビューチェックリスト

#### 命名/可読性/複雑度

- [ ] `subscribers.py:105-178` の `build_subscribers` は8段の検証・スキップ分岐を持つ単一関数。
  `rules.py:44-115` の `build_rules` と共通する「行ごとに検証してスキップ理由を積む」構造を、
  さらに関数分割する余地があるか確認する？(現状は分岐ごとに `continue` する素直なフラット構造では
  あるため、可読性への実害は小さいかもしれない)
- [ ] `subscribers.py:53` の `_build_area_index` の戻り値型 `dict[int, dict[int, str]]` は
  「外側キー=プレフィックス長、内側キー=正規化ネットワークアドレス整数値」という意味がシグネチャからは
  読み取れない。docstring(`:54-58`)を読めば分かるが、型エイリアスや変数名だけで意図が伝わるか確認する？

#### 例外処理/境界値

- [ ] `subscribers.py:82` の `_truncate_to_length` は `length=0`(全ビットマスク)や `length=128`
  (無視ビットなし)の境界で正しく動作するか、対応するテストが境界値を押さえているか確認する？
- [ ] `common.py:92-106` の `finalize_summary` は `skipped = total_input - emitted` を
  `skip_counts` の合計と突き合わせるassertを持たない。前提(`P1-CFG-01`: config の area_ids が
  互いに素)が崩れた場合に不整合なサマリが静かに生成されないか確認する？
- [ ] `subscribers.py:62-70` の `_build_area_index` は不正なエリア表行(arity不一致・poi_id形式
  違反・prefixパース不能)を `SkipReason` によるカウント無しで黙って索引から除外する。これは
  `03_data-spec.md` §4 のスキップ対象一覧(顧客CSV由来)とは異なる扱いだが、意図した設計か確認する？

#### テストカバレッジ/テスタビリティ

- [ ] `tests/unit/test_rules.py`(186行、`test_rul01`〜`test_rul18`)・
  `tests/unit/test_subscribers.py`(237行、`test_sub01`〜`test_sub20`)にそれぞれ対応する単体テストが
  存在することを確認済み。クランプ境界(`test_rul05`/`test_rul06`)・ロンゲストマッチの複数長
  (`test_sub01`〜`test_sub06`)など主要分岐は押さえられている。
- [ ] `transform/common.py` 単体を対象とした `tests/unit/test_common.py` に相当するファイルは
  見当たらない(`find tests -iname "*common*"` で確認)。`build_area_group_index`・
  `new_skip_counts`・`freeze_skip_counts`・`finalize_summary` は `test_rules.py`/
  `test_subscribers.py` 経由の間接テストのみになっていないか確認する？
- [ ] `subscribers.py:_longest_match` の「`sorted_area_lengths` は呼び出し側が降順ソート済みで
  渡す」という暗黙契約について、ソートされていない引数を渡した場合の単体テストがあるか確認する？
  (無くても実害が小さい可能性はあるが、契約が暗黙であることの確認事項として記載)

#### セキュリティ/外部入力

- [ ] `rules.py`・`subscribers.py` はいずれも外部DB(ルール表・エリア表)・外部SFTP(顧客CSV)由来の
  生文字列を扱う。フォーマット検証(`common.py` の正規表現)を通過した値のみが `Rule`/`Subscriber`
  に格納されるため、直接的なインジェクションのリスクは低いように見えるが、`subscribers.py:162`
  の `flow_id` 組み立てで `user_prefix`(CSV生値)をそのまま文字列結合している点は、
  `FLOW_ID_PATTERN` の事後検証(`:163-165`)に依存した設計であることを認識した上でよいか確認する？
- [ ] `common.py`・`rules.py`・`subscribers.py` のいずれもログ出力を行っていない(ログは呼び出し側
  `sync/*.py` の責務、フェーズ1設計文書「ログ・終了コード写像・外部I/Oはフェーズ4以降」と整合)。
  このスコープでは機密情報のログ混入に関する該当箇所なし。

## 仕様書との対応表

| コード (file:line) | 対応する要件/仕様 | 備考 |
|---|---|---|
| `transform/common.py:22-34 SkipReason` | 03_data-spec.md §4(REQ-09)、フェーズ1設計文書「スキップ理由キーは5種」 | 5種のスキップ理由(identifier_format/type_error/address_format/no_area/no_group)が §4 の列挙(パースエラー・所属エリア決定不能・グループ未属・検証規則違反)と対応するか目視確認 |
| `transform/common.py:37-44 TransformSummary` | 01_requirements.md REQ-12(件数サマリのログ出力要件) | サマリ自体はログ出力しない(呼び出し側の責務)。フィールド(total_input/emitted/skipped/skipped_by_reason/clamped)がREQ-12「取得件数・スキップ件数」を満たす構造か確認 |
| `transform/common.py:51-53 SERVICE_CODE_PATTERN` | 03_data-spec.md §3.1(表: サービスコード `^[A-Z]{2}[0-9]{2}-[0-9]{2}$`) | 正規表現が仕様書の表と一致(目視確認済み: 完全一致) |
| `transform/common.py:52 AREA_ID_PATTERN` | 03_data-spec.md §3.1(地域エリアID `^[0-9]{4}$`) | 一致確認済み |
| `transform/common.py:53 CUSTOMER_ID_PATTERN` | 03_data-spec.md §3.1(顧客ID `^[A-Z]{3}[0-9]{8,12}$`) | 一致確認済み |
| `transform/common.py:59 SUBPORT_NAME_PATTERN` | 03_data-spec.md §3.2(ルール名/subport名: 1〜15字、`0-9A-Za-z._~-`) | 一致確認済み(FX2 V20.00(00)の実装上の制限に従うと明記) |
| `transform/common.py:65 FLOW_ID_PATTERN` | 03_data-spec.md §3.3(加入者ID/flow_id: 1〜127字、拡張文字集合) | 一致確認済み |
| `transform/common.py:109-120 build_area_group_index` | 03_data-spec.md §2.4(グループへの割当)、QA決定事項#32(4桁ゼロ埋め正規化) | `f"{area_id:04d}"` が §2.4 の正規化規則と一致 |
| `transform/rules.py:44-115 build_rules` | 01_requirements.md REQ-04(望ましい状態生成)、03_data-spec.md §2.2(ルール名生成)・§1.1(ルール表入力) | 処理順序はdocstring(`:50-57`)にREQ番号無しで記述。フェーズ1設計文書のP1-RUL-01〜10と対応 |
| `transform/rules.py:104-107 pirクランプ` | 03_data-spec.md §5(単位・値域)、QA決定事項#22 | クランプ(スキップしない)という仕様が実装(`clamped`カウント、スキップ対象外)と一致 |
| `transform/rules.py:99-102 subport形式再検証` | 03_data-spec.md §3.1(「12字固定であるため15字上限を常に満たす」の裏付け、QA決定事項#12) | 仕様上「常に満たす」とされる検証を実装でも二重に行っている(DRY目的の防御的実装。フェーズ1設計文書に明記) |
| `transform/subscribers.py:105-178 build_subscribers` | 01_requirements.md REQ-04、03_data-spec.md §1.2・§1.3・§2.1・§2.3・§2.4 | フェーズ1設計文書のP1-SUB-01〜10と対応。処理順序がdocstring(`:112-117`)と一致するか確認済み |
| `transform/subscribers.py:_build_area_index` | 03_data-spec.md §1.2(エリア表)、フェーズ1設計文書ASK-2「エリア表の不正行は索引構築時スキップ」 | エリア表の完全性検証はfetch層(フェーズ2、本スコープ外)の責務と明記されており、本モジュールでの黙殺は仕様上の役割分担 |
| `transform/subscribers.py:86-102 _longest_match` | 03_data-spec.md §2.1(ロンゲストマッチ、「顧客プレフィックス長以下のエリア長のみ照合」) | 一致確認済み |
| `transform/subscribers.py:146-148 UserPrefix長検証` | 03_data-spec.md §1.3(`/56`または`/64`のCIDR表記) | `_VALID_USER_PREFIX_LENGTHS = (56, 64)` が一致 |
| `transform/subscribers.py:162 flow_id生成` | 03_data-spec.md §2.3(加入者ID生成規則) | `{顧客ID}@{顧客IPv6プレフィックス}@{ルール名}` の順序・区切り文字が一致 |
| `transform/rules.py`・`subscribers.py` 全体 | 01_requirements.md NFR-04(標準ライブラリのみ依存) | `re`・`ipaddress`・`dataclasses`・`enum`・`collections.abc`のみimport。外部ライブラリ依存なし(確認済み) |
| `transform/subscribers.py:_truncate_to_length`/`_build_area_index` | 01_requirements.md NFR-01(顧客最大600万件のスケール) | ビットマスク演算・ループ外での索引事前構築というR1/R8の設計判断がNFR-01を満たす方向性か確認(ベンチマーク自体は本スコープ外) |

対応が見つからない実装・仕様書に書かれているが実装が見当たらないものは、上記調査の範囲では
見当たらなかった(=`common.py`/`rules.py`/`subscribers.py` の主要ロジックは `03_data-spec.md`・
`01_requirements.md` のいずれかの記述に遡れた)。
