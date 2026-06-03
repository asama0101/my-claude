"""
rendering/views.py — ビュー別 SVG 生成モジュール
"""
from __future__ import annotations

from lib.rendering.layout import (
    _adaptive_iter,
    _canvas_size_for_nodes,
    _compute_layout,
    _layout_force_directed,
    _make_bbox_str,
)
from lib.rendering.svg import (
    _esc,
    _svg_bgp_edges,
    _svg_links,
    _svg_nodes,
    _svg_segment_edges,
    _svg_segments,
)


def _build_bgp_layout(
    devices: list[dict],
    bgp_entries: list[dict],
    interfaces: list[dict],
) -> tuple[dict[str, tuple[float, float]], list[dict]]:
    """BGP ビュー用レイアウト計算（BGP 参加 device のみ）"""
    bgp_device_ids: set[str] = set()
    for entry in bgp_entries:
        bgp_device_ids.add(entry["device"])

    # neighbor_ip が解決できる device も含める
    ip_to_device: dict[str, str] = {}
    for iface in interfaces:
        if iface.get("ip"):
            ip_only = iface["ip"].split("/")[0]
            ip_to_device[ip_only] = iface["device"]
    for entry in bgp_entries:
        neighbor_ip = entry.get("neighbor_ip", "")
        nbr_dev = ip_to_device.get(neighbor_ip)
        if nbr_dev:
            bgp_device_ids.add(nbr_dev)

    bgp_devices = [d for d in devices if d["id"] in bgp_device_ids]

    # エッジ: BGP セッション
    edge_list: list[tuple[str, str]] = []
    seen_pairs: set[frozenset] = set()
    for entry in bgp_entries:
        dev_id = entry["device"]
        nbr_dev = ip_to_device.get(entry.get("neighbor_ip", ""))
        if nbr_dev and nbr_dev != dev_id:
            pair = frozenset([dev_id, nbr_dev])
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                edge_list.append((dev_id, nbr_dev))

    node_ids = [d["id"] for d in bgp_devices]
    est_n = max(1, len(node_ids))
    est_w, est_h = _canvas_size_for_nodes(est_n)

    if not node_ids:
        return {}, bgp_devices
    if est_n <= 1:
        return _compute_layout(bgp_devices, []), bgp_devices

    positions = _layout_force_directed(
        node_ids, edge_list, width=est_w, height=est_h,
        iterations=_adaptive_iter(est_n)
    )
    return positions, bgp_devices


def _build_ospf_layout(
    devices: list[dict],
    ospf_entries: list[dict],
    links: list[dict],
) -> tuple[dict[str, tuple[float, float]], list[dict]]:
    """OSPF ビュー用レイアウト計算（OSPF 参加 device のみ）"""
    ospf_device_ids: set[str] = set(entry["device"] for entry in ospf_entries)
    ospf_devices = [d for d in devices if d["id"] in ospf_device_ids]

    # エッジ: 同一リンクの両端が共に OSPF 参加
    edge_list: list[tuple[str, str]] = []
    for lk in links:
        if lk["a_device"] in ospf_device_ids and lk["b_device"] in ospf_device_ids:
            edge_list.append((lk["a_device"], lk["b_device"]))

    node_ids = [d["id"] for d in ospf_devices]
    est_n = max(1, len(node_ids))
    est_w, est_h = _canvas_size_for_nodes(est_n)

    if not node_ids:
        return {}, ospf_devices
    if est_n <= 1:
        return _compute_layout(ospf_devices, []), ospf_devices

    positions = _layout_force_directed(
        node_ids, edge_list, width=est_w, height=est_h,
        iterations=_adaptive_iter(est_n)
    )
    return positions, ospf_devices


def _build_generic_proto_layout(
    devices: list[dict],
    proto_entries: list[dict],
    links: list[dict],
) -> tuple[dict[str, tuple[float, float]], list[dict]]:
    """汎用プロトコルビュー用レイアウト計算（参加 device のみ）"""
    device_ids: set[str] = set(entry["device"] for entry in proto_entries if "device" in entry)
    proto_devices = [d for d in devices if d["id"] in device_ids]

    # エッジ: 同一リンクの両端が共に参加
    edge_list: list[tuple[str, str]] = []
    for lk in links:
        if lk["a_device"] in device_ids and lk["b_device"] in device_ids:
            edge_list.append((lk["a_device"], lk["b_device"]))

    node_ids = [d["id"] for d in proto_devices]
    est_n = max(1, len(node_ids))
    est_w, est_h = _canvas_size_for_nodes(est_n)

    if not node_ids:
        return {}, proto_devices
    if est_n <= 1:
        return _compute_layout(proto_devices, []), proto_devices

    positions = _layout_force_directed(
        node_ids, edge_list, width=est_w, height=est_h,
        iterations=_adaptive_iter(est_n)
    )
    return positions, proto_devices


