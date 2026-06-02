"""
TDD テスト: build_topology.build()

テスト方針:
  1. ゴールデンテスト: サンプル2ファイルをパース → build() → examples/topology/（層別 YAML）と完全一致
  2. ID 採番ユニットテスト (device id: 重複/空/記号)
  3. リンク推論ユニットテスト (2メンバー→link / 3メンバー→segment / 1メンバー→なし /
     shutdown除外 / ip なし除外 / 自己ループ除外)
  4. BGP ユニットテスト (ebgp/ibgp/unknown / local_ip 解決 / 対向なし)
  5. 空入力テスト (devices=[])
  6. カバレッジ 80% 以上
"""

from __future__ import annotations

import ipaddress
import json
import os
import sys
import pytest

from lib.parsers.base import (
    BgpNeighbor,
    Device,
    Interface,
    OspfNetwork,
    StaticRoute,
)

# ================================================================
# ヘルパー: テスト用 Device を簡単に作るファクトリ
# ================================================================

def make_device(
    hostname: str,
    vendor: str = "cisco_ios",
    asn: int | None = None,
    interfaces: list[Interface] | None = None,
    bgp: list[BgpNeighbor] | None = None,
    ospf: list[OspfNetwork] | None = None,
    static: list[StaticRoute] | None = None,
) -> Device:
    return Device(
        hostname=hostname,
        vendor=vendor,
        asn=asn,
        interfaces=interfaces or [],
        bgp=bgp or [],
        ospf=ospf or [],
        static=static or [],
    )


def make_iface(
    name: str,
    ip: str | None = None,
    description: str | None = None,
    shutdown: bool = False,
    vlan: int | None = None,
) -> Interface:
    return Interface(name=name, ip=ip, description=description, shutdown=shutdown, vlan=vlan)


# ================================================================
# ゴールデンテスト (最重要)
# ================================================================

class TestGoldenOutput:
    """サンプル2ファイルからの build() 結果が examples/topology/ と完全一致する。"""

    @pytest.fixture(scope="class")
    def expected(self):
        """examples/topology/ の層別 YAML を load_topology() で読み込む（Stage2 正本）。"""
        from lib.topology_io import load_topology
        examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
        return load_topology(os.path.join(examples_dir, "topology"))

    @pytest.fixture(scope="class")
    def actual(self):
        from scripts.parse_configs import parse_paths
        from scripts.build_topology import build

        examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
        paths = [
            os.path.join(examples_dir, "configs", "sample-ios-r1.cfg"),
            os.path.join(examples_dir, "configs", "sample-junos-r2.conf"),
        ]
        devices = parse_paths(paths)
        return build(
            devices,
            generated_from=["sample-ios-r1.cfg", "sample-junos-r2.conf"],
            title="Network Topology (config-derived)",
        )

    def test_golden_exact_match(self, expected, actual):
        """build() 出力が examples/topology/（層別 YAML 正本）と完全一致する。"""
        assert actual == expected, (
            f"\n--- Expected ---\n{json.dumps(expected, ensure_ascii=False, indent=2)}"
            f"\n--- Actual ---\n{json.dumps(actual, ensure_ascii=False, indent=2)}"
        )

    def test_golden_title(self, expected, actual):
        assert actual["title"] == expected["title"]

    def test_golden_generated_from(self, expected, actual):
        assert actual["generated_from"] == expected["generated_from"]

    def test_golden_devices_count(self, expected, actual):
        assert len(actual["devices"]) == len(expected["devices"])

    def test_golden_interfaces_count(self, expected, actual):
        assert len(actual["interfaces"]) == len(expected["interfaces"])

    def test_golden_links_count(self, expected, actual):
        assert len(actual["links"]) == len(expected["links"])

    def test_golden_segments_empty(self, expected, actual):
        assert actual["segments"] == []

    def test_golden_bgp(self, expected, actual):
        assert actual["routing"]["bgp"] == expected["routing"]["bgp"]

    def test_golden_ospf(self, expected, actual):
        assert actual["routing"]["ospf"] == expected["routing"]["ospf"]

    def test_golden_static(self, expected, actual):
        assert actual["routing"]["static"] == expected["routing"]["static"]


# ================================================================
# ID 採番ユニットテスト
# ================================================================

