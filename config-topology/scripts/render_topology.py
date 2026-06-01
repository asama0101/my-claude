"""
render_topology.py — topology.json を自己完結 HTML (SVG + vanilla JS) にレンダリングする。

公開 API:
    render(topology: dict) -> str   # 自己完結 HTML 文字列を返す
    main()                          # CLI エントリーポイント

CLI:
    python scripts/render_topology.py <topology.json> [-o out.html]
    -o 省略時は入力と同じディレクトリに topology.html を生成する。

設計原則:
- 標準ライブラリのみ（外部依存なし）
- 決定論的レイアウト: Math.random() や時刻に依存しない
- self-contained HTML: file:// で直接開ける（外部 CDN 不使用）
- HTML エスケープ: hostname / description 等のユーザーデータは必ずエスケープ
- 堅牢性: 空 topology でもクラッシュしない
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import sys
from typing import Any


# ---------------------------------------------------------------------------
# HTML エスケープヘルパー
# ---------------------------------------------------------------------------

def _esc(value: Any) -> str:
    """値を HTML 安全な文字列に変換する"""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


# ---------------------------------------------------------------------------
# 決定論的レイアウト計算
# ---------------------------------------------------------------------------

def _compute_layout(devices: list[dict], segments: list[dict]) -> dict[str, tuple[float, float]]:
    """
    機器とセグメントノードの座標を決定的に計算する。

    配置アルゴリズム:
    - 機器は円形に等間隔配置（デバイス ID の安定ソート順）
    - セグメントノードは中心付近に配置
    - 1台の場合は中央、0台の場合も中央に配置
    """
    positions: dict[str, tuple[float, float]] = {}

    cx, cy = 460.0, 300.0  # SVG 中心
    device_radius = 200.0   # 機器配置円の半径

    sorted_devices = sorted(devices, key=lambda d: d["id"])
    n = len(sorted_devices)

    if n == 0:
        pass
    elif n == 1:
        positions[sorted_devices[0]["id"]] = (cx, cy)
    else:
        for i, dev in enumerate(sorted_devices):
            angle = (2 * math.pi * i / n) - math.pi / 2  # 上から時計回り
            x = cx + device_radius * math.cos(angle)
            y = cy + device_radius * math.sin(angle)
            positions[dev["id"]] = (x, y)

    # セグメントノードは中心寄りに配置
    sorted_segments = sorted(segments, key=lambda s: s["id"])
    m = len(sorted_segments)
    seg_radius = 80.0

    for j, seg in enumerate(sorted_segments):
        if m == 1:
            positions[seg["id"]] = (cx, cy - seg_radius)
        else:
            angle = (2 * math.pi * j / m)
            sx = cx + seg_radius * math.cos(angle)
            sy = cy + seg_radius * math.sin(angle)
            positions[seg["id"]] = (sx, sy)

    return positions


# ---------------------------------------------------------------------------
# SVG 生成
# ---------------------------------------------------------------------------

_NODE_WIDTH = 120
_NODE_HEIGHT = 50
_SEG_RX = 50
_SEG_RY = 25


def _svg_nodes(devices: list[dict], positions: dict) -> str:
    """機器ノードの SVG 要素を生成する"""
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

        parts.append(
            f'<g class="device-node" data-device="{dev_id}" '
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


# ---------------------------------------------------------------------------
# 機器カード生成
# ---------------------------------------------------------------------------

def _device_cards(
    devices: list[dict],
    interfaces: list[dict],
    routing: dict,
) -> str:
    """機器ごとのカード HTML を生成する（図の下に表示）"""
    # device_id -> interfaces マップ
    iface_by_device: dict[str, list[dict]] = {}
    for iface in interfaces:
        dev_id = iface["device"]
        iface_by_device.setdefault(dev_id, []).append(iface)

    # routing サマリー
    bgp_by_device: dict[str, list[dict]] = {}
    for entry in routing.get("bgp", []):
        bgp_by_device.setdefault(entry["device"], []).append(entry)

    ospf_by_device: dict[str, list[dict]] = {}
    for entry in routing.get("ospf", []):
        ospf_by_device.setdefault(entry["device"], []).append(entry)

    static_by_device: dict[str, list[dict]] = {}
    for entry in routing.get("static", []):
        static_by_device.setdefault(entry["device"], []).append(entry)

    cards = []
    for dev in sorted(devices, key=lambda d: d["id"]):
        dev_id = dev["id"]
        hostname = _esc(dev["hostname"])
        vendor = _esc(dev.get("vendor", ""))
        as_num = dev.get("as")
        as_str = f"AS{_esc(as_num)}" if as_num is not None else "—"

        # IF テーブル
        if_rows = ""
        for iface in sorted(iface_by_device.get(dev_id, []), key=lambda i: i["name"]):
            shutdown_mark = " (shutdown)" if iface.get("shutdown") else ""
            if_rows += (
                f"<tr>"
                f"<td>{_esc(iface['name'])}{_esc(shutdown_mark)}</td>"
                f"<td>{_esc(iface.get('ip', ''))}</td>"
                f"<td>{_esc(iface.get('description', ''))}</td>"
                f"</tr>"
            )

        # BGP サマリー
        bgp_rows = ""
        for b in bgp_by_device.get(dev_id, []):
            bgp_rows += (
                f"<tr>"
                f"<td>{_esc(b.get('neighbor_ip', ''))}</td>"
                f"<td>{_esc(b.get('peer_as', ''))}</td>"
                f"<td>{_esc(b.get('type', ''))}</td>"
                f"</tr>"
            )

        # OSPF サマリー
        ospf_rows = ""
        for o in ospf_by_device.get(dev_id, []):
            ospf_rows += (
                f"<tr>"
                f"<td>{_esc(o.get('network', ''))}</td>"
                f"<td>Area {_esc(o.get('area', ''))}</td>"
                f"<td>PID {_esc(o.get('process', ''))}</td>"
                f"</tr>"
            )

        # static サマリー
        static_rows = ""
        for s in static_by_device.get(dev_id, []):
            static_rows += (
                f"<tr>"
                f"<td>{_esc(s.get('prefix', ''))}</td>"
                f"<td>{_esc(s.get('next_hop', ''))}</td>"
                f"</tr>"
            )

        # sections 汎用テーブル
        section_html = ""
        for sec in dev.get("sections", []):
            sec_title = _esc(sec.get("title", ""))
            sec_rows = ""
            for row in sec.get("rows", []):
                cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
                sec_rows += f"<tr>{cells}</tr>"
            section_html += (
                f"<h4>{sec_title}</h4>"
                f"<table class='section-table'><tbody>{sec_rows}</tbody></table>"
            )

        card = f"""
