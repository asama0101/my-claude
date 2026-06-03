"""
rendering/svg.py — SVG 要素生成モジュール
"""
from __future__ import annotations

import html
from collections import defaultdict
from typing import Any

from lib.rendering.layout import (
    _NODE_WIDTH,
    _NODE_HEIGHT,
    _NODE_HEADER_H,
    _NODE_IF_ROW_H,
    _NODE_IF_PADDING,
    _SEG_RX,
    _SEG_RY,
    _node_size_for,
    _AS_GROUP_PADDING,
    _AS_GROUP_RX,
    _AS_GROUP_RY,
    OSPF_AREA_LABEL_FORMAT,
)


def _esc(value: Any) -> str:
    """値を HTML 安全な文字列に変換する"""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _make_link_id(a_device: str, a_if: str, b_device: str, b_if: str) -> str:
    """リンクの決定的 ID を返す。

    両端点 ``{device}::{iface}`` を sorted して ``|`` で結合する。
    両方向から呼んでも同じ文字列が得られる（対称性）。

    Args:
        a_device: A 側 device id
        a_if:     A 側 interface 名
        b_device: B 側 device id
        b_if:     B 側 interface 名

    Returns:
        例: ``"r1::eth0|r2::eth0"``
    """
    endpoints = sorted([f"{a_device}::{a_if}", f"{b_device}::{b_if}"])
    return "|".join(endpoints)


def _build_search_attr(dev: dict, interfaces_for_dev: list[dict]) -> str:
    """device ノードの data-search 属性値を構築する（hostname小文字 + IP群）"""
    parts = [dev["hostname"].lower()]
    for iface in interfaces_for_dev:
        ip = iface.get("ip")
        if ip:
            parts.append(ip.split("/")[0])
    return " ".join(parts)


def _svg_if_row(cx: float, if_start_y: float, k: int, iface: dict) -> str:
    """単一 IF 行の SVG <text> 要素を生成する（_svg_nodes の内部ヘルパー）。

    Args:
        cx:          ノード中心 x 座標
        if_start_y:  IF 行列の開始 y 座標（ヘッダー領域直下）
        k:           IF 行インデックス（0 始まり）
        iface:       IF 辞書
    """
    row_y = if_start_y + k * _NODE_IF_ROW_H + 11  # text baseline
    css_cls = "if-row if-shutdown" if iface.get("shutdown") else "if-row"
    if_name = _esc(iface.get("name", ""))
    if_ip = _esc(iface.get("ip") or "")
    desc = iface.get("description")
    label_text = f"{if_name}  {if_ip}" if if_ip else if_name
    title_elem = f"<title>{_esc(desc)}</title>" if desc else ""
    return (
        f'<text x="{cx:.1f}" y="{row_y:.1f}" text-anchor="middle" '
        f'class="{css_cls}">'
        f'{title_elem}{label_text}</text>'
    )


# IF チップ定数
_IF_CHIP_R = 5       # チップ円の半径（px）
_IF_CHIP_GAP = 14    # チップ間隔（px）
_IF_CHIP_OFFSET_X = 8   # ノード左端からの開始 x オフセット（px）
_IF_CHIP_OFFSET_Y = 12  # ノードヘッダー下端からの y オフセット（px）


def _is_loopback(name: str) -> bool:
    """IF 名が Loopback/lo インタフェースか判定する。

    対応パターン（大文字小文字不問）:
    - ``loopback``  で始まる（Cisco Loopback0 等）
    - ``lo`` に続けて数字・ドット・終端のいずれかが来る（Juniper lo0, lo0.0 等）
    - ``lo`` で終わる（``lo`` 単体）

    local0 / local-bridge 等 ``lo`` で始まるが loopback でないものは除外する。
    """
    n = name.lower()
    if n.startswith("loopback"):
        return True
    if n == "lo":
        return True
    if n.startswith("lo") and len(n) > 2 and (n[2].isdigit() or n[2] == "."):
        return True
    return False