class TestDeviceIdAssignment:
    """device id 採番規則の単体テスト。"""

    def _build_minimal(self, devices):
        from scripts.build_topology import build
        result = build(devices, generated_from=[])
        return [d["id"] for d in result["devices"]]

    @pytest.mark.unit
    def test_hostname_lowercased(self):
        """hostname を小文字化する。"""
        d = make_device("R1")
        ids = self._build_minimal([d])
        assert ids == ["r1"]

    @pytest.mark.unit
    def test_special_chars_replaced_with_hyphen(self):
        """英数字・ハイフン以外を - に置換する。"""
        d = make_device("Core_Switch.01")
        ids = self._build_minimal([d])
        assert ids == ["core-switch-01"]

    @pytest.mark.unit
    def test_duplicate_hostname_gets_suffix(self):
        """重複 hostname は -2, -3 を付与する。"""
        d1 = make_device("R1")
        d2 = make_device("R1")
        d3 = make_device("R1")
        ids = self._build_minimal([d1, d2, d3])
        assert ids == ["r1", "r1-2", "r1-3"]

    @pytest.mark.unit
    def test_empty_hostname_becomes_device(self):
        """空 hostname は 'device' になる。"""
        d = make_device("")
        ids = self._build_minimal([d])
        assert ids == ["device"]

    @pytest.mark.unit
    def test_empty_hostname_duplicates(self):
        """空 hostname が複数あれば 'device', 'device-2', ... となる。"""
        ids = self._build_minimal([make_device(""), make_device("")])
        assert ids == ["device", "device-2"]

    @pytest.mark.unit
    def test_hyphen_preserved(self):
        """ハイフンはそのまま保持される。"""
        d = make_device("core-rtr-01")
        ids = self._build_minimal([d])
        assert ids == ["core-rtr-01"]

    @pytest.mark.unit
    def test_device_id_in_interfaces(self):
        """interface id が '<device_id>::<name>' 形式になる。"""
        iface = make_iface("GigabitEthernet0/0", ip="10.0.0.1/30")
        d = make_device("R1", interfaces=[iface])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        if_ids = [i["id"] for i in result["interfaces"]]
        assert if_ids == ["r1::GigabitEthernet0/0"]

    @pytest.mark.unit
    def test_interface_device_field_matches_device_id(self):
        """interface.device フィールドが device id と一致する。"""
        iface = make_iface("eth0", ip="10.0.0.1/30")
        d = make_device("R1", interfaces=[iface])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert result["interfaces"][0]["device"] == "r1"


# ================================================================
# リンク推論ユニットテスト
# ================================================================

class TestLinkInference:
    """サブネットによる結線推論の単体テスト。"""

    @pytest.mark.unit
    def test_two_devices_same_subnet_creates_link(self):
        """別機器 2 IF が同一サブネット → links に 1 本。"""
        d1 = make_device("R1", interfaces=[make_iface("eth0", ip="10.0.0.1/30")])
        d2 = make_device("R2", interfaces=[make_iface("eth0", ip="10.0.0.2/30")])
        from scripts.build_topology import build
        result = build([d1, d2], generated_from=[])
        assert len(result["links"]) == 1
        assert result["segments"] == []

    @pytest.mark.unit
    def test_link_fields_correct(self):
        """link の a_device, b_device, a_if, b_if, subnet, kind が正しい。"""
        d1 = make_device("R1", interfaces=[make_iface("GigabitEthernet0/0", ip="10.0.0.1/30")])
        d2 = make_device("R2", interfaces=[make_iface("ge-0/0/0", ip="10.0.0.2/30")])
        from scripts.build_topology import build
        result = build([d1, d2], generated_from=[])
        link = result["links"][0]
        assert link["a_device"] == "r1"
        assert link["b_device"] == "r2"
        assert link["a_if"] == "GigabitEthernet0/0"
        assert link["b_if"] == "ge-0/0/0"
        assert link["subnet"] == "10.0.0.0/30"
        assert link["kind"] == "inferred-subnet"

    @pytest.mark.unit
    def test_link_stable_sorted_a_less_b(self):
        """a_device < b_device (ID 昇順) で安定化する。"""
        # device_id が 'r2' < 'r1' でなく 'r1' < 'r2' になるよう
        d1 = make_device("Z1", interfaces=[make_iface("eth0", ip="10.0.0.1/30")])
        d2 = make_device("A1", interfaces=[make_iface("eth0", ip="10.0.0.2/30")])
        from scripts.build_topology import build
        result = build([d1, d2], generated_from=[])
        link = result["links"][0]
        assert link["a_device"] <= link["b_device"]

    @pytest.mark.unit
    def test_three_devices_same_subnet_creates_segment(self):
        """3 IF が同一サブネット → segments に 1 ノード、links はなし。"""
        d1 = make_device("SW1", interfaces=[make_iface("eth0", ip="192.168.1.1/24")])
        d2 = make_device("SW2", interfaces=[make_iface("eth0", ip="192.168.1.2/24")])
        d3 = make_device("SW3", interfaces=[make_iface("eth0", ip="192.168.1.3/24")])
        from scripts.build_topology import build
        result = build([d1, d2, d3], generated_from=[])
        assert len(result["links"]) == 0
        assert len(result["segments"]) == 1

    @pytest.mark.unit
    def test_segment_fields_correct(self):
        """segment の id / subnet / members が正しい。"""
        d1 = make_device("SW1", interfaces=[make_iface("eth0", ip="192.168.1.1/24")])
        d2 = make_device("SW2", interfaces=[make_iface("eth0", ip="192.168.1.2/24")])
        d3 = make_device("SW3", interfaces=[make_iface("eth0", ip="192.168.1.3/24")])
        from scripts.build_topology import build
        result = build([d1, d2, d3], generated_from=[])
        seg = result["segments"][0]
        assert seg["id"] == "seg-192_168_1_0_24"
        assert seg["subnet"] == "192.168.1.0/24"
        # members は interface id の昇順
        assert seg["members"] == sorted(seg["members"])
        assert "sw1::eth0" in seg["members"]
        assert "sw2::eth0" in seg["members"]
        assert "sw3::eth0" in seg["members"]

    @pytest.mark.unit
    def test_single_if_subnet_no_link(self):
        """1 IF のみのサブネット → links/segments ともになし（スタブ）。"""
        d = make_device("R1", interfaces=[
            make_iface("Loopback0", ip="1.1.1.1/32"),
        ])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert result["links"] == []
        assert result["segments"] == []

    @pytest.mark.unit
    def test_shutdown_if_excluded_from_links(self):
        """shutdown=True の IF はリンク推論から除外される。"""
        d1 = make_device("R1", interfaces=[make_iface("eth0", ip="10.0.0.1/30", shutdown=True)])
        d2 = make_device("R2", interfaces=[make_iface("eth0", ip="10.0.0.2/30")])
        from scripts.build_topology import build
        result = build([d1, d2], generated_from=[])
        assert result["links"] == []

    @pytest.mark.unit
    def test_no_ip_if_excluded_from_links(self):
        """ip=None の IF はリンク推論から除外される。"""
        d1 = make_device("R1", interfaces=[make_iface("eth0", ip=None)])
        d2 = make_device("R2", interfaces=[make_iface("eth0", ip=None)])
        from scripts.build_topology import build
        result = build([d1, d2], generated_from=[])
        assert result["links"] == []

    @pytest.mark.unit
    def test_same_device_same_subnet_no_self_loop(self):
        """同一機器の同一サブネット IF → 自己ループリンクを作らない。"""
        # 異常設定: 同一機器に同じ /30 の IF が 2 本
        d = make_device("R1", interfaces=[
            make_iface("eth0", ip="10.0.0.1/30"),
            make_iface("eth1", ip="10.0.0.2/30"),
        ])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        # 自己ループは作らない
        for link in result["links"]:
            assert link["a_device"] != link["b_device"]

    @pytest.mark.unit
    def test_loopback_32_is_stub(self):
        """Loopback /32 は単独メンバー → スタブ。"""
        d = make_device("R1", interfaces=[make_iface("lo0", ip="2.2.2.2/32")])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert result["links"] == []
        assert result["segments"] == []

    @pytest.mark.unit
    def test_segment_id_slash_replaced(self):
        """segment id の / と . が _ に置換される。"""
        d1 = make_device("A", interfaces=[make_iface("eth0", ip="10.1.2.1/24")])
        d2 = make_device("B", interfaces=[make_iface("eth0", ip="10.1.2.2/24")])
        d3 = make_device("C", interfaces=[make_iface("eth0", ip="10.1.2.3/24")])
        from scripts.build_topology import build
        result = build([d1, d2, d3], generated_from=[])
        seg_id = result["segments"][0]["id"]
        assert "/" not in seg_id
        assert "." not in seg_id
        assert seg_id == "seg-10_1_2_0_24"


