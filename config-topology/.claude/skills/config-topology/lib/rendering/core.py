"""
rendering/core.py — render() 統括モジュール
"""
from __future__ import annotations

import json
import math

from lib.rendering.cards import _device_cards
from lib.rendering.layout import _compute_canvas
from lib.rendering.svg import _esc, _make_iface_by_device, _make_link_id
from lib.rendering.template import _layer_toggles, _node_filter_ui, build_html
from lib.rendering.views import (
    _bgp_has_resolved_edges,
    _build_physical_layout,
    _build_view_bgp,
    _build_view_generic,
    _build_view_ospf,
    _build_view_physical,
    _build_view_tabs,
    _generic_has_edges,
    _ospf_has_edges,
)


def _active_entries(entries: list) -> list[dict]:
    """エントリリストから device キーを持つ dict のみ返す。"""
    return [e for e in entries if isinstance(e, dict) and "device" in e]


def _active_routing_keys(routing: dict) -> list[str]:
    """routing dict のうちデータ（device キーを持つ dict エントリ）が1件以上あるキーを昇順で返す。"""
    return sorted(
        key for key, entries in routing.items()
        if any(isinstance(e, dict) and "device" in e for e in entries)
    )


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

    # ビュー ID リスト（タブ生成用）— L3 は削除
    all_view_ids = ["physical"] + proto_view_ids

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

    # 機器カード
    cards_html = _device_cards(devices, interfaces, routing, iface_link_id=iface_link_id)

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
    )
