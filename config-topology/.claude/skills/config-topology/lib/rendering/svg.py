"""
rendering/svg.py — SVG 要素生成モジュール
"""
from __future__ import annotations

import html
import ipaddress
from collections import defaultdict, OrderedDict
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


# B4: 外部ピア ID プレフィックス定数（マジックナンバー "ext:" と 4 を排除）
_EXT_ID_PREFIX = "ext:"


def _make_ext_id(ip: str) -> str:
    """外部ピア IP アドレスから外部ノード ID を生成する。

    Args:
        ip: 外部ピアの IP アドレス文字列

    Returns:
        ``"ext:{ip}"`` 形式の外部ノード ID
    """
    return f"{_EXT_ID_PREFIX}{ip}"


def _ext_id_to_ip(ext_id: str) -> str:
    """外部ノード ID から IP アドレスを逆算する。

    Args:
        ext_id: ``"ext:{ip}"`` 形式の外部ノード ID

    Returns:
        IP アドレス文字列（プレフィックスを除いた部分）
    """
    if ext_id.startswith(_EXT_ID_PREFIX):
        return ext_id[len(_EXT_ID_PREFIX):]
    return ext_id


def _esc(value: Any) -> str:
    """値を HTML 安全な文字列に変換する"""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _normalize_subnet(subnet: object) -> str:
    """サブネット文字列を正規化した CIDR 文字列を返す（OSPF ID 算出用）。

    ``ipaddress.ip_network(subnet, strict=False)`` で host bit を除去した
    ネットワークアドレスを返す。無効な入力は空文字を返す。

    Args:
        subnet: サブネット文字列（例: ``"10.0.0.0/30"``）

    Returns:
        正規化 CIDR 文字列。解析不能なら ``""``。
    """
    if not subnet:
        return ""
    try:
        return str(ipaddress.ip_network(subnet, strict=False))
    except (ValueError, TypeError):
        return ""


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
    """device ノードの data-search 属性値を構築する。

    含めるトークン（小文字・空白結合）:
    - hostname（小文字）
    - AS 番号: ``as{asn}`` と ``{asn}`` の両形式（``dev.get("as")`` がある場合）
    - vendor: ``dev.get("vendor")``
    - 各 IF の addresses から IP ホスト部と IP/prefix（link-local 除外）
    - 各 IF の description（あれば小文字化）
    - 各 IF の VLAN 番号: ``iface.get("vlan")`` または switchport から収集

    addresses がない旧形式は ip フィールドにフォールバックする（後方互換）。
    決定性: iface 順・addresses 順でトークンを追加する。
    """
    parts = [dev["hostname"].lower()]

    # AS 番号（as65000 と 65000 の両形式）
    asn = dev.get("as")
    if asn is not None:
        parts.append(f"as{asn}")
        parts.append(str(asn))

    # vendor
    vendor = dev.get("vendor")
    if vendor:
        parts.append(vendor.lower())

    for iface in interfaces_for_dev:
        addresses = iface.get("addresses")
        if addresses:
            # addresses リストから v4/v6 全アドレス（link-local 除く）のホスト部と CIDR を追加
            for addr in addresses:
                if addr.get("scope") == "link-local":
                    continue
                ip_str = addr.get("ip", "")
                if not ip_str:
                    continue
                # ホスト部（従来互換）
                parts.append(ip_str)
                # prefix 付き CIDR
                prefix = addr.get("prefix")
                if prefix is not None:
                    parts.append(f"{ip_str}/{prefix}")
        else:
            # フォールバック: ip フィールドのホスト部のみ（旧形式後方互換）
            ip = iface.get("ip")
            if ip:
                parts.append(ip.split("/")[0])

        # description
        desc = iface.get("description")
        if desc:
            parts.append(desc.lower())

        # VLAN
        vlan = iface.get("vlan")
        if vlan is not None:
            parts.append(f"vlan{vlan}")
            parts.append(str(vlan))

        # switchport から VLAN 番号を収集
        switchport = iface.get("switchport")
        if switchport:
            access_vlan = switchport.get("access_vlan")
            if access_vlan is not None:
                parts.append(f"vlan{access_vlan}")
                parts.append(str(access_vlan))
            trunk_vlans = switchport.get("trunk_vlans")
            if trunk_vlans:
                for tv in trunk_vlans:
                    parts.append(f"vlan{tv}")
                    parts.append(str(tv))

    return " ".join(parts)


def _build_ips_attr(interfaces_for_dev: list[dict]) -> str:
    """device ノードの data-ips 属性値を構築する（CIDR 内包判定用）。

    全 IF addresses から ``"{ip}/{prefix}"`` を収集（link-local 除外、v4/v6 とも）。
    addresses がない旧形式は ip フィールドにフォールバックする（後方互換）。
    決定性: iface 順・addresses 順で収集する。
    """
    parts = []
    for iface in interfaces_for_dev:
        addresses = iface.get("addresses")
        if addresses:
            for addr in addresses:
                if addr.get("scope") == "link-local":
                    continue
                ip_str = addr.get("ip", "")
                prefix = addr.get("prefix")
                if ip_str and prefix is not None:
                    parts.append(f"{ip_str}/{prefix}")
        else:
            # フォールバック: ip フィールド（旧形式後方互換）
            ip = iface.get("ip")
            if ip and "/" in ip:
                parts.append(ip)
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


def _chip_positions(
    dev: dict,
    chip_iface_ids: set[str],
    ifaces: list[dict],
    node_cx: float,
    node_cy: float,
) -> dict[str, tuple[float, float]]:
    """チップ集合の座標マップを返す純粋ヘルパー（iteration-4 #6）。

    描画と座標供給で共用する。IF を name ソート順でインデックス付けして
    ``{iface_id: (cx, cy)}`` を返す（決定的）。

    座標計算:
        ny = node_cy - node_h / 2  （node_cy を起点にノード上端を算出）
        cy = ny + _NODE_HEADER_H + _IF_CHIP_OFFSET_Y
        cx = nx + _IF_CHIP_OFFSET_X + k * _IF_CHIP_GAP  （k は name ソート順インデックス）
        node_h は _node_size_for(1) から取得（チップあり=1行分固定）。

    Args:
        dev:            device 辞書（id を持つ）
        chip_iface_ids: このノードで描画するチップの iface_id 集合
        ifaces:         このデバイスの全 IF リスト（名前解決・ソートに使用）
        node_cx:        ノード中心 x 座標
        node_cy:        ノード中心 y 座標（ny 算出に使用: ny = node_cy - node_h / 2）

    Returns:
        ``{iface_id: (cx, cy)}`` — chip_iface_ids に含まれる IF のみ。
    """
    if not chip_iface_ids:
        return {}

    # chip_iface_ids に含まれる IF のみ name ソート
    chip_ifaces = sorted(
        (i for i in ifaces if i["id"] in chip_iface_ids),
        key=lambda i: i["name"],
    )
    if not chip_ifaces:
        return {}

    # ノード矩形の左端・上端を計算（node_cx/ny は中心座標）
    # _svg_nodes と同じく「チップあり=1行分」で高さを算出（横1行配置の設計）
    _w, node_h = _node_size_for(1)
    nx = node_cx - _NODE_WIDTH / 2
    ny = node_cy - node_h / 2
    chip_start_y = ny + _NODE_HEADER_H

    result: dict[str, tuple[float, float]] = {}
    for k, iface in enumerate(chip_ifaces):
        cx = nx + _IF_CHIP_OFFSET_X + k * _IF_CHIP_GAP
        cy = chip_start_y + _IF_CHIP_OFFSET_Y
        result[iface["id"]] = (cx, cy)
    return result