# ================================================================
# BGP ユニットテスト
# ================================================================

class TestBgpResolution:
    """BGP 対向解決と type 判定の単体テスト。"""

    @pytest.mark.unit
    def test_ebgp_type(self):
        """local_as != peer_as → ebgp。"""
        d1 = make_device("R1", asn=65001,
                          interfaces=[make_iface("eth0", ip="10.0.0.1/30")],
                          bgp=[BgpNeighbor(neighbor_ip="10.0.0.2", peer_as=65002)])
        d2 = make_device("R2", asn=65002,
                          interfaces=[make_iface("eth0", ip="10.0.0.2/30")])
        from scripts.build_topology import build
        result = build([d1, d2], generated_from=[])
        bgp_entries = [b for b in result["routing"]["bgp"] if b["device"] == "r1"]
        assert bgp_entries[0]["type"] == "ebgp"

    @pytest.mark.unit
    def test_ibgp_type(self):
        """local_as == peer_as → ibgp。"""
        d1 = make_device("R1", asn=65001,
                          interfaces=[make_iface("eth0", ip="10.0.0.1/30")],
                          bgp=[BgpNeighbor(neighbor_ip="10.0.0.2", peer_as=65001)])
        d2 = make_device("R2", asn=65001,
                          interfaces=[make_iface("eth0", ip="10.0.0.2/30")])
        from scripts.build_topology import build
        result = build([d1, d2], generated_from=[])
        bgp_entries = [b for b in result["routing"]["bgp"] if b["device"] == "r1"]
        assert bgp_entries[0]["type"] == "ibgp"

    @pytest.mark.unit
    def test_unknown_type_when_peer_as_none(self):
        """peer_as=None → unknown。"""
        d = make_device("R1", asn=65001,
                         interfaces=[make_iface("eth0", ip="10.0.0.1/30")],
                         bgp=[BgpNeighbor(neighbor_ip="10.0.0.2", peer_as=None)])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert result["routing"]["bgp"][0]["type"] == "unknown"

    @pytest.mark.unit
    def test_local_ip_resolved(self):
        """neighbor_ip と同一サブネットにある自機 IF の IP が local_ip になる。"""
        d1 = make_device("R1", asn=65001,
                          interfaces=[make_iface("eth0", ip="10.0.0.1/30")],
                          bgp=[BgpNeighbor(neighbor_ip="10.0.0.2", peer_as=65002)])
        from scripts.build_topology import build
        result = build([d1], generated_from=[])
        assert result["routing"]["bgp"][0]["local_ip"] == "10.0.0.1"

    @pytest.mark.unit
    def test_local_ip_null_when_no_matching_subnet(self):
        """同一サブネットの自機 IF がなければ local_ip=null。"""
        d = make_device("R1", asn=65001,
                         interfaces=[make_iface("eth0", ip="192.168.1.1/24")],
                         bgp=[BgpNeighbor(neighbor_ip="10.0.0.2", peer_as=65002)])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert result["routing"]["bgp"][0]["local_ip"] is None

    @pytest.mark.unit
    def test_bgp_with_no_peer_config(self):
        """対向機器が config に存在しなくても BGP エントリは残る（片側）。"""
        d = make_device("R1", asn=65001,
                         interfaces=[make_iface("eth0", ip="10.0.0.1/30")],
                         bgp=[BgpNeighbor(neighbor_ip="203.0.113.1", peer_as=64512)])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert len(result["routing"]["bgp"]) == 1
        assert result["routing"]["bgp"][0]["neighbor_ip"] == "203.0.113.1"

    @pytest.mark.unit
    def test_bgp_local_as_from_device_asn(self):
        """bgp エントリの local_as は device.asn の値。"""
        d = make_device("R1", asn=65001,
                         bgp=[BgpNeighbor(neighbor_ip="10.0.0.2", peer_as=65002)])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert result["routing"]["bgp"][0]["local_as"] == 65001

    @pytest.mark.unit
    def test_bgp_neighbor_ip_field(self):
        """bgp エントリに neighbor_ip が正しく含まれる。"""
        d = make_device("R1", asn=65001,
                         bgp=[BgpNeighbor(neighbor_ip="10.0.0.2", peer_as=65002)])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert result["routing"]["bgp"][0]["neighbor_ip"] == "10.0.0.2"

    @pytest.mark.unit
    def test_bgp_entries_ordered_by_device(self):
        """BGP エントリは device 順。"""
        d1 = make_device("R1", asn=65001,
                          bgp=[BgpNeighbor(neighbor_ip="10.0.0.2", peer_as=65002)])
        d2 = make_device("R2", asn=65002,
                          bgp=[BgpNeighbor(neighbor_ip="10.0.0.1", peer_as=65001)])
        from scripts.build_topology import build
        result = build([d1, d2], generated_from=[])
        device_order = [b["device"] for b in result["routing"]["bgp"]]
        # r1 が先に来る
        assert device_order.index("r1") < device_order.index("r2")