def _svg_if_chip(
    nx: float,
    chip_start_y: float,
    k: int,
    iface: dict,
) -> str:
    """単一 IF チップ要素を生成する（_svg_nodes の内部ヘルパー、iteration-3 #2）。

    チップは小さな circle で表現し、<title> に「IF名 IP（desc）」を持つ。
    shutdown の場合は if-chip-shutdown クラスを追加。

    Args:
        nx:           ノード矩形の左端 x 座標
        chip_start_y: チップ列の開始 y 座標（ヘッダー領域下端）
        k:            チップインデックス（0 始まり）
        iface:        IF 辞書
    """
    # チップを横に並べる: 各チップの中心 x
    cx = nx + _IF_CHIP_OFFSET_X + k * _IF_CHIP_GAP
    cy = chip_start_y + _IF_CHIP_OFFSET_Y

    if_name = iface.get("name", "")
    if_ip = iface.get("ip") or ""
    desc = iface.get("description") or ""

    # title テキスト: "IF名 IP（desc）" 形式
    title_parts = [if_name]
    if if_ip:
        title_parts.append(if_ip)
    if desc:
        title_parts.append(f"（{desc}）")
    title_text = _esc(" ".join(title_parts))

    css_cls = "if-chip if-chip-shutdown" if iface.get("shutdown") else "if-chip"

    return (
        f'<g class="{css_cls}" data-if="{_esc(if_name)}">'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{_IF_CHIP_R}"/>'
        f'<title>{title_text}</title>'
        f'</g>'
    )


def _svg_nodes(
    devices: list[dict],
    positions: dict,
    iface_by_device: dict[str, list[dict]] | None = None,
    *,
    show_interfaces: bool = False,
    connected_iface_ids: set[str] | None = None,
) -> str:
    """機器ノードの SVG 要素を生成する。

    show_interfaces=True のとき（Physical ビュー用）、ノードを可変高カード型にして
    接続IF/Loopback のみを小さなチップ（circle）で表示する（iteration-3 #2）。
    全 IF の詳細はカード表に残る。

    show_interfaces=False（デフォルト）のとき、従来通り hostname + AS/vendor のコンパクト表示。

    Args:
        devices:             デバイスリスト
        positions:           デバイスID → (x, y) 座標辞書
        iface_by_device:     デバイスID → IF リスト辞書
        show_interfaces:     True のとき Physical ビュー用チップ表示
        connected_iface_ids: リンク/セグメント端点の iface-id 集合（Physical ビュー用）。
                             None のとき空集合扱い＝Loopback のみを chip 表示する。
                             Physical ビューでは必ず集合を渡すこと。
    """
    if iface_by_device is None:
        iface_by_device = {}
    if connected_iface_ids is None:
        connected_iface_ids = set()
    parts = []
    for dev in sorted(devices, key=lambda d: d["id"]):
        x, y = positions.get(dev["id"], (0, 0))
        hostname = _esc(dev["hostname"])
        vendor = _esc(dev.get("vendor", ""))
        as_num = _esc(dev.get("as", ""))
        dev_id = _esc(dev["id"])

        label2 = f"AS{as_num}" if dev.get("as") is not None else vendor

        search_val = _esc(_build_search_attr(dev, iface_by_device.get(dev["id"], [])))

        # ノード高さを分岐前に確定して nx/ny を共通計算
        if show_interfaces:
            all_ifaces = sorted(iface_by_device.get(dev["id"], []), key=lambda i: i["name"])
            # 表示対象: 接続IF + Loopback のみ（iteration-3 #2）
            chip_ifaces = [
                iface for iface in all_ifaces
                if iface["id"] in connected_iface_ids or _is_loopback(iface.get("name", ""))
            ]
            # チップは横1行に並べるため高さは固定（チップあり=1行分、なし=0行分）
            n_chip = 1 if chip_ifaces else 0
        else:
            chip_ifaces = []
            n_chip = 0

        _w, node_h = _node_size_for(n_chip) if show_interfaces else (float(_NODE_WIDTH), float(_NODE_HEIGHT))
        nx = x - _NODE_WIDTH / 2
        ny = y - node_h / 2

        if show_interfaces:
            # ----- Physical ビュー: チップ型ノード（iteration-3 #2）-----
            # hostname は上部中央（太字）
            label_y = ny + 14
            sublabel_y = ny + 26

            # チップ開始 y 座標（ヘッダー領域直下）
            chip_start_y = ny + _NODE_HEADER_H

            chips_str = "\n".join(
                _svg_if_chip(nx, chip_start_y, k, iface)
                for k, iface in enumerate(chip_ifaces)
            )

            parts.append(
                f'<g class="device-node" data-device="{dev_id}" '
                f'data-search="{search_val}" '
                f'transform="translate(0,0)">'
                f'<rect x="{nx:.1f}" y="{ny:.1f}" width="{_NODE_WIDTH}" height="{node_h:.1f}" '
                f'rx="6" ry="6" class="node-rect"/>'
                f'<text x="{x:.1f}" y="{label_y:.1f}" text-anchor="middle" class="node-label">'
                f'{hostname}</text>'
                f'<text x="{x:.1f}" y="{sublabel_y:.1f}" text-anchor="middle" class="node-sublabel">'
                f'{label2}</text>'
                + (f'\n{chips_str}' if chips_str else '')
                + f'\n</g>'
            )
        else:
            # ----- BGP/OSPF 等: 従来通りコンパクト表示 -----
            parts.append(
                f'<g class="device-node" data-device="{dev_id}" '
                f'data-search="{search_val}" '
                f'transform="translate(0,0)">'
                f'<rect x="{nx:.1f}" y="{ny:.1f}" width="{_NODE_WIDTH}" height="{_NODE_HEIGHT}" '
                f'rx="6" ry="6" class="node-rect"/>'
                f'<text x="{x:.1f}" y="{y - 6:.1f}" text-anchor="middle" class="node-label">'
                f'{hostname}</text>'
                f'<text x="{x:.1f}" y="{y + 10:.1f}" text-anchor="middle" class="node-sublabel">'
                f'{label2}</text>'
                f'</g>'
            )
    return "\n".join(parts)


