"""
rendering/core.py — render() 統括モジュール
"""
from __future__ import annotations

import ipaddress
import json
import math

from lib.rendering.cards import _device_cards
from lib.rendering.layout import _compute_canvas
from lib.rendering.svg import _build_ip_to_device, _esc, _make_iface_by_device, _make_link_id, _normalize_subnet
from lib.rendering.template import _layer_toggles, _node_filter_ui, build_html
from lib.rendering.views import (
    _bgp_has_resolved_edges,
    _build_ifinv_table,
    _build_physical_layout,
    _build_view_bgp,
    _build_view_generic,
    _build_view_ospf,
    _build_view_physical,
    _build_view_tabs,
    _generic_has_edges,
    _ospf_has_edges,
)


# _normalize_ospf_id は svg._normalize_subnet への後方互換エイリアス。
# 独自実装は svg._normalize_subnet に一本化済み。
# routing.network と link.ospf_network は同一 subnet を指す前提のため、
# 両者を正規化すれば同一の ospf_id が得られることが保証される。
_normalize_ospf_id = _normalize_subnet


def _build_ospf_marking_map(
    ospf_entries: list[dict],
) -> dict[tuple[str, str], str]:
    """OSPF エントリから (device, network) → ospf_id マップを構築する。

    ospf_id は ``_normalize_ospf_id(network)``（= ``_normalize_subnet``）で正規化した CIDR 文字列。
    解決できないエントリ（normalizeが空文字）はスキップする。

    ``routing.network`` と ``link.ospf_network`` は同一 subnet を指す前提であり、
    両者を正規化すれば同一の ospf_id が得られる。これにより SVG 側の
    ``data-ospf-id``（正規化 subnet）とカード側の ``data-ospf-id`` が一致する。

    Args:
        ospf_entries: routing["ospf"] のエントリリスト

    Returns:
        ``{(device_id, network_str): ospf_id}`` 辞書（安定順序）。
        マップキーは raw network 文字列のまま、値（ospf_id）のみ正規化される。
    """
    result: dict[tuple[str, str], str] = {}
    for entry in sorted(ospf_entries, key=lambda e: (e.get("device", ""), e.get("network", ""))):
        dev_id = entry.get("device", "")
        network = entry.get("network", "")
        if not (dev_id and network):
            continue
        ospf_id = _normalize_ospf_id(network)
        if not ospf_id:
            continue
        result[(dev_id, network)] = ospf_id
    return result


def _active_entries(entries: list) -> list[dict]:
    """エントリリストから device キーを持つ dict のみ返す。"""
    return [e for e in entries if isinstance(e, dict) and "device" in e]


def _active_routing_keys(routing: dict) -> list[str]:
    """routing dict のうちデータ（device キーを持つ dict エントリ）が1件以上あるキーを昇順で返す。"""
    return sorted(
        key for key, entries in routing.items()
        if any(isinstance(e, dict) and "device" in e for e in entries)
    )


