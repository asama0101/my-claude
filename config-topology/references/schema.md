# `topology.json` スキーマ仕様

`config-topology` の中間表現。**ベンダー中立**で、パーサ層の出力（正規化モデル）を `build_topology.py` が結線推論して組み立てる。レンダラー（`render_topology.py`）と将来の別出力（Mermaid 等）はこの JSON だけを入力とする。

## 目次
- [設計原則](#設計原則)
- [トップレベル構造](#トップレベル構造)
- [devices](#devices)
- [interfaces](#interfaces)
- [links](#links)
- [segments](#segments)
- [routing](#routing)
- [ID 採番規則](#id-採番規則)
- [拡張方法](#拡張方法)

## 設計原則
- **IP は interface に帰属する**。機器に直接 IP を持たせない（実機と同じ構造）。
- **物理層（devices / interfaces / links / segments）と論理層（routing）を分離**。レンダラーはレイヤートグルで重ねる。
- **由来を保持する**: `links[].kind` で結線の根拠（初版は `inferred-subnet`）を残し、将来 CDP/LLDP 由来を加算できるようにする。
- **破壊しない拡張**: 新しいプロトコルは `routing` のキー追加、機器固有の追加情報は `devices[].sections` で吸収する。既存フィールドの意味は変えない。

## トップレベル構造
| キー | 型 | 説明 |
|-----|----|------|
| `title` | string | 図のタイトル。既定 `"Network Topology (config-derived)"` |
| `generated_from` | string[] | 元になった config ファイル名（読み込み順） |
| `devices` | object[] | 機器 |
| `interfaces` | object[] | インターフェース（IP はここ） |
| `links` | object[] | 2 機器間の point-to-point 結線 |
| `segments` | object[] | 3 メンバー以上が同一サブネットを共有する L2 セグメント |
| `routing` | object | プロトコル名をキーにした論理オーバーレイ |

## devices
| フィールド | 型 | 説明 |
|-----------|----|------|
| `id` | string | 機器 ID（[採番規則](#id-採番規則)） |
| `hostname` | string | config 上のホスト名（verbatim） |
| `vendor` | string | `cisco_ios` / `juniper_junos`（パーサ識別子） |
| `as` | int \| null | ローカル AS 番号（BGP/autonomous-system が無ければ null） |
| `sections` | object[] | 拡張枠（初版は空配列）。`{"title": "...", "rows": [...]}` 形式で任意データを添付可能 |

## interfaces
| フィールド | 型 | 説明 |
|-----------|----|------|
| `id` | string | `"<device_id>::<name>"` |
| `device` | string | 所属機器 ID |
| `name` | string | IF 名（config 上の表記。例 `GigabitEthernet0/0` / `ge-0/0/0`） |
| `ip` | string \| null | `"a.b.c.d/prefixlen"`（CIDR 正規化済み）。IP 未設定 IF は null |
| `vlan` | int \| null | access/SVI の VLAN（v1 では基本 null。L2 は将来拡張） |
| `description` | string \| null | IF の description |
| `shutdown` | bool | 管理停止状態。`true` のIFは結線推論から除外する |

## links
2 機器のちょうど 2 つの IF が同一サブネットを共有するとき 1 本生成。
| フィールド | 型 | 説明 |
|-----------|----|------|
| `a_device` / `b_device` | string | 端点機器 ID（`a` < `b` で安定ソート） |
| `a_if` / `b_if` | string | 端点 IF 名 |
| `subnet` | string | 共有サブネット CIDR（例 `10.0.0.0/30`） |
| `kind` | string | 結線の由来。初版は常に `"inferred-subnet"` |

`links` には `id` を設けない（`segments` とは異なる）。リンクは `(subnet, a_device, a_if, b_device, b_if)` の複合キーで一意に定まるため。将来 CDP/LLDP 由来の結線を混在させる際は `kind` で由来を区別する。

## segments
同一サブネットに **3 つ以上** の IF が属するとき、L2 セグメント（スイッチ/共有メディア相当）として 1 ノード生成し、各 IF を接続する。
| フィールド | 型 | 説明 |
|-----------|----|------|
| `id` | string | `"seg-<subnet>"`（`/` と `.` は `_` に置換。例 `seg-192_168_1_0_24`） |
| `subnet` | string | サブネット CIDR |
| `members` | string[] | 接続する interface ID の配列（安定ソート） |

## routing
プロトコル名をキーにした dict。**新プロトコルはキーを足すだけ**でスキーマを壊さない。

### `bgp`（object[]）
| フィールド | 型 | 説明 |
|-----------|----|------|
| `device` | string | 機器 ID |
| `local_as` | int | ローカル AS |
| `local_ip` | string \| null | neighbor と同一サブネットにある自 IF の IP（解決できなければ null） |
| `neighbor_ip` | string | ネイバー IP |
| `peer_as` | int \| null | ピア AS |
| `type` | string | `ebgp`（local_as ≠ peer_as）/ `ibgp`（一致）/ `unknown`（peer_as 不明） |

### `ospf`（object[]）
network 文 1 件につき 1 エントリ。
| フィールド | 型 | 説明 |
|-----------|----|------|
| `device` | string | 機器 ID |
| `process` | int \| null | プロセス ID（JunOS は null 可） |
| `network` | string | CIDR（IOS の wildcard は逆マスクして CIDR 化） |
| `area` | string | エリア（`"0"` など。文字列で保持） |

### `static`（object[]）
| フィールド | 型 | 説明 |
|-----------|----|------|
| `device` | string | 機器 ID |
| `prefix` | string | 宛先 CIDR（`0.0.0.0/0` など） |
| `next_hop` | string | ネクストホップ IP |

## ID 採番規則
- **device id**: `hostname` を小文字化し、英数字・ハイフン以外を `-` に置換。**最初の出現はサフィックスなし、2 番目は `-2`、3 番目は `-3`**（例: hostname が `R1`,`R1` → `r1`,`r1-2`）。さらに、既存の別 id（例 hostname `R1-2` 由来の `r1-2`）と衝突する場合は、衝突しない番号までカウントを繰り上げて一意性を保証する。空 hostname は `device`,`device-2`,...。
- **interface id**: `"<device_id>::<name>"`（name は config 表記のまま）。
- **segment id**: `"seg-" + subnet`（`.` と `/` を `_` に置換）。

## 拡張方法
| 追加したいもの | 方法 | スキーマ影響 |
|--------------|------|------------|
| 新ベンダー | パーサを足す（正規化モデルに合わせる） | なし |
| 新プロトコル（VRRP 等） | `routing` に新キー | なし（加算） |
| 機器固有の追加情報 | `devices[].sections` に append | なし（加算） |
| CDP/LLDP 由来リンク | `links[].kind` に新値 | なし（加算） |
