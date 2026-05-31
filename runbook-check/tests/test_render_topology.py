"""
build_render_data() の tables 生成（機器ごとカード構造）に対するユニットテスト。
stdlib unittest のみ使用（openpyxl 不要）。

テスト要件:
1. 2機器 + 各機器にIF複数、BGP(device別)、static(device別)、片方にsections(OSPF) を持つ
   topology dict で build_render_data() を呼び、tables が機器数(+orphanがあれば+1) のカード
2. 各カードが title/node/status/sections を持つ
3. 各機器カードの sections に IF/BGP/static/OSPF がその機器のぶんだけ入ること
4. BGP 行の flow が "bgp%d" で元配列インデックスと一致すること
5. status:"added" が行・カードに伝播していること
6. device未割当のBGP/staticが orphan カード(title="その他（機器未割当）") に入り、
   そのsectionだけ"機器"列を持つこと
7. devices=[] でも例外を出さず orphan カードに集約されること
"""
import sys
import os
import unittest

# PYTHONPATH を通す
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from render_topology import build_render_data


def make_topo():
    """2機器 + IF複数 + BGP(device別) + static(device別) + OSPF sections を持つ topology dict"""
    return {
        "title": "テスト構成",
        "devices": [
            {"id": "dev1", "hostname": "router-A", "as": 65001, "status": "existing"},
            {"id": "dev2", "hostname": "router-B", "as": 65002, "status": "added"},
        ],
        "interfaces": [
            {"id": "dev1-if1", "device": "dev1", "name": "GE0/0", "ip": "10.0.0.1/30", "vlan": None, "description": "to-B", "status": "existing"},
            {"id": "dev1-if2", "device": "dev1", "name": "GE0/1", "ip": "192.168.1.1/24", "vlan": 100, "description": "LAN", "status": "existing"},
            {"id": "dev2-if1", "device": "dev2", "name": "GE0/0", "ip": "10.0.0.2/30", "vlan": None, "description": "to-A", "status": "added"},
            {"id": "dev2-if2", "device": "dev2", "name": "GE0/1", "ip": "172.16.0.1/24", "vlan": None, "description": "WAN", "status": "existing"},
        ],
        "phys_links": [],
        "bgp": [
            # index 0: dev1 ↔ dev2
            {"device": "dev1", "local_ip": "10.0.0.1", "neighbor_ip": "10.0.0.2", "local_as": 65001, "peer_as": 65002, "status": "existing"},
            # index 1: dev2 ↔ dev1 (対向)
            {"device": "dev2", "local_ip": "10.0.0.2", "neighbor_ip": "10.0.0.1", "local_as": 65002, "peer_as": 65001, "status": "added"},
        ],
        "static_routes": [
            # index 0: dev1 の static
            {"device": "dev1", "prefix": "0.0.0.0/0", "next_hop": "10.0.0.2", "status": "existing"},
            # index 1: dev2 の static
            {"device": "dev2", "prefix": "10.0.0.0/8", "next_hop": "172.16.0.254", "status": "added"},
        ],
        "facilities": [],
    }


def make_topo_with_sections():
    """片方の機器(dev1)に sections(OSPF) を持つ topology dict"""
    topo = make_topo()
    topo["devices"][0]["sections"] = [
        {
            "category": "OSPF",
            "columns": ["network", "area", "cost"],
            "rows": [
                {"cells": ["10.0.0.0/30", "0", "10"], "status": "existing"},
                {"cells": ["192.168.1.0/24", "1", "20"], "status": "added", "node": "dev1-if2"},
            ],
        }
    ]
    return topo


def make_topo_with_orphan():
    """device 未割当の BGP / static を持つ topology dict"""
    topo = make_topo()
    topo["bgp"].append(
        {"device": "unknown-dev", "local_ip": "1.2.3.4", "neighbor_ip": "5.6.7.8", "local_as": 99999, "peer_as": 88888, "status": "existing"}
    )
    topo["static_routes"].append(
        {"device": "unknown-dev", "prefix": "8.8.8.0/24", "next_hop": "1.2.3.1", "status": "existing"}
    )
    return topo


