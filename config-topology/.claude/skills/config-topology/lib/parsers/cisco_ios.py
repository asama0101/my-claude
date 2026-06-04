"""
Cisco IOS / IOS-XE パーサ

行指向・`!` 区切り形式のコンフィグをパースし、正規化 Device を返す。

パース規則（vendor-parsing.md より）:
- hostname X → Device.hostname
- interface <name> ブロック:
  - ip address A.B.C.D MASK → addresses に {af:"v4", ip:"...", prefix:n} エントリを追加。
    secondary は addresses に secondary=True で収録（無視せず全て保持）。
  - ipv6 address X:Y:Z/PL → addresses に {af:"v6", ip:"正規化済みアドレス", prefix:n} エントリを追加。
  - shutdown → shutdown=True
  - no shutdown → shutdown=False
  - description X → description
- router bgp <asn> → Device.asn。配下 neighbor <ip> remote-as <peer> → BgpNeighbor
- router ospf <pid> 配下 network <addr> <wildcard> area <a> → OspfNetwork
- ip route <prefix> <mask> <next_hop> → StaticRoute
"""

from __future__ import annotations

import ipaddress
import re

from .base import (
    ADMIN_DOWN, ADMIN_UP, AF_V6, L2, L3, SCOPE_LINK_LOCAL, SOURCE_PARSED,
    BgpNeighbor, Device, Interface, OspfNetwork, StaticRoute,
    derive_ip_from_addresses, normalize_v6, sort_addresses,
)


def detect(text: str) -> bool:
    """
    IOS config かどうかを判定。

    条件（いずれかが満たされ、かつ set 行が支配的でないこと）:
    - "hostname " で始まる行がある
    - "interface ...Ethernet" や "interface Loopback" 等の行がある
    - "!" 区切り行が複数ある
    """
    if not text.strip():
        return False

    lines = text.splitlines()

    # set 行が過半数なら JunOS
    set_lines = sum(1 for ln in lines if ln.strip().startswith("set "))
    non_empty = sum(1 for ln in lines if ln.strip())
    if non_empty > 0 and set_lines / non_empty > 0.4:
        return False

    # IOS 特徴チェック
    for ln in lines:
        stripped = ln.strip()
        if re.match(r'^hostname\s+\S', stripped):
            return True
        if re.match(r'^interface\s+\S', stripped):
            return True
        if stripped == "!":
            return True

    return False


def _ensure_switchport(sp: dict | None) -> dict:
    """switchport dict が None なら空 dict を返す小ヘルパー（重複初期化を排除）。"""
    return sp if sp is not None else {}


def _mask_to_prefixlen(mask: str) -> int:
    """サブネットマスク文字列を prefix 長に変換する。"""
    return ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen


def _wildcard_to_prefixlen(wildcard: str) -> int:
    """OSPF ワイルドカードマスクを prefix 長に変換する（逆マスク）。"""
    # ワイルドカードの各オクテットを 255 から引いてサブネットマスクを得る
    parts = wildcard.split(".")
    subnet_mask = ".".join(str(255 - int(p)) for p in parts)
    return _mask_to_prefixlen(subnet_mask)


