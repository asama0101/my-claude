# ベンダー別パース要点と新ベンダー追加手順

各パーサは config テキストを受け取り、ベンダー中立な**正規化モデル**（`scripts/parsers/base.py` の `Device`）を返す。`build_topology.py` はこのモデルだけを見るので、パーサが差異を吸収する。

## 正規化モデル（base.py）
```python
@dataclass
class Interface:
    name: str
    ip: str | None          # "a.b.c.d/prefixlen"（CIDR 正規化済み）
    description: str | None
    shutdown: bool = False
    vlan: int | None = None

@dataclass
class BgpNeighbor:
    neighbor_ip: str
    peer_as: int | None

@dataclass
class OspfNetwork:
    process: int | None
    network: str            # CIDR
    area: str

@dataclass
class StaticRoute:
    prefix: str             # CIDR
    next_hop: str

@dataclass
class Device:
    hostname: str
    vendor: str             # "cisco_ios" / "juniper_junos"
    asn: int | None
    interfaces: list[Interface]
    bgp: list[BgpNeighbor]
    ospf: list[OspfNetwork]
    static: list[StaticRoute]
```

## パーサ共通インターフェース
各ベンダーモジュールは 2 つの関数を公開する（`parsers/__init__.py` の registry が利用）:
- `detect(text: str) -> bool` — その config が当該ベンダーか判定
- `parse(text: str) -> Device` — 正規化モデルを返す

`parse_configs.py` はファイルごとに registry を回し、`detect` が真の最初のパーサを使う。

## Cisco IOS / IOS-XE（cisco_ios.py）
- 行指向・`!` 区切り。`interface <name>` ブロック内をインデントで把握。
- `hostname X` → hostname。
- `ip address A.B.C.D MASK` → `ip`（マスクは prefixlen に変換。`ipaddress` 使用）。`secondary` は v1 では無視。
- `shutdown`（ブロック内・`no` なし）→ `shutdown=True`。
- `description X` → description。
- `router bgp <asn>` → asn。配下 `neighbor <ip> remote-as <peer>` → BgpNeighbor。
- `router ospf <pid>` 配下 `network <addr> <wildcard> area <a>` → OspfNetwork（wildcard を逆マスクして CIDR 化）。
- `ip route <prefix> <mask> <next_hop>` → StaticRoute（`0.0.0.0 0.0.0.0` → `0.0.0.0/0`）。
- **detect**: `^hostname `・`^interface .*Ethernet`・`^!` 等の IOS 特徴で判定。非空行のうち `^set ` が **40% 超**を占める場合は JunOS とみなし false（registry は JunOS → IOS の順で試すため通常はこのガードに到達しない。閾値が JunOS の 50% とずれているのは、IOS の特徴行が無い純 set 形式を確実に JunOS 側へ寄せるための非対称な安全マージン）。

## Juniper JunOS（juniper_junos.py）— set 形式
- 全行 `set ...` 前提。
- `set system host-name X` → hostname。
- `set interfaces <if> description "X"` → description（クォート除去）。
- `set interfaces <if> unit N family inet address A.B.C.D/PL` → `ip`（既に CIDR）。IF 名は `<if>`（unit は v1 では IF 名に含めない）。
- `set interfaces <if> disable` → shutdown。
- `set routing-options autonomous-system <asn>` → asn。
- `set protocols bgp group <g> neighbor <ip> peer-as <peer>` → BgpNeighbor。
- `set ... ospf area <a> interface <if>` があれば OspfNetwork（area, network は IF の IP から導出可能なら CIDR、無理なら IF 名を network に格納）。v1 は best-effort。
- `set routing-options static route <prefix> next-hop <ip>` → StaticRoute。
- **detect**: 非空行の **過半数（50% 超）** が `^set ` で始まる。

## 新ベンダー追加手順（例: Cisco NX-OS）
1. `scripts/parsers/nxos.py` を作り `detect` / `parse` を実装（`Device` を返す）。
2. `scripts/parsers/__init__.py` の registry リストに追加（detect の特異度が高い順に並べる）。
3. `tests/test_parsers.py` にサンプル config とアサーションを追加。
4. スキーマ・build_topology・renderer は**変更不要**（正規化モデルに合わせるだけ）。
