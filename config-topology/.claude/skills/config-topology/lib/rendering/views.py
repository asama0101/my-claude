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
    _build_ip_to_device,
    _build_ip_to_iface_id,
    _chip_positions,
    _esc,
    _is_loopback,
    _make_link_id,
    _merge_links_by_link_id,
    _normalize_subnet,
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
    # Phase 3G: v6 addresses 対応のため _build_ip_to_device を共用
    ip_to_device = _build_ip_to_device(interfaces)
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

    # チップ数に基づく node_sizes（1行=チップあり、0=チップなし）
    bgp_chip_ids = _build_bgp_chip_iface_ids(bgp_entries, interfaces)
    iface_by_device_tmp: dict[str, list[dict]] = {}
    for iface in interfaces:
        iface_by_device_tmp.setdefault(iface["device"], []).append(iface)
    node_sizes: dict[str, int] = {
        dev_id: (1 if any(i["id"] in bgp_chip_ids for i in iface_by_device_tmp.get(dev_id, [])) else 0)
        for dev_id in node_ids
    }

    positions = _layout_force_directed(
        node_ids, edge_list, width=est_w, height=est_h,
        iterations=_adaptive_iter(est_n),
        node_sizes=node_sizes,
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

    # チップ数に基づく node_sizes（デバイスのみ; セグメントノードは 0）
    ospf_chip_ids = _build_ospf_chip_iface_ids(links, segments, interfaces or [], ospf_device_ids)
    iface_by_device_tmp: dict[str, list[dict]] = {}
    for iface in (interfaces or []):
        iface_by_device_tmp.setdefault(iface["device"], []).append(iface)
    node_sizes: dict[str, int] = {
        dev_id: (1 if any(i["id"] in ospf_chip_ids for i in iface_by_device_tmp.get(dev_id, [])) else 0)
        for dev_id in [d["id"] for d in ospf_devices]
    }
    # セグメントノードのサイズは 0（楕円）
    for seg in ospf_segments:
        node_sizes[seg["id"]] = 0

    positions = _layout_force_directed(
        node_ids, edge_list, width=est_w, height=est_h,
        iterations=_adaptive_iter(est_n),
        node_sizes=node_sizes,
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
    """BGP エントリに解決可能な neighbor（= 同トポロジー内の device）が存在するか

    Phase 3G: v6 BGP ネイバーに対応するため _build_ip_to_device を共用する。
    （旧実装の ip フィールドのみの逆引きを addresses 対応に拡張）
    """
    ip_to_device = _build_ip_to_device(interfaces)
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


def _build_physical_chip_iface_ids(
    interfaces: list[dict],
    links: list[dict],
    segments: list[dict],
) -> set[str]:
    """Physical ビュー用チップ集合を返す（接続IF + Loopback）。

    iteration-3 #2 と同じ選定ロジックを集中管理する。
    devices パラメータは不要（interfaces/links/segments のみ使用）。
    """
    connected = _build_connected_iface_ids(links, segments, interfaces)
    result: set[str] = set()
    for iface in interfaces:
        if iface["id"] in connected or _is_loopback(iface.get("name", "")):
            result.add(iface["id"])
    return result


def _build_view_physical(
    devices: list[dict],
    interfaces: list[dict],
    links: list[dict],
    segments: list[dict],
    positions: dict[str, tuple[float, float]],
    iface_by_device: dict[str, list[dict]],
) -> str:
    """Physical ビュー SVG コンテンツを生成する（BGP オーバーレイなし）。

    ノードは chip_iface_ids=phys_chip_ids（接続IF + Loopback）でチップ型描画。
    iteration-3 #2: 接続IF/Loopback のみをチップとして表示し、全 IF はカード表に残す。
    iteration-4 #6: チップアンカー（リンク端点をチップ座標に接続）。
    整理: 描画チップ集合とアンカー集合の源泉を phys_chip_ids に一本化する（ドリフト防止）。
    """
    # Physical チップ集合（接続IF + Loopback）— 描画・アンカー共通の単一源泉
    phys_chip_ids = _build_physical_chip_iface_ids(interfaces, links, segments)

    # チップ座標マップを構築（全デバイス分）
    all_chip_positions: dict[str, tuple[float, float]] = {}
    for dev in devices:
        dev_pos = positions.get(dev["id"])
        if dev_pos is None:
            continue
        dev_ifaces = iface_by_device.get(dev["id"], [])
        dev_chip_ids = {i["id"] for i in dev_ifaces if i["id"] in phys_chip_ids}
        if dev_chip_ids:
            cp = _chip_positions(dev, dev_chip_ids, dev_ifaces, dev_pos[0], dev_pos[1])
            all_chip_positions.update(cp)

    # name_to_iface_id マップ（_svg_links のチップアンカー用）
    name_to_iface_id = {(i["device"], i["name"]): i["id"] for i in interfaces}

    seg_edges = _svg_segment_edges(segments, interfaces, positions,
                                    chip_positions=all_chip_positions)
    links_str = _svg_links(
        links, positions,
        chip_positions=all_chip_positions,
        name_to_iface_id=name_to_iface_id,
    )
    segs_str = _svg_segments(segments, positions)
    # Physical ビュー: chip_iface_ids=phys_chip_ids を単一経路として渡す。
    # _svg_nodes 内の show_interfaces/connected_iface_ids は chip_iface_ids が
    # 明示されたとき無視される（優先）ため、描画チップ集合とアンカー集合が同一源泉に統一される。
    nodes_str = _svg_nodes(
        devices, positions, iface_by_device,
        chip_iface_ids=phys_chip_ids,
    )
    bbox = _make_bbox_str(positions)
    inner = "\n".join(filter(None, [seg_edges, links_str, segs_str, nodes_str]))
    return (
        f'<g class="view view-physical" data-bbox="{bbox}">\n'
        f'{inner}\n'
        f'</g>'
    )


def _build_bgp_chip_iface_ids(
    bgp_entries: list[dict],
    interfaces: list[dict],
) -> set[str]:
    """BGP ビュー用チップ集合を返す（BGP セッション関与 IF のみ）。

    各エントリの local_ip / neighbor_ip にマッチする IF を集める。
    - local_ip → 当該デバイスの IF
    - neighbor_ip → 逆引きで隣接デバイスの IF
    - local_ip=null（iBGP Loopback 源）のとき、当該デバイスの Loopback IF を追加
      （iBGP は Loopback アドレス経由が一般的であり、neighbor_ip で逆引きできない
       ケースを補完する）
    決定的（IP ソート）。
    """
    # ip_only -> iface_id マップ（共通ヘルパーを使用）
    ip_to_iface_id = _build_ip_to_iface_id(interfaces)

    # device -> Loopback iface_id リスト（local_ip=null 補完用）
    dev_loopbacks: dict[str, list[str]] = {}
    for iface in interfaces:
        if _is_loopback(iface.get("name", "")):
            dev_loopbacks.setdefault(iface["device"], []).append(iface["id"])

    result: set[str] = set()
    for entry in bgp_entries:
        local_ip = (entry.get("local_ip") or "").split("/")[0]
        neighbor_ip = (entry.get("neighbor_ip") or "").split("/")[0]
        if local_ip and local_ip in ip_to_iface_id:
            result.add(ip_to_iface_id[local_ip])
        elif not local_ip:
            # local_ip=null: 当該デバイスの Loopback を BGP ソース IF として追加
            dev_id = entry.get("device", "")
            for lb_id in dev_loopbacks.get(dev_id, []):
                result.add(lb_id)
        if neighbor_ip and neighbor_ip in ip_to_iface_id:
            result.add(ip_to_iface_id[neighbor_ip])
    return result


def _build_view_bgp(
    devices: list[dict],
    interfaces: list[dict],
    bgp_entries: list[dict],
    links: list[dict],
    iface_by_device: dict[str, list[dict]],
) -> str:
    """BGP ビュー SVG コンテンツを生成する。

    描画順: AS 枠（背面）→ BGP エッジ → ノード（前面）
    iteration-4 #6: BGP セッション関与 IF のみチップ表示、エッジ端点をチップにアンカー。
    """
    positions_bgp, bgp_devices = _build_bgp_layout(devices, bgp_entries, interfaces)

    # BGP チップ集合（セッション関与 IF のみ）
    bgp_chip_ids = _build_bgp_chip_iface_ids(bgp_entries, interfaces)

    # チップ座標マップを構築（BGP 参加デバイス分）
    all_chip_positions: dict[str, tuple[float, float]] = {}
    bgp_node_sizes: dict[str, int] = {}
    for dev in bgp_devices:
        dev_pos = positions_bgp.get(dev["id"])
        if dev_pos is None:
            continue
        dev_ifaces = iface_by_device.get(dev["id"], [])
        dev_chip_ids = {i["id"] for i in dev_ifaces if i["id"] in bgp_chip_ids}
        if dev_chip_ids:
            cp = _chip_positions(dev, dev_chip_ids, dev_ifaces, dev_pos[0], dev_pos[1])
            all_chip_positions.update(cp)
            bgp_node_sizes[dev["id"]] = 1 if dev_chip_ids else 0

    as_groups_str = _svg_bgp_as_groups(bgp_devices, positions_bgp, node_sizes=bgp_node_sizes)
    bgp_str = _svg_bgp_edges(
        bgp_entries, interfaces, positions_bgp,
        chip_positions=all_chip_positions,
    )
    nodes_str = _svg_nodes(
        bgp_devices, positions_bgp, iface_by_device,
        chip_iface_ids=bgp_chip_ids,
    )
    bbox = _make_bbox_str(positions_bgp)
    inner = "\n".join(filter(None, [as_groups_str, bgp_str, nodes_str]))
    return (
        f'<g class="view view-bgp" data-bbox="{bbox}" style="display:none">\n'
        f'{inner}\n'
        f'</g>'
    )


def _build_ospf_chip_iface_ids(
    links: list[dict],
    segments: list[dict],
    interfaces: list[dict],
    ospf_device_ids: set[str],
) -> set[str]:
    """OSPF ビュー用チップ集合を返す（リンク端点 IF + セグメントメンバー）。

    - OSPF p2p リンクの a_if / b_if（ospf_area 付き or 両端 OSPF 参加）
    - OSPF セグメントのメンバー iface_id
    interfaces から (device, name) -> iface_id を解決する。
    決定的。
    """
    name_to_id = {(i["device"], i["name"]): i["id"] for i in interfaces}
    result: set[str] = set()

    # p2p リンク端点（ospf_area があるか両端が OSPF 参加のリンク）
    for lk in links:
        is_ospf_link = (
            lk.get("ospf_area") is not None or
            (lk["a_device"] in ospf_device_ids and lk["b_device"] in ospf_device_ids)
        )
        if is_ospf_link:
            a_if = lk.get("a_if") or ""
            b_if = lk.get("b_if") or ""
            if a_if:
                iid = name_to_id.get((lk["a_device"], a_if))
                if iid:
                    result.add(iid)
            if b_if:
                iid = name_to_id.get((lk["b_device"], b_if))
                if iid:
                    result.add(iid)

    # セグメントメンバー
    for seg in segments:
        if seg.get("ospf_area") is not None:
            for member_iface_id in seg.get("members", []):
                result.add(member_iface_id)

    return result


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

    iteration-4 #6: OSPF 参加 IF のみチップ表示、エッジ端点をチップにアンカー。
    """
    if segments is None:
        segments = []
    if interfaces is None:
        interfaces = []

    positions_ospf, ospf_devices, ospf_segments = _build_ospf_layout(
        devices, ospf_entries, links, segments, interfaces
    )

    # OSPF 参加デバイス集合
    ospf_device_ids: set[str] = set(d["id"] for d in ospf_devices)

    # OSPF チップ集合（p2p リンク端点 + セグメントメンバー）
    ospf_chip_ids = _build_ospf_chip_iface_ids(
        links, segments, interfaces, ospf_device_ids
    )

    # チップ座標マップを構築（OSPF 参加デバイス分）
    all_chip_positions: dict[str, tuple[float, float]] = {}
    for dev in ospf_devices:
        dev_pos = positions_ospf.get(dev["id"])
        if dev_pos is None:
            continue
        dev_ifaces = iface_by_device.get(dev["id"], [])
        dev_chip_ids = {i["id"] for i in dev_ifaces if i["id"] in ospf_chip_ids}
        if dev_chip_ids:
            cp = _chip_positions(dev, dev_chip_ids, dev_ifaces, dev_pos[0], dev_pos[1])
            all_chip_positions.update(cp)

    # name_to_iface_id マップ（OSPF p2p リンクのチップアンカー用）
    name_to_iface_id = {(i["device"], i["name"]): i["id"] for i in interfaces}

    # OSPF エッジ（同一リンクの両端が OSPF 参加）— チップアンカー対応
    # Phase 3H: 同一 link_id の v4/v6 エントリを1エッジに統合（dual-stack 重複防止）
    # OSPF 参加リンクのみ抽出
    ospf_links = [
        lk for lk in links
        if lk["a_device"] in ospf_device_ids and lk["b_device"] in ospf_device_ids
    ]
    # 同一 IF ペアを統合（v4/v6 → 1エントリ、subnets リストに両方を格納）
    merged_ospf_links = _merge_links_by_link_id(ospf_links)

    parts = []
    for lk in sorted(merged_ospf_links, key=lambda l: (l.get("a_device", ""), l.get("b_device", ""))):
        # チップアンカー
        a_pos = positions_ospf.get(lk["a_device"], (0.0, 0.0))
        b_pos = positions_ospf.get(lk["b_device"], (0.0, 0.0))
        a_if = lk.get("a_if") or ""
        b_if = lk.get("b_if") or ""
        if all_chip_positions:
            a_iface_id = name_to_iface_id.get((lk["a_device"], a_if))
            b_iface_id = name_to_iface_id.get((lk["b_device"], b_if))
            if a_iface_id and a_iface_id in all_chip_positions:
                a_pos = all_chip_positions[a_iface_id]
            if b_iface_id and b_iface_id in all_chip_positions:
                b_pos = all_chip_positions[b_iface_id]
        x1, y1 = a_pos
        x2, y2 = b_pos

        # Phase 3H: 統合エントリの全 subnet を取得（sorted 決定的）
        subnets = lk.get("subnets") or [lk.get("subnet", "")]
        primary_subnet_raw = subnets[0] if subnets else lk.get("subnet", "")
        primary_subnet = _esc(primary_subnet_raw)

        ospf_area = lk.get("ospf_area")

        # Phase 3H: data-ospf-id は全 subnet を空白区切りで列挙（双方向連動）
        # 統合エッジが v4/v6 両行の ospf_id と対応できるよう複数値を保持する。
        # NOTE: lk.get("ospf_network") は _merge_links_by_link_id で最初の link の
        # ospf_network を保持しているため、subnets の各要素に適用すると全て
        # v4 ospf_network で上書きされ v6 id が欠落する。
        # そのため各 subnet を個別に _normalize_subnet() で正規化する。
        ospf_ids = [
            _normalize_subnet(s)
            for s in subnets
        ]
        ospf_ids = sorted(set(oid for oid in ospf_ids if oid))  # 決定的・重複除去
        if ospf_ids:
            ospf_id_attr = f' data-ospf-id="{_esc(" ".join(ospf_ids))}"'
        else:
            ospf_id_attr = ""

        # リンク中点
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2 - 15

        if ospf_area is not None:
            # Phase 3H: 統合エッジのラベルに全 subnet を「/」区切りで表示（dual-stack 対応）
            if len(subnets) > 1:
                subnets_label = " / ".join(_esc(s) for s in subnets if s)
                label_line1 = OSPF_AREA_LABEL_FORMAT.format(
                    area=_esc(ospf_area), subnet=subnets_label
                )
            else:
                label_line1 = OSPF_AREA_LABEL_FORMAT.format(
                    area=_esc(ospf_area), subnet=primary_subnet
                )
            label_elem = (
                f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" '
                f'class="link-label layer-ospf">{label_line1}</text>'
            )
        else:
            # ospf_area 欠如: subnet のみ表示（後方互換）
            label_elem = (
                f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" '
                f'class="link-label layer-ospf">{primary_subnet}</text>'
            )

        parts.append(
            f'<g class="link-edge" data-subnet="{primary_subnet}" '
            f'data-a="{_esc(lk["a_device"])}" data-b="{_esc(lk["b_device"])}"'
            f'{ospf_id_attr}>'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'class="link-line layer-ospf"/>'
            f'{label_elem}'
            f'</g>'
        )
    edges_str = "\n".join(parts)

    # OSPF 参加セグメント描画（チップアンカー対応）
    ospf_seg_edges_str = _svg_ospf_segment_edges(
        ospf_segments, interfaces, positions_ospf,
        chip_positions=all_chip_positions,
    )
    ospf_segs_str = _svg_ospf_segments(ospf_segments, positions_ospf)

    nodes_str = _svg_nodes(
        ospf_devices, positions_ospf, iface_by_device,
        chip_iface_ids=ospf_chip_ids,
    )
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
        "ifinv": "IF一覧",
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


def _count_if_status(ifaces: list[dict]) -> tuple[int, int, int, int]:
    """IF リストから admin_status を集計し (up, down, admin_down, other) のタプルを返す。

    既知の3種 (up/down/admin-down) 以外の値（None 含む）は other にカウントし
    サイレントドロップしない。

    Args:
        ifaces: interfaces リスト

    Returns:
        (count_up, count_down, count_admin_down, count_other)
    """
    count_up = count_down = count_admin_down = count_other = 0
    for iface in ifaces:
        st = (iface.get("admin_status") or "").lower()
        if st == "up":
            count_up += 1
        elif st == "down":
            count_down += 1
        elif st == "admin-down":
            count_admin_down += 1
        else:
            count_other += 1
    return count_up, count_down, count_admin_down, count_other


def _build_ifinv_table(devices: list[dict], interfaces: list[dict]) -> str:
    """全機器の IF 横断一覧テーブル HTML を生成して返す。

    行は device_id → IF 名の辞書順で決定的に並ぶ。
    各行に ``data-iface-id`` を付与し、将来の編集フック（editable 化）に備える。

    未使用候補（IP 無し かつ admin_status が down または admin-down）の行には
    ``data-unused="1"`` を付与する。

    表上部に status 集計（up / down / admin-down 件数）を表示する。
    既知3種以外の admin_status は other にカウントし（サイレントドロップしない）、
    件数が 1 以上の場合のみバッジとして表示する。

    Args:
        devices: topology の devices リスト（id/hostname）
        interfaces: topology の interfaces リスト（Phase2D 以降の拡張フィールドを含む）

    Returns:
        HTML 文字列（#view-ifinv-table div 全体）
    """
    # device_id -> hostname マップ（表の Device 列用）
    dev_hostname: dict[str, str] = {
        d["id"]: d.get("hostname", d["id"]) for d in devices
    }

    # IF を device_id → IF 名 の辞書順でソート（決定性保証）
    sorted_ifaces = sorted(interfaces, key=lambda i: (i.get("device", ""), i.get("name", "")))

    # status 集計（ヘルパーに委譲）
    count_up, count_down, count_admin_down, count_other = _count_if_status(sorted_ifaces)

    # 集計バー（other は件数>0 の場合のみ表示）
    other_badge = (
        f'<span class="ifinv-badge" style="background:#f3f4f6;color:#374151;border:1px solid #d1d5db;">'
        f'other: {count_other}</span>'
        if count_other > 0 else ""
    )
    summary_html = (
        f'<div class="ifinv-summary">'
        f'<span class="ifinv-badge ifinv-badge-up">up: {count_up}</span>'
        f'<span class="ifinv-badge ifinv-badge-down">down: {count_down}</span>'
        f'<span class="ifinv-badge ifinv-badge-admindown">admin-down: {count_admin_down}</span>'
        f'{other_badge}'
        f'</div>'
    )

    # 検索・フィルタ UI（DC5: イベントは addEventListener で登録 → インライン不使用）
    search_filter_html = (
        f'<div class="ifinv-toolbar">'
        f'<input type="search" id="ifinv-search" placeholder="Device / IF / IP / Description...">'
        f'<label class="ifinv-filter-label">'
        f'<input type="checkbox" id="ifinv-unused-toggle"> '
        f'未使用のみ表示</label>'
        f'</div>'
    )

    # テーブルヘッダ（列ソート: onclick）
    # 列定義が単一の真実源（colOrder は DOM data-col から取得するため列追加時はここだけ変更）
    columns = [
        ("device", "Device"),
        ("name", "Interface"),
        ("ip", "IP"),
        ("admin_status", "Status"),
        ("mtu", "MTU"),
        ("vlan", "VLAN"),
        ("l2_l3", "L2L3"),
        ("description", "Description"),
    ]
    header_cells = []
    for col_key, col_label in columns:
        header_cells.append(
            f'<th class="ifinv-th" data-col="{_esc(col_key)}" data-label="{_esc(col_label)}" '
            f'onclick="sortIfTable(\'{_esc(col_key)}\')" style="cursor:pointer;" '
            f'title="クリックでソート">{_esc(col_label)}</th>'
        )
    thead = f'<thead><tr>{"".join(header_cells)}</tr></thead>'

    # テーブル行
    rows = []
    for iface in sorted_ifaces:
        dev_id = iface.get("device", "")
        iface_id = iface.get("id", "")
        name = iface.get("name", "")
        ip = iface.get("ip") or ""
        admin_status = iface.get("admin_status") or ""
        mtu = iface.get("mtu")
        vlan = iface.get("vlan")
        l2_l3 = iface.get("l2_l3") or ""
        description = iface.get("description") or ""
        hostname = dev_hostname.get(dev_id, dev_id)

        # 未使用候補判定: IP 無し かつ down 系
        st_lower = admin_status.lower()
        is_unused = (not ip) and (st_lower in ("down", "admin-down"))
        unused_attr = ' data-unused="1"' if is_unused else ""

        # 検索用テキスト（device / IF 名 / IP / description）
        search_text = f"{hostname} {name} {ip} {description}".lower()

        # MTU は数値 or 空
        mtu_str = str(mtu) if mtu is not None else ""

        # VLAN 列: iface.vlan 優先 → switchport フォールバック → 空欄
        # switchport 構造: {mode, access_vlan?, trunk_vlans?}
        # trunk_vlans は str または list（パーサー由来 str / テスト由来 list 両対応）
        switchport = iface.get("switchport")
        if vlan is not None:
            # iface.vlan が非 null → 最優先（単一整数扱い、data-num 付与）
            vlan_str = str(vlan)
            vlan_data_num = vlan_str
        elif switchport:
            sp_mode = switchport.get("mode", "")
            if sp_mode == "access":
                av = switchport.get("access_vlan")
                if av is not None:
                    vlan_str = str(av)
                    vlan_data_num = vlan_str  # 単一整数 → data-num 付与
                else:
                    vlan_str = ""
                    vlan_data_num = ""
            elif sp_mode == "trunk":
                tv = switchport.get("trunk_vlans")
                if tv is not None:
                    if isinstance(tv, list):
                        vlan_str = ",".join(str(v) for v in sorted(tv))
                    else:
                        vlan_str = str(tv)
                    vlan_data_num = ""  # trunk 複数 VLAN → data-num なし（文字列ソート扱い）
                else:
                    vlan_str = ""
                    vlan_data_num = ""
            else:
                vlan_str = ""
                vlan_data_num = ""
        else:
            vlan_str = ""
            vlan_data_num = ""

        # 将来の editable フック: data-iface-id が差込点（編集 UI は実装しない）
        row_attrs = (
            f' data-iface-id="{_esc(iface_id)}"'
            f' data-device="{_esc(dev_id)}"'
            f'{unused_attr}'
            f' data-search="{_esc(search_text)}"'
        )
        cells = [
            f'<td>{_esc(hostname)}</td>',
            f'<td>{_esc(name)}</td>',
            f'<td>{_esc(ip)}</td>',
            f'<td>{_esc(admin_status)}</td>',
            f'<td data-num="{_esc(mtu_str)}">{_esc(mtu_str)}</td>',
            f'<td data-num="{_esc(vlan_data_num)}">{_esc(vlan_str)}</td>',
            f'<td>{_esc(l2_l3)}</td>',
            f'<td>{_esc(description)}</td>',
        ]
        rows.append(f'<tr{row_attrs}>{"".join(cells)}</tr>')

    tbody_rows = "\n".join(rows)
    tbody = f'<tbody id="ifinv-table-body">{tbody_rows}</tbody>'

    table_html = f'<table class="ifinv-table">{thead}{tbody}</table>'

    # 全体コンテナ（初期非表示: selectView('ifinv') で表示）
    return (
        f'<div id="view-ifinv-table" style="display:none" '
        f'class="ifinv-container">'
        f'{summary_html}'
        f'{search_filter_html}'
        f'{table_html}'
        f'</div>'
    )
