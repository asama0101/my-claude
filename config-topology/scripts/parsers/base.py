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
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field


@dataclass
class Interface:
    name: str
    ip: str | None           # "a.b.c.d/prefixlen"（CIDR 正規化済み）
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