def _svg_segments(segments: list[dict], positions: dict) -> str:
    """セグメントノード（楕円）の SVG 要素を生成する。

    #7: <g class="segment-node"> と <ellipse> に ``data-seg-id`` を付与する。
    """
    parts = []
    for seg in sorted(segments, key=lambda s: s["id"]):
        x, y = positions.get(seg["id"], (0, 0))
        seg_id = _esc(seg["id"])
        subnet = _esc(seg["subnet"])
        parts.append(
            f'<g class="segment-node" data-segment="{seg_id}" data-seg-id="{seg_id}">'
            f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{_SEG_RX}" ry="{_SEG_RY}" '
            f'class="seg-ellipse" data-seg-id="{seg_id}"/>'
            f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" class="seg-label">'
            f'{subnet}</text>'
            f'</g>'
        )
    return "\n".join(parts)


def _svg_links(links: list[dict], positions: dict) -> str:
    """リンクエッジの SVG 要素を生成する（Physical ビュー用）。

    常時テキストラベルは持たない（iteration-3 #1）。
    subnet/IF 名は hover の <title> で参照できる程度に留める。
    各 <g class="link-edge"> と <line class="link-line"> に ``data-link-id`` を付与する。
    link-id は ``_make_link_id(a_device, a_if, b_device, b_if)`` で導出（決定的・対称）。
    """
    parts = []
    for link in sorted(links, key=lambda l: (l["a_device"], l["b_device"])):
        a_dev = link["a_device"]
        b_dev = link["b_device"]
        x1, y1 = positions.get(a_dev, (0, 0))
        x2, y2 = positions.get(b_dev, (0, 0))
        subnet = _esc(link.get("subnet", ""))
        a_if_raw = link.get("a_if") or ""
        b_if_raw = link.get("b_if") or ""
        a_if = _esc(a_if_raw)
        b_if = _esc(b_if_raw)
        # 決定的 link-id（両端点をソートして結合）
        link_id = _esc(_make_link_id(a_dev, a_if_raw, b_dev, b_if_raw))
        parts.append(
            f'<g class="link-edge" data-subnet="{subnet}" '
            f'data-a="{_esc(a_dev)}" data-b="{_esc(b_dev)}" data-link-id="{link_id}">'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'class="link-line layer-physical" data-link-id="{link_id}"/>'
            f'<title>{subnet} ({a_if} — {b_if})</title>'
            f'</g>'
        )
    return "\n".join(parts)


def _svg_segment_edges(
    segments: list[dict],
    interfaces: list[dict],
    positions: dict,
) -> str:
    """セグメントメンバーへの接続エッジを生成する。

    #7: <line class="seg-edge"> に ``data-seg-id`` を付与する。
    """
    # interface id -> device id マップ
    iface_map = {iface["id"]: iface["device"] for iface in interfaces}

    parts = []
    for seg in sorted(segments, key=lambda s: s["id"]):
        sx, sy = positions.get(seg["id"], (0, 0))
        seg_id = _esc(seg["id"])
        for member_iface_id in sorted(seg.get("members", [])):
            dev_id = iface_map.get(member_iface_id)
            if dev_id and dev_id in positions:
                dx, dy = positions[dev_id]
                parts.append(
                    f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{dx:.1f}" y2="{dy:.1f}" '
                    f'class="seg-edge layer-physical" data-seg="{seg_id}" '
                    f'data-seg-id="{seg_id}" data-device="{_esc(dev_id)}"/>'
                )
    return "\n".join(parts)


