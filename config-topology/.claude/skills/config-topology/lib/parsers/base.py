"""
正規化モデル（ベンダー中立 dataclass）

各パーサは config テキストを受け取り、この Device を返す。
build_topology.py はこのモデルだけを見るので、パーサが差異を吸収する。

設計判断:
- asn は int | None（BGP/autonomous-system がなければ None）
- Interface.ip は CIDR 正規化済み文字列 or None
- shutdown のデフォルトは False
- vlan のデフォルトは None（v1 では未使用）
- device id はここでは付けない（build_topology の責務）
- switchport は Cisco IOS 専用フィールド。JunOS は l2_l3='l2' で L2 を表現し、
  switchport は常に None（JunOS には switchport コマンドが存在しない）。
- no ip address は「IP 未設定」を示す IOS 構文だが、これを検知して何かをすることはしない
  （ip address コマンドがなければ ip=None になる）。
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

# ================================================================
# モジュール定数（マジック文字列を一元管理）
# ================================================================

ADMIN_UP: str = "up"
ADMIN_DOWN: str = "down"
L2: str = "l2"
L3: str = "l3"
SOURCE_PARSED: str = "parsed"


@dataclass
class Interface:
    name: str
    ip: str | None           # "a.b.c.d/prefixlen"（CIDR 正規化済み）
    description: str | None
    shutdown: bool = False
    vlan: int | None = None
    # IF属性拡充（optional, default None; source は SOURCE_PARSED）
    admin_status: str | None = None   # ADMIN_UP / ADMIN_DOWN（shutdown 由来）
    oper_status: str | None = None    # None（config から取得不可・将来 SNMP 拡張予定）
    mtu: int | None = None            # int | None
    speed: str | None = None          # 文字列（"1000", "1g" 等）
    duplex: str | None = None         # "full" / "half" / None（JunOS set 形式では通常 None）
    l2_l3: str | None = None          # L2 / L3 / None
    switchport: dict | None = None    # {mode, access_vlan?, trunk_vlans?} | None（IOS 専用）
    encapsulation: str | None = None  # "dot1q", "flexible-ethernet-services" 等
    source: str = SOURCE_PARSED       # 固定値 SOURCE_PARSED


@dataclass
class BgpNeighbor:
    neighbor_ip: str
    peer_as: int | None


@dataclass
class OspfNetwork:
    process: int | None
    network: str             # CIDR
    area: str


@dataclass
class StaticRoute:
    prefix: str              # CIDR
    next_hop: str


@dataclass
class Device:
    hostname: str
    vendor: str              # "cisco_ios" / "juniper_junos"
    asn: int | None
    interfaces: list[Interface] = field(default_factory=list)
    bgp: list[BgpNeighbor] = field(default_factory=list)
    ospf: list[OspfNetwork] = field(default_factory=list)
    static: list[StaticRoute] = field(default_factory=list)
