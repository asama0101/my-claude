"""
rendering/svg.py — SVG 要素生成モジュール
"""
from __future__ import annotations

import html
from typing import Any

from lib.rendering.layout import (
    _NODE_WIDTH,
    _NODE_HEIGHT,
    _SEG_RX,
    _SEG_RY,
)


def _esc(value: Any) -> str:
    """値を HTML 安全な文字列に変換する"""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _build_search_attr(dev: dict, interfaces_for_dev: list[dict]) -> str:
    """device ノードの data-search 属性値を構築する（hostname小文字 + IP群）"""
    parts = [dev["hostname"].lower()]
    for iface in interfaces_for_dev:
        ip = iface.get("ip")
        if ip:
            parts.append(ip.split("/")[0])
    return " ".join(parts)


def _svg_nodes(
    devices: list[dict],
    positions: dict,
    iface_by_device: dict[str, list[dict]] | None = None,
) -> str:
    """機器ノードの SVG 要素を生成する"""
    if iface_by_device is None:
        iface_by_device = {}
    parts = []
    for dev in sorted(devices, key=lambda d: d["id"]):
        x, y = positions.get(dev["id"], (0, 0))
        nx = x - _NODE_WIDTH / 2
        ny = y - _NODE_HEIGHT / 2
        hostname = _esc(dev["hostname"])
        vendor = _esc(dev.get("vendor", ""))
        as_num = _esc(dev.get("as", ""))
        dev_id = _esc(dev["id"])

        label2 = f"AS{as_num}" if dev.get("as") is not None else vendor

        search_val = _esc(_build_search_attr(dev, iface_by_device.get(dev["id"], [])))

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
    """リンクエッジの SVG 要素を生成する"""
    parts = []
    for link in sorted(links, key=lambda l: (l["a_device"], l["b_device"])):
        a_dev = link["a_device"]
        b_dev = link["b_device"]
        x1, y1 = positions.get(a_dev, (0, 0))
        x2, y2 = positions.get(b_dev, (0, 0))
        subnet = _esc(link["subnet"])
        a_if = _esc(link["a_if"])
        b_if = _esc(link["b_if"])
        parts.append(
            f'<g class="link-edge" data-subnet="{subnet}" '
            f'data-a="{_esc(a_dev)}" data-b="{_esc(b_dev)}">'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'class="link-line layer-physical"/>'
            f'<title>{subnet} ({a_if} — {b_if})</title>'
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
                    f'class="seg-edge layer-physical" data-seg="{seg_id}"/>'
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
            f'<g class="bgp-session" data-type="{_esc(bgp_type)}">'
            f'<path d="M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}" '
            f'class="{css_class}" fill="none"/>'
            f'<text x="{mx:.1f}" y="{my - 5:.1f}" text-anchor="middle" '
            f'class="bgp-badge layer-bgp">{_esc(bgp_type)} {local_as}↔{peer_as}</text>'
            f'</g>'
        )
    return "\n".join(parts)


def _make_iface_by_device(interfaces: list[dict]) -> dict[str, list[dict]]:
    """interface リストを device_id → [iface, ...] に変換する"""
    result: dict[str, list[dict]] = {}
    for iface in interfaces:
        result.setdefault(iface["device"], []).append(iface)
    return result


def _svg_l3_subnet_nodes(
    links: list[dict],
    segments: list[dict],
    positions_l3: dict,
) -> str:
    """L3 ビュー用サブネットノード（P2Pリンク + segments のサブネット楕円）"""
    parts = []
    seen_subnets: set[str] = set()

    # P2P リンクのサブネット
    for lk in sorted(links, key=lambda l: l["subnet"]):
        subnet = lk["subnet"]
        if subnet in seen_subnets:
            continue
        seen_subnets.add(subnet)
        node_id = f"l3-sub-{subnet}"
        x, y = positions_l3.get(node_id, (0, 0))
        parts.append(
            f'<g class="segment-node" data-segment="{_esc(node_id)}">'
            f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{_SEG_RX}" ry="{_SEG_RY}" '
            f'class="seg-ellipse"/>'
            f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" class="seg-label">'
            f'{_esc(subnet)}</text>'
            f'</g>'
        )

    # segments のサブネット（既存の segment ノード）
    for seg in sorted(segments, key=lambda s: s["id"]):
        node_id = seg["id"]
        if node_id in positions_l3:
            x, y = positions_l3[node_id]
            parts.append(
                f'<g class="segment-node" data-segment="{_esc(node_id)}">'
                f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{_SEG_RX}" ry="{_SEG_RY}" '
                f'class="seg-ellipse"/>'
                f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" class="seg-label">'
                f'{_esc(seg["subnet"])}</text>'
                f'</g>'
            )

    return "\n".join(parts)


def _svg_l3_edges(
    links: list[dict],
    segments: list[dict],
    interfaces: list[dict],
    routing: dict,
    positions_l3: dict,
) -> str:
    """L3 ビュー用エッジ（device → サブネットノード）"""
    iface_to_device = {iface["id"]: iface["device"] for iface in interfaces}
    parts = []

    # P2P リンク: 両端 device → サブネットノード（デデュップ: dev_id × subnet_node_id で一意化）
    seen_dev_subnet: set[tuple[str, str]] = set()
    for lk in sorted(links, key=lambda l: l["subnet"]):
        subnet = lk["subnet"]
        subnet_node_id = f"l3-sub-{subnet}"
        if subnet_node_id not in positions_l3:
            continue
        sx, sy = positions_l3[subnet_node_id]
        for dev_id in (lk["a_device"], lk["b_device"]):
            pair = (dev_id, subnet_node_id)
            if pair in seen_dev_subnet:
                continue
            seen_dev_subnet.add(pair)
            if dev_id in positions_l3:
                dx, dy = positions_l3[dev_id]
                parts.append(
                    f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{dx:.1f}" y2="{dy:.1f}" '
                    f'class="l3-edge layer-l3" data-seg="{_esc(subnet_node_id)}"/>'
                )

    # segments メンバー（デデュップ: dev_id × node_id で一意化）
    for seg in sorted(segments, key=lambda s: s["id"]):
        node_id = seg["id"]
        if node_id not in positions_l3:
            continue
        sx, sy = positions_l3[node_id]
        for member_iface_id in sorted(seg.get("members", [])):
            dev_id = iface_to_device.get(member_iface_id)
            if dev_id and dev_id in positions_l3:
                pair = (dev_id, node_id)
                if pair in seen_dev_subnet:
                    continue
                seen_dev_subnet.add(pair)
                dx, dy = positions_l3[dev_id]
                parts.append(
                    f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{dx:.1f}" y2="{dy:.1f}" '
                    f'class="l3-edge layer-l3" data-seg="{_esc(node_id)}"/>'
                )

    # BGP オーバーレイ（routing 隣接強調）
    bgp_entries = routing.get("bgp", [])
    if bgp_entries:
        parts.append(_svg_bgp_edges(bgp_entries, interfaces, positions_l3))

    return "\n".join(parts)