def _resolve_nexthop_device(
    members: dict[str, str],
    next_hop_raw: str,
    next_hop_normalized: str,
    next_hop_addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> str | None:
    """members {ip_str: dev_id} から next_hop に対応するデバイス ID を返す。

    文字列完全一致（高速パス）→ ipaddress 正規化比較の順で探索し、
    v6 short-form 表記（"2001:db8:1::" == "2001:db8:1::0"）の不一致に対応する。

    Args:
        members: ``{ip_str: dev_id}`` 形式のマップ（リンク/セグメントのメンバー）
        next_hop_raw: next_hop の生文字列（例 "2001:db8:1::"）
        next_hop_normalized: str(ip_address(next_hop)) で正規化した文字列（例 "2001:db8:1::"）
        next_hop_addr: ipaddress オブジェクト（比較用）

    Returns:
        対応する dev_id または None
    """
    # 高速パス: 文字列完全一致
    dev = members.get(next_hop_raw) or members.get(next_hop_normalized)
    if dev:
        return dev
    # フォールバック: ipaddress 正規化比較（short-form / long-form 差異を吸収）
    for ip_key, dev_id in members.items():
        try:
            if ipaddress.ip_address(ip_key) == next_hop_addr:
                return dev_id
        except ValueError:
            continue
    return None


def _build_static_route_map(
    static_entries: list[dict],
    links: list[dict],
    segments: list[dict],
    interfaces: list[dict],
) -> dict[tuple[str, str], dict]:
    """static ルートエントリから経路解決マップを構築する。

    各エントリの next_hop が乗る直接接続リンク（p2p）またはセグメントを
    ``ipaddress`` で検索し、解決できた場合に ``route_edge_id``（link_id または seg-id）と
    ``nexthop_device_id`` を格納した辞書を返す。

    Returns:
        ``{(device, prefix): {"route_edge_id": str|None, "nexthop_device_id": str|None}}``
        形式の辞書。解決できないエントリはキーを持たない。
        順序安定（デバイス・プレフィックス昇順でソート済み）。
    """
    # iface_id -> {ip, device, name} マップ構築（セグメント走査用）
    iface_info: dict[str, dict] = {}
    # iface_id -> list[str] マップ（セグメントの v6-only IF 解決用）
    iface_id_to_ips: dict[str, list[str]] = {}
    # HM1: (device, name) -> list[str] マップ構築（p2p リンク走査を O(1) 引きに）
    # 修正1: addresses の v4/v6 エントリを全て登録し、v6-only IF の nexthop 機器解決に対応。
    # v4 ip フィールドと addresses の両方を収集して重複排除する。
    dev_name_to_ips: dict[tuple[str, str], list[str]] = {}
    for iface in interfaces:
        iface_info[iface["id"]] = {
            "ip": iface.get("ip") or "",
            "device": iface.get("device", ""),
            "name": iface.get("name", ""),
        }
        dev = iface.get("device", "")
        name = iface.get("name", "")
        if not (dev and name):
            continue
        ips: list[str] = []
        # v4 ip フィールド（後方互換）
        ip_cidr = iface.get("ip") or ""
        ip_only = ip_cidr.split("/")[0]
        if ip_only:
            ips.append(ip_only)
        # addresses の各エントリ（v4/v6 両対応）
        for addr in iface.get("addresses") or []:
            addr_ip = addr.get("ip", "")
            if addr_ip and addr_ip not in ips:
                ips.append(addr_ip)
        if ips:
            dev_name_to_ips[(dev, name)] = ips
            iface_id_to_ips[iface["id"]] = ips

    # p2p リンクのサブネット → (link_id, {dev: ip}) マップ
    # {subnet_str: {"link_id": str, "members": {ip: dev_id}}}
    # MC1: ソート安定化（重複サブネットで route_edge_id が入力順依存になるのを防ぐ）
    link_subnet_map: list[dict] = []
    for link in sorted(links, key=lambda lk: (lk.get("a_device", ""), lk.get("b_device", ""), lk.get("subnet", ""))):
        a_dev = link.get("a_device", "")
        b_dev = link.get("b_device", "")
        a_if_name = link.get("a_if") or ""
        b_if_name = link.get("b_if") or ""
        subnet_str = link.get("subnet") or ""
        if not (a_dev and b_dev and subnet_str):
            continue
        lid = _make_link_id(a_dev, a_if_name, b_dev, b_if_name)
        # HM1: (device,name)->ips マップで両端の全 IP を収集（v4/v6 両対応）
        members: dict[str, str] = {}
        for ip in dev_name_to_ips.get((a_dev, a_if_name), []):
            members[ip] = a_dev
        for ip in dev_name_to_ips.get((b_dev, b_if_name), []):
            members[ip] = b_dev
        link_subnet_map.append({
            "link_id": lid,
            "subnet": subnet_str,
            "members": members,  # {ip: dev_id}
            "a_dev": a_dev,
            "b_dev": b_dev,
        })

    # セグメントのサブネット → {seg_id, members: {ip: dev_id}} マップ
    seg_subnet_map: list[dict] = []
    for seg in segments:
        seg_id = seg.get("id", "")
        subnet_str = seg.get("subnet") or ""
        if not (seg_id and subnet_str):
            continue
        # メンバー IF から IP を収集（v4/v6 両対応: iface_id_to_ips を使用）
        members: dict[str, str] = {}
        for member_iface_id in seg.get("members", []):
            info = iface_info.get(member_iface_id, {})
            dev = info.get("device", "")
            if not dev:
                continue
            for ip in iface_id_to_ips.get(member_iface_id, []):
                if ip:
                    members[ip] = dev
        seg_subnet_map.append({
            "seg_id": seg_id,
            "subnet": subnet_str,
            "members": members,
        })

    result: dict[tuple[str, str], dict] = {}

    for entry in sorted(static_entries, key=lambda e: (e.get("device", ""), e.get("prefix", ""))):
        device = entry.get("device", "")
        prefix = entry.get("prefix", "")
        next_hop = entry.get("next_hop", "")
        if not (device and prefix and next_hop):
            continue

        route_edge_id: str | None = None
        nexthop_device_id: str | None = None

        try:
            nh_addr = ipaddress.ip_address(next_hop)
        except ValueError:
            continue

        # next_hop を正規化した文字列（ip_address オブジェクトの str）
        # 例: "2001:db8:1::" と "2001:db8:1::0" は同一アドレスなので正規化して比較
        nh_addr_str = str(nh_addr)

        # p2p リンクを検索
        found = False
        for link_info in link_subnet_map:
            try:
                net = ipaddress.ip_network(link_info["subnet"], strict=False)
            except ValueError:
                continue
            if nh_addr in net:
                route_edge_id = link_info["link_id"]
                nexthop_device_id = _resolve_nexthop_device(
                    link_info["members"], next_hop, nh_addr_str, nh_addr
                )
                found = True
                break

        # セグメントを検索（p2p で見つからなかった場合）
        if not found:
            for seg_info in seg_subnet_map:
                try:
                    net = ipaddress.ip_network(seg_info["subnet"], strict=False)
                except ValueError:
                    continue
                if nh_addr in net:
                    route_edge_id = seg_info["seg_id"]
                    nexthop_device_id = _resolve_nexthop_device(
                        seg_info["members"], next_hop, nh_addr_str, nh_addr
                    )
                    found = True
                    break

        if found:
            result[(device, prefix)] = {
                "route_edge_id": route_edge_id,
                "nexthop_device_id": nexthop_device_id,
            }

    return result


def _build_bgp_session_map(
    bgp_entries: list[dict],
    interfaces: list[dict],
) -> dict[tuple[str, str], str]:
    """BGP エントリから (device, neighbor_ip) → bgp_id マップを構築する。

    bgp_id は両端 device id を sorted して '|' で結合した決定的な値。
    ``_svg_bgp_edges`` の bgp_id 計算と同じ規則（sorted ペア）を使用する。
    ip_to_device 逆引きには ``svg._build_ip_to_device`` を共用しており、
    ``_svg_bgp_edges`` と挙動が同一であることを保証する。

    neighbor_ip に対応する device が interfaces から逆引きできない場合は
    そのエントリをスキップする（bgp-session <g> が生成されないため不要）。

    Args:
        bgp_entries: routing["bgp"] のエントリリスト
        interfaces:  topology の interfaces リスト

    Returns:
        ``{(device_id, neighbor_ip): bgp_id}`` 辞書（安定順序）。
    """
    # ip_only -> device_id 逆引き（svg._build_ip_to_device と同じ規則を共有）
    ip_to_device = _build_ip_to_device(interfaces)

    result: dict[tuple[str, str], str] = {}
    for entry in sorted(bgp_entries, key=lambda e: (e.get("device", ""), e.get("neighbor_ip", ""))):
        dev_id = entry.get("device", "")
        neighbor_ip = entry.get("neighbor_ip", "")
        if not (dev_id and neighbor_ip):
            continue
        neighbor_dev = ip_to_device.get(neighbor_ip)
        if not neighbor_dev or neighbor_dev == dev_id:
            continue
        bgp_id = "|".join(sorted([dev_id, neighbor_dev]))
        result[(dev_id, neighbor_ip)] = bgp_id

    return result


def _build_iface_seg_id(segments: list[dict]) -> dict[str, str]:
    """iface_id -> seg_id マップを構築する。

    各セグメントの members リストを走査し、
    ``{iface_id: seg_id}`` 形式の辞書を返す。

    Args:
        segments: topology の segments リスト

    Returns:
        ``{iface_id: seg_id}`` 辞書（安定順序）
    """
    result: dict[str, str] = {}
    for seg in sorted(segments, key=lambda s: s.get("id", "")):
        seg_id = seg.get("id", "")
        if not seg_id:
            continue
        for member_iface_id in sorted(seg.get("members", [])):
            result[member_iface_id] = seg_id
    return result


def render(topology: dict) -> str:
    """
    topology dict を受け取り、自己完結 HTML 文字列を返す。

    Stage2: レイヤー別ビュー（physical / プロトコル別）をすべて SVG 内に埋め込み、
    JS タブで切替える。座標は全ビュー分 Python で事前計算し決定性を維持する。

    Args:
        topology: topology dict（references/schema.md 準拠。
                  topology_io.load_topology() または build_topology.build() の出力）

    Returns:
        file:// で直接開ける自己完結 HTML 文字列
    """
    title = _esc(topology.get("title", "Network Topology"))
    devices: list[dict] = topology.get("devices", [])
    interfaces: list[dict] = topology.get("interfaces", [])
    links: list[dict] = topology.get("links", [])
    segments: list[dict] = topology.get("segments", [])
    routing: dict = topology.get("routing", {})

    # iface_by_device マップ（検索属性生成・各ビュー共用）
    iface_by_device = _make_iface_by_device(interfaces)

    # ---------------------------------------------------------------------------
    # Physical ビューのレイアウト計算
    # ---------------------------------------------------------------------------
    positions = _build_physical_layout(devices, interfaces, links, segments)

    # device ごとの IF 数マップ（viewBox 計算でノード矩形半寸を加味するため）
    _iface_count: dict[str, int] = {}
    for _iface in interfaces:
        _dev = _iface["device"]
        _iface_count[_dev] = _iface_count.get(_dev, 0) + 1

    # 動的キャンバス（全ビューのうち Physical を基準とした SVG サイズ）
    vb_min_x, vb_min_y, svg_width, svg_height = _compute_canvas(positions, node_sizes=_iface_count)
    svg_width = math.ceil(svg_width)
    svg_height = math.ceil(svg_height)

    # ---------------------------------------------------------------------------
    # ビュー SVG コンテンツ生成
    # ---------------------------------------------------------------------------
    # Physical ビュー（BGP オーバーレイなし）
    view_physical_svg = _build_view_physical(
        devices, interfaces, links, segments, positions, iface_by_device
    )

    # プロトコル別ビュー（routing キーを走査して動的生成）
    # ゲーティング: エッジ集合が非空のビューのみ生成する
    proto_views: list[str] = []
    proto_view_ids: list[str] = []
    for proto_key in sorted(routing.keys()):
        proto_entries = routing.get(proto_key, [])
        # エントリが空、または device フィールドを持つものが1つもない場合はスキップ
        # ただし ospf は routing.ospf=[] でも ospf_area 付きセグメントがあれば描画する
        active_entries = _active_entries(proto_entries)
        if proto_key != "ospf" and not active_entries:
            continue
        # ゲーティング: プロトコル種別に応じてエッジ有無を判定
        # static はセッション/隣接を表さないため常にビュー化しない
        if proto_key == "static":
            continue
        if proto_key == "bgp":
            if not active_entries:
                continue
            if not _bgp_has_resolved_edges(active_entries, interfaces):
                continue
            view_svg = _build_view_bgp(
                devices, interfaces, proto_entries, links, iface_by_device
            )
        elif proto_key == "ospf":
            # OSPF 参加 p2p リンク または OSPF 参加セグメントが存在すれば描画
            # H2: routing.ospf が空でも ospf_area 付きセグメントがあればビューを生成する
            ospf_segs = [s for s in segments if s.get("ospf_area") is not None]
            if not _ospf_has_edges(active_entries, links) and not ospf_segs:
                continue
            view_svg = _build_view_ospf(
                devices, proto_entries, links, iface_by_device,
                segments=segments, interfaces=interfaces,
            )
        else:
            if not _generic_has_edges(active_entries, links):
                continue
            view_svg = _build_view_generic(
                proto_key, devices, proto_entries, links, iface_by_device
            )
        proto_views.append(view_svg)
        proto_view_ids.append(proto_key)

    # ビュー ID リスト（タブ生成用）— L3 は削除。ifinv は常に末尾に追加
    all_view_ids = ["physical"] + proto_view_ids + ["ifinv"]

    # SVG 内の全ビューを結合
    all_views_svg = "\n".join(
        [view_physical_svg] + proto_views
    )

    # タブ HTML
    tabs_html = _build_view_tabs(all_view_ids)

    # ---------------------------------------------------------------------------
    # iface_id -> link_id マップ（IF 行に data-link-id を付与するため）
    # iface_by_device（既存）を流用して O(links) で構築
    # ---------------------------------------------------------------------------
    iface_link_id: dict[str, str] = {}
    for link in links:
        a_dev = link.get("a_device", "")
        a_if_name = link.get("a_if") or ""
        b_dev = link.get("b_device", "")
        b_if_name = link.get("b_if") or ""
        if not (a_dev and b_dev):
            continue
        lid = _make_link_id(a_dev, a_if_name, b_dev, b_if_name)
        # iface_by_device を使って device ごとの IF リストから一致するものを登録
        for iface in iface_by_device.get(a_dev, []):
            if iface["name"] == a_if_name:
                iface_link_id[iface["id"]] = lid
        for iface in iface_by_device.get(b_dev, []):
            if iface["name"] == b_if_name:
                iface_link_id[iface["id"]] = lid

    # ---------------------------------------------------------------------------
    # #7: iface_id -> seg_id マップ（IF 行に data-seg-id を付与するため）
    # ---------------------------------------------------------------------------
    iface_seg_id = _build_iface_seg_id(segments)

    # ---------------------------------------------------------------------------
    # #6: static ルート経路解決マップ（static 行に data-route-edge 等を付与するため）
    # ---------------------------------------------------------------------------
    static_route_map = _build_static_route_map(
        routing.get("static", []),
        links,
        segments,
        interfaces,
    )

    # ---------------------------------------------------------------------------
    # #5: BGP セッションマップ（BGP 行に data-bgp-id を付与するため）
    # ---------------------------------------------------------------------------
    bgp_session_map = _build_bgp_session_map(
        routing.get("bgp", []),
        interfaces,
    )

    # ---------------------------------------------------------------------------
    # #1B: OSPF マーキングマップ（OSPF 行に data-ospf-id を付与するため）
    # ---------------------------------------------------------------------------
    ospf_marking_map = _build_ospf_marking_map(
        routing.get("ospf", []),
    )

    # 機器カード
    cards_html = _device_cards(
        devices, interfaces, routing,
        iface_link_id=iface_link_id,
        iface_seg_id=iface_seg_id,
        static_route_map=static_route_map,
        bgp_session_map=bgp_session_map,
        ospf_marking_map=ospf_marking_map,
    )

    # データのある routing キーを一度だけ計算し、トグルと CSS 両方に使用
    active = _active_routing_keys(routing)
    toggles_html = _layer_toggles(active)
    layer_ids = ["physical"] + active  # L3 は削除
    layer_hide_css_parts = []
    for layer_id in layer_ids:
        esc_id = _esc(layer_id)
        if layer_id == "physical":
            layer_hide_css_parts.append(
                f"    body.hide-physical #cards-section .layer-physical {{ display: none; }}"
            )
        else:
            layer_hide_css_parts.append(
                f"    body.hide-{esc_id} #cards-section .layer-{esc_id} {{ display: none; }}"
            )
    layer_hide_css = "\n".join(layer_hide_css_parts)

    # topology JSON の埋め込み
    topology_json = json.dumps(topology, ensure_ascii=False, sort_keys=True, indent=2)
    topology_json_safe = topology_json.replace("</", "<\\/").replace("<!--", "<\\!--")

    # ノードフィルタ UI（hostname 昇順チェックリスト）
    node_filter_html = _node_filter_ui(devices)

    # ---------------------------------------------------------------------------
    # Phase2E: IF 一覧テーブル HTML（全機器横断・決定的）
    # ---------------------------------------------------------------------------
    ifinv_table_html = _build_ifinv_table(devices, interfaces)

    return build_html(
        title=title,
        layer_hide_css=layer_hide_css,
        tabs_html=tabs_html,
        toggles_html=toggles_html,
        node_filter_html=node_filter_html,
        svg_height=svg_height,
        vb_min_x=vb_min_x,
        vb_min_y=vb_min_y,
        svg_width=svg_width,
        all_views_svg=all_views_svg,
        cards_html=cards_html,
        topology_json_safe=topology_json_safe,
        ifinv_table_html=ifinv_table_html,
    )