def _svg_ospf_segments(segments: list[dict], positions: dict) -> str:
    """OSPF 参加セグメントノード（楕円）の SVG 要素を生成する。

    Physical ビューの _svg_segments と同様だが、ラベルに「area {area} · {subnet}」を
    表示し、layer-ospf クラスを付与する。
    ospf_area が付いているセグメントのみを対象とする。
    """
    parts = []
    for seg in sorted(segments, key=lambda s: s["id"]):
        ospf_area = seg.get("ospf_area")
        if ospf_area is None:
            continue
        x, y = positions.get(seg["id"], (0, 0))
        seg_id = _esc(seg["id"])
        subnet = _esc(seg["subnet"])
        area_label = OSPF_AREA_LABEL_FORMAT.format(
            area=_esc(ospf_area), subnet=subnet
        )
        parts.append(
            f'<g class="segment-node layer-ospf" data-segment="{seg_id}">'
            f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{_SEG_RX}" ry="{_SEG_RY}" '
            f'class="seg-ellipse layer-ospf"/>'
            f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" '
            f'class="seg-label layer-ospf">'
            f'{area_label}</text>'
            f'</g>'
        )
    return "\n".join(parts)


def _svg_ospf_segment_edges(
    segments: list[dict],
    interfaces: list[dict],
    positions: dict,
) -> str:
    """OSPF 参加セグメントからメンバー機器への接続エッジを生成する。

    Physical ビューの _svg_segment_edges と同様だが、layer-ospf クラスを付与する。
    ospf_area が付いているセグメントのみを対象とする。
    """
    iface_map = {iface["id"]: iface["device"] for iface in interfaces}

    parts = []
    for seg in sorted(segments, key=lambda s: s["id"]):
        if seg.get("ospf_area") is None:
            continue
        sx, sy = positions.get(seg["id"], (0, 0))
        seg_id = _esc(seg["id"])
        for member_iface_id in sorted(seg.get("members", [])):
            dev_id = iface_map.get(member_iface_id)
            if dev_id and dev_id in positions:
                dx, dy = positions[dev_id]
                parts.append(
                    f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{dx:.1f}" y2="{dy:.1f}" '
                    f'class="seg-edge layer-ospf" data-seg="{seg_id}" '
                    f'data-device="{_esc(dev_id)}"/>'
                )
    return "\n".join(parts)


def _svg_bgp_edges(
    bgp_entries: list[dict],
    interfaces: list[dict],
    positions: dict,
) -> str:
    """BGP ピアリングエッジを生成する（ebgp=青、ibgp=橙）"""
    # local_ip -> device_id マップ（各 IF の IP から /prefix を除去して検索）
    ip_to_device: dict[str, str] = {}
    for iface in interfaces:
        if iface.get("ip"):
            ip_only = iface["ip"].split("/")[0]
            ip_to_device[ip_only] = iface["device"]

    parts = []
    # 重複エッジ防止（双方向のペアを1本に）
    seen_pairs: set[frozenset] = set()

    for entry in sorted(bgp_entries, key=lambda e: (e["device"], e["neighbor_ip"])):
        dev_id = entry["device"]
        neighbor_ip = entry.get("neighbor_ip", "")
        bgp_type = entry.get("type", "unknown")

        neighbor_dev = ip_to_device.get(neighbor_ip)
        if not neighbor_dev or neighbor_dev == dev_id:
            continue

        pair = frozenset([dev_id, neighbor_dev])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        if dev_id not in positions or neighbor_dev not in positions:
            continue

        x1, y1 = positions[dev_id]
        x2, y2 = positions[neighbor_dev]

        css_class = f"bgp-edge bgp-{_esc(bgp_type)} layer-bgp"
        peer_as = _esc(entry.get("peer_as", ""))
        local_as = _esc(entry.get("local_as", ""))
        local_ip_raw = entry.get("local_ip") or ""
        neighbor_ip_raw = entry.get("neighbor_ip") or ""

        # エッジを少しオフセットして重なりを防ぐ
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2 - 15

        # #5: IP↔IP 表示テキストを構築
        # local_ip が null の場合は neighbor_ip のみ表示
        if local_ip_raw and neighbor_ip_raw:
            ip_label = f"{_esc(local_ip_raw)}↔{_esc(neighbor_ip_raw)}"
        elif neighbor_ip_raw:
            ip_label = _esc(neighbor_ip_raw)
        else:
            ip_label = ""

        # <title> に完全情報（AS + IP）を埋め込む
        title_parts = [f"{_esc(bgp_type)} AS{local_as}↔AS{peer_as}"]
        if ip_label:
            title_parts.append(ip_label)
        title_text = " | ".join(title_parts)

        # バッジ: 上段に type/AS、下段に IP を2行表示
        # SVG text は tspan で複数行化
        if ip_label:
            badge_svg = (
                f'<text x="{mx:.1f}" y="{my - 8:.1f}" text-anchor="middle" '
                f'class="bgp-badge layer-bgp">'
                f'<tspan x="{mx:.1f}" dy="0">{_esc(bgp_type)} {local_as}↔{peer_as}</tspan>'
                f'<tspan x="{mx:.1f}" dy="12">{ip_label}</tspan>'
                f'</text>'
            )
        else:
            badge_svg = (
                f'<text x="{mx:.1f}" y="{my - 5:.1f}" text-anchor="middle" '
                f'class="bgp-badge layer-bgp">{_esc(bgp_type)} {local_as}↔{peer_as}</text>'
            )

        parts.append(
            f'<g class="bgp-session" data-type="{_esc(bgp_type)}" '
            f'data-a="{_esc(dev_id)}" data-b="{_esc(neighbor_dev)}">'
            f'<path d="M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}" '
            f'class="{css_class}" fill="none"/>'
            f'<title>{title_text}</title>'
            f'{badge_svg}'
            f'</g>'
        )
    return "\n".join(parts)