class TestBuildRenderDataTablesStructure(unittest.TestCase):
    """テスト1・2: カード数と必須キーの確認"""

    def setUp(self):
        self.topo = make_topo()
        self.data = build_render_data(self.topo)
        self.tables = self.data["tables"]

    def test_tables_count_equals_device_count(self):
        """orphan なし: tables の数 == devices の数（2台）"""
        self.assertEqual(len(self.tables), 2)

    def test_each_card_has_required_keys(self):
        """各カードが title/node/status/sections を持つ"""
        for card in self.tables:
            self.assertIn("title", card, f"card に title がない: {card}")
            self.assertIn("node", card, f"card に node がない: {card}")
            self.assertIn("status", card, f"card に status がない: {card}")
            self.assertIn("sections", card, f"card に sections がない: {card}")

    def test_card_title_includes_hostname_and_as(self):
        """title が hostname / AS<as> 形式になっている"""
        titles = [c["title"] for c in self.tables]
        self.assertIn("router-A / AS65001", titles)
        self.assertIn("router-B / AS65002", titles)

    def test_card_node_matches_device_id(self):
        """card の node が device id と一致する"""
        nodes = [c["node"] for c in self.tables]
        self.assertIn("dev1", nodes)
        self.assertIn("dev2", nodes)

    def test_card_status_matches_device_status(self):
        """card の status が device の status を反映する"""
        card_by_node = {c["node"]: c for c in self.tables}
        self.assertEqual(card_by_node["dev1"]["status"], "existing")
        self.assertEqual(card_by_node["dev2"]["status"], "added")


class TestBuildRenderDataSectionsContent(unittest.TestCase):
    """テスト3: 各機器カードの sections 内容（混在しないこと）"""

    def setUp(self):
        self.topo = make_topo_with_sections()
        self.data = build_render_data(self.topo)
        self.tables = self.data["tables"]
        self.card_by_node = {c["node"]: c for c in self.tables}

    def test_dev1_has_if_section(self):
        """dev1 カードに IF section がある"""
        secs = self.card_by_node["dev1"]["sections"]
        cats = [s["category"] for s in secs]
        self.assertIn("IF", cats)

    def test_dev1_if_section_has_2_rows(self):
        """dev1 の IF section に 2 行（dev1 の IF 2本分）"""
        secs = self.card_by_node["dev1"]["sections"]
        if_sec = next(s for s in secs if s["category"] == "IF")
        self.assertEqual(len(if_sec["rows"]), 2)

    def test_dev2_if_section_has_2_rows(self):
        """dev2 の IF section に 2 行（dev2 の IF 2本分）"""
        secs = self.card_by_node["dev2"]["sections"]
        if_sec = next(s for s in secs if s["category"] == "IF")
        self.assertEqual(len(if_sec["rows"]), 2)

    def test_dev1_bgp_section_only_dev1_bgp(self):
        """dev1 の BGP section には dev1 の BGP のみ（dev2 の BGP が混ざらない）"""
        secs = self.card_by_node["dev1"]["sections"]
        bgp_sec = next((s for s in secs if s["category"] == "BGP"), None)
        self.assertIsNotNone(bgp_sec, "dev1 カードに BGP section がない")
        self.assertEqual(len(bgp_sec["rows"]), 1, f"dev1 の BGP section が 1 行でない: {bgp_sec['rows']}")

    def test_dev2_bgp_section_only_dev2_bgp(self):
        """dev2 の BGP section には dev2 の BGP のみ"""
        secs = self.card_by_node["dev2"]["sections"]
        bgp_sec = next((s for s in secs if s["category"] == "BGP"), None)
        self.assertIsNotNone(bgp_sec, "dev2 カードに BGP section がない")
        self.assertEqual(len(bgp_sec["rows"]), 1)

    def test_dev1_static_section_only_dev1_static(self):
        """dev1 の static section には dev1 の static のみ"""
        secs = self.card_by_node["dev1"]["sections"]
        st_sec = next((s for s in secs if s["category"] == "static"), None)
        self.assertIsNotNone(st_sec, "dev1 に static section がない")
        self.assertEqual(len(st_sec["rows"]), 1)

    def test_dev2_static_section_only_dev2_static(self):
        """dev2 の static section には dev2 の static のみ"""
        secs = self.card_by_node["dev2"]["sections"]
        st_sec = next((s for s in secs if s["category"] == "static"), None)
        self.assertIsNotNone(st_sec, "dev2 に static section がない")
        self.assertEqual(len(st_sec["rows"]), 1)

    def test_dev1_has_ospf_section(self):
        """dev1 に OSPF section（拡張 sections）がある"""
        secs = self.card_by_node["dev1"]["sections"]
        cats = [s["category"] for s in secs]
        self.assertIn("OSPF", cats)

    def test_ospf_section_rows_count(self):
        """OSPF section に 2 行ある"""
        secs = self.card_by_node["dev1"]["sections"]
        ospf_sec = next(s for s in secs if s["category"] == "OSPF")
        self.assertEqual(len(ospf_sec["rows"]), 2)

    def test_dev2_has_no_ospf_section(self):
        """dev2 には OSPF section がない"""
        secs = self.card_by_node["dev2"]["sections"]
        cats = [s["category"] for s in secs]
        self.assertNotIn("OSPF", cats)

    def test_bgp_section_columns_no_device_column(self):
        """機器カードの BGP section には '機器' 列がない（orphan 以外）"""
        for card in self.tables:
            if card["node"] is None:
                continue  # orphan は除く
            secs = card["sections"]
            bgp_sec = next((s for s in secs if s["category"] == "BGP"), None)
            if bgp_sec:
                self.assertNotIn("機器", bgp_sec["columns"],
                                 f"node={card['node']} の BGP section に '機器' 列がある")

    def test_static_section_columns_no_device_column(self):
        """機器カードの static section には '機器' 列がない（orphan 以外）"""
        for card in self.tables:
            if card["node"] is None:
                continue
            secs = card["sections"]
            st_sec = next((s for s in secs if s["category"] == "static"), None)
            if st_sec:
                self.assertNotIn("機器", st_sec["columns"],
                                 f"node={card['node']} の static section に '機器' 列がある")