# ================================================================
# OSPF / Static ユニットテスト
# ================================================================

class TestOspfAndStatic:
    """routing.ospf / routing.static の出力テスト。"""

    @pytest.mark.unit
    def test_ospf_entry_fields(self):
        """OSPF エントリに device / process / network / area が含まれる。"""
        d = make_device("R1",
                         ospf=[OspfNetwork(process=1, network="192.168.1.0/24", area="0")])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert len(result["routing"]["ospf"]) == 1
        entry = result["routing"]["ospf"][0]
        assert entry["device"] == "r1"
        assert entry["process"] == 1
        assert entry["network"] == "192.168.1.0/24"
        assert entry["area"] == "0"

    @pytest.mark.unit
    def test_static_entry_fields(self):
        """static エントリに device / prefix / next_hop が含まれる。"""
        d = make_device("R1",
                         static=[StaticRoute(prefix="0.0.0.0/0", next_hop="10.0.0.2")])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert len(result["routing"]["static"]) == 1
        entry = result["routing"]["static"][0]
        assert entry["device"] == "r1"
        assert entry["prefix"] == "0.0.0.0/0"
        assert entry["next_hop"] == "10.0.0.2"

    @pytest.mark.unit
    def test_ospf_entries_ordered_by_device(self):
        """OSPF エントリは device 順。"""
        d1 = make_device("R1", ospf=[OspfNetwork(process=1, network="10.0.0.0/30", area="0")])
        d2 = make_device("R2", ospf=[OspfNetwork(process=1, network="10.0.0.4/30", area="0")])
        from scripts.build_topology import build
        result = build([d1, d2], generated_from=[])
        devices = [e["device"] for e in result["routing"]["ospf"]]
        assert devices.index("r1") < devices.index("r2")

    @pytest.mark.unit
    def test_static_entries_ordered_by_device(self):
        """static エントリは device 順。"""
        d1 = make_device("R1", static=[StaticRoute(prefix="0.0.0.0/0", next_hop="1.1.1.1")])
        d2 = make_device("R2", static=[StaticRoute(prefix="0.0.0.0/0", next_hop="2.2.2.2")])
        from scripts.build_topology import build
        result = build([d1, d2], generated_from=[])
        devices = [e["device"] for e in result["routing"]["static"]]
        assert devices.index("r1") < devices.index("r2")