def _svg_if_chip(
    nx: float,
    chip_start_y: float,
    k: int,
    iface: dict,
) -> str:
    """単一 IF チップ要素を生成する（_svg_nodes の内部ヘルパー、iteration-3 #2）。

    チップは小さな circle で表現し、<title> に「IF名 IP（desc）」を持つ。
    CSS クラス付与ルール:
    - 常に ``if-chip`` を付与（ベースクラス）
    - Loopback IF の場合は ``if-chip-loopback`` を追加（_is_loopback() で判定）
    - shutdown の場合は ``if-chip-shutdown`` を追加
    - Loopback かつ shutdown の場合は両クラスが共存（複合色は CSS で管理）
    iteration-4 #6: data-iface-id 属性を付与（チップアンカー・将来連動用）。

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
    if_id = iface.get("id", "")
    desc = iface.get("description") or ""

    # title テキスト: "IF名 v4addr v6addr（desc）" 形式
    # addresses 優先（link-local 除外）、なければ ip フィールドにフォールバック
    title_parts = [if_name]
    addresses = iface.get("addresses") or []
    # link-local を除いて v4/v6 ごとに最初の1件を取り出す（上限で簡潔に）
    v4_ips = [a["ip"] for a in addresses if a.get("af") == "v4" and not a.get("scope") and not a.get("secondary")]
    v6_ips = [a["ip"] for a in addresses if a.get("af") == "v6" and a.get("scope") != "link-local"]
    if v4_ips or v6_ips:
        for ip in v4_ips[:1]:
            prefix = next((a["prefix"] for a in addresses if a.get("ip") == ip and a.get("af") == "v4"), None)
            title_parts.append(_esc(f"{ip}/{prefix}" if prefix is not None else ip))
        for ip in v6_ips[:1]:
            prefix = next((a["prefix"] for a in addresses if a.get("ip") == ip and a.get("af") == "v6" and a.get("scope") != "link-local"), None)
            title_parts.append(_esc(f"{ip}/{prefix}" if prefix is not None else ip))
    else:
        # フォールバック: ip フィールドのみ
        if_ip = iface.get("ip") or ""
        if if_ip:
            title_parts.append(_esc(if_ip))
    if desc:
        title_parts.append(f"（{_esc(desc)}）")
    title_text = " ".join(title_parts)

    # CSS クラスを決定: loopback / shutdown の組み合わせを処理
    extra_classes = []
    if _is_loopback(if_name):
        extra_classes.append("if-chip-loopback")
    if iface.get("shutdown"):
        extra_classes.append("if-chip-shutdown")
    css_cls = "if-chip" + ("".join(f" {c}" for c in extra_classes))

    return (
        f'<g class="{css_cls}" data-if="{_esc(if_name)}" data-iface-id="{_esc(if_id)}">'
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
    chip_iface_ids: set[str] | None = None,
) -> str:
    """機器ノードの SVG 要素を生成する。

    show_interfaces=True のとき（Physical ビュー用）、ノードを可変高カード型にして
    接続IF/Loopback のみを小さなチップ（circle）で表示する（iteration-3 #2）。
    全 IF の詳細はカード表に残る。

    show_interfaces=False（デフォルト）かつ chip_iface_ids が指定された場合も
    チップ表示を行う（BGP/OSPF 等ビュー用）。iteration-4 #6。

    Args:
        devices:             デバイスリスト
        positions:           デバイスID → (x, y) 座標辞書
        iface_by_device:     デバイスID → IF リスト辞書
        show_interfaces:     True のとき Physical ビュー用チップ表示（connected_iface_ids + Loopback）
        connected_iface_ids: リンク/セグメント端点の iface-id 集合（Physical ビュー用）。
                             None のとき空集合扱い＝Loopback のみを chip 表示する。
                             Physical ビューでは必ず集合を渡すこと。
        chip_iface_ids:      全ビューで描画するチップの iface-id 集合（iteration-4 #6）。
                             指定時は connected_iface_ids/show_interfaces を上書きしてこちらを優先。
                             None のとき show_interfaces/connected_iface_ids の従来動作を踏襲。
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
        ips_val = _esc(_build_ips_attr(iface_by_device.get(dev["id"], [])))

        all_ifaces = sorted(iface_by_device.get(dev["id"], []), key=lambda i: i["name"])

        # ---- チップ集合を決定 ----
        # chip_iface_ids が明示的に渡された場合はそちらを優先（BGP/OSPF ビュー用）
        if chip_iface_ids is not None:
            # このデバイスの chip_iface_ids に含まれる IF
            chip_ifaces = [i for i in all_ifaces if i["id"] in chip_iface_ids]
        elif show_interfaces:
            # Physical ビュー: 接続IF + Loopback（従来通り）
            chip_ifaces = [
                iface for iface in all_ifaces
                if iface["id"] in connected_iface_ids or _is_loopback(iface.get("name", ""))
            ]
        else:
            chip_ifaces = []

        use_chips = bool(chip_ifaces)
        # チップは横1行: n_chip = チップ有無（1 or 0）のみで高さを計算（従来通り）
        n_chip = 1 if use_chips else 0

        if use_chips:
            _w, node_h = _node_size_for(n_chip)
        else:
            _w, node_h = float(_NODE_WIDTH), float(_NODE_HEIGHT)
        nx = x - _NODE_WIDTH / 2
        ny = y - node_h / 2

        if use_chips:
            # ----- チップ型ノード（iteration-3 #2 / iteration-4 #6）-----
            label_y = ny + 14
            sublabel_y = ny + 26
            chip_start_y = ny + _NODE_HEADER_H

            chips_str = "\n".join(
                _svg_if_chip(nx, chip_start_y, k, iface)
                for k, iface in enumerate(chip_ifaces)
            )

            parts.append(
                f'<g class="device-node" data-device="{dev_id}" '
                f'data-search="{search_val}" '
                f'data-ips="{ips_val}" '
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
            # ----- コンパクト表示 -----
            parts.append(
                f'<g class="device-node" data-device="{dev_id}" '
                f'data-search="{search_val}" '
                f'data-ips="{ips_val}" '
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


def _merge_links_by_link_id(links: list[dict]) -> list[dict]:
    """同一 link_id を持つリンク（dual-stack の v4/v6 エントリ）を1エントリに統合する。

    Phase 3H: dual-stack エッジ統合（描画層のみ）。
    - link_id は ``_make_link_id(a_device, a_if, b_device, b_if)`` で算出
    - 同一 link_id のリンクは同一 IF ペア（v4/v6 両方）= 描画時に重なる
    - 統合後エントリの "subnet" は最初のリンクの subnet を保持
    - 統合後エントリに "subnets" フィールドで全 subnet をリスト化（sorted 決定的）
    - single-stack（link_id が唯一）は従来通り1エントリ = 変化なし

    ospf_area / ospf_network の引き継ぎ（Phase 3H レビュー修正）:
    - base（最初のリンク）に ospf_area がない場合、後続エントリから補完する。
    - v4/v6 で異なる ospf_area が存在する場合は数値昇順 '/' 区切りで集約する
      （_annotate_links_with_ospf_area の集約方式と整合）。

    Args:
        links: リンクリスト（_infer_links_and_segments 等の出力）

    Returns:
        統合済みリンクリスト（決定的順序）
    """
    # link_id → 統合エントリ（最初の link をベースに subnets を蓄積）
    merged: OrderedDict[str, dict] = OrderedDict()
    # link_id → ospf_area 集合（複数 area 集約用）
    merged_areas: dict[str, set[str]] = {}
    # link_id → OSPF 参加 subnet 集合（ospf_area を持つリンクの subnet のみ）
    merged_ospf_subnets: dict[str, set[str]] = {}

    for link in sorted(links, key=lambda l: (l.get("a_device", ""), l.get("a_if", ""), l.get("subnet", ""))):
        a_dev = link.get("a_device", "")
        a_if = link.get("a_if", "") or ""
        b_dev = link.get("b_device", "")
        b_if = link.get("b_if", "") or ""
        lid = _make_link_id(a_dev, a_if, b_dev, b_if)
        subnet = link.get("subnet", "")
        ospf_area = link.get("ospf_area")

        if lid not in merged:
            # 初出: コピーして subnets フィールドを初期化
            entry = dict(link)
            entry["subnets"] = [subnet] if subnet else []
            entry["_link_id"] = lid
            merged[lid] = entry
            merged_areas[lid] = {ospf_area} if ospf_area is not None else set()
            # ospf_subnets: このリンクが OSPF 参加なら subnet を収集
            merged_ospf_subnets[lid] = {subnet} if (ospf_area is not None and subnet) else set()
        else:
            # 同一 link_id: subnet を追加（重複除去）
            if subnet and subnet not in merged[lid]["subnets"]:
                merged[lid]["subnets"].append(subnet)
            # ospf_area を収集（後でまとめて集約）
            if ospf_area is not None:
                merged_areas[lid].add(ospf_area)
                # OSPF 参加 subnet として追加
                if subnet:
                    merged_ospf_subnets[lid].add(subnet)

    # subnets を sorted で決定的に固定（IPv4 before IPv6 は自然ソートで概ね担保される）
    # ospf_area を集約してエントリに書き戻す
    # ospf_subnets も sorted で決定的に固定
    result = []
    for lid, entry in merged.items():
        entry["subnets"] = sorted(entry["subnets"])
        # ospf_subnets: OSPF 参加 subnet のみ（sorted 決定的）
        entry["ospf_subnets"] = sorted(merged_ospf_subnets.get(lid, set()))
        areas = merged_areas.get(lid, set())
        if areas:
            if len(areas) == 1:
                entry["ospf_area"] = next(iter(areas))
            else:
                # 複数 area: 数値昇順 '/' 区切りで集約（非数値は文字列昇順フォールバック）
                def _area_sort_key(a: str) -> tuple:
                    try:
                        return (0, int(a), a)
                    except (ValueError, TypeError):
                        return (1, 0, a)
                entry["ospf_area"] = "/".join(
                    sorted(areas, key=_area_sort_key)
                )
        result.append(entry)
    return result


def _svg_links(
    links: list[dict],
    positions: dict,
    chip_positions: dict[str, tuple[float, float]] | None = None,
    name_to_iface_id: dict[tuple[str, str], str] | None = None,
) -> str:
    """リンクエッジの SVG 要素を生成する（Physical ビュー用）。

    常時テキストラベルは持たない（iteration-3 #1）。
    subnet/IF 名は hover の <title> で参照できる程度に留める。
    各 <g class="link-edge"> と <line class="link-line"> に ``data-link-id`` を付与する。
    link-id は ``_make_link_id(a_device, a_if, b_device, b_if)`` で導出（決定的・対称）。

    Phase 3H: 同一 link_id のリンク（dual-stack v4/v6）を1エッジに統合。
    統合エッジの <title> に全 subnet を「 / 」区切りで表示。
    single-stack は従来通り1本（変化なし）。

    iteration-4 #6: chip_positions と name_to_iface_id が渡された場合、
    端点の iface_id に対応するチップ座標を線の端点に使用する。
    チップが無い端点はノード中心にフォールバックする。

    Args:
        links:             リンクリスト
        positions:         デバイスID → (cx, cy) 座標辞書
        chip_positions:    iface_id → (cx, cy) チップ座標辞書（None のときフォールバック）
        name_to_iface_id:  (device_id, if_name) → iface_id マップ（None のときフォールバック）
    """
    # Phase 3H: 同一 link_id のエントリ（v4/v6 dual-stack）を統合
    merged_links = _merge_links_by_link_id(links)

    parts = []
    for link in sorted(merged_links, key=lambda l: (l.get("a_device", ""), l.get("b_device", ""))):
        a_dev = link["a_device"]
        b_dev = link["b_device"]
        a_if_raw = link.get("a_if") or ""
        b_if_raw = link.get("b_if") or ""

        # チップアンカー: iface_id からチップ座標を解決
        a_pos = positions.get(a_dev, (0.0, 0.0))
        b_pos = positions.get(b_dev, (0.0, 0.0))
        if chip_positions is not None and name_to_iface_id is not None:
            a_iface_id = name_to_iface_id.get((a_dev, a_if_raw))
            b_iface_id = name_to_iface_id.get((b_dev, b_if_raw))
            if a_iface_id and a_iface_id in chip_positions:
                a_pos = chip_positions[a_iface_id]
            if b_iface_id and b_iface_id in chip_positions:
                b_pos = chip_positions[b_iface_id]

        x1, y1 = a_pos
        x2, y2 = b_pos

        a_if = _esc(a_if_raw)
        b_if = _esc(b_if_raw)
        # 決定的 link-id（両端点をソートして結合）
        link_id = _esc(_make_link_id(a_dev, a_if_raw, b_dev, b_if_raw))

        # Phase 3H: 統合エントリの全 subnet を <title> に含める（決定的: sorted 済み）
        subnets = link.get("subnets") or [link.get("subnet", "")]
        # <title> 用: "subnet1 / subnet2 (a_if — b_if)"
        title_subnets = " / ".join(_esc(s) for s in subnets if s)
        title_text = f"{title_subnets} ({a_if} — {b_if})" if title_subnets else f"({a_if} — {b_if})"
        # data-subnet は最初（primary）の subnet（後方互換）
        primary_subnet = _esc(subnets[0]) if subnets else ""

        parts.append(
            f'<g class="link-edge" data-subnet="{primary_subnet}" '
            f'data-a="{_esc(a_dev)}" data-b="{_esc(b_dev)}" data-link-id="{link_id}">'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'class="link-line layer-physical" data-link-id="{link_id}"/>'
            f'<title>{title_text}</title>'
            f'</g>'
        )
    return "\n".join(parts)


def _svg_segment_edges(
    segments: list[dict],
    interfaces: list[dict],
    positions: dict,
    chip_positions: dict[str, tuple[float, float]] | None = None,
) -> str:
    """セグメントメンバーへの接続エッジを生成する。

    #7: <line class="seg-edge"> に ``data-seg-id`` を付与する。

    iteration-4 クロスレビュー バグ3修正: chip_positions が渡された場合、
    機器側端点をメンバー iface_id のチップ座標にアンカーする。
    _svg_ospf_segment_edges と対称な動作。
    チップが無い場合はノード中心にフォールバック。

    Args:
        segments:       セグメントリスト
        interfaces:     topology の interfaces リスト
        positions:      ノードID → (cx, cy) 座標辞書
        chip_positions: iface_id → (cx, cy) チップ座標辞書（None のときフォールバック）
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
                # チップアンカー: メンバー iface_id のチップ座標を使用
                if chip_positions is not None and member_iface_id in chip_positions:
                    dx, dy = chip_positions[member_iface_id]
                else:
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

    #1B: ``data-ospf-id`` を付与する（subnet を正規化した CIDR）。
    """
    parts = []
    for seg in sorted(segments, key=lambda s: s["id"]):
        ospf_area = seg.get("ospf_area")
        if ospf_area is None:
            continue
        x, y = positions.get(seg["id"], (0, 0))
        seg_id = _esc(seg["id"])
        subnet_raw = seg.get("subnet", "")
        subnet = _esc(subnet_raw)
        # #1B: ospf_network または subnet から ospf_id を正規化して取得
        ospf_id = _normalize_subnet(seg.get("ospf_network") or subnet_raw)
        ospf_id_attr = f' data-ospf-id="{_esc(ospf_id)}"' if ospf_id else ""
        area_label = OSPF_AREA_LABEL_FORMAT.format(
            area=_esc(ospf_area), subnet=subnet
        )
        # data-ospf-id は <g> のみに付与し <ellipse> には付与しない（クリックは <g> で拾う設計）
        parts.append(
            f'<g class="segment-node layer-ospf" data-segment="{seg_id}"{ospf_id_attr}>'
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
    chip_positions: dict[str, tuple[float, float]] | None = None,
) -> str:
    """OSPF 参加セグメントからメンバー機器への接続エッジを生成する。

    Physical ビューの _svg_segment_edges と同様だが、layer-ospf クラスを付与する。
    ospf_area が付いているセグメントのみを対象とする。

    iteration-4 #6: chip_positions が渡された場合、機器側端点を
    メンバー iface_id のチップ座標にアンカーする。
    チップが無い場合はノード中心にフォールバック。

    Args:
        segments:       セグメントリスト
        interfaces:     topology の interfaces リスト
        positions:      ノードID → (cx, cy) 座標辞書
        chip_positions: iface_id → (cx, cy) チップ座標辞書（None のときフォールバック）
    """
    iface_map = {iface["id"]: iface["device"] for iface in interfaces}

    parts = []
    for seg in sorted(segments, key=lambda s: s["id"]):
        if seg.get("ospf_area") is None:
            continue
        sx, sy = positions.get(seg["id"], (0, 0))
        seg_id = _esc(seg["id"])
        # #1B: セグメントの ospf_id を算出（ospf_network または subnet から正規化）
        ospf_id = _normalize_subnet(seg.get("ospf_network") or seg.get("subnet") or "")
        ospf_id_attr = f' data-ospf-id="{_esc(ospf_id)}"' if ospf_id else ""
        for member_iface_id in sorted(seg.get("members", [])):
            dev_id = iface_map.get(member_iface_id)
            if dev_id and dev_id in positions:
                # チップアンカー: メンバー iface_id のチップ座標を使用
                if chip_positions is not None and member_iface_id in chip_positions:
                    dx, dy = chip_positions[member_iface_id]
                else:
                    dx, dy = positions[dev_id]
                parts.append(
                    f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{dx:.1f}" y2="{dy:.1f}" '
                    f'class="seg-edge layer-ospf" data-seg="{seg_id}" '
                    f'data-seg-id="{seg_id}" data-device="{_esc(dev_id)}"{ospf_id_attr}/>'
                )
    return "\n".join(parts)


def _svg_bgp_edges(
    bgp_entries: list[dict],
    interfaces: list[dict],
    positions: dict,
    chip_positions: dict[str, tuple[float, float]] | None = None,
) -> str:
    """BGP ピアリングエッジを生成する（ebgp=青、ibgp=橙）。

    data-bgp-id 属性: 両端 device id を sorted して '|' で結合した決定的な値。
    例: r1 と r2 のセッションなら "r1|r2"（どちらの方向から呼んでも同一）。

    Phase 3I [HIGH3]: 同一機器ペアに v4/v6 両 BGP セッションがある場合、
    統合エッジの <title>/badge に全 af セッションの local_ip↔neighbor_ip を併記する。
    - 双方向エントリ（r1→r2, r2→r1）は1本に統合（従来通り）
    - v4/v6 複数 af も1本に統合し、IP ペアを " / " 区切りで列挙
    - single-stack は従来通り変化なし

    iteration-4 #6: chip_positions が渡された場合、
    BGP セッション端点を該当チップ座標にアンカーする。
    - A 側: local_ip → iface_id → chip_positions
    - B 側: neighbor_ip → iface_id → chip_positions
    チップが無い端点はノード中心にフォールバック（local_ip 欠損時も含む）。

    Args:
        bgp_entries:    BGP エントリリスト
        interfaces:     topology の interfaces リスト
        positions:      デバイスID → (cx, cy) 座標辞書
        chip_positions: iface_id → (cx, cy) チップ座標辞書（None のときフォールバック）
    """
    # local_ip -> device_id 逆引き（共通ヘルパーを使用）
    ip_to_device = _build_ip_to_device(interfaces)

    # ip_only -> iface_id マップ（チップアンカー用: 共通ヘルパーを使用）
    ip_to_iface_id: dict[str, str] = _build_ip_to_iface_id(interfaces) if chip_positions is not None else {}

    # Phase 3I [HIGH3]: ペアごとに全セッションを収集（v4/v6 統合用）
    # pair(frozenset) → list[(dev_id, neighbor_dev, entry)]
    pair_sessions: dict[frozenset, list[tuple[str, str, dict]]] = {}
    pair_order: list[frozenset] = []  # 決定的順序保持

    for entry in sorted(bgp_entries, key=lambda e: (e["device"], e.get("neighbor_ip", ""))):
        dev_id = entry["device"]
        neighbor_ip = entry.get("neighbor_ip", "")

        neighbor_dev = ip_to_device.get(neighbor_ip)
        if not neighbor_dev or neighbor_dev == dev_id:
            continue

        if dev_id not in positions or neighbor_dev not in positions:
            continue

        pair = frozenset([dev_id, neighbor_dev])

        # 既にこのペアを「逆向き」として登録済みの場合も同じ pair に収集
        # ペア内の「正規代表」は sorted で小さい方を先にする
        canonical_dev, canonical_nbr = sorted([dev_id, neighbor_dev])
        # 既登録エントリが逆向き（neighbor_dev が canonical_dev に該当）の場合は収集のみ
        if pair not in pair_sessions:
            pair_sessions[pair] = []
            pair_order.append(pair)

        # 重複（同じ dev_id + neighbor_ip の組）は skip
        already_registered = any(
            e.get("device") == entry.get("device") and
            e.get("neighbor_ip") == entry.get("neighbor_ip")
            for _, _, e in pair_sessions[pair]
        )
        if not already_registered:
            pair_sessions[pair].append((dev_id, neighbor_dev, entry))

    parts = []
    seen_pairs: set[frozenset] = set()

    for pair in pair_order:
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        sessions = pair_sessions[pair]
        if not sessions:
            continue

        # 代表エントリ（1件目）から dev_id/neighbor_dev/bgp_type/as 情報を取得
        dev_id, neighbor_dev, repr_entry = sessions[0]
        bgp_type = repr_entry.get("type", "unknown")
        peer_as = _esc(repr_entry.get("peer_as", ""))
        local_as = _esc(repr_entry.get("local_as", ""))

        # デフォルト: ノード中心
        x1, y1 = positions[dev_id]
        x2, y2 = positions[neighbor_dev]

        # チップアンカー（A6c: af 対応解決 — sessions を走査して解決できる最初のセッションを使う）
        if chip_positions is not None:
            # A 側: dev_id 側のセッションを決定的順（af→neighbor_ip ソート順）に走査し、
            # local_ip が chip_positions に解決できる最初のセッションのチップ座標を使う。
            # local_ip が全て null（iBGP Loopback 源）のフォールバックは維持。
            # ※ sessions には双方向エントリが混在するため dev_id でフィルタする。
            sorted_sessions = sorted(
                sessions,
                key=lambda t: (t[2].get("af", "v4"), t[2].get("neighbor_ip", "")),
            )
            a_side = [(s_dev, s_nbr, sess) for s_dev, s_nbr, sess in sorted_sessions if s_dev == dev_id]
            b_side = [(s_dev, s_nbr, sess) for s_dev, s_nbr, sess in sorted_sessions if s_dev == neighbor_dev]
            # フォールバック: dev_id フィルタで空になる場合（逆向きのみの場合）は全体を使う
            if not a_side:
                a_side = sorted_sessions
            if not b_side:
                b_side = sorted_sessions

            a_anchored = False
            for _, _, sess_a in a_side:
                local_ip_raw = sess_a.get("local_ip") or ""
                if local_ip_raw:
                    a_iface_id = ip_to_iface_id.get(local_ip_raw)
                    if a_iface_id and a_iface_id in chip_positions:
                        x1, y1 = chip_positions[a_iface_id]
                        a_anchored = True
                        break
            if not a_anchored:
                # local_ip が全て null か全て解決失敗: iBGP Loopback フォールバック
                has_any_local_ip = any(
                    (sess.get("local_ip") or "") for _, _, sess in a_side
                )
                if not has_any_local_ip:
                    lb_candidates = sorted(
                        iface_id for iface_id in chip_positions
                        if iface_id.startswith(f"{dev_id}::")
                        and _is_loopback(iface_id[len(dev_id) + 2:])
                    )
                    if lb_candidates:
                        x1, y1 = chip_positions[lb_candidates[0]]
            # B 側: neighbor_dev 側のセッションで neighbor_ip が解決できる最初のものを使う
            for _, _, sess_b in b_side:
                neighbor_ip_raw = sess_b.get("local_ip") or ""  # B側から見た local_ip = A側の neighbor_ip
                if neighbor_ip_raw:
                    b_iface_id = ip_to_iface_id.get(neighbor_ip_raw)
                    if b_iface_id and b_iface_id in chip_positions:
                        x2, y2 = chip_positions[b_iface_id]
                        break
            # B 側: b_side が空か全て解決失敗の場合は a_side の neighbor_ip でフォールバック
            if (x2, y2) == tuple(positions[neighbor_dev]):
                for _, _, sess_a in a_side:
                    neighbor_ip_raw = sess_a.get("neighbor_ip") or ""
                    if neighbor_ip_raw:
                        b_iface_id = ip_to_iface_id.get(neighbor_ip_raw)
                        if b_iface_id and b_iface_id in chip_positions:
                            x2, y2 = chip_positions[b_iface_id]
                            break

        css_class = f"bgp-edge bgp-{_esc(bgp_type)} layer-bgp"

        # エッジを少しオフセットして重なりを防ぐ
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2 - 15

        # Phase 3I [HIGH3]: 全セッションの IP ペアを収集（決定的: af ソート v4→v6）
        # 双方向エントリのうち dev_id が canonical 側のものだけを収集（重複防止）
        canonical_dev, canonical_nbr = sorted([dev_id, neighbor_dev])
        ip_pairs: list[str] = []
        seen_ip_pairs: set[tuple[str, str]] = set()
        for _, _, sess_entry in sorted(
            sessions,
            key=lambda t: (t[2].get("af", "v4"), t[2].get("neighbor_ip", "")),
        ):
            # canonical 側（dev_id が canonical_dev）のエントリのみ使用
            sess_dev = sess_entry.get("device", "")
            if sess_dev != canonical_dev:
                continue
            local_ip = sess_entry.get("local_ip") or ""
            neighbor_ip = sess_entry.get("neighbor_ip") or ""
            pair_key = (local_ip, neighbor_ip)
            if pair_key in seen_ip_pairs:
                continue
            seen_ip_pairs.add(pair_key)
            if local_ip and neighbor_ip:
                ip_pairs.append(f"{_esc(local_ip)}↔{_esc(neighbor_ip)}")
            elif neighbor_ip:
                ip_pairs.append(_esc(neighbor_ip))

        # A4: dual-stack 時は v4/v6 ペアを別リストに分ける（":" 有無で判定）
        v4_pairs = [p for p in ip_pairs if ":" not in p]
        v6_pairs = [p for p in ip_pairs if ":" in p]
        is_dual_stack = bool(v4_pairs and v6_pairs)

        ip_label = " / ".join(ip_pairs)

        # <title> に完全情報（AS + 全 IP ペア）を埋め込む
        title_parts = [f"{_esc(bgp_type)} AS{local_as}↔AS{peer_as}"]
        if ip_label:
            title_parts.append(ip_label)
        title_text = " | ".join(title_parts)

        # バッジ: 上段に type/AS、以降は IP ペア行
        # dual-stack 時: v4ペア行 + v6ペア行 = 最大3行
        # single-stack 時: 従来通り 2行（type/AS + IPペア）
        if ip_label:
            if is_dual_stack:
                # v4 行 + v6 行を別 tspan で表現
                v4_label = " / ".join(v4_pairs)
                v6_label = " / ".join(v6_pairs)
                badge_svg = (
                    f'<text x="{mx:.1f}" y="{my - 8:.1f}" text-anchor="middle" '
                    f'class="bgp-badge layer-bgp">'
                    f'<tspan x="{mx:.1f}" dy="0">{_esc(bgp_type)} {local_as}↔{peer_as}</tspan>'
                    f'<tspan x="{mx:.1f}" dy="12">{v4_label}</tspan>'
                    f'<tspan x="{mx:.1f}" dy="12">{v6_label}</tspan>'
                    f'</text>'
                )
            else:
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

        # #5: 決定的 bgp-id（両端 device id を sorted して結合）
        bgp_id = "|".join(sorted([dev_id, neighbor_dev]))

        parts.append(
            f'<g class="bgp-session" data-type="{_esc(bgp_type)}" '
            f'data-a="{_esc(dev_id)}" data-b="{_esc(neighbor_dev)}" '
            f'data-bgp-id="{_esc(bgp_id)}">'
            f'<path d="M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}" '
            f'class="{css_class}" fill="none"/>'
            f'<title>{title_text}</title>'
            f'{badge_svg}'
            f'</g>'
        )
    return "\n".join(parts)


def _svg_bgp_external_nodes(
    bgp_entries: list[dict],
    interfaces: list[dict],
    ext_positions: dict[str, tuple[float, float]],
) -> str:
    """BGP 外部ピアノード（topology 外）の SVG 要素を生成する。

    外部ピア = neighbor_ip が interfaces の ip_to_device に解決されないもの。
    外部ノード ID: ``"ext:{neighbor_ip}"``（dedup・neighbor_ip 昇順決定的）。

    B4: 外部ノードは BGP ビューのみ。点線 rect + AS ラベル + neighbor_ip sublabel。

    Args:
        bgp_entries:   BGP エントリリスト
        interfaces:    topology の interfaces リスト
        ext_positions: ext_id → (cx, cy) 座標辞書（_compute_ext_bgp_positions で算出）
    """
    if not ext_positions:
        return ""

    # C HIGH-2: ip_to_device の重複呼び出しを除去。
    # ext_positions のキー（ext_id）に対するエントリのみが外部ピアと確定しているため、
    # _build_ip_to_device による再判定は不要。ext_positions.keys() で外部判定を行う。

    # ext_id → peer_as マップ（最初に見つかったエントリの peer_as を使用）
    ext_peer_as: dict[str, str] = {}
    for entry in sorted(bgp_entries, key=lambda e: (e["device"], e.get("neighbor_ip", ""))):
        neighbor_ip = entry.get("neighbor_ip", "")
        if not neighbor_ip:
            continue
        ext_id = _make_ext_id(neighbor_ip)
        if ext_id not in ext_positions:
            continue  # 外部ピアでない（内部解決済み）: スキップ
        if ext_id not in ext_peer_as:
            peer_as = entry.get("peer_as")
            ext_peer_as[ext_id] = str(peer_as) if peer_as is not None else ""

    parts = []
    for ext_id in sorted(ext_positions.keys()):
        x, y = ext_positions[ext_id]
        # ext_id から neighbor_ip を逆算
        neighbor_ip = _ext_id_to_ip(ext_id)
        peer_as_str = ext_peer_as.get(ext_id, "")

        nx = x - _NODE_WIDTH / 2
        ny = y - _NODE_HEIGHT / 2
        label = f"AS{_esc(peer_as_str)}" if peer_as_str else "external"
        sublabel = _esc(neighbor_ip)

        parts.append(
            f'<g class="device-node external-node" data-device="{_esc(ext_id)}">'
            f'<rect x="{nx:.1f}" y="{ny:.1f}" width="{_NODE_WIDTH}" height="{_NODE_HEIGHT:.1f}" '
            f'rx="6" ry="6" class="node-rect external-rect"/>'
            f'<text x="{x:.1f}" y="{y - 6:.1f}" text-anchor="middle" class="node-label external-label">'
            f'{label}</text>'
            f'<text x="{x:.1f}" y="{y + 10:.1f}" text-anchor="middle" class="node-sublabel">'
            f'{sublabel}</text>'
            f'</g>'
        )
    return "\n".join(parts)


def _svg_bgp_external_edges(
    bgp_entries: list[dict],
    interfaces: list[dict],
    positions: dict,
    ext_positions: dict[str, tuple[float, float]],
    chip_positions: dict[str, tuple[float, float]] | None = None,
) -> str:
    """BGP 外部ピア向けエッジを生成する（内部デバイス → 外部ノード）。

    data-bgp-id: ``"{dev_id}|ext:{neighbor_ip}"``（sorted して結合）。
    これにより cards の外部行と図の外部線が同一 data-bgp-id で連動する。

    B4: 外部ノード専用。内部解決済みピアは _svg_bgp_edges が処理する。

    Args:
        bgp_entries:   BGP エントリリスト
        interfaces:    topology の interfaces リスト
        positions:     内部デバイスID → (cx, cy) 座標辞書
        ext_positions: ext_id → (cx, cy) 外部ノード座標辞書
        chip_positions: iface_id → (cx, cy) チップ座標辞書（None のときフォールバック）
    """
    if not ext_positions:
        return ""

    ip_to_device = _build_ip_to_device(interfaces)
    ip_to_iface_id: dict[str, str] = _build_ip_to_iface_id(interfaces) if chip_positions is not None else {}

    # (dev_id, ext_id) ペアごとに収集（dedup）
    # pair(frozenset[dev_id, ext_id]) → list[(dev_id, ext_id, entry)]
    pair_sessions: dict[frozenset, list[tuple[str, str, dict]]] = {}
    pair_order: list[frozenset] = []

    for entry in sorted(bgp_entries, key=lambda e: (e["device"], e.get("neighbor_ip", ""))):
        dev_id = entry["device"]
        neighbor_ip = entry.get("neighbor_ip", "")
        if not neighbor_ip:
            continue
        if ip_to_device.get(neighbor_ip):
            continue  # 内部解決: _svg_bgp_edges が処理
        if dev_id not in positions:
            continue

        ext_id = _make_ext_id(neighbor_ip)
        if ext_id not in ext_positions:
            continue

        pair = frozenset([dev_id, ext_id])
        if pair not in pair_sessions:
            pair_sessions[pair] = []
            pair_order.append(pair)
        # 重複スキップ
        already = any(
            e.get("device") == dev_id and e.get("neighbor_ip") == neighbor_ip
            for _, _, e in pair_sessions[pair]
        )
        if not already:
            pair_sessions[pair].append((dev_id, ext_id, entry))

    # C MED-2: pair_order は pair_sessions 初出時のみ追加されるため seen 重複チェックは不要
    parts = []
    for pair in pair_order:
        sessions = pair_sessions[pair]
        if not sessions:
            continue

        dev_id, ext_id, repr_entry = sessions[0]
        bgp_type = repr_entry.get("type", "unknown")
        peer_as = _esc(repr_entry.get("peer_as", ""))
        local_as = _esc(repr_entry.get("local_as", ""))
        neighbor_ip = repr_entry.get("neighbor_ip", "")

        # デフォルト座標: 内部ノード中心 → 外部ノード中心
        x1, y1 = positions[dev_id]
        x2, y2 = ext_positions[ext_id]

        # チップアンカー（A 側のみ。外部ノードはチップなし）
        if chip_positions is not None:
            a_anchored = False
            for _, _, sess in sorted(sessions, key=lambda t: (t[2].get("af", "v4"), t[2].get("neighbor_ip", ""))):
                if sess.get("device") != dev_id:
                    continue
                local_ip_raw = sess.get("local_ip") or ""
                if local_ip_raw:
                    a_iface_id = ip_to_iface_id.get(local_ip_raw)
                    if a_iface_id and a_iface_id in chip_positions:
                        x1, y1 = chip_positions[a_iface_id]
                        a_anchored = True
                        break
            if not a_anchored:
                # local_ip なし: Loopback フォールバック
                has_local = any(
                    (s.get("local_ip") or "") for _, _, s in sessions if s.get("device") == dev_id
                )
                if not has_local:
                    lb_candidates = sorted(
                        iface_id for iface_id in chip_positions
                        if iface_id.startswith(f"{dev_id}::")
                        and _is_loopback(iface_id[len(dev_id) + 2:])
                    )
                    if lb_candidates:
                        x1, y1 = chip_positions[lb_candidates[0]]

        css_class = f"bgp-edge bgp-{_esc(bgp_type)} layer-bgp"
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2 - 15

        ip_label = _esc(neighbor_ip) if neighbor_ip else ""
        title_text = f"{_esc(bgp_type)} AS{local_as}↔AS{peer_as}"
        if ip_label:
            title_text += f" | {ip_label}"

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

        # data-bgp-id: dev_id と ext_id を sorted で結合（cards と共有）
        bgp_id = "|".join(sorted([dev_id, ext_id]))

        parts.append(
            f'<g class="bgp-session" data-type="{_esc(bgp_type)}" '
            f'data-a="{_esc(dev_id)}" data-b="{_esc(ext_id)}" '
            f'data-bgp-id="{_esc(bgp_id)}">'
            f'<path d="M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}" '
            f'class="{css_class}" fill="none"/>'
            f'<title>{title_text}</title>'
            f'{badge_svg}'
            f'</g>'
        )
    return "\n".join(parts)


_AS_COLOR_PALETTE = [
    # (stroke, fill_rgba)  — 6色・色覚配慮・判別しやすい固定パレット
    # Phase 1C #5: AS番号ごとに決定的色分け（asn % len(_AS_COLOR_PALETTE) で循環）
    # label_bg は常に stroke と同色のため 2 要素に簡素化。
    # _as_color() 内で label_bg = stroke として展開する。
    ("#2563eb", "rgba(219,234,254,0.35)"),   # 青系  (index 0)
    ("#16a34a", "rgba(187,247,208,0.35)"),   # 緑系  (index 1)
    ("#d97706", "rgba(254,243,199,0.35)"),   # 橙系  (index 2)
    ("#9333ea", "rgba(243,232,255,0.35)"),   # 紫系  (index 3)
    ("#0891b2", "rgba(207,250,254,0.35)"),   # 水色系 (index 4)
    ("#dc2626", "rgba(254,226,226,0.35)"),   # 赤系  (index 5)
]


def _as_color(asn: int) -> tuple[str, str, str]:
    """AS番号から (stroke, fill_rgba, label_bg) 色タプルを返す（決定的・循環）。

    ``asn % len(_AS_COLOR_PALETTE)`` でパレットインデックスを決定する。
    同一 asn は常に同じ色（決定的）。asn が len を超えると循環する。
    label_bg は stroke と同色（_AS_COLOR_PALETTE は 2 要素で管理）。

    前提: asn は int（parser が int を保証する）。
    """
    idx = asn % len(_AS_COLOR_PALETTE)
    stroke, fill_rgba = _AS_COLOR_PALETTE[idx]
    label_bg = stroke  # ラベルチップ背景は枠線と同色
    return stroke, fill_rgba, label_bg


def _svg_bgp_as_groups(
    bgp_devices: list[dict],
    positions: dict[str, tuple[float, float]],
    padding: float = _AS_GROUP_PADDING,
    node_sizes: dict[str, int] | None = None,
) -> str:
    """BGP ビュー用 AS グルーピング枠を生成する。

    同一 local_as（device["as"]）の BGP 参加機を
    <g class="as-group-container" data-as="{asn}"> で囲み、
    内部に <rect class="as-group"> と <text class="as-group-label"> を配置する。
    local_as が None の機器は枠なし（クラッシュしない）。
    描画順はノードの背面になるよう呼び出し側で先に出力すること。

    決定性: AS 番号昇順・同一 AS 内はデバイス ID 昇順でソートして処理する。

    iteration-4 #6: node_sizes={device_id: n_ifaces} を渡すことで
    実ノード高（チップ有り時は _node_size_for(n_ifaces)[1]）を使って
    bounding box を計算する。None のとき固定 _NODE_HEIGHT を使用（従来動作）。

    Phase 1C #5: AS番号ごとに決定的に異なる色を割当（_AS_COLOR_PALETTE 固定パレット循環）。
    枠線(stroke)・淡塗り(fill)・ラベルチップ背景(label-bg) に AS別インライン style を適用。
    ラベル文字は白固定（全背景色で可読コントラスト確保）。

    Args:
        bgp_devices:  BGP 参加デバイスリスト
        positions:    デバイスID → (cx, cy) 座標辞書
        padding:      枠とノード矩形間のパディング（px）
        node_sizes:   デバイスID → n_ifaces マップ（None のとき固定高）
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

    _nsizes = node_sizes or {}

    parts = []
    for asn in sorted(asn_to_devs.keys()):
        dev_ids = asn_to_devs[asn]
        if not dev_ids:
            continue

        # Phase 1C #5: AS番号から決定的色を取得（色は svg のインライン style で AS 別に付与）
        stroke_color, fill_color, label_bg_color = _as_color(asn)

        # bounding box を計算（実ノード高対応: iteration-4 #6）
        xs = [positions[d][0] for d in dev_ids]
        ys = [positions[d][1] for d in dev_ids]

        # 各デバイスの実ノード高を使って上下端を個別計算
        tops = []
        bottoms = []
        for d in dev_ids:
            cy = positions[d][1]
            n_if = _nsizes.get(d, 0)
            _w, node_h = _node_size_for(n_if)
            tops.append(cy - node_h / 2)
            bottoms.append(cy + node_h / 2)

        min_x = min(xs) - _NODE_WIDTH / 2 - padding
        min_y = min(tops) - padding
        max_x = max(xs) + _NODE_WIDTH / 2 + padding
        max_y = max(bottoms) + padding

        rect_w = max_x - min_x
        rect_h = max_y - min_y

        # M5: <g class="as-group-container" data-as="{asn}"> でラップ
        # #4: ラベルを左上チップ（背景 rect + text）として配置
        chip_x = min_x + 8
        chip_y = min_y - 9   # 枠上端より少し上にはみ出してチップを置く
        chip_text = f"AS {_esc(asn)}"
        # チップ背景矩形のサイズ算出（#8: font-size 15px 対応）:
        #   chip_w = len(label) * 9 + 12
        #     - 9: 拡大フォント（15px）における1文字あたりの概算幅（px）
        #     - 12: 左右パディング合計（各6px）
        #     - 例: "AS 65001"(8文字) → 8*9+12 = 84px
        #   chip_h = 20: 拡大フォント（15px）を余裕を持って収める高さ
        #   text_y = chip_y + chip_h * 0.7: ベースラインをボックス上端から70%に設定
        chip_w = len(f"AS {asn}") * 9 + 12
        chip_h = 20
        # テキスト y: 背景矩形の垂直中央（chip_h の約 70% をベースラインとして使用）
        text_y = chip_y + chip_h * 0.7
        parts.append(
            f'<g class="as-group-container" data-as="{_esc(asn)}">'
            f'<rect x="{min_x:.1f}" y="{min_y:.1f}" '
            f'width="{rect_w:.1f}" height="{rect_h:.1f}" '
            f'rx="{_AS_GROUP_RX}" ry="{_AS_GROUP_RY}" class="as-group" '
            f'style="stroke:{stroke_color};fill:{fill_color};"/>'
            f'<rect x="{chip_x:.1f}" y="{chip_y:.1f}" '
            f'width="{chip_w:.1f}" height="{chip_h:.1f}" '
            f'rx="4" ry="4" class="as-group-label-bg" '
            f'style="fill:{label_bg_color};"/>'
            f'<text x="{chip_x + 5:.1f}" y="{text_y:.1f}" '
            f'text-anchor="start" class="as-group-label" '
            f'style="fill:#ffffff;">'
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


def _build_ip_to_device(interfaces: list[dict]) -> dict[str, str]:
    """interfaces から ip_only -> device_id 逆引きマップを構築する。

    Phase 3F 拡張: addresses リストが存在する場合は全アドレス（v4/v6）を登録する。
    addresses がない旧形式では ip フィールドにフォールバックする（後方互換）。

    Phase 3H 拡張: IPv6 アドレスは raw 文字列に加え、ipaddress.ip_address() で
    正規化した文字列も登録する（"2001:db8:1::" と "2001:db8:1::0" が同一アドレスを
    指す short-form / full-form の差異を吸収する）。

    Args:
        interfaces: topology の interfaces リスト

    Returns:
        ``{ip_only: device_id}`` 辞書。
        ip を持たないエントリはスキップする。
    """
    result: dict[str, str] = {}
    for iface in interfaces:
        dev_id = iface.get("device", "")
        addresses = iface.get("addresses")
        if addresses:
            # Phase 3F: addresses から全アドレスを登録（v4 + v6）
            for addr in addresses:
                ip_str = addr.get("ip", "")
                if ip_str:
                    result[ip_str] = dev_id
                    # Phase 3H: v6 アドレスは正規化形式も登録（short-form/full-form 両対応）
                    try:
                        normalized = str(ipaddress.ip_address(ip_str))
                        if normalized != ip_str:
                            result[normalized] = dev_id
                    except (ValueError, TypeError):
                        pass
        else:
            # フォールバック: ip フィールドから登録（旧形式後方互換）
            if iface.get("ip"):
                ip_only = iface["ip"].split("/")[0]
                result[ip_only] = dev_id
    return result


def _build_ip_to_iface_id(interfaces: list[dict]) -> dict[str, str]:
    """interfaces から ip_only -> iface_id 逆引きマップを構築する。

    _build_ip_to_device と対称なヘルパー。チップアンカー解決に使用する。

    Phase 3F 拡張: addresses リストが存在する場合は全アドレス（v4/v6）を登録する。
    addresses がない旧形式では ip フィールドにフォールバックする（後方互換）。

    Phase 3H 拡張: IPv6 アドレスは raw 文字列に加え正規化形式も登録する
    （_build_ip_to_device と対称）。

    Args:
        interfaces: topology の interfaces リスト

    Returns:
        ``{ip_only: iface_id}`` 辞書。
        ip を持たないエントリはスキップする。
    """
    result: dict[str, str] = {}
    for iface in interfaces:
        iface_id = iface.get("id", "")
        addresses = iface.get("addresses")
        if addresses:
            # Phase 3F: addresses から全アドレスを登録（v4 + v6）
            for addr in addresses:
                ip_str = addr.get("ip", "")
                if ip_str:
                    result[ip_str] = iface_id
                    # Phase 3H: v6 アドレスは正規化形式も登録（short-form/full-form 両対応）
                    try:
                        normalized = str(ipaddress.ip_address(ip_str))
                        if normalized != ip_str:
                            result[normalized] = iface_id
                    except (ValueError, TypeError):
                        pass
        else:
            # フォールバック: ip フィールドから登録（旧形式後方互換）
            if iface.get("ip"):
                ip_only = iface["ip"].split("/")[0]
                result[ip_only] = iface_id
    return result


def _format_iface_ip_cell(iface: dict) -> str:
    """IF の IP アドレスを HTML セル用文字列として返す。

    dual-stack（v4 + v6 GUA）の場合は v4/v6 を個別に _esc() してから
    '<br>' で連結した HTML 断片を返す（HTML テキストノードで改行が折り畳まれる問題を回避）。
    single-stack（v4のみ/v6のみ）または空の場合は '<br>' なしの単一文字列を返す。

    cards.py / views.py 双方から import して使用する共通ヘルパー。

    Args:
        iface: インタフェース辞書

    Returns:
        HTML セル用文字列。dual-stack: "<v4><br><v6>"、single: "<ip>"、空: ""
    """
    ip_val = iface.get("ip") or ""
    addresses = iface.get("addresses") or []

    if ip_val:
        # dual-stack 判定: v6 GUA があれば v4<br>v6 形式
        v6_gua = ""
        for addr in addresses:
            if addr.get("af") != "v6":
                continue
            if addr.get("scope") == "link-local":
                continue
            v6_ip = addr.get("ip", "")
            v6_prefix = addr.get("prefix")
            if not v6_ip:
                continue
            v6_gua = f"{v6_ip}/{v6_prefix}" if v6_prefix is not None else v6_ip
            break
        if v6_gua:
            return f"{_esc(ip_val)}<br>{_esc(v6_gua)}"
        return _esc(ip_val)

    # ip が None/空: addresses から先頭 v6 GUA を取得（単一行）
    for addr in addresses:
        if addr.get("af") != "v6":
            continue
        if addr.get("scope") == "link-local":
            continue
        ip_str = addr.get("ip", "")
        prefix = addr.get("prefix")
        if not ip_str:
            continue
        v6_str = f"{ip_str}/{prefix}" if prefix is not None else ip_str
        return _esc(v6_str)

    return ""