def parse(text: str) -> Device:
    """
    IOS コンフィグテキストをパースして Device を返す。

    Phase 3F 拡張:
    - ip address（primary / secondary）と ipv6 address を addresses リストに収集
    - ip フィールドは addresses 中の最初の非 secondary v4 から派生（_derive_ip_from_addresses 相当）
    - addresses は (af 順, ipaddress オブジェクト, prefix) でソート（決定的）
    """
    hostname = ""
    asn: int | None = None
    interfaces: list[Interface] = []
    bgp_neighbors: list[BgpNeighbor] = []
    ospf_networks: list[OspfNetwork] = []
    static_routes: list[StaticRoute] = []

    lines = text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # hostname
        m = re.match(r'^hostname\s+(\S+)', stripped)
        if m:
            hostname = m.group(1)
            i += 1
            continue

        # interface ブロック
        m = re.match(r'^interface\s+(\S+)', stripped)
        if m:
            if_name = m.group(1)
            if_ip: str | None = None
            if_desc: str | None = None
            if_shutdown = False
            if_mtu: int | None = None
            if_speed: str | None = None
            if_duplex: str | None = None
            if_switchport: dict | None = None
            if_encapsulation: str | None = None
            if_has_ip_cmd = False      # "ip address" コマンドがあったか
            if_no_switchport = False   # "no switchport" があったか
            # Phase 3F: addresses 収集用リスト（パース中の生データ）
            if_addresses: list[dict] = []
            i += 1
            # ブロック内を読む（インデントされた行か次のトップレベルまで）
            while i < len(lines):
                inner = lines[i]
                inner_stripped = inner.strip()
                # ブロック終端: 空行 or "!" or インデントなしの非空行
                if not inner or inner_stripped == "!" or (inner and not inner[0].isspace() and inner_stripped):
                    break
                # ip address（primary / secondary 両方対応）
                m2 = re.match(r'^ip\s+address\s+(\S+)\s+(\S+)(\s+secondary)?$', inner_stripped)
                if m2:
                    addr = m2.group(1)
                    mask = m2.group(2)
                    is_secondary = bool(m2.group(3) and "secondary" in m2.group(3))
                    try:
                        prefixlen = _mask_to_prefixlen(mask)
                        addr_entry: dict = {"af": "v4", "ip": addr, "prefix": prefixlen}
                        if is_secondary:
                            addr_entry["secondary"] = True
                        else:
                            # primary のみ if_ip に採用（後方互換）
                            if_ip = f"{addr}/{prefixlen}"
                            if_has_ip_cmd = True
                        if_addresses.append(addr_entry)
                    except ValueError:
                        pass
                # ipv6 address（グローバル / link-local 両方対応）
                m_v6 = re.match(r'^ipv6\s+address\s+(\S+)(?:\s+(\S+))?$', inner_stripped, re.IGNORECASE)
                if m_v6:
                    v6_spec = m_v6.group(1)
                    v6_qualifier = (m_v6.group(2) or "").lower()
                    if "/" in v6_spec:
                        # グローバルアドレス: "2001:db8::1/64" 形式
                        v6_addr_str, v6_prefix_str = v6_spec.rsplit("/", 1)
                        try:
                            v6_prefix = int(v6_prefix_str)
                            v6_normalized = normalize_v6(v6_addr_str)
                            addr_entry = {"af": AF_V6, "ip": v6_normalized, "prefix": v6_prefix}
                            if_addresses.append(addr_entry)
                            if_has_ip_cmd = True  # ip が設定されている = L3 扱い
                        except (ValueError, TypeError):
                            pass
                    elif v6_qualifier == "link-local":
                        # link-local: "fe80::1 link-local" 形式
                        try:
                            v6_normalized = normalize_v6(v6_spec)
                            addr_entry = {"af": AF_V6, "ip": v6_normalized, "prefix": 64, "scope": SCOPE_LINK_LOCAL}
                            if_addresses.append(addr_entry)
                        except (ValueError, TypeError):
                            pass
                # description
                m3 = re.match(r'^description\s+(.*)', inner_stripped)
                if m3:
                    if_desc = m3.group(1).strip()
                # shutdown / no shutdown
                if inner_stripped == "shutdown":
                    if_shutdown = True
                if inner_stripped == "no shutdown":
                    if_shutdown = False
                # mtu（\d+ マッチ済みなので ValueError は発生しない）
                m_mtu = re.match(r'^mtu\s+(\d+)', inner_stripped)
                if m_mtu:
                    if_mtu = int(m_mtu.group(1))
                # speed
                m_speed = re.match(r'^speed\s+(\S+)', inner_stripped)
                if m_speed:
                    if_speed = m_speed.group(1)
                # duplex
                m_duplex = re.match(r'^duplex\s+(\S+)', inner_stripped)
                if m_duplex:
                    if_duplex = m_duplex.group(1)
                # switchport mode access / trunk
                m_sw_mode = re.match(r'^switchport\s+mode\s+(\S+)', inner_stripped)
                if m_sw_mode:
                    if_switchport = _ensure_switchport(if_switchport)
                    if_switchport["mode"] = m_sw_mode.group(1)
                # switchport access vlan <id>（\d+ マッチ済みなので ValueError は発生しない）
                m_sw_av = re.match(r'^switchport\s+access\s+vlan\s+(\d+)', inner_stripped)
                if m_sw_av:
                    if_switchport = _ensure_switchport(if_switchport)
                    if_switchport["access_vlan"] = int(m_sw_av.group(1))
                # switchport trunk allowed vlan <range>
                m_sw_tv = re.match(r'^switchport\s+trunk\s+allowed\s+vlan\s+(\S+)', inner_stripped)
                if m_sw_tv:
                    if_switchport = _ensure_switchport(if_switchport)
                    if_switchport["trunk_vlans"] = m_sw_tv.group(1)
                # no switchport
                if inner_stripped == "no switchport":
                    if_no_switchport = True
                # encapsulation dot1Q <vlan>（IGNORECASE で DOT1Q 等も許容）
                m_enc = re.match(r'^encapsulation\s+dot1[Qq]\s+(\d+)', inner_stripped, re.IGNORECASE)
                if m_enc:
                    if_encapsulation = "dot1q"
                i += 1
            # l2_l3 判定（IOS: ip あり / no switchport が L3 判定で優先される）
            if if_has_ip_cmd or if_no_switchport:
                if_l2_l3 = L3
            elif if_switchport is not None:
                if_l2_l3 = L2
            else:
                if_l2_l3 = None
            # admin_status: shutdown 由来（定数使用）
            if_admin_status = ADMIN_DOWN if if_shutdown else ADMIN_UP
            # Phase 3F: addresses をソートして格納（base.sort_addresses で DRY）
            sorted_addrs = sort_addresses(if_addresses)
            # ip: addresses から派生（primary v4 が存在すれば if_ip と同値・v6-only なら None）
            derived_ip = derive_ip_from_addresses(sorted_addrs) if sorted_addrs else if_ip
            interfaces.append(Interface(
                name=if_name,
                ip=derived_ip,
                description=if_desc,
                shutdown=if_shutdown,
                mtu=if_mtu,
                speed=if_speed,
                duplex=if_duplex,
                switchport=if_switchport,
                encapsulation=if_encapsulation,
                l2_l3=if_l2_l3,
                admin_status=if_admin_status,
                addresses=sorted_addrs,
            ))
            continue

        # router bgp <asn>
        m = re.match(r'^router\s+bgp\s+(\d+)', stripped)
        if m:
            asn = int(m.group(1))
            i += 1
            while i < len(lines):
                inner = lines[i]
                inner_stripped = inner.strip()
                if not inner or inner_stripped == "!" or (inner and not inner[0].isspace() and inner_stripped):
                    break
                m2 = re.match(r'^neighbor\s+(\S+)\s+remote-as\s+(\d+)', inner_stripped)
                if m2:
                    bgp_neighbors.append(BgpNeighbor(
                        neighbor_ip=m2.group(1),
                        peer_as=int(m2.group(2)),
                    ))
                i += 1
            continue

        # router ospf <pid>
        m = re.match(r'^router\s+ospf\s+(\d+)', stripped)
        if m:
            pid = int(m.group(1))
            i += 1
            while i < len(lines):
                inner = lines[i]
                inner_stripped = inner.strip()
                if not inner or inner_stripped == "!" or (inner and not inner[0].isspace() and inner_stripped):
                    break
                # network <addr> <wildcard> area <a>
                m2 = re.match(r'^network\s+(\S+)\s+(\S+)\s+area\s+(\S+)', inner_stripped)
                if m2:
                    addr = m2.group(1)
                    wildcard = m2.group(2)
                    area = m2.group(3)
                    try:
                        prefixlen = _wildcard_to_prefixlen(wildcard)
                        # prefixlen=0 は wildcard 全1（全ホストマッチ）で不正な OSPF network
                        if prefixlen > 0:
                            network_cidr = f"{addr}/{prefixlen}"
                            ospf_networks.append(OspfNetwork(
                                process=pid,
                                network=network_cidr,
                                area=area,
                            ))
                    except ValueError:
                        pass
                i += 1
            continue

        # ip route <prefix> <mask> <next_hop>
        m = re.match(r'^ip\s+route\s+(\S+)\s+(\S+)\s+(\S+)', stripped)
        if m:
            prefix_addr = m.group(1)
            prefix_mask = m.group(2)
            next_hop = m.group(3)
            try:
                prefixlen = _mask_to_prefixlen(prefix_mask)
                prefix_cidr = f"{prefix_addr}/{prefixlen}"
                static_routes.append(StaticRoute(
                    prefix=prefix_cidr,
                    next_hop=next_hop,
                ))
            except ValueError:
                pass
            i += 1
            continue

        i += 1

    return Device(
        hostname=hostname,
        vendor="cisco_ios",
        asn=asn,
        interfaces=interfaces,
        bgp=bgp_neighbors,
        ospf=ospf_networks,
        static=static_routes,
    )
