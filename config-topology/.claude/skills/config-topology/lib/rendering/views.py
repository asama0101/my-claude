"""
rendering/views.py — ビュー別 SVG 生成モジュール
"""
from __future__ import annotations

from lib.rendering.layout import (
    _adaptive_iter,
    _canvas_size_for_nodes,
    _compute_canvas,
    _compute_layout,
    _layout_force_directed,
    _make_bbox_str,
    _node_size_for,
    OSPF_AREA_LABEL_FORMAT,
)
from lib.rendering.svg import (
    _esc,
    _svg_bgp_as_groups,
    _svg_bgp_edges,
    _svg_links,
    _svg_nodes,
    _svg_ospf_segment_edges,
    _svg_ospf_segments,
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
    segments: list[dict] | None = None,
    interfaces: list[dict] | None = None,
) -> tuple[dict[str, tuple[float, float]], list[dict], list[dict]]:
    """OSPF ビュー用レイアウト計算（OSPF 参加 device + OSPF 参加 segment）

    Returns:
        positions: ノード ID → (x, y) 座標の辞書（device + segment）
        ospf_devices: OSPF 参加 device リスト
        ospf_segments: OSPF 参加セグメント（ospf_area 付き）リスト
    """
    if segments is None:
        segments = []
    if interfaces is None:
        interfaces = []

    ospf_device_ids: set[str] = set(entry["device"] for entry in ospf_entries)

    # OSPF 参加セグメント（ospf_area が付いているもの）
    ospf_segments = [s for s in segments if s.get("ospf_area") is not None]

    # interface id → device id のマップ（segment メンバー解決用）
    iface_to_device: dict[str, str] = {iface["id"]: iface["device"] for iface in interfaces}

    # H2: ospf_area 付きセグメントのメンバー device を ospf_device_ids に追加
    # routing.ospf が空でも ospf_area 付きセグメントがあればメンバーが孤立しない
    for seg in ospf_segments:
        for member_iface_id in seg.get("members", []):
            dev_id = iface_to_device.get(member_iface_id)
            if dev_id:
                ospf_device_ids.add(dev_id)

    ospf_devices = [d for d in devices if d["id"] in ospf_device_ids]

    # エッジリスト: p2p リンク（両端が OSPF 参加）
    edge_list: list[tuple[str, str]] = []
    for lk in links:
        if lk["a_device"] in ospf_device_ids and lk["b_device"] in ospf_device_ids:
            edge_list.append((lk["a_device"], lk["b_device"]))

    # セグメントノード → メンバー機器 のエッジ（OSPF 参加機器のみ）
    for seg in ospf_segments:
        for member_iface_id in seg.get("members", []):
            dev_id = iface_to_device.get(member_iface_id)
            if dev_id and dev_id in ospf_device_ids:
                edge_list.append((seg["id"], dev_id))

    # セグメント ID も node_ids に含める
    node_ids = [d["id"] for d in ospf_devices] + [s["id"] for s in ospf_segments]
    est_n = len(node_ids)
    if not node_ids:
        return {}, ospf_devices, ospf_segments
    if est_n == 1:
        return _compute_layout(ospf_devices, ospf_segments), ospf_devices, ospf_segments
    # ここに到達する時点で est_n >= 2 が保証される
    est_w, est_h = _canvas_size_for_nodes(est_n)

    positions = _layout_force_directed(
        node_ids, edge_list, width=est_w, height=est_h,
        iterations=_adaptive_iter(est_n)
    )
    return positions, ospf_devices, ospf_segments


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
    """Physical ビュー用レイアウト計算（device + segment ノード）。

    可変高対応: デバイスの IF 数を node_sizes として渡し、
    重なり強制分離パスで矩形ベースの間隔を使用する。
    また最大ノード高からキャンバス高を補正し、多 IF ノードが viewBox に収まるよう保証する。
    """
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

    # device ごとの IF 数マップ（可変高分離用）
    iface_count: dict[str, int] = {}
    for iface in interfaces:
        dev_id = iface["device"]
        iface_count[dev_id] = iface_count.get(dev_id, 0) + 1

    # 最大ノード高を算出してキャンバス高に反映（多 IF ノード対応）
    max_node_h = max(
        (_node_size_for(cnt)[1] for cnt in iface_count.values()),
        default=_node_size_for(0)[1],
    )

    est_n = max(1, len(node_ids))
    est_w, est_h = _canvas_size_for_nodes(est_n, max_node_h=max_node_h)

    if est_n <= 1:
        return _compute_layout(devices, segments)

    return _layout_force_directed(
        node_ids, edge_list, width=est_w, height=est_h,
        iterations=_adaptive_iter(est_n),
        node_sizes=iface_count,
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


def _build_connected_iface_ids(
    links: list[dict],
    segments: list[dict],
    interfaces: list[dict],
) -> set[str]:
    """リンク/セグメントの端点になっている iface-id の集合を返す（iteration-3 #2）。

    接続IF判定に使用する。IF 名から iface-id へのマップを構築して効率化する。
    """
    connected: set[str] = set()

    # iface name → iface id マップ（device 付きで衝突回避）
    name_to_id: dict[tuple[str, str], str] = {
        (iface["device"], iface["name"]): iface["id"]
        for iface in interfaces
    }

    # リンク端点の iface-id を登録
    for link in links:
        a_dev = link.get("a_device", "")
        a_if = link.get("a_if") or ""
        b_dev = link.get("b_device", "")
        b_if = link.get("b_if") or ""
        if a_dev and a_if:
            iid = name_to_id.get((a_dev, a_if))
            if iid:
                connected.add(iid)
        if b_dev and b_if:
            iid = name_to_id.get((b_dev, b_if))
            if iid:
                connected.add(iid)

    # セグメントメンバーの iface-id を登録
    for seg in segments:
        for member_iface_id in seg.get("members", []):
            connected.add(member_iface_id)

    return connected


def _build_view_physical(
    devices: list[dict],
    interfaces: list[dict],
    links: list[dict],
    segments: list[dict],
    positions: dict[str, tuple[float, float]],
    iface_by_device: dict[str, list[dict]],
) -> str:
    """Physical ビュー SVG コンテンツを生成する（BGP オーバーレイなし）。

    ノードは show_interfaces=True でチップ型（接続IF/Loopback のみ）。
    iteration-3 #2: 接続IF/Loopback のみをチップとして表示し、全 IF はカード表に残す。
    """
    # 接続 iface-id 集合を計算（iteration-3 #2）
    connected_iface_ids = _build_connected_iface_ids(links, segments, interfaces)

    seg_edges = _svg_segment_edges(segments, interfaces, positions)
    links_str = _svg_links(links, positions)
    segs_str = _svg_segments(segments, positions)
    # Physical ビューのみ show_interfaces=True（BGP/OSPF ビューはデフォルトのコンパクト）
    nodes_str = _svg_nodes(
        devices, positions, iface_by_device,
        show_interfaces=True,
        connected_iface_ids=connected_iface_ids,
    )
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
    """BGP ビュー SVG コンテンツを生成する。

    描画順: AS 枠（背面）→ BGP エッジ → ノード（前面）
    """
    positions_bgp, bgp_devices = _build_bgp_layout(devices, bgp_entries, interfaces)
    as_groups_str = _svg_bgp_as_groups(bgp_devices, positions_bgp)
    bgp_str = _svg_bgp_edges(bgp_entries, interfaces, positions_bgp)
    nodes_str = _svg_nodes(bgp_devices, positions_bgp, iface_by_device)
    bbox = _make_bbox_str(positions_bgp)
    inner = "\n".join(filter(None, [as_groups_str, bgp_str, nodes_str]))
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
    segments: list[dict] | None = None,
    interfaces: list[dict] | None = None,
) -> str:
    """OSPF ビュー SVG コンテンツを生成する。

    OSPF 参加リンクのエッジ中点に「area {area} · {subnet}」を常時 <text> 表示する。
    ospf_area が付いているリンクは area ラベルを表示。
    ospf_area が欠如しているリンクはサブネットのみ表示（後方互換）。
    両端で area が異なる場合（例 "0/1"）はそのまま表示。

    OSPF 参加セグメント（ospf_area 付き）を楕円ノードとして描画し、
    メンバー機器へ seg-edge を引き「area {area} · {subnet}」ラベルを表示する。
    """
    if segments is None:
        segments = []
    if interfaces is None:
        interfaces = []

    positions_ospf, ospf_devices, ospf_segments = _build_ospf_layout(
        devices, ospf_entries, links, segments, interfaces
    )

    # OSPF エッジ（同一リンクの両端が OSPF 参加）
    ospf_device_ids: set[str] = set(d["id"] for d in ospf_devices)
    parts = []
    for lk in sorted(links, key=lambda l: (l["a_device"], l["b_device"])):
        if lk["a_device"] in ospf_device_ids and lk["b_device"] in ospf_device_ids:
            x1, y1 = positions_ospf.get(lk["a_device"], (0, 0))
            x2, y2 = positions_ospf.get(lk["b_device"], (0, 0))
            subnet = _esc(lk["subnet"])
            ospf_area = lk.get("ospf_area")
            # リンク中点（Physical ビューの link-label と同様の手法）
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2 - 15

            if ospf_area is not None:
                label_line1 = OSPF_AREA_LABEL_FORMAT.format(
                    area=_esc(ospf_area), subnet=subnet
                )
                label_elem = (
                    f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" '
                    f'class="link-label layer-ospf">{label_line1}</text>'
                )
            else:
                # ospf_area 欠如: subnet のみ表示（後方互換）
                label_elem = (
                    f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" '
                    f'class="link-label layer-ospf">{subnet}</text>'
                )

            parts.append(
                f'<g class="link-edge" data-subnet="{subnet}" '
                f'data-a="{_esc(lk["a_device"])}" data-b="{_esc(lk["b_device"])}">'
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'class="link-line layer-ospf"/>'
                f'{label_elem}'
                f'</g>'
            )
    edges_str = "\n".join(parts)

    # OSPF 参加セグメント描画
    ospf_seg_edges_str = _svg_ospf_segment_edges(
        ospf_segments, interfaces, positions_ospf
    )
    ospf_segs_str = _svg_ospf_segments(ospf_segments, positions_ospf)

    nodes_str = _svg_nodes(ospf_devices, positions_ospf, iface_by_device)
    bbox = _make_bbox_str(positions_ospf)
    inner = "\n".join(filter(None, [
        ospf_seg_edges_str, edges_str, ospf_segs_str, nodes_str
    ]))
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