# ================================================================
# 空入力テスト
# ================================================================

class TestEmptyInput:
    """devices=[] でも例外なく正しい空構造が返る。"""

    @pytest.fixture
    def empty_result(self):
        from scripts.build_topology import build
        return build([], generated_from=[])

    @pytest.mark.unit
    def test_empty_devices_no_exception(self, empty_result):
        """例外が発生しない。"""
        assert empty_result is not None

    @pytest.mark.unit
    def test_empty_devices_list(self, empty_result):
        assert empty_result["devices"] == []

    @pytest.mark.unit
    def test_empty_interfaces_list(self, empty_result):
        assert empty_result["interfaces"] == []

    @pytest.mark.unit
    def test_empty_links_list(self, empty_result):
        assert empty_result["links"] == []

    @pytest.mark.unit
    def test_empty_segments_list(self, empty_result):
        assert empty_result["segments"] == []

    @pytest.mark.unit
    def test_empty_bgp(self, empty_result):
        assert empty_result["routing"]["bgp"] == []

    @pytest.mark.unit
    def test_empty_ospf(self, empty_result):
        assert empty_result["routing"]["ospf"] == []

    @pytest.mark.unit
    def test_empty_static(self, empty_result):
        assert empty_result["routing"]["static"] == []

    @pytest.mark.unit
    def test_default_title(self, empty_result):
        assert empty_result["title"] == "Network Topology (config-derived)"

    @pytest.mark.unit
    def test_custom_title(self):
        from scripts.build_topology import build
        result = build([], generated_from=[], title="My Network")
        assert result["title"] == "My Network"

    @pytest.mark.unit
    def test_generated_from_preserved(self):
        from scripts.build_topology import build
        result = build([], generated_from=["a.cfg", "b.conf"])
        assert result["generated_from"] == ["a.cfg", "b.conf"]


# ================================================================
# build() の出力構造テスト
# ================================================================

class TestBuildOutputStructure:
    """build() の返す dict の構造が正しい。"""

    @pytest.mark.unit
    def test_build_returns_dict(self):
        from scripts.build_topology import build
        result = build([], generated_from=[])
        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_build_has_required_top_level_keys(self):
        from scripts.build_topology import build
        result = build([], generated_from=[])
        required_keys = {"title", "generated_from", "devices", "interfaces",
                         "links", "segments", "routing"}
        assert required_keys.issubset(result.keys())

    @pytest.mark.unit
    def test_routing_has_required_keys(self):
        from scripts.build_topology import build
        result = build([], generated_from=[])
        assert set(result["routing"].keys()) == {"bgp", "ospf", "static"}

    @pytest.mark.unit
    def test_device_entry_has_required_fields(self):
        """device エントリに id/hostname/vendor/as/sections が含まれる。"""
        d = make_device("R1", vendor="cisco_ios", asn=65001)
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        dev = result["devices"][0]
        for key in ("id", "hostname", "vendor", "as", "sections"):
            assert key in dev, f"device に '{key}' フィールドがない"

    @pytest.mark.unit
    def test_device_sections_is_empty_list(self):
        """sections は空リストで初期化される。"""
        d = make_device("R1")
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert result["devices"][0]["sections"] == []

    @pytest.mark.unit
    def test_device_as_field_maps_to_asn(self):
        """device の 'as' フィールドが device.asn の値。"""
        d = make_device("R1", asn=65001)
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert result["devices"][0]["as"] == 65001

    @pytest.mark.unit
    def test_device_as_field_null_when_no_asn(self):
        d = make_device("R1", asn=None)
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert result["devices"][0]["as"] is None

    @pytest.mark.unit
    def test_interface_entry_has_required_fields(self):
        """interface エントリに id/device/name/ip/vlan/description/shutdown が含まれる。"""
        iface = make_iface("eth0", ip="10.0.0.1/30", description="uplink")
        d = make_device("R1", interfaces=[iface])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        if_entry = result["interfaces"][0]
        for key in ("id", "device", "name", "ip", "vlan", "description", "shutdown"):
            assert key in if_entry, f"interface に '{key}' フィールドがない"

    @pytest.mark.unit
    def test_interface_vlan_null_by_default(self):
        iface = make_iface("eth0")
        d = make_device("R1", interfaces=[iface])
        from scripts.build_topology import build
        result = build([d], generated_from=[])
        assert result["interfaces"][0]["vlan"] is None

    @pytest.mark.unit
    def test_interfaces_ordered_device_then_config(self):
        """interfaces は device 順 × config 出現順。"""
        d1 = make_device("R1", interfaces=[
            make_iface("eth1"),
            make_iface("eth0"),
        ])
        d2 = make_device("R2", interfaces=[
            make_iface("eth0"),
        ])
        from scripts.build_topology import build
        result = build([d1, d2], generated_from=[])
        ids = [i["id"] for i in result["interfaces"]]
        # r1 の IF が r2 より前
        assert ids.index("r1::eth1") < ids.index("r2::eth0")
        # r1 内の順序は config 出現順を保持
        assert ids.index("r1::eth1") < ids.index("r1::eth0")