class TestBuildRenderDataFlowIndex(unittest.TestCase):
    """テスト4: BGP/static 行の flow が元配列インデックスと一致すること"""

    def setUp(self):
        self.topo = make_topo()
        self.data = build_render_data(self.topo)
        self.tables = self.data["tables"]
        self.card_by_node = {c["node"]: c for c in self.tables}

    def test_dev1_bgp_flow_uses_global_index_0(self):
        """dev1 の BGP は bgp[0] → flow='bgp0'"""
        secs = self.card_by_node["dev1"]["sections"]
        bgp_sec = next(s for s in secs if s["category"] == "BGP")
        flows = [r["flow"] for r in bgp_sec["rows"]]
        self.assertIn("bgp0", flows, f"dev1 BGP の flow が bgp0 でない: {flows}")

    def test_dev2_bgp_flow_uses_global_index_1(self):
        """dev2 の BGP は bgp[1] → flow='bgp1'（元配列インデックス 1 を維持）"""
        secs = self.card_by_node["dev2"]["sections"]
        bgp_sec = next(s for s in secs if s["category"] == "BGP")
        flows = [r["flow"] for r in bgp_sec["rows"]]
        self.assertIn("bgp1", flows, f"dev2 BGP の flow が bgp1 でない: {flows}")

    def test_dev1_static_flow_uses_global_index_0(self):
        """dev1 の static は statics[0] → flow='st0'"""
        secs = self.card_by_node["dev1"]["sections"]
        st_sec = next(s for s in secs if s["category"] == "static")
        flows = [r["flow"] for r in st_sec["rows"]]
        self.assertIn("st0", flows, f"dev1 static の flow が st0 でない: {flows}")

    def test_dev2_static_flow_uses_global_index_1(self):
        """dev2 の static は statics[1] → flow='st1'"""
        secs = self.card_by_node["dev2"]["sections"]
        st_sec = next(s for s in secs if s["category"] == "static")
        flows = [r["flow"] for r in st_sec["rows"]]
        self.assertIn("st1", flows, f"dev2 static の flow が st1 でない: {flows}")


class TestBuildRenderDataStatusPropagation(unittest.TestCase):
    """テスト5: status:'added' が行・カードに伝播すること"""

    def setUp(self):
        self.topo = make_topo()
        self.data = build_render_data(self.topo)
        self.tables = self.data["tables"]
        self.card_by_node = {c["node"]: c for c in self.tables}

    def test_dev2_card_status_is_added(self):
        """dev2 カード自体の status が 'added'"""
        self.assertEqual(self.card_by_node["dev2"]["status"], "added")

    def test_dev2_if_row_status_is_added(self):
        """dev2 の GE0/0 IF 行の status が 'added'"""
        secs = self.card_by_node["dev2"]["sections"]
        if_sec = next(s for s in secs if s["category"] == "IF")
        ge00_row = next((r for r in if_sec["rows"] if r["cells"][0] == "GE0/0"), None)
        self.assertIsNotNone(ge00_row)
        self.assertEqual(ge00_row["status"], "added")

    def test_dev2_bgp_row_status_is_added(self):
        """dev2 の BGP 行（bgp1）の status が 'added'"""
        secs = self.card_by_node["dev2"]["sections"]
        bgp_sec = next(s for s in secs if s["category"] == "BGP")
        row = bgp_sec["rows"][0]
        self.assertEqual(row["status"], "added")

    def test_dev2_static_row_status_is_added(self):
        """dev2 の static 行（st1）の status が 'added'"""
        secs = self.card_by_node["dev2"]["sections"]
        st_sec = next(s for s in secs if s["category"] == "static")
        row = st_sec["rows"][0]
        self.assertEqual(row["status"], "added")