def _svg_bgp_as_groups(
    bgp_devices: list[dict],
    positions: dict[str, tuple[float, float]],
    padding: float = _AS_GROUP_PADDING,
) -> str:
    """BGP ビュー用 AS グルーピング枠を生成する。

    同一 local_as（device["as"]）の BGP 参加機を
    <g class="as-group-container" data-as="{asn}"> で囲み、
    内部に <rect class="as-group"> と <text class="as-group-label"> を配置する。
    local_as が None の機器は枠なし（クラッシュしない）。
    描画順はノードの背面になるよう呼び出し側で先に出力すること。

    決定性: AS 番号昇順・同一 AS 内はデバイス ID 昇順でソートして処理する。
    """
    # device["as"] を local_as として使用（build 済みなので信頼する）
    # asn -> [device_id, ...] のマップを AS 番号昇順で構築
    asn_to_devs: dict[int, list[str]] = defaultdict(list)
    for dev in sorted(bgp_devices, key=lambda d: d["id"]):
        asn = dev.get("as")
        if asn is None:
            continue
        if dev["id"] in positions:
            asn_to_devs[asn].append(dev["id"])

    parts = []
    for asn in sorted(asn_to_devs.keys()):
        dev_ids = asn_to_devs[asn]
        if not dev_ids:
            continue

        # bounding box を計算（ノード中心座標から node-rect の左上/右下を算出）
        xs = [positions[d][0] for d in dev_ids]
        ys = [positions[d][1] for d in dev_ids]
        min_x = min(xs) - _NODE_WIDTH / 2 - padding
        min_y = min(ys) - _NODE_HEIGHT / 2 - padding
        max_x = max(xs) + _NODE_WIDTH / 2 + padding
        max_y = max(ys) + _NODE_HEIGHT / 2 + padding

        rect_w = max_x - min_x
        rect_h = max_y - min_y

        # M5: <g class="as-group-container" data-as="{asn}"> でラップ
        # #4: ラベルを左上チップ（背景 rect + text）として配置
        chip_x = min_x + 8
        chip_y = min_y - 9   # 枠上端より少し上にはみ出してチップを置く
        chip_text = f"AS {_esc(asn)}"
        # チップ背景矩形のサイズ（文字数に応じた概算幅: 1文字 ≒ 7px）
        chip_w = len(f"AS {asn}") * 7 + 10
        chip_h = 16
        parts.append(
            f'<g class="as-group-container" data-as="{_esc(asn)}">'
            f'<rect x="{min_x:.1f}" y="{min_y:.1f}" '
            f'width="{rect_w:.1f}" height="{rect_h:.1f}" '
            f'rx="{_AS_GROUP_RX}" ry="{_AS_GROUP_RY}" class="as-group"/>'
            f'<rect x="{chip_x:.1f}" y="{chip_y:.1f}" '
            f'width="{chip_w:.1f}" height="{chip_h:.1f}" '
            f'rx="4" ry="4" class="as-group-label-bg"/>'
            f'<text x="{chip_x + 5:.1f}" y="{chip_y + 11:.1f}" '
            f'text-anchor="start" class="as-group-label">'
            f'{chip_text}</text>'
            f'</g>'
        )
    return "\n".join(parts)


def _make_iface_by_device(interfaces: list[dict]) -> dict[str, list[dict]]:
    """interface リストを device_id → [iface, ...] に変換する"""
    result: dict[str, list[dict]] = {}
    for iface in interfaces:
        result.setdefault(iface["device"], []).append(iface)
    return result