# ================================================================
# 決定性テスト
# ================================================================

class TestDeterminism:
    """同一入力で常に同じ出力が得られる。"""

    @pytest.mark.unit
    def test_build_is_deterministic(self):
        """同じ入力から 2 回 build しても結果が同じ。"""
        d1 = make_device("R1", asn=65001,
                          interfaces=[make_iface("eth0", ip="10.0.0.1/30")],
                          bgp=[BgpNeighbor(neighbor_ip="10.0.0.2", peer_as=65002)])
        d2 = make_device("R2", asn=65002,
                          interfaces=[make_iface("eth0", ip="10.0.0.2/30")])
        from scripts.build_topology import build
        r1 = build([d1, d2], generated_from=["a.cfg"])
        r2 = build([d1, d2], generated_from=["a.cfg"])
        assert r1 == r2


# ================================================================
# CLI 統合テスト
# ================================================================

class TestCLI:
    """build_topology.py の CLI 動作テスト（Stage2: -o はディレクトリ出力）。"""

    @pytest.mark.integration
    def test_cli_generates_yaml_dir(self, tmp_path):
        """CLI 実行で層別 YAML ディレクトリが生成される（Stage2）。"""
        import subprocess
        examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "build_topology.py")
        out_dir = str(tmp_path / "out_topo")
        result = subprocess.run(
            [sys.executable, script_path,
             os.path.join(examples_dir, "configs", "sample-ios-r1.cfg"),
             os.path.join(examples_dir, "configs", "sample-junos-r2.conf"),
             "-o", out_dir],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"CLI が失敗: {result.stderr}"
        assert os.path.isdir(out_dir), "出力ディレクトリが生成されていない"
        # 層別 YAML の必須ファイルが存在する
        for fname in ["_meta.yaml", "devices.yaml", "physical.yaml"]:
            assert os.path.exists(os.path.join(out_dir, fname)), \
                f"必須ファイル {fname} が存在しない"

    @pytest.mark.integration
    def test_cli_yaml_load_matches_build(self, tmp_path):
        """CLI 出力を load_topology() で読み込むと build() と dict 一致する（Stage2）。"""
        import subprocess
        from lib.topology_io import load_topology
        from scripts.parse_configs import parse_paths
        from scripts.build_topology import build

        examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "build_topology.py")
        out_dir = str(tmp_path / "yaml_out")
        paths = [
            os.path.join(examples_dir, "configs", "sample-ios-r1.cfg"),
            os.path.join(examples_dir, "configs", "sample-junos-r2.conf"),
        ]
        result = subprocess.run(
            [sys.executable, script_path] + paths + ["-o", out_dir],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"CLI が失敗: {result.stderr}"
        # load_topology で読んだ dict が build() と一致する
        loaded = load_topology(out_dir)
        devices = parse_paths(paths)
        expected = build(devices, generated_from=["sample-ios-r1.cfg", "sample-junos-r2.conf"])
        assert loaded == expected

    @pytest.mark.integration
    def test_cli_default_output_dir(self, tmp_path):
        """CLI で -o 省略時、カレントディレクトリに topology/ が生成される（Stage2）。"""
        import subprocess
        examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "build_topology.py")
        result = subprocess.run(
            [sys.executable, script_path,
             os.path.join(examples_dir, "configs", "sample-ios-r1.cfg"),
             os.path.join(examples_dir, "configs", "sample-junos-r2.conf")],
            capture_output=True, text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, f"CLI が失敗: {result.stderr}"
        assert os.path.isdir(str(tmp_path / "topology")), \
            "デフォルト出力ディレクトリ topology/ が生成されていない"

    @pytest.mark.integration
    def test_cli_info_written_to_stderr(self, tmp_path):
        """CLI 実行時に [INFO] Written: <dir> が stderr に出力される（Stage2）。"""
        import subprocess
        examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "build_topology.py")
        out_dir = str(tmp_path / "info_test")
        result = subprocess.run(
            [sys.executable, script_path,
             os.path.join(examples_dir, "configs", "sample-ios-r1.cfg"),
             os.path.join(examples_dir, "configs", "sample-junos-r2.conf"),
             "-o", out_dir],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"CLI が失敗: {result.stderr}"
        assert "[INFO] Written:" in result.stderr, \
            f"stderr に [INFO] Written: がない: {result.stderr}"


# ================================================================
# [HIGH] device id 採番の衝突テスト（修正項目 1）
# ================================================================

class TestDeviceIdCollisionFix:
    """別 hostname が正規化後に既存 ID と衝突するケースの採番テスト。"""

    def _ids(self, hostnames: list[str]) -> list[str]:
        from scripts.build_topology import build
        devices = [make_device(h) for h in hostnames]
        result = build(devices, generated_from=[])
        return [d["id"] for d in result["devices"]]

    @pytest.mark.unit
    def test_no_duplicate_ids_when_second_hostname_clashes(self):
        """["R1","R1-2","R1"] → 正規化後 r1,r1-2,r1 で r1-2 が衝突する。
        全 ID が一意になること。"""
        ids = self._ids(["R1", "R1-2", "R1"])
        assert len(ids) == len(set(ids)), f"ID に重複あり: {ids}"

    @pytest.mark.unit
    def test_collision_case_all_ids_unique(self):
        """["R1","R1-2","R1"] のケースで具体的に一意な ID が3本得られる。"""
        ids = self._ids(["R1", "R1-2", "R1"])
        assert len(ids) == 3
        assert len(set(ids)) == 3

    @pytest.mark.unit
    def test_normal_duplicate_still_works(self):
        """通常の重複 ["R1","R1","R1"] は r1,r1-2,r1-3 で一意になる。"""
        ids = self._ids(["R1", "R1", "R1"])
        assert ids == ["r1", "r1-2", "r1-3"]
        assert len(set(ids)) == 3

    @pytest.mark.unit
    def test_empty_hostname_collision(self):
        """空 hostname 複数でも全 ID が一意になる。"""
        ids = self._ids(["", "", ""])
        assert len(ids) == len(set(ids)), f"ID に重複あり: {ids}"
        assert ids[0] == "device"

    @pytest.mark.unit
    def test_symbol_hostname_collision(self):
        """記号入り hostname が正規化後に衝突しても一意になる。"""
        # "R1_2" → "r1-2", "R1-2" → "r1-2", "R1" → "r1" 後に r1-2 採番
        ids = self._ids(["R1", "R1_2", "R1-2"])
        assert len(ids) == len(set(ids)), f"ID に重複あり: {ids}"
        assert len(ids) == 3

    @pytest.mark.unit
    def test_ids_collision_interface_ids_also_unique(self):
        """ID 衝突が修正された場合、interface id も一意になる。"""
        from scripts.build_topology import build
        iface = make_iface("eth0", ip="10.0.0.1/30")
        devices = [make_device(h, interfaces=[iface]) for h in ["R1", "R1-2", "R1"]]
        result = build(devices, generated_from=[])
        if_ids = [i["id"] for i in result["interfaces"]]
        assert len(if_ids) == len(set(if_ids)), f"interface id に重複あり: {if_ids}"


# ================================================================
# [MEDIUM] BGP local_as=None 誤判定テスト（修正項目 2）
# ================================================================

class TestBgpTypeLocalAsNone:
    """local_as=None のとき peer_as が有効でも unknown を返すことを検証。"""

    @pytest.mark.unit
    def test_local_as_none_with_valid_peer_as_returns_unknown(self):
        """local_as=None かつ peer_as 有効 → unknown（現状は ebgp の誤判定）。"""
        from scripts.build_topology import _determine_bgp_type
        result = _determine_bgp_type(local_as=None, peer_as=65001)
        assert result == "unknown", f"Expected 'unknown', got '{result}'"

    @pytest.mark.unit
    def test_local_as_none_peer_as_none_returns_unknown(self):
        """local_as=None かつ peer_as=None → unknown。"""
        from scripts.build_topology import _determine_bgp_type
        result = _determine_bgp_type(local_as=None, peer_as=None)
        assert result == "unknown"

    @pytest.mark.unit
    def test_peer_as_none_returns_unknown(self):
        """peer_as=None（local_as 有効）→ unknown（既存動作の維持確認）。"""
        from scripts.build_topology import _determine_bgp_type
        result = _determine_bgp_type(local_as=65001, peer_as=None)
        assert result == "unknown"

    @pytest.mark.unit
    def test_ibgp_unchanged(self):
        """local_as == peer_as → ibgp（既存動作の維持確認）。"""
        from scripts.build_topology import _determine_bgp_type
        result = _determine_bgp_type(local_as=65001, peer_as=65001)
        assert result == "ibgp"

    @pytest.mark.unit
    def test_ebgp_unchanged(self):
        """local_as != peer_as（両方 int）→ ebgp（既存動作の維持確認）。"""
        from scripts.build_topology import _determine_bgp_type
        result = _determine_bgp_type(local_as=65001, peer_as=65002)
        assert result == "ebgp"

    @pytest.mark.unit
    def test_build_local_as_none_gives_unknown_type(self):
        """build() 経由でも local_as=None デバイスの BGP type が unknown。"""
        from scripts.build_topology import build
        from lib.parsers.base import BgpNeighbor
        d = make_device("R1", asn=None,
                         interfaces=[make_iface("eth0", ip="10.0.0.1/30")],
                         bgp=[BgpNeighbor(neighbor_ip="10.0.0.2", peer_as=65002)])
        result = build([d], generated_from=[])
        assert result["routing"]["bgp"][0]["type"] == "unknown"


# ================================================================
# [maint HIGH] デッドコード削除の確認テスト（修正項目 3）
# ================================================================

class TestDeadCodeRemoval:
    """dev_id_to_interfaces が削除された後も build() が正常動作することを確認。"""

    @pytest.mark.unit
    def test_build_still_works_after_dead_code_removal(self):
        """build() が例外なく動作し、interfaces セクションが正しく生成される。"""
        from scripts.build_topology import build
        iface = make_iface("eth0", ip="10.0.0.1/30")
        d = make_device("R1", interfaces=[iface])
        result = build([d], generated_from=[])
        assert len(result["interfaces"]) == 1
        assert result["interfaces"][0]["device"] == "r1"

    @pytest.mark.unit
    def test_bgp_resolution_works_without_dev_id_to_interfaces(self):
        """デッドコード削除後も BGP local_ip 解決が正常に動作する。"""
        from scripts.build_topology import build
        from lib.parsers.base import BgpNeighbor
        iface = make_iface("eth0", ip="10.0.0.1/30")
        d = make_device("R1", asn=65001, interfaces=[iface],
                         bgp=[BgpNeighbor(neighbor_ip="10.0.0.2", peer_as=65002)])
        result = build([d], generated_from=[])
        assert result["routing"]["bgp"][0]["local_ip"] == "10.0.0.1"


# ================================================================
# [correct MED] build() generated_from にバセネームを適用（修正項目 4）
# ================================================================

class TestGeneratedFromBasename:
    """build() が generated_from の各要素に basename を適用することを検証。"""

    @pytest.mark.unit
    def test_full_path_becomes_basename(self):
        """フルパスを渡すと generated_from がファイル名のみになる。"""
        from scripts.build_topology import build
        result = build([], generated_from=["/home/user/configs/router.cfg"])
        assert result["generated_from"] == ["router.cfg"]

    @pytest.mark.unit
    def test_multiple_full_paths_become_basenames(self):
        """複数フルパスが全て basename に変換される。"""
        from scripts.build_topology import build
        result = build([], generated_from=[
            "/home/user/configs/r1.cfg",
            "/var/data/r2.conf",
        ])
        assert result["generated_from"] == ["r1.cfg", "r2.conf"]

    @pytest.mark.unit
    def test_basename_only_input_unchanged(self):
        """既に basename のみの入力は変化しない（ゴールデンテスト互換性確認）。"""
        from scripts.build_topology import build
        result = build([], generated_from=["sample-ios-r1.cfg", "sample-junos-r2.conf"])
        assert result["generated_from"] == ["sample-ios-r1.cfg", "sample-junos-r2.conf"]

    @pytest.mark.unit
    def test_empty_generated_from_unchanged(self):
        """空リストは空リストのまま。"""
        from scripts.build_topology import build
        result = build([], generated_from=[])
        assert result["generated_from"] == []


# ================================================================
# カバレッジ欠如の補完テスト
# ================================================================

class TestSelfLoopAndDuplicateIp:
    """自己ループ排除の完全検証と重複 IP 耐性テスト。"""

    @pytest.mark.unit
    def test_same_device_same_subnet_no_link_and_no_segment(self):
        """同一機器の2つの IF が同一サブネット（メンバー数2）のとき、
        links も segments も空であること（自己ループ排除の完全検証）。"""
        from scripts.build_topology import build
        d = make_device("R1", interfaces=[
            make_iface("eth0", ip="10.0.0.1/30"),
            make_iface("eth1", ip="10.0.0.2/30"),
        ])
        result = build([d], generated_from=[])
        assert result["links"] == [], f"自己ループが生成された: {result['links']}"
        assert result["segments"] == [], f"セグメントが生成された: {result['segments']}"

    @pytest.mark.unit
    def test_duplicate_ip_two_devices_no_extra_links(self):
        """同一サブネットに同一 IP を持つ 2 機器で、links が 2 本以上に増殖しない。
        link-inference.md の方針: v1 はクラッシュしない。"""
        from scripts.build_topology import build
        # 両機器が同一 IP 10.0.0.1/30 を持つ（重複 IP 異常設定）
        d1 = make_device("R1", interfaces=[make_iface("eth0", ip="10.0.0.1/30")])
        d2 = make_device("R2", interfaces=[make_iface("eth0", ip="10.0.0.1/30")])
        # 例外が発生しないこと & links が高々 1 本であること
        result = build([d1, d2], generated_from=[])
        assert len(result["links"]) <= 1, (
            f"link が増殖した（{len(result['links'])} 本）: {result['links']}"
        )

    @pytest.mark.unit
    def test_duplicate_ip_does_not_crash(self):
        """重複 IP 設定でも build() が例外なく完了する。"""
        from scripts.build_topology import build
        d1 = make_device("R1", interfaces=[make_iface("eth0", ip="10.0.0.1/30")])
        d2 = make_device("R2", interfaces=[make_iface("eth0", ip="10.0.0.1/30")])
        try:
            result = build([d1, d2], generated_from=[])
        except Exception as e:
            pytest.fail(f"重複 IP で例外が発生した: {e}")