class TestBuildRenderDataOrphanCard(unittest.TestCase):
    """テスト6: device 未割当 BGP/static が orphan カードに集約されること"""

    def setUp(self):
        self.topo = make_topo_with_orphan()
        self.data = build_render_data(self.topo)
        self.tables = self.data["tables"]

    def test_orphan_card_exists(self):
        """orphan カード（title='その他（機器未割当）'）が存在する"""
        titles = [c["title"] for c in self.tables]
        self.assertIn("その他（機器未割当）", titles)

    def test_tables_count_is_devices_plus_orphan(self):
        """table 数 = devices(2) + orphan(1) = 3"""
        self.assertEqual(len(self.tables), 3)

    def test_orphan_card_node_is_none(self):
        """orphan カードの node は None"""
        orphan = next(c for c in self.tables if c["title"] == "その他（機器未割当）")
        self.assertIsNone(orphan["node"])

    def test_orphan_bgp_section_has_device_column(self):
        """orphan の BGP section には '機器' 列がある"""
        orphan = next(c for c in self.tables if c["title"] == "その他（機器未割当）")
        secs = orphan["sections"]
        bgp_sec = next((s for s in secs if s["category"] == "BGP"), None)
        self.assertIsNotNone(bgp_sec, "orphan に BGP section がない")
        self.assertIn("機器", bgp_sec["columns"])

    def test_orphan_static_section_has_device_column(self):
        """orphan の static section には '機器' 列がある"""
        orphan = next(c for c in self.tables if c["title"] == "その他（機器未割当）")
        secs = orphan["sections"]
        st_sec = next((s for s in secs if s["category"] == "static"), None)
        self.assertIsNotNone(st_sec, "orphan に static section がない")
        self.assertIn("機器", st_sec["columns"])

    def test_orphan_bgp_cells_include_device(self):
        """orphan の BGP 行の cells 先頭に device が入っている"""
        orphan = next(c for c in self.tables if c["title"] == "その他（機器未割当）")
        bgp_sec = next(s for s in orphan["sections"] if s["category"] == "BGP")
        row = bgp_sec["rows"][0]
        self.assertEqual(row["cells"][0], "unknown-dev")

    def test_orphan_static_cells_include_device(self):
        """orphan の static 行の cells 先頭に device が入っている"""
        orphan = next(c for c in self.tables if c["title"] == "その他（機器未割当）")
        st_sec = next(s for s in orphan["sections"] if s["category"] == "static")
        row = st_sec["rows"][0]
        self.assertEqual(row["cells"][0], "unknown-dev")

    def test_orphan_bgp_flow_is_delinked(self):
        """orphan の BGP は描画可能な端点を持たずフローが除外されるため、表行の flow は連動解除(None)。

        bgp%d のインデックス採番自体は維持しているが、除外済みフローを指したまま残すと
        クリックしても無反応になる。そのため _linked_flow が None に落とす（=クリック不可UI）。
        """
        orphan = next(c for c in self.tables if c["title"] == "その他（機器未割当）")
        bgp_sec = next(s for s in orphan["sections"] if s["category"] == "BGP")
        flow_ids = {fl["id"] for fl in self.data["flows"]}
        for r in bgp_sec["rows"]:
            self.assertIsNone(r["flow"],
                              f"orphan BGP が除外済みフローを参照している: {r['flow']}（valid={flow_ids}）")

    def test_device_cards_not_contain_orphan_bgp(self):
        """dev1/dev2 カードに orphan の BGP が混ざっていない"""
        for card in self.tables:
            if card["node"] not in ("dev1", "dev2"):
                continue
            secs = card["sections"]
            bgp_sec = next((s for s in secs if s["category"] == "BGP"), None)
            if bgp_sec:
                flows = [r["flow"] for r in bgp_sec["rows"]]
                self.assertNotIn("bgp2", flows,
                                 f"{card['node']} カードに orphan の bgp2 が混ざっている")