<div class="device-card" data-device="{_esc(dev_id)}">
  <h3>{hostname} <span class="badge-vendor">{vendor}</span> <span class="badge-as">{as_str}</span></h3>
  <h4>Interfaces</h4>
  <table>
    <thead><tr><th>Name</th><th>IP</th><th>Description</th></tr></thead>
    <tbody>{if_rows}</tbody>
  </table>
  {f'''<h4 class="layer-bgp">BGP Sessions</h4>
  <table class="layer-bgp">
    <thead><tr><th>Neighbor</th><th>Peer AS</th><th>Type</th></tr></thead>
    <tbody>{bgp_rows}</tbody>
  </table>''' if bgp_rows else ''}
  {f'''<h4 class="layer-ospf">OSPF Networks</h4>
  <table class="layer-ospf">
    <thead><tr><th>Network</th><th>Area</th><th>Process</th></tr></thead>
    <tbody>{ospf_rows}</tbody>
  </table>''' if ospf_rows else ''}
  {f'''<h4 class="layer-static">Static Routes</h4>
  <table class="layer-static">
    <thead><tr><th>Prefix</th><th>Next Hop</th></tr></thead>
    <tbody>{static_rows}</tbody>
  </table>''' if static_rows else ''}
  {section_html}
</div>"""
        cards.append(card)

    return "\n".join(cards)


# ---------------------------------------------------------------------------
# レイヤートグル生成
# ---------------------------------------------------------------------------

def _layer_toggles(routing: dict) -> str:
    """routing キーを走査してレイヤートグルチェックボックスを生成する"""
    layers = [("physical", "Physical", True)]
    for key in sorted(routing.keys()):
        layers.append((key, key.upper(), True))

    toggles = []
    for layer_id, label, checked in layers:
        checked_attr = "checked" if checked else ""
        toggles.append(
            f'<label class="layer-toggle">'
            f'<input type="checkbox" id="toggle-{_esc(layer_id)}" '
            f'data-layer="{_esc(layer_id)}" {checked_attr} '
            f'onchange="handleLayerToggle(this)"> {_esc(label)}'
            f'</label>'
        )
    return "\n".join(toggles)


# ---------------------------------------------------------------------------
# メイン render 関数
# ---------------------------------------------------------------------------

def render(topology: dict) -> str:
    """
    topology dict を受け取り、自己完結 HTML 文字列を返す。

    Args:
        topology: topology.json スキーマ準拠の dict

    Returns:
        file:// で直接開ける自己完結 HTML 文字列
    """
    title = _esc(topology.get("title", "Network Topology"))
    devices: list[dict] = topology.get("devices", [])
    interfaces: list[dict] = topology.get("interfaces", [])
    links: list[dict] = topology.get("links", [])
    segments: list[dict] = topology.get("segments", [])
    routing: dict = topology.get("routing", {})

    # 決定論的レイアウト計算
    positions = _compute_layout(devices, segments)

    # SVG コンテンツ生成
    svg_segment_edges = _svg_segment_edges(segments, interfaces, positions)
    svg_links_str = _svg_links(links, positions)
    svg_bgp_edges = _svg_bgp_edges(routing.get("bgp", []), interfaces, positions)
    svg_segments_str = _svg_segments(segments, positions)
    svg_nodes_str = _svg_nodes(devices, positions)

    # 機器カード
    cards_html = _device_cards(devices, interfaces, routing)

    # レイヤートグル
    toggles_html = _layer_toggles(routing)

    # レイヤー表示制御 CSS を動的生成（physical + routing の全キー）
    layer_ids = ["physical"] + sorted(routing.keys())
    layer_hide_css_parts = []
    for layer_id in layer_ids:
        esc_id = _esc(layer_id)
        if layer_id == "physical":
            layer_hide_css_parts.append(
                f"    body.hide-physical .layer-physical,\n"
                f"    body.hide-physical .seg-edge {{ display: none; }}"
            )
        else:
            layer_hide_css_parts.append(
                f"    body.hide-{esc_id} .layer-{esc_id} {{ display: none; }}"
            )
    layer_hide_css = "\n".join(layer_hide_css_parts)

    # topology JSON の埋め込み（HTML エスケープ済みの JSON）
    topology_json = json.dumps(topology, ensure_ascii=False, sort_keys=True, indent=2)
    # JSON 内の </script> と HTML コメント開始 <!-- を安全にエスケープ
    topology_json_safe = topology_json.replace("</", "<\\/").replace("<!--", "<\\!--")

    svg_width = 920
    svg_height = 600

    html_output = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    /* CSS 変数によるカラースキーム（拡張用） */
    :root {{
      --color-node-fill: #dbeafe;
      --color-node-stroke: #3b82f6;
      --color-node-text: #1e3a5f;
      --color-seg-fill: #fef3c7;
      --color-seg-stroke: #d97706;
      --color-link: #6b7280;
      --color-bgp-ebgp: #2563eb;
      --color-bgp-ibgp: #d97706;
      --color-bgp-unknown: #9ca3af;
      --color-highlight: #f59e0b;
      --color-selected: #ef4444;
      --color-card-bg: #f9fafb;
      --color-card-border: #e5e7eb;
      --font-main: 'Segoe UI', Arial, sans-serif;
      --font-mono: 'Consolas', 'Courier New', monospace;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: var(--font-main);
      background: #f3f4f6;
      color: #111827;
    }}

    header {{
      background: #1e3a5f;
      color: #fff;
      padding: 12px 20px;
      display: flex;
      align-items: center;
      gap: 16px;
    }}

    header h1 {{
      font-size: 1.1rem;
      font-weight: 600;
    }}

    .controls {{
      background: #fff;
      border-bottom: 1px solid var(--color-card-border);
      padding: 8px 20px;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
    }}

    .controls-label {{
      font-size: 0.8rem;
      font-weight: 600;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    .layer-toggle {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 0.85rem;
      cursor: pointer;
      padding: 3px 8px;
      border-radius: 4px;
      border: 1px solid var(--color-card-border);
      background: var(--color-card-bg);
      user-select: none;
    }}

    .layer-toggle:hover {{
      background: #e5e7eb;
    }}

    kbd {{
      font-family: var(--font-mono);
      background: #e5e7eb;
      border: 1px solid #9ca3af;
      border-radius: 3px;
      padding: 1px 5px;
      font-size: 0.75rem;
    }}

    #svg-container {{
      overflow: hidden;
      background: #fff;
      border-bottom: 1px solid var(--color-card-border);
      cursor: grab;
      position: relative;
    }}

    #svg-container:active {{
      cursor: grabbing;
    }}

    #topology-svg {{
      display: block;
    }}

    /* ノード */
    .node-rect {{
      fill: var(--color-node-fill);
      stroke: var(--color-node-stroke);
      stroke-width: 2;
      transition: fill 0.15s, stroke-width 0.15s;
    }}

    .device-node:hover .node-rect,
    .device-node.highlighted .node-rect {{
      fill: #bfdbfe;
      stroke-width: 3;
    }}

    .device-node.selected .node-rect {{
      fill: #fef08a;
      stroke: var(--color-selected);
      stroke-width: 3;
    }}

    .node-label {{
      font-size: 13px;
      font-weight: 700;
      fill: var(--color-node-text);
      pointer-events: none;
    }}

    .node-sublabel {{
      font-size: 10px;
      fill: #6b7280;
      pointer-events: none;
    }}

    /* セグメントノード */
    .seg-ellipse {{
      fill: var(--color-seg-fill);
      stroke: var(--color-seg-stroke);
      stroke-width: 2;
    }}

    .seg-label {{
      font-size: 10px;
      fill: #92400e;
      pointer-events: none;
    }}

    .seg-edge {{
      stroke: var(--color-seg-stroke);
      stroke-width: 1.5;
      stroke-dasharray: 6 3;
    }}

    /* リンク */
    .link-line {{
      stroke: var(--color-link);
      stroke-width: 2;
      transition: stroke 0.15s, stroke-width 0.15s;
    }}

    .link-edge:hover .link-line,
    .link-edge.highlighted .link-line {{
      stroke: var(--color-highlight);
      stroke-width: 4;
    }}

    /* BGP エッジ */
    .bgp-edge {{
      stroke-width: 2;
      stroke-dasharray: 8 4;
      opacity: 0.8;
    }}

    .bgp-ebgp {{ stroke: var(--color-bgp-ebgp); }}
    .bgp-ibgp {{ stroke: var(--color-bgp-ibgp); }}
    .bgp-unknown {{ stroke: var(--color-bgp-unknown); }}

    .bgp-badge {{
      font-size: 9px;
      fill: var(--color-bgp-ebgp);
      pointer-events: none;
      font-family: var(--font-mono);
    }}

    /* カード */
    #cards-section {{
      padding: 20px;
    }}

    #cards-section h2 {{
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 12px;
      color: #374151;
    }}

    .cards-grid {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
    }}

    .device-card {{
      background: var(--color-card-bg);
      border: 1px solid var(--color-card-border);
      border-radius: 8px;
      padding: 16px;
      min-width: 280px;
      max-width: 480px;
      flex: 1;
    }}

    .device-card h3 {{
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 10px;
      display: flex;
      gap: 6px;
      align-items: center;
      flex-wrap: wrap;
    }}

    .device-card h4 {{
      font-size: 0.8rem;
      font-weight: 600;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin: 10px 0 4px;
    }}

    .badge-vendor {{
      font-size: 0.7rem;
      background: #e0e7ff;
      color: #3730a3;
      padding: 2px 6px;
      border-radius: 10px;
      font-weight: 500;
    }}

    .badge-as {{
      font-size: 0.7rem;
      background: #d1fae5;
      color: #065f46;
      padding: 2px 6px;
      border-radius: 10px;
      font-weight: 500;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.8rem;
    }}

    th {{
      text-align: left;
      padding: 3px 6px;
      background: #f3f4f6;
      color: #6b7280;
      font-weight: 600;
    }}

    td {{
      padding: 3px 6px;
      border-bottom: 1px solid #f3f4f6;
      font-family: var(--font-mono);
      word-break: break-all;
    }}

    tr:last-child td {{ border-bottom: none; }}

    .section-table {{ margin-top: 4px; }}

    /* レイヤー表示制御（routing キーから動的生成） */
{layer_hide_css}
  </style>
</head>
<body>
  <header>
    <h1 id="topo-title">{title}</h1>
    <span style="font-size:0.75rem;opacity:0.7;">
      <kbd>F</kbd> 全体表示　<kbd>Esc</kbd> リセット　ホイール=ズーム　ドラッグ=パン
    </span>
  </header>

  <div class="controls">
    <span class="controls-label">Layers:</span>
    {toggles_html}
  </div>

  <div id="svg-container" style="width:100%;height:{svg_height}px;">
    <svg id="topology-svg"
         width="{svg_width}" height="{svg_height}"
         viewBox="0 0 {svg_width} {svg_height}"
         xmlns="http://www.w3.org/2000/svg">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8"
                refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill="#6b7280"/>
        </marker>
      </defs>
      <!-- ズーム/パン用グループ -->
      <g id="viewport">
        <!-- セグメント接続エッジ（背面） -->
        {svg_segment_edges}
        <!-- P2P リンク -->
        {svg_links_str}
        <!-- BGP オーバーレイ -->
        {svg_bgp_edges}
        <!-- セグメントノード -->
        {svg_segments_str}
        <!-- 機器ノード -->
        {svg_nodes_str}
      </g>
    </svg>
  </div>

  <div id="cards-section">
    <h2>Device Details</h2>
    <div class="cards-grid">
      {cards_html}
    </div>
  </div>

  <!-- 埋め込み topology データ -->
  <script type="application/json" id="topology-data">
{topology_json_safe}
  </script>

  <script>
    // ============================================================
    // ズーム / パン
    // ============================================================
    (function() {{
      const container = document.getElementById('svg-container');
      const svg = document.getElementById('topology-svg');
      const vp = document.getElementById('viewport');

      let scale = 1.0;
      let translateX = 0;
      let translateY = 0;
      let isDragging = false;
      let dragStart = {{ x: 0, y: 0 }};
      let translateStart = {{ x: 0, y: 0 }};

      function applyTransform() {{
        vp.setAttribute('transform',
          'translate(' + translateX + ',' + translateY + ') scale(' + scale + ')');
      }}

      // ズーム（マウスホイール）
      container.addEventListener('wheel', function(e) {{
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        scale = Math.max(0.2, Math.min(5.0, scale * delta));
        applyTransform();
      }}, {{ passive: false }});

      // パン（マウスドラッグ）
      container.addEventListener('mousedown', function(e) {{
        if (e.target.closest('.device-node') || e.target.closest('.link-edge')) return;
        isDragging = true;
        dragStart = {{ x: e.clientX, y: e.clientY }};
        translateStart = {{ x: translateX, y: translateY }};
        e.preventDefault();
      }});

      document.addEventListener('mousemove', function(e) {{
        if (!isDragging) return;
        translateX = translateStart.x + (e.clientX - dragStart.x);
        translateY = translateStart.y + (e.clientY - dragStart.y);
        applyTransform();
      }});

      document.addEventListener('mouseup', function() {{
        isDragging = false;
      }});

      // キーボード
      document.addEventListener('keydown', function(e) {{
        if (e.key === 'f' || e.key === 'F') {{
          // 全体表示（リセット）
          scale = 1.0;
          translateX = 0;
          translateY = 0;
          applyTransform();
        }} else if (e.key === 'Escape') {{
          // 選択/ハイライト解除 + 表示リセット
          clearSelection();
          scale = 1.0;
          translateX = 0;
          translateY = 0;
          applyTransform();
        }}
      }});

      applyTransform();
    }})();

    // ============================================================
    // ホバー & 選択ハイライト
    // ============================================================
    (function() {{
      const allNodes = document.querySelectorAll('.device-node');
      const allLinks = document.querySelectorAll('.link-edge');
      const allBgp = document.querySelectorAll('.bgp-session');

      function highlight(deviceId) {{
        allNodes.forEach(function(n) {{
          if (n.dataset.device === deviceId) {{
            n.classList.add('highlighted');
          }}
        }});
        allLinks.forEach(function(l) {{
          if (l.dataset.a === deviceId || l.dataset.b === deviceId) {{
            l.classList.add('highlighted');
          }}
        }});
      }}

      function clearHighlight() {{
        allNodes.forEach(function(n) {{ n.classList.remove('highlighted'); }});
        allLinks.forEach(function(l) {{ l.classList.remove('highlighted'); }});
      }}

      // ノードホバー
      allNodes.forEach(function(node) {{
        node.addEventListener('mouseover', function(e) {{
          e.stopPropagation();
          clearHighlight();
          highlight(node.dataset.device);
        }});
        node.addEventListener('mouseenter', function() {{
          highlight(node.dataset.device);
        }});
        node.addEventListener('mouseleave', function() {{
          clearHighlight();
        }});
      }});

      // リンクホバー
      allLinks.forEach(function(link) {{
        link.addEventListener('mouseover', function(e) {{
          e.stopPropagation();
          clearHighlight();
          link.classList.add('highlighted');
          if (link.dataset.a) highlight(link.dataset.a);
          if (link.dataset.b) highlight(link.dataset.b);
        }});
        link.addEventListener('mouseleave', function() {{
          clearHighlight();
        }});
      }});

      // ノードクリックで選択強調
      allNodes.forEach(function(node) {{
        node.addEventListener('click', function(e) {{
          e.stopPropagation();
          const wasSelected = node.classList.contains('selected');
          clearSelection();
          if (!wasSelected) {{
            node.classList.add('selected');
            // 対応するカードをスクロール
            const card = document.querySelector(
              '.device-card[data-device="' + node.dataset.device + '"]'
            );
            if (card) card.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
          }}
        }});
      }});

      document.getElementById('topology-svg').addEventListener('click', function() {{
        clearSelection();
      }});
    }})();

    function clearSelection() {{
      document.querySelectorAll('.device-node.selected').forEach(function(n) {{
        n.classList.remove('selected');
      }});
    }}

    // ============================================================
    // レイヤートグル
    // ============================================================
    function handleLayerToggle(checkbox) {{
      const layer = checkbox.dataset.layer;
      if (checkbox.checked) {{
        document.body.classList.remove('hide-' + layer);
      }} else {{
        document.body.classList.add('hide-' + layer);
      }}
    }}
  </script>
</body>
</html>"""

    return html_output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI エントリーポイント"""
    parser = argparse.ArgumentParser(
        description="Render topology.json to a self-contained HTML file."
    )
    parser.add_argument("topology_json", help="入力 topology.json ファイルパス")
    parser.add_argument(
        "-o",
        "--output",
        help="出力 HTML ファイルパス（省略時は入力と同じディレクトリに topology.html）",
        default=None,
    )
    args = parser.parse_args()

    topology_path = args.topology_json
    if not os.path.isfile(topology_path):
        print(f"Error: ファイルが見つかりません: {topology_path}", file=sys.stderr)
        sys.exit(1)

    with open(topology_path, encoding="utf-8") as f:
        try:
            topology = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: JSON 解析に失敗しました: {e}", file=sys.stderr)
            sys.exit(1)

    html_content = render(topology)

    if args.output:
        out_path = args.output
    else:
        input_dir = os.path.dirname(os.path.abspath(topology_path))
        out_path = os.path.join(input_dir, "topology.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Generated: {out_path}")


if __name__ == "__main__":
    main()