def _build_physical_layout(
    devices: list[dict],
    interfaces: list[dict],
    links: list[dict],
    segments: list[dict],
) -> dict[str, tuple[float, float]]:
    """Physical ビュー用レイアウト計算（device + segment ノード）"""
    node_ids = [d["id"] for d in devices] + [s["id"] for s in segments]
    iface_to_device = {iface["id"]: iface["device"] for iface in interfaces}
    edge_list: list[tuple[str, str]] = []
    for lk in links:
        edge_list.append((lk["a_device"], lk["b_device"]))
    for seg in segments:
        for member_iface_id in seg.get("members", []):
            dev_id = iface_to_device.get(member_iface_id)
            if dev_id:
                edge_list.append((seg["id"], dev_id))

    est_n = max(1, len(node_ids))
    est_w, est_h = _canvas_size_for_nodes(est_n)

    if est_n <= 1:
        return _compute_layout(devices, segments)

    return _layout_force_directed(
        node_ids, edge_list, width=est_w, height=est_h,
        iterations=_adaptive_iter(est_n)
    )


def _bgp_has_resolved_edges(bgp_entries: list[dict], interfaces: list[dict]) -> bool:
    """BGP エントリに解決可能な neighbor（= 同トポロジー内の device）が存在するか"""
    ip_to_device: dict[str, str] = {}
    for iface in interfaces:
        if iface.get("ip"):
            ip_to_device[iface["ip"].split("/")[0]] = iface["device"]
    for entry in bgp_entries:
        dev_id = entry.get("device", "")
        nbr = ip_to_device.get(entry.get("neighbor_ip", ""))
        if nbr and nbr != dev_id:
            return True
    return False


def _ospf_has_edges(ospf_entries: list[dict], links: list[dict]) -> bool:
    """OSPF エントリに、両端が OSPF 参加するリンクが存在するか"""
    ospf_device_ids = set(e["device"] for e in ospf_entries if "device" in e)
    for lk in links:
        if lk["a_device"] in ospf_device_ids and lk["b_device"] in ospf_device_ids:
            return True
    return False


def _generic_has_edges(proto_entries: list[dict], links: list[dict]) -> bool:
    """汎用プロトコルエントリに、両端が参加するリンクが存在するか"""
    device_ids = set(e["device"] for e in proto_entries if "device" in e)
    for lk in links:
        if lk["a_device"] in device_ids and lk["b_device"] in device_ids:
            return True
    return False


def _build_view_physical(
    devices: list[dict],
    interfaces: list[dict],
    links: list[dict],
    segments: list[dict],
    positions: dict[str, tuple[float, float]],
    iface_by_device: dict[str, list[dict]],
) -> str:
    """Physical ビュー SVG コンテンツを生成する（BGP オーバーレイなし）"""
    seg_edges = _svg_segment_edges(segments, interfaces, positions)
    links_str = _svg_links(links, positions)
    segs_str = _svg_segments(segments, positions)
    nodes_str = _svg_nodes(devices, positions, iface_by_device)
    bbox = _make_bbox_str(positions)
    inner = "\n".join(filter(None, [seg_edges, links_str, segs_str, nodes_str]))
    return (
        f'<g class="view view-physical" data-bbox="{bbox}">\n'
        f'{inner}\n'
        f'</g>'
    )


