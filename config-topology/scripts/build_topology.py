"""
build_topology.py — 結線推論層

正規化済みの Device リストを受け取り、topology.json スキーマに準拠した dict を返す。

公開 API:
    build(devices: list[Device], generated_from: list[str],
          title: str = "Network Topology (config-derived)") -> dict

CLI:
    python scripts/build_topology.py [paths...] [-o out.json]
        - paths 省略時は parse_configs.collect_inputs() で inbox/ から収集
        - parse_configs.parse_paths() で Device 群を得て build() し、
          -o（既定 topology.json）へ JSON 書き出し（ensure_ascii=False, indent=2）

設計判断:
    - ipaddress 標準モジュールのみ使用（外部依存なし）
    - 決定性を保証: 乱数・時刻に依存しない、全リストは安定ソート
    - link-inference.md および schema.md に厳密準拠
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
from collections import defaultdict

# スクリプトから直接実行された場合もインポートできるようにパスを追加
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.parsers.base import Device


# ================================================================
# ID 採番
# ================================================================

def _make_device_id_base(hostname: str) -> str:
    """hostname を device id の基底文字列に変換する。

    - 小文字化
    - 英数字・ハイフン以外を '-' に置換
    - 空文字列の場合は 'device'
    """
    if not hostname:
        return "device"
    base = hostname.lower()
    base = re.sub(r"[^a-z0-9\-]", "-", base)
    return base


def _assign_device_ids(devices: list[Device]) -> list[str]:
    """Device リストに対して決定的な device id を採番する。

    重複時は -2, -3 ... を付与する。入力の順序を保持する。
    別 hostname が正規化後に既存 ID と衝突する場合も、
    発行済み ID セットと衝突しないサフィックスまでカウントを繰り上げる。
    """
    issued: set[str] = set()
    counter: dict[str, int] = {}
    ids: list[str] = []

    for device in devices:
        base = _make_device_id_base(device.hostname)
        count = counter.get(base, 0) + 1

        if count == 1:
            candidate = base
        else:
            candidate = f"{base}-{count}"

        # 衝突が解消されるまでカウントを繰り上げる
        while candidate in issued:
            count += 1
            candidate = f"{base}-{count}"

        counter[base] = count
        issued.add(candidate)
        ids.append(candidate)

    return ids


# ================================================================
# build() メイン関数
# ================================================================

def build(
    devices: list[Device],
    generated_from: list[str],
    title: str = "Network Topology (config-derived)",
) -> dict:
    """Device リストから topology.json スキーマに準拠した dict を組み立てる。

    Args:
        devices: 正規化済み Device のリスト（パーサ層出力）
        generated_from: 元になった config ファイル名（読み込み順）
        title: 図のタイトル

    Returns:
        topology.json スキーマに準拠した dict
    """
    # --- generated_from を basename に正規化（フルパスが渡されても情報漏洩しない） ---
    generated_from = [os.path.basename(p) for p in generated_from]

    # --- device id 採番 ---
    device_ids = _assign_device_ids(devices)

    # --- devices セクション ---
    devices_out: list[dict] = []
    for dev, dev_id in zip(devices, device_ids):
        devices_out.append({
            "id": dev_id,
            "hostname": dev.hostname,
            "vendor": dev.vendor,
            "as": dev.asn,
            "sections": [],
        })

    # --- interfaces セクション (device 順 × config 出現順) ---
    interfaces_out: list[dict] = []
    for dev, dev_id in zip(devices, device_ids):
        for iface in dev.interfaces:
            interfaces_out.append({
                "id": f"{dev_id}::{iface.name}",
                "device": dev_id,
                "name": iface.name,
                "ip": iface.ip,
                "vlan": iface.vlan,
                "description": iface.description,
                "shutdown": iface.shutdown,
            })

    # --- リンク推論 ---
    links_out, segments_out = _infer_links_and_segments(devices, device_ids)

    # --- BGP 解決 ---
    bgp_out = _build_bgp(devices, device_ids)

    # --- OSPF ---
    ospf_out: list[dict] = []
    for dev, dev_id in zip(devices, device_ids):
        for entry in dev.ospf:
            ospf_out.append({
                "device": dev_id,
                "process": entry.process,
                "network": entry.network,
                "area": entry.area,
            })

    # --- Static ---
    static_out: list[dict] = []
    for dev, dev_id in zip(devices, device_ids):
        for entry in dev.static:
            static_out.append({
                "device": dev_id,
                "prefix": entry.prefix,
                "next_hop": entry.next_hop,
            })

    return {
        "title": title,
        "generated_from": generated_from,
        "devices": devices_out,
        "interfaces": interfaces_out,
        "links": links_out,
        "segments": segments_out,
        "routing": {
            "bgp": bgp_out,
            "ospf": ospf_out,
            "static": static_out,
        },
    }


# ================================================================
# リンク推論
# ================================================================

def _infer_links_and_segments(
    devices: list[Device],
    device_ids: list[str],
) -> tuple[list[dict], list[dict]]:
    """サブネットによる結線推論を行い links と segments を返す。

    Rules (link-inference.md 準拠):
    - ip あり & shutdown=False の IF のみ対象
    - ネットワーク（ip_interface.network）でグルーピング
      - メンバー 2 かつ別機器ペアが存在 → links に 1 本
      - メンバー >= 3 → segments に 1 ノード
      - メンバー 1 → スタブ（何もしない）
    - 同一機器内の同一サブネット: 自己ループ link を作らない
    """
    # (network_str) → list of (dev_id, if_name)
    subnet_to_members: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for dev, dev_id in zip(devices, device_ids):
        for iface in dev.interfaces:
            if iface.ip is None or iface.shutdown:
                continue
            try:
                network = str(ipaddress.ip_interface(iface.ip).network)
            except ValueError:
                continue
            subnet_to_members[network].append((dev_id, iface.name))

    links_out: list[dict] = []
    segments_out: list[dict] = []

    for network_str, members in sorted(subnet_to_members.items()):
        count = len(members)

        if count == 1:
            # スタブ: 何もしない
            continue

        if count == 2:
            # メンバー 2: link 候補
            (dev_a, if_a), (dev_b, if_b) = members
            if dev_a == dev_b:
                # 同一機器 → 自己ループを作らない
                continue
            # a < b で安定化
            if dev_a > dev_b:
                dev_a, if_a, dev_b, if_b = dev_b, if_b, dev_a, if_a
            links_out.append({
                "a_device": dev_a,
                "a_if": if_a,
                "b_device": dev_b,
                "b_if": if_b,
                "subnet": network_str,
                "kind": "inferred-subnet",
            })

        else:
            # メンバー >= 3: segment
            seg_id = "seg-" + network_str.replace(".", "_").replace("/", "_")
            member_ids = sorted(
                f"{dev_id}::{if_name}" for dev_id, if_name in members
            )
            segments_out.append({
                "id": seg_id,
                "subnet": network_str,
                "members": member_ids,
            })

    # links は (a_device, a_if) 昇順でソート
    links_out.sort(key=lambda l: (l["a_device"], l["a_if"]))
    # segments は id 昇順
    segments_out.sort(key=lambda s: s["id"])

    return links_out, segments_out


# ================================================================
# BGP 解決
# ================================================================

def _build_bgp(
    devices: list[Device],
    device_ids: list[str],
) -> list[dict]:
    """BGP エントリを組み立てる。

    - local_ip: neighbor_ip と同一サブネットにある自機 IF の IP（ホスト部）
    - type: ebgp / ibgp / unknown
    """
    bgp_out: list[dict] = []

    for dev, dev_id in zip(devices, device_ids):
        for neighbor in dev.bgp:
            local_ip = _resolve_local_ip(dev, neighbor.neighbor_ip)
            bgp_type = _determine_bgp_type(dev.asn, neighbor.peer_as)

            bgp_out.append({
                "device": dev_id,
                "local_as": dev.asn,
                "local_ip": local_ip,
                "neighbor_ip": neighbor.neighbor_ip,
                "peer_as": neighbor.peer_as,
                "type": bgp_type,
            })

    return bgp_out


def _resolve_local_ip(dev: Device, neighbor_ip: str) -> str | None:
    """neighbor_ip と同一サブネットにある自機 IF の IP（ホスト部のみ）を返す。

    同一サブネットの IF が見つからなければ None を返す。
    """
    try:
        neighbor_addr = ipaddress.ip_address(neighbor_ip)
    except ValueError:
        return None

    for iface in dev.interfaces:
        if iface.ip is None:
            continue
        try:
            iface_net = ipaddress.ip_interface(iface.ip)
        except ValueError:
            continue
        if neighbor_addr in iface_net.network:
            # ホスト部のみ（プレフィックス長なし）
            return str(iface_net.ip)

    return None


def _determine_bgp_type(local_as: int | None, peer_as: int | None) -> str:
    """BGP タイプを判定する。

    - peer_as 不明または local_as 不明 → unknown
    - local_as == peer_as → ibgp
    - それ以外（両方既知かつ異なる）→ ebgp
    """
    if peer_as is None or local_as is None:
        return "unknown"
    if local_as == peer_as:
        return "ibgp"
    return "ebgp"


# ================================================================
# CLI
# ================================================================

def main() -> None:
    """CLI エントリポイント。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build topology.json from network config files."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Config file paths. If omitted, collects from inbox/.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="topology.json",
        help="Output JSON path (default: topology.json)",
    )
    args = parser.parse_args()

    from scripts.parse_configs import collect_inputs, parse_paths

    if args.paths:
        paths: list[str] = []
        for arg in args.paths:
            paths.extend(collect_inputs(arg))
    else:
        paths = collect_inputs()

    devices = parse_paths(paths)
    generated_from = [os.path.basename(p) for p in paths]
    topology = build(devices, generated_from=generated_from)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(topology, f, ensure_ascii=False, indent=2)

    print(f"[INFO] Written: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