class TestBuildRenderDataEmptyDevices(unittest.TestCase):
    """テスト7: devices=[] でも例外なく orphan カードに集約されること"""

    def setUp(self):
        self.topo = {
            "title": "空デバイス",
            "devices": [],
            "interfaces": [],
            "phys_links": [],
            "bgp": [
                {"device": "x", "local_ip": "1.1.1.1", "neighbor_ip": "2.2.2.2",
                 "local_as": 1, "peer_as": 2, "status": "existing"},
            ],
            "static_routes": [
                {"device": "y", "prefix": "0.0.0.0/0", "next_hop": "9.9.9.9", "status": "existing"},
            ],
            "facilities": [],
        }

    def test_no_exception_with_empty_devices(self):
        """devices=[] でも build_render_data() が例外を出さない"""
        try:
            data = build_render_data(self.topo)
        except Exception as e:
            self.fail(f"devices=[] で例外が発生した: {e}")

    def test_all_bgp_static_go_to_orphan_when_no_devices(self):
        """devices=[] のとき全 BGP/static が orphan カードに入る"""
        data = build_render_data(self.topo)
        tables = data["tables"]
        self.assertGreaterEqual(len(tables), 1)
        orphan = next((c for c in tables if c["title"] == "その他（機器未割当）"), None)
        self.assertIsNotNone(orphan, f"orphan カードがない: {[c['title'] for c in tables]}")
        bgp_sec = next((s for s in orphan["sections"] if s["category"] == "BGP"), None)
        st_sec = next((s for s in orphan["sections"] if s["category"] == "static"), None)
        self.assertIsNotNone(bgp_sec)
        self.assertIsNotNone(st_sec)
        self.assertEqual(len(bgp_sec["rows"]), 1)
        self.assertEqual(len(st_sec["rows"]), 1)


class TestBuildRenderDataRobustness(unittest.TestCase):
    """レビュー指摘の堅牢性: id欠落device・除外フローの非連動"""

    def test_device_without_id_does_not_capture_none_device_bgp(self):
        """id を持たない不正 device に、device欠落のBGPが誤って紐づかず orphan へ行く"""
        topo = {
            "devices": [{"hostname": "no-id-dev"}],  # id なし → did=None
            "interfaces": [],
            "bgp": [{"local_ip": "10.0.0.1", "neighbor_ip": "10.0.0.2",
                     "local_as": 65001, "peer_as": 65002, "status": "existing"}],  # device 欠落 → None
            "static_routes": [],
        }
        data = build_render_data(topo)
        tables = data["tables"]
        # id欠落カードの BGP section は無い（None 同士の誤マッチをしない）
        noid = tables[0]
        self.assertFalse(any(s["category"] == "BGP" for s in noid["sections"]),
                         "id欠落deviceがdevice欠落BGPを誤って取り込んでいる")
        # device欠落BGPは orphan カードに入る
        orphan = next((c for c in tables if c["title"] == "その他（機器未割当）"), None)
        self.assertIsNotNone(orphan, "device欠落BGPがorphanに入っていない")
        bgp_sec = next(s for s in orphan["sections"] if s["category"] == "BGP")
        self.assertEqual(len(bgp_sec["rows"]), 1)

    def test_orphan_flow_delinked_when_flow_filtered_out(self):
        """端点ノード不在で除外された orphan static の flow は連動解除(None)される"""
        topo = {
            "devices": [{"id": "dev1", "hostname": "A"}],
            "interfaces": [{"id": "dev1-if1", "device": "dev1", "name": "GE0", "ip": "10.0.0.1/30"}],
            "bgp": [],
            # device が存在しない → flow の src ノードが無く flow は除外される
            "static_routes": [{"device": "ghost", "prefix": "172.16.0.0/16", "next_hop": "9.9.9.9"}],
        }
        data = build_render_data(topo)
        flow_ids = {fl["id"] for fl in data["flows"]}
        orphan = next(c for c in data["tables"] if c["title"] == "その他（機器未割当）")
        st_sec = next(s for s in orphan["sections"] if s["category"] == "static")
        row = st_sec["rows"][0]
        # 除外フローを参照していない（クリック無反応を防ぐ）
        self.assertIsNone(row["flow"], "除外済みフローが表行に残っている（無反応クリックの原因）")
        self.assertNotIn("st0", flow_ids)  # 前提: flow は除外されている


if __name__ == "__main__":
    unittest.main(verbosity=2)
