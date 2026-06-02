"""
rendering/cards.py — 機器カード HTML 生成モジュール
"""
from __future__ import annotations

from scripts.rendering.svg import _esc


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
        if_row_parts = []
        for iface in sorted(iface_by_device.get(dev_id, []), key=lambda i: i["name"]):
            shutdown_mark = " (shutdown)" if iface.get("shutdown") else ""
            if_row_parts.append(
                f"<tr>"
                f"<td>{_esc(iface['name'])}{_esc(shutdown_mark)}</td>"
                f"<td>{_esc(iface.get('ip', ''))}</td>"
                f"<td>{_esc(iface.get('description', ''))}</td>"
                f"</tr>"
            )
        if_rows = "".join(if_row_parts)

        # BGP サマリー
        bgp_row_parts = []
        for b in bgp_by_device.get(dev_id, []):
            bgp_row_parts.append(
                f"<tr>"
                f"<td>{_esc(b.get('neighbor_ip', ''))}</td>"
                f"<td>{_esc(b.get('peer_as', ''))}</td>"
                f"<td>{_esc(b.get('type', ''))}</td>"
                f"</tr>"
            )
        bgp_rows = "".join(bgp_row_parts)

        # OSPF サマリー
        ospf_row_parts = []
        for o in ospf_by_device.get(dev_id, []):
            ospf_row_parts.append(
                f"<tr>"
                f"<td>{_esc(o.get('network', ''))}</td>"
                f"<td>Area {_esc(o.get('area', ''))}</td>"
                f"<td>PID {_esc(o.get('process', ''))}</td>"
                f"</tr>"
            )
        ospf_rows = "".join(ospf_row_parts)

        # static サマリー
        static_row_parts = []
        for s in static_by_device.get(dev_id, []):
            static_row_parts.append(
                f"<tr>"
                f"<td>{_esc(s.get('prefix', ''))}</td>"
                f"<td>{_esc(s.get('next_hop', ''))}</td>"
                f"</tr>"
            )
        static_rows = "".join(static_row_parts)

        # sections 汎用テーブル
        section_parts = []
        for sec in dev.get("sections", []):
            sec_title = _esc(sec.get("title", ""))
            sec_row_parts = []
            for row in sec.get("rows", []):
                cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
                sec_row_parts.append(f"<tr>{cells}</tr>")
            sec_rows = "".join(sec_row_parts)
            section_parts.append(
                f"<h4>{sec_title}</h4>"
                f"<table class='section-table'><tbody>{sec_rows}</tbody></table>"
            )
        section_html = "".join(section_parts)

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
