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
    _AS_GROUP_LABEL_OFFSET,
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


def _svg_nodes(
    devices: list[dict],
    positions: dict,
    iface_by_device: dict[str, list[dict]] | None = None,
    *,
    show_interfaces: bool = False,
) -> str:
    """機器ノードの SVG 要素を生成する。

    show_interfaces=True のとき（Physical ビュー用）、ノードを可変高カード型にして
    配下の全 IF（name/ip）を小フォントで列挙する。shutdown は淡色クラス付与。
    description がある IF 行には <title> でホバー表示する。

    show_interfaces=False（デフォルト）のとき、従来通り hostname + AS/vendor のコンパクト表示。
    """
    if iface_by_device is None:
        iface_by_device = {}
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
            ifaces = sorted(iface_by_device.get(dev["id"], []), key=lambda i: i["name"])
            n_if = len(ifaces)
        else:
            ifaces = []
            n_if = 0

        _w, node_h = _node_size_for(n_if) if show_interfaces else (float(_NODE_WIDTH), float(_NODE_HEIGHT))
        nx = x - _NODE_WIDTH / 2
        ny = y - node_h / 2

        if show_interfaces:
            # ----- Physical ビュー: 可変高カード型ノード -----
            # hostname は上部中央（太字）
            label_y = ny + 14
            sublabel_y = ny + 26

            # IF 行開始 y 座標
            if_start_y = ny + _NODE_HEADER_H + _NODE_IF_PADDING // 2

            if_rows_str = "\n".join(
                _svg_if_row(x, if_start_y, k, iface)
                for k, iface in enumerate(ifaces)
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
                + (f'\n{if_rows_str}' if if_rows_str else '')
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
    """セグメントノード（楕円）の SVG 要素を生成する"""
    parts = []
    for seg in sorted(segments, key=lambda s: s["id"]):
        x, y = positions.get(seg["id"], (0, 0))
        seg_id = _esc(seg["id"])
        subnet = _esc(seg["subnet"])
        parts.append(
            f'<g class="segment-node" data-segment="{seg_id}">'
            f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{_SEG_RX}" ry="{_SEG_RY}" '
            f'class="seg-ellipse"/>'
            f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" class="seg-label">'
            f'{subnet}</text>'
            f'</g>'
        )
    return "\n".join(parts)


def _svg_links(links: list[dict], positions: dict) -> str:
    """リンクエッジの SVG 要素を生成する（Physical ビュー用）。

    リンク中点に「a_if — b_if」＋ subnet の常時 <text> ラベルを表示する。
    オフセットは BGP バッジと同様の手法（中点から -15px 上）を流用する。
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
        # リンク中点（BGP バッジと同様の手法）
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2 - 15
        label_text = f"{a_if} — {b_if}"
        parts.append(
            f'<g class="link-edge" data-subnet="{subnet}" '
            f'data-a="{_esc(a_dev)}" data-b="{_esc(b_dev)}" data-link-id="{link_id}">'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'class="link-line layer-physical" data-link-id="{link_id}"/>'
            f'<title>{subnet} ({a_if} — {b_if})</title>'
            f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" class="link-label layer-physical">'
            f'{label_text}</text>'
            f'<text x="{mx:.1f}" y="{my + 12:.1f}" text-anchor="middle" class="link-label layer-physical">'
            f'{subnet}</text>'
            f'</g>'
        )
    return "\n".join(parts)


def _svg_segment_edges(
    segments: list[dict],
    interfaces: list[dict],
    positions: dict,
) -> str:
    """セグメントメンバーへの接続エッジを生成する"""
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
                    f'data-device="{_esc(dev_id)}"/>'
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

        # エッジを少しオフセットして重なりを防ぐ
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2 - 15

        parts.append(
            f'<g class="bgp-session" data-type="{_esc(bgp_type)}" '
            f'data-a="{_esc(dev_id)}" data-b="{_esc(neighbor_dev)}">'
            f'<path d="M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}" '
            f'class="{css_class}" fill="none"/>'
            f'<text x="{mx:.1f}" y="{my - 5:.1f}" text-anchor="middle" '
            f'class="bgp-badge layer-bgp">{_esc(bgp_type)} {local_as}↔{peer_as}</text>'
            f'</g>'
        )
    return "\n".join(parts)


def _svg_bgp_as_groups(
    bgp_devices: list[dict],
    positions: dict[str, tuple[float, float]],
    padding: float = _AS_GROUP_PADDING,
    label_offset_y: float = _AS_GROUP_LABEL_OFFSET,
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
        label_x = (min_x + max_x) / 2
        label_y = min_y + label_offset_y

        # M5: <g class="as-group-container" data-as="{asn}"> でラップ
        parts.append(
            f'<g class="as-group-container" data-as="{_esc(asn)}">'
            f'<rect x="{min_x:.1f}" y="{min_y:.1f}" '
            f'width="{rect_w:.1f}" height="{rect_h:.1f}" '
            f'rx="{_AS_GROUP_RX}" ry="{_AS_GROUP_RY}" class="as-group"/>'
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" '
            f'text-anchor="middle" class="as-group-label">'
            f'AS {_esc(asn)}</text>'
            f'</g>'
        )
    return "\n".join(parts)


def _make_iface_by_device(interfaces: list[dict]) -> dict[str, list[dict]]:
    """interface リストを device_id → [iface, ...] に変換する"""
    result: dict[str, list[dict]] = {}
    for iface in interfaces:
        result.setdefault(iface["device"], []).append(iface)
    return result