def _build_view_bgp(
    devices: list[dict],
    interfaces: list[dict],
    bgp_entries: list[dict],
    links: list[dict],
    iface_by_device: dict[str, list[dict]],
) -> str:
    """BGP ビュー SVG コンテンツを生成する"""
    positions_bgp, bgp_devices = _build_bgp_layout(devices, bgp_entries, interfaces)
    bgp_str = _svg_bgp_edges(bgp_entries, interfaces, positions_bgp)
    nodes_str = _svg_nodes(bgp_devices, positions_bgp, iface_by_device)
    bbox = _make_bbox_str(positions_bgp)
    inner = "\n".join(filter(None, [bgp_str, nodes_str]))
    return (
        f'<g class="view view-bgp" data-bbox="{bbox}" style="display:none">\n'
        f'{inner}\n'
        f'</g>'
    )


def _build_view_ospf(
    devices: list[dict],
    ospf_entries: list[dict],
    links: list[dict],
    iface_by_device: dict[str, list[dict]],
) -> str:
    """OSPF ビュー SVG コンテンツを生成する"""
    positions_ospf, ospf_devices = _build_ospf_layout(devices, ospf_entries, links)

    # OSPF エッジ（同一リンクの両端が OSPF 参加）
    ospf_device_ids: set[str] = set(d["id"] for d in ospf_devices)
    parts = []
    for lk in sorted(links, key=lambda l: (l["a_device"], l["b_device"])):
        if lk["a_device"] in ospf_device_ids and lk["b_device"] in ospf_device_ids:
            x1, y1 = positions_ospf.get(lk["a_device"], (0, 0))
            x2, y2 = positions_ospf.get(lk["b_device"], (0, 0))
            subnet = _esc(lk["subnet"])
            parts.append(
                f'<g class="link-edge" data-subnet="{subnet}" '
                f'data-a="{_esc(lk["a_device"])}" data-b="{_esc(lk["b_device"])}">'
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'class="link-line layer-ospf"/>'
                f'<title>{subnet}</title>'
                f'</g>'
            )
    edges_str = "\n".join(parts)
    nodes_str = _svg_nodes(ospf_devices, positions_ospf, iface_by_device)
    bbox = _make_bbox_str(positions_ospf)
    inner = "\n".join(filter(None, [edges_str, nodes_str]))
    return (
        f'<g class="view view-ospf" data-bbox="{bbox}" style="display:none">\n'
        f'{inner}\n'
        f'</g>'
    )


def _build_view_generic(
    view_id: str,
    devices: list[dict],
    proto_entries: list[dict],
    links: list[dict],
    iface_by_device: dict[str, list[dict]],
) -> str:
    """汎用プロトコルビュー SVG コンテンツを生成する（bgp/ospf 以外）"""
    positions, proto_devices = _build_generic_proto_layout(devices, proto_entries, links)

    proto_device_ids: set[str] = set(d["id"] for d in proto_devices)
    parts = []
    for lk in sorted(links, key=lambda l: (l["a_device"], l["b_device"])):
        if lk["a_device"] in proto_device_ids and lk["b_device"] in proto_device_ids:
            x1, y1 = positions.get(lk["a_device"], (0, 0))
            x2, y2 = positions.get(lk["b_device"], (0, 0))
            subnet = _esc(lk["subnet"])
            safe_id = _esc(view_id)
            parts.append(
                f'<g class="link-edge" data-subnet="{subnet}" '
                f'data-a="{_esc(lk["a_device"])}" data-b="{_esc(lk["b_device"])}">'
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'class="link-line layer-{safe_id}"/>'
                f'<title>{subnet}</title>'
                f'</g>'
            )
    edges_str = "\n".join(parts)
    nodes_str = _svg_nodes(proto_devices, positions, iface_by_device)
    bbox = _make_bbox_str(positions)
    inner = "\n".join(filter(None, [edges_str, nodes_str]))
    return (
        f'<g class="view view-{_esc(view_id)}" data-bbox="{bbox}" style="display:none">\n'
        f'{inner}\n'
        f'</g>'
    )


def _build_view_tabs(view_ids: list[str]) -> str:
    """ビュー切替タブ HTML を生成する"""
    labels = {
        "physical": "Physical",
        "bgp": "BGP",
        "ospf": "OSPF",
    }
    tabs = []
    for vid in view_ids:
        label = labels.get(vid, vid.upper())
        active = ' class="view-tab active"' if vid == "physical" else ' class="view-tab"'
        tabs.append(
            f'<button{active} data-view="{_esc(vid)}" '
            f'onclick="selectView(this.dataset.view)">{_esc(label)}</button>'
        )
    return "\n".join(tabs)
