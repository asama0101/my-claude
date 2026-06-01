"""
Juniper JunOS パーサ（set 形式）

全行 `set ...` 形式のコンフィグをパースし、正規化 Device を返す。

パース規則（vendor-parsing.md より）:
- set system host-name X → Device.hostname
- set interfaces <if> description "X" → description（クォート除去）
- set interfaces <if> unit N family inet address A.B.C.D/PL → ip
- set interfaces <if> disable → shutdown=True
- set routing-options autonomous-system <asn> → Device.asn
- set protocols bgp group <g> neighbor <ip> peer-as <peer> → BgpNeighbor
- set routing-options static route <prefix> next-hop <ip> → StaticRoute
- OSPF: best-effort（v1）

IF 名の取り扱い:
- `set interfaces <if>` の <if> 部分をそのまま使う
- unit は名前に含めない（ge-0/0/0 unit 0 → name="ge-0/0/0"）
"""

from __future__ import annotations

import re

from .base import BgpNeighbor, Device, Interface, OspfNetwork, StaticRoute


def detect(text: str) -> bool:
    """
    JunOS set 形式 config かどうかを判定。

    行の過半数が `set ` で始まること。
    """
    if not text.strip():
        return False

    lines = text.splitlines()
    non_empty = [ln for ln in lines if ln.strip()]
    if not non_empty:
        return False

    set_count = sum(1 for ln in non_empty if ln.strip().startswith("set "))
    return set_count / len(non_empty) > 0.5


def _strip_quotes(s: str) -> str:
    """前後のダブルクォートを除去する。"""
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s


def parse(text: str) -> Device:
    """
    JunOS set 形式コンフィグをパースして Device を返す。
    """
    hostname = ""
    asn: int | None = None
    bgp_neighbors: list[BgpNeighbor] = []
    ospf_networks: list[OspfNetwork] = []
    static_routes: list[StaticRoute] = []

    # IF ごとのデータを収集するための辞書
    # key: if_name, value: dict with keys ip, description, shutdown
    if_data: dict[str, dict] = {}

    def ensure_if(name: str) -> None:
        if name not in if_data:
            if_data[name] = {"ip": None, "description": None, "shutdown": False}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("set "):
            continue
        # "set " を除去してトークン分割
        rest = stripped[4:]

        # set system host-name X
        m = re.match(r'^system\s+host-name\s+(\S+)', rest)
        if m:
            hostname = m.group(1)
            continue

        # set interfaces <if> description "X"
        m = re.match(r'^interfaces\s+(\S+)\s+description\s+(.*)', rest)
        if m:
            if_name = m.group(1)
            desc = _strip_quotes(m.group(2).strip())
            ensure_if(if_name)
            if_data[if_name]["description"] = desc
            continue

        # set interfaces <if> unit N family inet address A.B.C.D/PL
        # 先勝ち: 既に ip が設定済みの場合は上書きしない
        m = re.match(r'^interfaces\s+(\S+)\s+unit\s+\d+\s+family\s+inet\s+address\s+(\S+)', rest)
        if m:
            if_name = m.group(1)
            ip = m.group(2)
            ensure_if(if_name)
            if if_data[if_name]["ip"] is None:
                if_data[if_name]["ip"] = ip
            continue

        # set interfaces <if> disable
        m = re.match(r'^interfaces\s+(\S+)\s+disable$', rest)
        if m:
            if_name = m.group(1)
            ensure_if(if_name)
            if_data[if_name]["shutdown"] = True
            continue

        # set routing-options autonomous-system <asn>
        m = re.match(r'^routing-options\s+autonomous-system\s+(\d+)', rest)
        if m:
            asn = int(m.group(1))
            continue

        # set protocols bgp group <g> neighbor <ip> peer-as <peer>
        m = re.match(r'^protocols\s+bgp\s+group\s+\S+\s+neighbor\s+(\S+)\s+peer-as\s+(\d+)', rest)
        if m:
            bgp_neighbors.append(BgpNeighbor(
                neighbor_ip=m.group(1),
                peer_as=int(m.group(2)),
            ))
            continue

        # set routing-options static route <prefix> next-hop <ip>
        m = re.match(r'^routing-options\s+static\s+route\s+(\S+)\s+next-hop\s+(\S+)', rest)
        if m:
            static_routes.append(StaticRoute(
                prefix=m.group(1),
                next_hop=m.group(2),
            ))
            continue

        # OSPF (best-effort v1):
        # set protocols ospf area <a> interface <if>
        m = re.match(r'^protocols\s+ospf\s+area\s+(\S+)\s+interface\s+(\S+)', rest)
        if m:
            area = m.group(1)
            if_ref = m.group(2)
            ospf_networks.append(OspfNetwork(
                process=None,
                network=if_ref,   # v1: IF 名を格納（build_topology で IP から導出可能）
                area=area,
            ))
            continue

    # IF データを Interface リストに変換（収集順を保持）
    interfaces: list[Interface] = []
    for name, data in if_data.items():
        interfaces.append(Interface(
            name=name,
            ip=data["ip"],
            description=data["description"],
            shutdown=data["shutdown"],
        ))

    return Device(
        hostname=hostname,
        vendor="juniper_junos",
        asn=asn,
        interfaces=interfaces,
        bgp=bgp_neighbors,
        ospf=ospf_networks,
        static=static_routes,
    )
