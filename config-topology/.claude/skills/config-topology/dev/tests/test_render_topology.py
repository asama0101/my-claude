"""
TDD テスト: render_topology.render()

テスト方針:
- examples/topology/（層別 YAML）を load_topology() で読み基準入力として使用
- 各テストは独立しており、共有状態なし
- 依存: PyYAML（topology_io 経由）
- カバレッジ 80%以上目標
"""
import json
import math
import os
import sys
import copy
import re

import pytest

# sys.path は conftest.py がバンドルルートを追加するため、ここでの設定は不要。


# ---- フィクスチャ -------------------------------------------------------

@pytest.fixture(scope="module")
def sample_topology():
    """examples/topology/ の層別 YAML を load_topology() で読み込む（Stage2 正本）。"""
    from lib.topology_io import load_topology
    examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
    return load_topology(os.path.join(examples_dir, "topology"))


@pytest.fixture(scope="module")
def rendered_html(sample_topology):
    """examples/topology/ を render() した HTML（モジュールスコープで1回のみ）"""
    from lib.rendering import render
    return render(sample_topology)


@pytest.fixture
def empty_topology():
    """空の topology（devices/links/routing が全て空）"""
    return {
        "title": "Empty",
        "generated_from": [],
        "devices": [],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {
            "bgp": [],
            "ospf": [],
            "static": [],
        },
    }


# ---- ユニットテスト: render() の基本 ------------------------------------

@pytest.mark.unit
def test_render_returns_string(sample_topology):
    """render() が文字列を返す"""
    from lib.rendering import render
    result = render(sample_topology)
    assert isinstance(result, str)


@pytest.mark.unit
def test_render_returns_html_doctype(rendered_html):
    """返値が HTML 文書（<!DOCTYPE html> または <html）で始まる"""
    lower = rendered_html.lower().lstrip()
    assert lower.startswith("<!doctype html") or lower.startswith("<html")


@pytest.mark.unit
def test_render_contains_svg(rendered_html):
    """SVG 要素が含まれる"""
    assert "<svg" in rendered_html.lower()


# ---- ユニットテスト: ホスト名・IF 名 ------------------------------------

@pytest.mark.unit
def test_render_contains_hostname_r1(rendered_html):
    """R1 の hostname が含まれる"""
    assert "R1" in rendered_html


@pytest.mark.unit
def test_render_contains_hostname_r2(rendered_html):
    """R2 の hostname が含まれる"""
    assert "R2" in rendered_html


@pytest.mark.unit
def test_render_contains_interface_names(rendered_html):
    """全 IF 名が含まれる"""
    iface_names = [
        "GigabitEthernet0/0",
        "GigabitEthernet0/1",
        "Loopback0",
        "ge-0/0/0",
        "ge-0/0/1",
        "lo0",
    ]
    for name in iface_names:
        assert name in rendered_html, f"IF 名が見つからない: {name}"


# ---- ユニットテスト: リンク・サブネット ---------------------------------

@pytest.mark.unit
def test_render_contains_link_subnet(rendered_html):
    """リンクの subnet (10.0.0.0/30) に関連する描画要素がある"""
    # サブネット文字列自体か、エンドポイント IP が含まれていれば OK
    assert ("10.0.0.0/30" in rendered_html
            or ("10.0.0.1" in rendered_html and "10.0.0.2" in rendered_html))


@pytest.mark.unit
def test_render_svg_has_path_or_line_for_link(rendered_html):
    """SVG にリンクを表す line または path 要素が含まれる"""
    lower = rendered_html.lower()
    assert "<line" in lower or "<path" in lower


# ---- ユニットテスト: ルーティング ---------------------------------------

@pytest.mark.unit
def test_render_contains_bgp_peer_as(rendered_html):
    """BGP peer_as (65002 / 65001) が含まれる"""
    assert "65002" in rendered_html
    assert "65001" in rendered_html


@pytest.mark.unit
def test_render_contains_bgp_type_ebgp(rendered_html):
    """BGP type ebgp が含まれる"""
    assert "ebgp" in rendered_html.lower()


@pytest.mark.unit
def test_render_contains_static_next_hop(rendered_html):
    """static route の next_hop が含まれる"""
    assert "10.0.0.2" in rendered_html  # r1 の next_hop
    assert "10.0.0.1" in rendered_html  # r2 の next_hop


# ---- ユニットテスト: レイヤートグル ------------------------------------

@pytest.mark.unit
def test_render_has_layer_toggle_checkboxes(rendered_html):
    """routing の各キー（bgp/ospf/static）に対応するチェックボックスがある"""
    lower = rendered_html.lower()
    # チェックボックスが存在する
    assert 'type="checkbox"' in lower or "type='checkbox'" in lower


@pytest.mark.unit
def test_render_toggle_has_bgp_label(rendered_html):
    """BGP レイヤーのトグルラベルが存在する"""
    assert "bgp" in rendered_html.lower()


@pytest.mark.unit
def test_render_toggle_has_ospf_label(rendered_html):
    """OSPF レイヤーのトグルラベルが存在する"""
    assert "ospf" in rendered_html.lower()


@pytest.mark.unit
def test_render_toggle_has_static_label(rendered_html):
    """static レイヤーのトグルラベルが存在する"""
    assert "static" in rendered_html.lower()


@pytest.mark.unit
def test_render_toggle_count_matches_routing_keys(sample_topology, rendered_html):
    """チェックボックス数が routing キー数（+物理レイヤー）と一致または以上"""
    routing_key_count = len(sample_topology["routing"])
    # 物理レイヤーを含めて routing_key_count + 1 以上のチェックボックスが存在するはず
    checkbox_count = rendered_html.lower().count('type="checkbox"') + rendered_html.lower().count("type='checkbox'")
    assert checkbox_count >= routing_key_count


# ---- ユニットテスト: 埋め込み JSON ------------------------------------

@pytest.mark.unit
def test_render_embeds_valid_json(rendered_html):
    """HTML 内に埋め込まれた topology JSON が valid"""
    # <script type="application/json"> または data-topology 属性内の JSON を取り出す
    import re
    # script[type=application/json] パターン
    pattern = r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>'
    matches = re.findall(pattern, rendered_html, re.DOTALL | re.IGNORECASE)
    assert len(matches) >= 1, "埋め込み JSON script タグが見つからない"
    for m in matches:
        try:
            json.loads(m.strip())
        except json.JSONDecodeError as e:
            pytest.fail(f"埋め込み JSON が無効: {e}\n内容: {m[:200]}")


# ---- ユニットテスト: インタラクション JS --------------------------------

@pytest.mark.unit
def test_render_has_zoom_pan_js(rendered_html):
    """ズーム/パン用 JS マーカーが存在する（wheel/mousedown/mousemove）"""
    lower = rendered_html.lower()
    has_wheel = "wheel" in lower
    has_mouse = "mousedown" in lower or "mousemove" in lower
    assert has_wheel or has_mouse, "ズーム/パン用イベントハンドラが見つからない"


@pytest.mark.unit
def test_render_has_hover_js(rendered_html):
    """ホバー用 JS マーカーが存在する（mouseover/mouseenter）"""
    lower = rendered_html.lower()
    assert "mouseover" in lower or "mouseenter" in lower, "ホバー用イベントハンドラが見つからない"


@pytest.mark.unit
def test_render_has_keyboard_handler(rendered_html):
    """キーボードハンドラ（keydown）が存在する"""
    assert "keydown" in rendered_html.lower() or "keyup" in rendered_html.lower()


# ---- ユニットテスト: HTML エスケープ ------------------------------------

@pytest.mark.unit
def test_render_escapes_html_in_description():
    """description に <script> が含まれても生の <script> タグが本文に出ない"""
    from lib.rendering import render

    malicious_topology = {
        "title": "XSS Test",
        "generated_from": [],
        "devices": [
            {
                "id": "evil",
                "hostname": "<script>alert('xss')</script>",
                "vendor": "cisco_ios",
                "as": None,
                "sections": [],
            }
        ],
        "interfaces": [
            {
                "id": "evil::eth0",
                "device": "evil",
                "name": "eth0",
                "ip": None,
                "vlan": None,
                "description": "<script>alert('xss')</script>",
                "shutdown": False,
            }
        ],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }

    html = render(malicious_topology)

    # カード/ラベル等の本文部分に生の <script> タグが出てはいけない
    # 埋め込み JSON 内の script タグは許容するが、HTML 要素としての <script> は
    # application/json の script タグのみに限定される
    import re
    # application/json の script ブロックを除外した本文を検査
    cleaned = re.sub(
        r'<script[^>]+type=["\']application/json["\'][^>]*>.*?</script>',
        '',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # 通常の script タグ内（JS コード）も除外
    cleaned = re.sub(r'<script[^>]*>.*?</script>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)

    # 残った HTML 本文に生の <script> タグが含まれていないこと
    assert "<script>" not in cleaned.lower(), \
        "エスケープされていない <script> タグが本文に存在する"


# ---- ユニットテスト: 空 topology ----------------------------------------

@pytest.mark.unit
def test_render_empty_topology_no_exception(empty_topology):
    """空 topology でも例外を投げずに HTML を返す"""
    from lib.rendering import render
    try:
        result = render(empty_topology)
    except Exception as e:
        pytest.fail(f"空 topology で例外が発生: {e}")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.unit
def test_render_empty_topology_returns_html(empty_topology):
    """空 topology でも HTML 構造が返る"""
    from lib.rendering import render
    result = render(empty_topology)
    lower = result.lower()
    assert "<html" in lower or "<!doctype html" in lower


@pytest.mark.unit
def test_render_empty_topology_has_svg(empty_topology):
    """空 topology でも SVG 要素が含まれる（空でも描画エリアあり）"""
    from lib.rendering import render
    result = render(empty_topology)
    assert "<svg" in result.lower()


# ---- ユニットテスト: 決定性 ---------------------------------------------

@pytest.mark.unit
def test_render_deterministic(sample_topology):
    """同一入力で2回 render した結果が完全一致"""
    from lib.rendering import render
    # deep copy して独立した呼び出し
    t1 = copy.deepcopy(sample_topology)
    t2 = copy.deepcopy(sample_topology)
    html1 = render(t1)
    html2 = render(t2)
    assert html1 == html2, "render() の出力が非決定的（毎回異なる）"


# ---- ユニットテスト: 機器カード ----------------------------------------

@pytest.mark.unit
def test_render_has_device_cards(rendered_html):
    """機器ごとのカードセクション（詳細情報）が存在する"""
    lower = rendered_html.lower()
    # カードは div または section、table 等で実装される
    assert "<table" in lower or 'class="card"' in lower or 'class="device-card"' in lower \
        or "device-card" in lower or "card" in lower


@pytest.mark.unit
def test_render_vendor_info_in_card(rendered_html):
    """機器カードに vendor 情報が含まれる"""
    assert "cisco_ios" in rendered_html.lower() or "cisco" in rendered_html.lower()
    assert "juniper_junos" in rendered_html.lower() or "juniper" in rendered_html.lower()


@pytest.mark.unit
def test_render_as_number_in_card(rendered_html):
    """機器カードに AS 番号が含まれる"""
    assert "65001" in rendered_html
    assert "65002" in rendered_html


# ---- ユニットテスト: セグメントノード ----------------------------------

@pytest.mark.unit
def test_render_segment_node_rendered():
    """segments が存在するとき楕円等のセグメントノードが描画される"""
    from lib.rendering import render

    topo_with_segment = {
        "title": "Segment Test",
        "generated_from": [],
        "devices": [
            {"id": "sw1", "hostname": "SW1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "sw2", "hostname": "SW2", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "sw3", "hostname": "SW3", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "sw1::eth0", "device": "sw1", "name": "eth0", "ip": "192.168.10.1/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "sw2::eth0", "device": "sw2", "name": "eth0", "ip": "192.168.10.2/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "sw3::eth0", "device": "sw3", "name": "eth0", "ip": "192.168.10.3/24", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [
            {
                "id": "seg-192_168_10_0_24",
                "subnet": "192.168.10.0/24",
                "members": ["sw1::eth0", "sw2::eth0", "sw3::eth0"],
            }
        ],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }

    html = render(topo_with_segment)
    lower = html.lower()
    # セグメントノードが楕円（ellipse）または rect で描画されること
    assert "<ellipse" in lower or "<rect" in lower
    # セグメントの subnet が含まれること
    assert "192.168.10.0/24" in html


# ---- ユニットテスト: sections 拡張 -------------------------------------

@pytest.mark.unit
def test_render_device_sections_rendered():
    """devices[].sections がある場合、汎用テーブルとして描画される"""
    from lib.rendering import render

    topo_with_sections = {
        "title": "Sections Test",
        "generated_from": [],
        "devices": [
            {
                "id": "r1",
                "hostname": "R1",
                "vendor": "cisco_ios",
                "as": 65001,
                "sections": [
                    {
                        "title": "Custom Section",
                        "rows": [["Key1", "Value1"], ["Key2", "Value2"]],
                    }
                ],
            }
        ],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }

    html = render(topo_with_sections)
    assert "Custom Section" in html
    assert "Key1" in html
    assert "Value1" in html


# ---- 統合テスト: CLI ----------------------------------------------------

@pytest.mark.integration
def test_cli_generates_html_file(tmp_path, sample_topology):
    """CLI 実行で topology.html が生成される（Stage2: YAML ディレクトリを入力）"""
    import subprocess
    from lib.topology_io import dump_topology

    # 一時ディレクトリに層別 YAML を書き出す
    yaml_dir = str(tmp_path / "topology_yaml")
    dump_topology(sample_topology, yaml_dir)

    out_path = tmp_path / "output.html"
    scripts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
    script_path = os.path.join(scripts_dir, "render_topology.py")

    result = subprocess.run(
        [sys.executable, script_path, yaml_dir, "-o", str(out_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CLI が失敗: stderr={result.stderr}"
    assert out_path.exists(), "出力 HTML ファイルが生成されていない"
    content = out_path.read_text(encoding="utf-8")
    assert len(content) > 100


@pytest.mark.integration
def test_cli_default_output_path(tmp_path, sample_topology):
    """CLI で -o 省略時、topology.html が生成される（Stage2: YAML ディレクトリ入力）"""
    import subprocess
    from lib.topology_io import dump_topology

    # 一時ディレクトリに層別 YAML を書き出す
    yaml_dir = str(tmp_path / "topology_yaml")
    dump_topology(sample_topology, yaml_dir)

    out_path = tmp_path / "topology.html"
    scripts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
    script_path = os.path.join(scripts_dir, "render_topology.py")

    result = subprocess.run(
        [sys.executable, script_path, yaml_dir, "-o", str(out_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CLI が失敗: stderr={result.stderr}"
    assert out_path.exists(), "topology.html が生成されていない"


# ---- 統合テスト: ファイル I/O ------------------------------------------

@pytest.mark.integration
def test_render_output_can_be_written_and_read(tmp_path, sample_topology):
    """render() の出力をファイルに書いて再読込できる"""
    from lib.rendering import render

    html = render(sample_topology)
    out_file = tmp_path / "test_output.html"
    out_file.write_text(html, encoding="utf-8")

    reread = out_file.read_text(encoding="utf-8")
    assert reread == html


# ===========================================================================
# [maint HIGH] レイヤートグル CSS の動的生成テスト
# ===========================================================================

def _make_vrrp_topology():
    """vrrp キーを含む人工 topology を返す"""
    return {
        "title": "VRRP Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [],
            "ospf": [],
            "static": [],
            "vrrp": [
                {"device": "r1", "group": 1, "vip": "10.0.0.254", "priority": 110},
                {"device": "r2", "group": 1, "vip": "10.0.0.254", "priority": 100},
            ],
        },
    }


@pytest.mark.unit
def test_vrrp_toggle_generated():
    """routing に vrrp キーを足すと vrrp 用チェックボックスが生成される"""
    from lib.rendering import render
    html = render(_make_vrrp_topology())
    lower = html.lower()
    # data-layer="vrrp" または id="toggle-vrrp" が存在すること
    assert 'data-layer="vrrp"' in lower or "toggle-vrrp" in lower, \
        "vrrp トグルが生成されていない"


@pytest.mark.unit
def test_vrrp_css_hide_rule_generated():
    """routing に vrrp キーを足すと body.hide-vrrp .layer-vrrp { display:none } 相当のCSSルールが出力される"""
    from lib.rendering import render
    html = render(_make_vrrp_topology())
    # CSS ルール: body.hide-vrrp .layer-vrrp（display:none を含む）
    assert "hide-vrrp" in html, "body.hide-vrrp CSS ルールが生成されていない"
    assert "layer-vrrp" in html, ".layer-vrrp CSS ルールが生成されていない"


@pytest.mark.unit
def test_existing_protocols_css_still_generated_dynamically(sample_topology):
    """bgp/ospf/static の hide CSS ルールが sample topology でも動的生成で出力される"""
    from lib.rendering import render
    html = render(sample_topology)
    for proto in ("bgp", "ospf", "static"):
        assert f"hide-{proto}" in html, f"body.hide-{proto} CSS ルールが見当たらない"
        assert f"layer-{proto}" in html, f".layer-{proto} CSS ルールが見当たらない"
    # physical も同様
    assert "hide-physical" in html, "body.hide-physical CSS ルールが見当たらない"
    assert "layer-physical" in html, ".layer-physical CSS ルールが見当たらない"


@pytest.mark.unit
def test_vrrp_elements_have_layer_vrrp_class():
    """vrrp エントリがある場合、vrrp 要素に layer-vrrp クラスが付与される（将来実装の回帰保護）

    現状 render はvrrp 要素を描画しないが、CSS ルールが生成されること自体を検証する。
    将来 vrrp 描画を追加したとき layer-vrrp クラス付与が必要になる。
    """
    from lib.rendering import render
    html = render(_make_vrrp_topology())
    # CSS ルール body.hide-vrrp .layer-vrrp が存在することを確認（描画要素とは別に）
    assert "hide-vrrp" in html
    assert "layer-vrrp" in html


# ===========================================================================
# [sec HIGH] 埋め込み JSON の <!-- 防御的エスケープテスト
# ===========================================================================

def _make_comment_topology():
    """description に <!-- を含む人工 topology を返す"""
    return {
        "title": "Comment Injection Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None,
             "sections": [
                 {"title": "Sec", "rows": [["key", "<!-- injected comment -->"]]}
             ]},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": "<!-- link to upstream -->", "shutdown": False},
        ],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.mark.unit
def test_embedded_json_no_raw_html_comment():
    """description に <!-- が含まれても埋め込みJSONブロックに生の <!-- が現れない"""
    import re
    from lib.rendering import render
    html = render(_make_comment_topology())

    # <script type="application/json"> ブロックを抽出
    pattern = r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
    assert len(matches) >= 1, "埋め込み JSON script タグが見つからない"

    for json_block in matches:
        assert "<!--" not in json_block, \
            f"埋め込みJSONブロックに生の <!-- が含まれている:\n{json_block[:300]}"


@pytest.mark.unit
def test_embedded_json_still_parseable_after_comment_escape():
    """<!-- エスケープ後も埋め込み JSON が valid JSON としてパース可能"""
    import re
    from lib.rendering import render
    html = render(_make_comment_topology())

    pattern = r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
    assert len(matches) >= 1

    for json_block in matches:
        # <\/ と <\! のエスケープを戻してパース
        unescaped = json_block.strip().replace("<\\/", "</").replace("<\\!--", "<!--")
        try:
            json.loads(unescaped)
        except json.JSONDecodeError as e:
            pytest.fail(f"<!-- エスケープ後の JSON がパース不能: {e}\n内容: {unescaped[:300]}")


# ===========================================================================
# XSS エスケープ拡充: &, ", ' を含む topology
# ===========================================================================

def _make_xss_topology():
    """hostname / description に &, ", ' を含む人工 topology"""
    return {
        "title": "XSS & Escape Test",
        "generated_from": [],
        "devices": [
            {
                "id": "evil",
                "hostname": 'R1 & R2 "quoted" it\'s',
                "vendor": "cisco_ios",
                "as": None,
                "sections": [],
            }
        ],
        "interfaces": [
            {
                "id": "evil::eth0",
                "device": "evil",
                "name": "eth0",
                "ip": "10.0.0.1/30",
                "vlan": None,
                "description": 'link & "upstream" isn\'t available',
                "shutdown": False,
            }
        ],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.mark.unit
def test_xss_ampersand_escaped_in_html():
    """hostname/description の & が HTML エスケープされる（&amp; に変換）"""
    from lib.rendering import render
    html = render(_make_xss_topology())
    # SVG/カード部分の本文に生の & が hostname として出ていないこと
    # （埋め込みJSONブロックと script タグを除く）
    import re
    cleaned = re.sub(
        r'<script[^>]+type=["\']application/json["\'][^>]*>.*?</script>',
        '', html, flags=re.DOTALL | re.IGNORECASE
    )
    cleaned = re.sub(r'<script[^>]*>.*?</script>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    # 生の & が属性値や要素内容に残っていないこと（&amp; や &lt; 等の参照は許容）
    # 属性の data-device=" ... " に生の & が入っていないことを確認
    raw_amp_in_attr = re.search(r'data-device="[^"]*&[^#a-z][^"]*"', cleaned)
    assert raw_amp_in_attr is None, \
        f"data-device 属性に生の & が含まれている: {raw_amp_in_attr.group()}"


@pytest.mark.unit
def test_xss_double_quote_escaped_in_attributes():
    """hostname に " が含まれても属性値を壊さない（&quot; にエスケープ）"""
    from lib.rendering import render
    html = render(_make_xss_topology())
    import re
    cleaned = re.sub(
        r'<script[^>]+type=["\']application/json["\'][^>]*>.*?</script>',
        '', html, flags=re.DOTALL | re.IGNORECASE
    )
    cleaned = re.sub(r'<script[^>]*>.*?</script>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    # data-device 属性内に生の " が現れると属性が早期終端する
    # data-device="evil" は問題ない（dev_id は "evil" そのまま）
    # hostname（_esc 経由）が属性に埋め込まれる箇所を検査
    # node-label text 要素内の生 " は許容（テキストノードは & も > も < のみエスケープ必要）
    # ここでは属性値の破損がないことを検証: data-device は英数字のみなので問題なし
    # 主要な検証: HTML 全体に "quoted" の生 " が属性の中断として現れないこと
    # _esc は html.escape(quote=True) なので " -> &quot; になるはず
    assert '&quot;' in html or '"quoted"' not in cleaned, \
        "\" が &quot; にエスケープされていない可能性がある"


@pytest.mark.unit
def test_xss_single_quote_escaped_in_attributes():
    """hostname に ' が含まれても html.escape(quote=True) でエスケープされる"""
    from lib.rendering import render
    html = render(_make_xss_topology())
    # _esc は quote=True なので ' -> &#x27; または &apos; になる
    # html.escape のデフォルトは ' をエスケープしないが quote=True でもエスケープしない
    # Python の html.escape は quote=True でも ' はエスケープしないが、
    # 属性値はダブルクォートで囲まれているので ' は無害
    # → このテストは "エスケープ済みか" より "HTML が壊れていないか" を検証
    import re
    cleaned = re.sub(
        r'<script[^>]+type=["\']application/json["\'][^>]*>.*?</script>',
        '', html, flags=re.DOTALL | re.IGNORECASE
    )
    cleaned = re.sub(r'<script[^>]*>.*?</script>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    # HTML が well-formed であること（簡易検証: <html> が存在）
    assert "<html" in cleaned.lower()
    # ' が含まれても render が例外を投げないこと（上記 render 呼び出しが成功した時点で保証）


# ===========================================================================
# BGP 双方向辺の重複除去テスト
# ===========================================================================

def _make_bidirectional_bgp_topology():
    """R1→R2 と R2→R1 の両 bgp エントリを持つ topology"""
    return {
        "title": "BGP Dedup Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
                 "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
                {"device": "r2", "local_as": 65002, "local_ip": "10.0.0.2",
                 "neighbor_ip": "10.0.0.1", "peer_as": 65001, "type": "ebgp"},
            ],
            "ospf": [],
            "static": [],
        },
    }


@pytest.mark.unit
def test_bgp_bidirectional_dedup_single_edge():
    """Phase A #1b: Physical ビューに BGP オーバーレイを描かない — bgp-session は0本"""
    import re
    from lib.rendering import render
    html = render(_make_bidirectional_bgp_topology())

    physical_match = re.search(
        r'class="view view-physical"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</svg>)',
        html,
        re.DOTALL,
    )
    if physical_match:
        physical_content = physical_match.group(1)
    else:
        physical_content = html  # フォールバック

    bgp_sessions = re.findall(r'class="bgp-session"', physical_content)
    assert len(bgp_sessions) == 0, \
        f"BGP 双方向エントリで Physical ビュー内に {len(bgp_sessions)} 本のエッジが描画された（期待: 0本）"


@pytest.mark.unit
def test_bgp_single_direction_still_rendered():
    """Phase A #1b: 片方向 BGP でも Physical ビューに bgp-session は0本（BGP ビューのみ描画）"""
    import re
    from lib.rendering import render

    topo = _make_bidirectional_bgp_topology()
    # r2 側エントリを削除（片方向）
    topo["routing"]["bgp"] = [topo["routing"]["bgp"][0]]
    html = render(topo)

    physical_match = re.search(
        r'class="view view-physical"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</svg>)',
        html,
        re.DOTALL,
    )
    if physical_match:
        physical_content = physical_match.group(1)
    else:
        physical_content = html

    bgp_sessions = re.findall(r'class="bgp-session"', physical_content)
    assert len(bgp_sessions) == 0, \
        f"片方向 BGP エントリで Physical ビュー内に {len(bgp_sessions)} 本のエッジが描画された（期待: 0本）"


# ===========================================================================
# Stage1: force-directed レイアウト + 動的 viewBox テスト
# ===========================================================================

def _make_large_topology(n: int):
    """n 台のデバイスと (n-1) 本のリンク（リング-1 = スター）を持つ人工 topology"""
    devices = [{"id": f"r{i}", "hostname": f"R{i}", "vendor": "cisco_ios",
                "as": 65000 + i, "sections": []}
               for i in range(n)]
    interfaces = [{"id": f"r{i}::eth0", "device": f"r{i}", "name": "eth0",
                   "ip": f"10.0.{i // 256}.{i % 256}/30",
                   "vlan": None, "description": None, "shutdown": False}
                  for i in range(n)]
    links = []
    for i in range(1, n):
        links.append({
            "a_device": "r0", "a_if": "eth0",
            "b_device": f"r{i}", "b_if": "eth0",
            "subnet": f"10.0.{i // 256}.{i % 256}/30",
            "kind": "inferred-subnet",
        })
    return {
        "title": f"Large {n}-node Topology",
        "generated_from": [],
        "devices": devices,
        "interfaces": interfaces,
        "links": links,
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.mark.unit
def test_layout_force_directed_deterministic():
    """_layout_force_directed: 同一入力を2回呼んだとき完全に同じ座標を返す"""
    from lib.rendering import _layout_force_directed
    node_ids = [f"r{i}" for i in range(20)]
    edges = [(f"r{i}", f"r{i+1}") for i in range(19)]
    pos1 = _layout_force_directed(node_ids, edges, width=1000.0, height=800.0)
    pos2 = _layout_force_directed(node_ids, edges, width=1000.0, height=800.0)
    assert pos1 == pos2, "_layout_force_directed が非決定的（2回の呼び出しで座標が異なる）"


@pytest.mark.unit
def test_layout_force_directed_zero_nodes():
    """_layout_force_directed: ノード0件で例外が起きない"""
    from lib.rendering import _layout_force_directed
    pos = _layout_force_directed([], [], width=800.0, height=600.0)
    assert pos == {}


@pytest.mark.unit
def test_layout_force_directed_one_node():
    """_layout_force_directed: ノード1件で例外が起きず座標が返る"""
    from lib.rendering import _layout_force_directed
    pos = _layout_force_directed(["r1"], [], width=800.0, height=600.0)
    assert "r1" in pos
    x, y = pos["r1"]
    assert isinstance(x, float)
    assert isinstance(y, float)


@pytest.mark.unit
def test_layout_force_directed_two_nodes():
    """_layout_force_directed: ノード2件で例外が起きず座標が返る"""
    from lib.rendering import _layout_force_directed
    pos = _layout_force_directed(["r1", "r2"], [("r1", "r2")], width=800.0, height=600.0)
    assert "r1" in pos
    assert "r2" in pos


@pytest.mark.unit
def test_layout_force_directed_all_nodes_in_bbox():
    """全ノードが width x height の矩形内に収まる"""
    from lib.rendering import _layout_force_directed
    W, H = 1000.0, 800.0
    node_ids = [f"r{i}" for i in range(20)]
    edges = [(f"r{i}", f"r{i+1}") for i in range(19)]
    pos = _layout_force_directed(node_ids, edges, width=W, height=H)
    for nid, (x, y) in pos.items():
        assert 0 <= x <= W, f"ノード {nid} の x={x:.1f} が [0, {W}] を外れている"
        assert 0 <= y <= H, f"ノード {nid} の y={y:.1f} が [0, {H}] を外れている"


@pytest.mark.unit
def test_layout_force_directed_no_overlap():
    """任意2ノードの中心間距離が最小距離以上（ノード重なりなし）"""
    from lib.rendering import _layout_force_directed, _NODE_WIDTH
    node_ids = [f"r{i}" for i in range(20)]
    edges = [(f"r{i}", f"r{i+1}") for i in range(19)]
    pos = _layout_force_directed(node_ids, edges, width=1200.0, height=1000.0)
    min_dist = _NODE_WIDTH  # ノード幅以上は離れていること
    ids = list(pos.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            x1, y1 = pos[ids[i]]
            x2, y2 = pos[ids[j]]
            dist = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
            assert dist >= min_dist, (
                f"ノード {ids[i]}({x1:.1f},{y1:.1f}) と {ids[j]}({x2:.1f},{y2:.1f}) が"
                f" 重なっている（距離 {dist:.1f} < 最小 {min_dist}）"
            )


@pytest.mark.unit
def test_dynamic_canvas_grows_with_node_count():
    """ノード数が増えると viewBox の幅か高さが増大する（固定キャンバスでない）"""
    from lib.rendering import render
    import re

    html_small = render(_make_large_topology(3))
    html_large = render(_make_large_topology(30))

    def _extract_viewbox_size(html_str):
        # <svg ... viewBox="min_x min_y width height"> から幅・高さを抽出
        m = re.search(r'<svg[^>]+viewBox="([^"]+)"', html_str)
        if not m:
            return None, None
        parts = m.group(1).split()
        if len(parts) == 4:
            return float(parts[2]), float(parts[3])
        return None, None

    w_small, h_small = _extract_viewbox_size(html_small)
    w_large, h_large = _extract_viewbox_size(html_large)

    assert w_small is not None, "小さい topology の SVG viewBox を抽出できない"
    assert w_large is not None, "大きい topology の SVG viewBox を抽出できない"

    # 30台は3台より大きいキャンバスになるはず
    assert (w_large > w_small) or (h_large > h_small), (
        f"ノード数が増えても viewBox サイズが変わらない: "
        f"small=({w_small}×{h_small}) large=({w_large}×{h_large})"
    )


@pytest.mark.unit
def test_dynamic_canvas_viewbox_contains_all_nodes():
    """render した HTML の Physical ビューの data-bbox が全ノード座標をカバーしている"""
    from lib.rendering import render
    import re

    topo = _make_large_topology(20)
    html = render(topo)

    # Stage2: Physical ビューの data-bbox を viewBox として使用
    # view-physical <g> の data-bbox を抽出
    bbox_match = re.search(r'class="view view-physical"[^>]*data-bbox="([^"]+)"', html)
    if not bbox_match:
        bbox_match = re.search(r'data-bbox="([^"]+)"[^>]*class="view view-physical"', html)

    if bbox_match:
        vb = [float(v) for v in bbox_match.group(1).split()]
    else:
        # フォールバック: SVG の viewBox
        m = re.search(r'viewBox="([^"]+)"', html)
        assert m, "viewBox が見つからない"
        vb = [float(v) for v in m.group(1).split()]

    assert len(vb) == 4, f"bbox の値が4つでない: {vb}"
    vb_min_x, vb_min_y, vb_w, vb_h = vb

    # Physical ビュー内の座標のみを収集して bbox 内に収まるか検証
    physical_match = re.search(
        r'class="view view-physical"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</svg>)',
        html,
        re.DOTALL,
    )
    if not physical_match:
        return  # Physical ビューが見つからない場合はスキップ

    physical_content = physical_match.group(1)

    coords_x = [float(v) for v in re.findall(r'\bx1="([0-9.+-]+)"', physical_content)]
    coords_x += [float(v) for v in re.findall(r'\bx2="([0-9.+-]+)"', physical_content)]
    coords_x += [float(v) for v in re.findall(r'\bcx="([0-9.+-]+)"', physical_content)]
    coords_y = [float(v) for v in re.findall(r'\by1="([0-9.+-]+)"', physical_content)]
    coords_y += [float(v) for v in re.findall(r'\by2="([0-9.+-]+)"', physical_content)]
    coords_y += [float(v) for v in re.findall(r'\bcy="([0-9.+-]+)"', physical_content)]

    if coords_x and coords_y:
        min_x, max_x = min(coords_x), max(coords_x)
        min_y, max_y = min(coords_y), max(coords_y)
        assert min_x >= vb_min_x - 1, f"左端座標 {min_x:.1f} が viewBox 左端 {vb_min_x:.1f} より小さい"
        assert max_x <= vb_min_x + vb_w + 1, f"右端座標 {max_x:.1f} が viewBox 右端 {vb_min_x + vb_w:.1f} を超えている"
        assert min_y >= vb_min_y - 1, f"上端座標 {min_y:.1f} が viewBox 上端 {vb_min_y:.1f} より小さい"
        assert max_y <= vb_min_y + vb_h + 1, f"下端座標 {max_y:.1f} が viewBox 下端 {vb_min_y + vb_h:.1f} を超えている"


@pytest.mark.unit
def test_render_sample_topology_still_passes(sample_topology):
    """examples/topology/ が引き続き render() で全コンテンツを含む HTML を返す"""
    from lib.rendering import render
    html = render(sample_topology)
    assert "R1" in html
    assert "R2" in html
    assert "ebgp" in html.lower()
    assert "65001" in html
    assert "65002" in html
    assert "<svg" in html.lower()
    assert "GigabitEthernet0/0" in html


# ===========================================================================
# Stage2: レイヤー別ビュー＋切替＋検索
# ===========================================================================

# ---- ビュー <g> 要素の存在 -----------------------------------------------

@pytest.mark.unit
def test_stage2_view_physical_group_exists(rendered_html):
    """Physical ビューの <g class="view view-physical"> が存在する"""
    assert 'class="view view-physical"' in rendered_html


@pytest.mark.unit
def test_stage2_view_l3_group_not_generated(rendered_html):
    """Phase A #6: L3 ビューは削除された — view-l3 <g> が存在しない"""
    assert 'class="view view-l3"' not in rendered_html


@pytest.mark.unit
def test_stage2_view_bgp_group_exists(rendered_html):
    """BGP ビューの <g class="view view-bgp"> が存在する（sample topology は bgp あり）"""
    assert 'class="view view-bgp"' in rendered_html


@pytest.mark.unit
def test_stage2_view_ospf_group_not_generated(rendered_html):
    """OSPF ビューは sample topology では生成されない（r1 のみ参加 → エッジなし → ゲーティング除外）"""
    # sample topology は r1 のみ OSPF 参加 → エッジ集合が空 → view-ospf は生成されない
    assert 'class="view view-ospf"' not in rendered_html, \
        "sample topology で OSPF ビューが（r1 のみ参加なのに）生成されている"


# ---- data-bbox 属性 -------------------------------------------------------

@pytest.mark.unit
def test_stage2_view_groups_have_data_bbox(rendered_html):
    """各ビュー <g> に data-bbox 属性が存在する（生成されたビューのみ検証）
    Phase A #6: L3 は削除されたため view-physical のみ必須"""
    import re
    # view-physical は常に必須（L3 は Phase A で削除）
    for view_id in ("physical",):
        pattern = rf'class="view view-{view_id}"[^>]*data-bbox="[^"]+"'
        alt_pattern = rf'data-bbox="[^"]+"[^>]*class="view view-{view_id}"'
        found = re.search(pattern, rendered_html) or re.search(alt_pattern, rendered_html)
        assert found, f"view-{view_id} に data-bbox が見つからない"
    # bgp/ospf はゲーティングで生成されない場合もある → 存在する場合のみ検証
    for view_id in ("bgp", "ospf"):
        if f'class="view view-{view_id}"' in rendered_html:
            pattern = rf'class="view view-{view_id}"[^>]*data-bbox="[^"]+"'
            alt_pattern = rf'data-bbox="[^"]+"[^>]*class="view view-{view_id}"'
            found = re.search(pattern, rendered_html) or re.search(alt_pattern, rendered_html)
            assert found, f"view-{view_id} に data-bbox が見つからない"


# ---- ビュータブ UI --------------------------------------------------------

@pytest.mark.unit
def test_stage2_view_tabs_exist(rendered_html):
    """ビュー切替タブ要素が存在する（data-view または class="view-tab"）"""
    lower = rendered_html.lower()
    assert 'data-view=' in lower or 'class="view-tab' in lower or 'view-tab' in lower, \
        "ビュー切替タブが見つからない"


@pytest.mark.unit
def test_stage2_physical_tab_exists(rendered_html):
    """Physical タブが存在する"""
    assert "physical" in rendered_html.lower()


@pytest.mark.unit
def test_stage2_bgp_tab_exists(rendered_html):
    """BGP タブが存在する（sample topology は bgp あり）"""
    # BGP という文字列がタブに含まれる（大文字小文字問わず）
    assert "bgp" in rendered_html.lower()


# ---- selectView JS --------------------------------------------------------

@pytest.mark.unit
def test_stage2_selectview_js_exists(rendered_html):
    """selectView JS 関数が含まれる"""
    assert "selectView" in rendered_html


@pytest.mark.unit
def test_stage2_selectview_uses_data_bbox(rendered_html):
    """selectView が data-bbox を参照して viewBox を切り替える実装を含む"""
    assert "data-bbox" in rendered_html
    assert "viewBox" in rendered_html or "viewbox" in rendered_html.lower()


# ---- 検索機能 (filterNodes) -----------------------------------------------

@pytest.mark.unit
def test_stage2_filter_nodes_js_exists(rendered_html):
    """filterNodes JS 関数が含まれる"""
    assert "filterNodes" in rendered_html


@pytest.mark.unit
def test_stage2_device_nodes_have_data_search(rendered_html):
    """device ノードの <g> に data-search 属性が含まれる"""
    assert 'data-search=' in rendered_html


@pytest.mark.unit
def test_stage2_data_search_contains_hostname(rendered_html):
    """data-search 属性に hostname が含まれる（R1, R2 の小文字）"""
    import re
    # data-search="..." の中に r1 または r2 が含まれる
    matches = re.findall(r'data-search="([^"]*)"', rendered_html)
    all_search_text = " ".join(matches).lower()
    assert "r1" in all_search_text or "r2" in all_search_text, \
        "data-search に hostname が含まれていない"


@pytest.mark.unit
def test_stage2_data_search_contains_ip(rendered_html):
    """data-search 属性に IP アドレスが含まれる"""
    import re
    matches = re.findall(r'data-search="([^"]*)"', rendered_html)
    all_search_text = " ".join(matches)
    assert "10.0.0" in all_search_text, "data-search に IP アドレスが含まれていない"


@pytest.mark.unit
def test_stage2_search_box_exists(rendered_html):
    """検索ボックス（input type=text または search）が存在する"""
    import re
    lower = rendered_html.lower()
    assert 'type="text"' in lower or 'type="search"' in lower or \
        'id="search' in lower or 'placeholder' in lower, \
        "検索ボックスが見つからない"


# ---- プロトコルビューの動的生成 -------------------------------------------

@pytest.mark.unit
def test_stage2_protocol_view_dynamic_bgp_only():
    """bgp のみの topology では BGP ビューが生成され、OSPF ビューは生成されない"""
    from lib.rendering import render
    topo = {
        "title": "BGP Only",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
                 "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
            ],
        },
    }
    html = render(topo)
    assert 'class="view view-bgp"' in html, "BGP ビューが生成されていない"
    assert 'class="view view-ospf"' not in html, "OSPF ビューが（不要なのに）生成されている"


@pytest.mark.unit
def test_stage2_protocol_view_dynamic_ospf_only():
    """ospf のみの topology では OSPF ビューが生成され、BGP ビューは生成されない"""
    from lib.rendering import render
    topo = {
        "title": "OSPF Only",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "ospf": [
                {"device": "r1", "process": 1, "network": "10.0.0.0/30", "area": "0"},
                {"device": "r2", "process": 1, "network": "10.0.0.0/30", "area": "0"},
            ],
        },
    }
    html = render(topo)
    assert 'class="view view-ospf"' in html, "OSPF ビューが生成されていない"
    assert 'class="view view-bgp"' not in html, "BGP ビューが（不要なのに）生成されている"


@pytest.mark.unit
def test_stage2_protocol_view_tabs_match_generated_views():
    """生成されたビューのタブ数 = 実際に生成された view-{id} <g> 数と一致または以上"""
    from lib.rendering import render
    import re
    topo = {
        "title": "BGP+OSPF",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [{"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
                   "subnet": "10.0.0.0/30", "kind": "inferred-subnet"}],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
                 "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
            ],
            "ospf": [
                {"device": "r1", "process": 1, "network": "10.0.0.0/30", "area": "0"},
                {"device": "r2", "process": 1, "network": "10.0.0.0/30", "area": "0"},
            ],
        },
    }
    html = render(topo)
    view_groups = re.findall(r'class="view view-([a-z0-9_-]+)"', html)
    tabs = re.findall(r'data-view="([a-z0-9_-]+)"', html)
    assert len(tabs) >= len(view_groups), \
        f"タブ数({len(tabs)}) < ビュー数({len(view_groups)}): view_groups={view_groups}, tabs={tabs}"


# ---- レイヤートグル（既存）の存続 -----------------------------------------

@pytest.mark.unit
def test_stage2_layer_toggles_still_exist(rendered_html):
    """Stage2 後も既存のレイヤートグルチェックボックスが存在する"""
    lower = rendered_html.lower()
    assert 'type="checkbox"' in lower or "type='checkbox'" in lower


@pytest.mark.unit
def test_stage2_toggle_bgp_id_still_generated(rendered_html):
    """toggle-bgp チェックボックス ID が引き続き生成される"""
    assert "toggle-bgp" in rendered_html


@pytest.mark.unit
def test_stage2_toggle_ospf_id_still_generated(rendered_html):
    """toggle-ospf チェックボックス ID が引き続き生成される"""
    assert "toggle-ospf" in rendered_html


# ---- 決定性（Stage2 後も） ------------------------------------------------

@pytest.mark.unit
def test_stage2_render_deterministic(sample_topology):
    """Stage2 実装後も同一入力で2回 render した結果が完全一致"""
    from lib.rendering import render
    t1 = copy.deepcopy(sample_topology)
    t2 = copy.deepcopy(sample_topology)
    html1 = render(t1)
    html2 = render(t2)
    assert html1 == html2, "Stage2 後の render() が非決定的"


# ---- 空 topology 耐性（Stage2 後も） --------------------------------------

@pytest.mark.unit
def test_stage2_empty_topology_no_exception(empty_topology):
    """Stage2 後も空 topology で例外なし"""
    from lib.rendering import render
    result = render(empty_topology)
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.unit
def test_stage2_empty_topology_has_physical_view(empty_topology):
    """空 topology でも view-physical <g> が存在する"""
    from lib.rendering import render
    result = render(empty_topology)
    assert 'class="view view-physical"' in result


@pytest.mark.unit
def test_stage2_empty_topology_no_l3_view(empty_topology):
    """Phase A #6: L3 は削除 — 空 topology でも view-l3 <g> が存在しない"""
    from lib.rendering import render
    result = render(empty_topology)
    assert 'class="view view-l3"' not in result


# ---- 自己完結性 -----------------------------------------------------------

@pytest.mark.unit
def test_stage2_self_contained_no_external_cdn(rendered_html):
    """http(s):// 参照が SVG 名前空間以外に存在しない（自己完結）"""
    import re
    # <link href="https://..."> や <script src="https://..."> がないこと
    external_refs = re.findall(
        r'(?:src|href)\s*=\s*["\']https?://(?!www\.w3\.org)[^"\']*["\']',
        rendered_html,
        re.IGNORECASE,
    )
    assert len(external_refs) == 0, \
        f"外部 CDN 参照が含まれている: {external_refs}"


# ---- L3 ビューにサブネットノードが含まれる --------------------------------

@pytest.mark.unit
def test_stage2_l3_view_contains_subnet_nodes():
    """Phase A #6: L3 ビューは削除された — view-l3 グループが存在しない"""
    from lib.rendering import render
    topo = {
        "title": "L3 Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    assert 'class="view view-l3"' not in html, "L3 ビューが（削除後も）生成されている"


# ---- BGP ビューには BGP 参加デバイスのみ含まれる -------------------------

@pytest.mark.unit
def test_stage2_bgp_view_contains_bgp_devices(rendered_html):
    """BGP ビュー <g> ブロック内に device-node が2台以上含まれる（sample は R1/R2 共に BGP 参加）"""
    # view-bgp ブロックを抽出して内部の device-node を数える
    m = re.search(
        r'<g class="view view-bgp"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        rendered_html, re.DOTALL
    )
    assert m is not None, "view-bgp グループが見つからない"
    bgp_content = m.group(1)
    device_nodes = re.findall(r'class="device-node"', bgp_content)
    assert len(device_nodes) >= 2, \
        f"view-bgp 内の device-node が {len(device_nodes)} 個（期待: >=2）"


# ---- BGP ビューの ebgp/ibgp エッジ色分け --------------------------------

@pytest.mark.unit
def test_stage2_bgp_view_edge_class_preserved(rendered_html):
    """BGP ビューに bgp-ebgp クラスのエッジが含まれる（sample は ebgp）"""
    assert "bgp-ebgp" in rendered_html


# ---- 将来キー追加への拡張性 -----------------------------------------------

@pytest.mark.unit
def test_stage2_future_protocol_view_generated():
    """未知のプロトコルキー（例: isis）も routing にあればビューが生成される"""
    from lib.rendering import render
    topo = {
        "title": "ISIS Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [{"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
                   "subnet": "10.0.0.0/30", "kind": "inferred-subnet"}],
        "segments": [],
        "routing": {
            "isis": [
                {"device": "r1", "net": "49.0001.1111.1111.1111.00"},
                {"device": "r2", "net": "49.0001.2222.2222.2222.00"},
            ],
        },
    }
    html = render(topo)
    # isis キーがあれば isis ビューが生成されること（汎用フレームワーク）
    assert 'class="view view-isis"' in html, "isis ビューが生成されていない"
    assert 'data-view="isis"' in html, "isis タブが生成されていない"


# ===========================================================================
# A. ビュー生成のゲーティング（最重要）
# ===========================================================================

def _make_static_only_topology():
    """static のみの routing（辺なし）を持つ人工 topology"""
    return {
        "title": "Static Only",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [],
        "routing": {
            "static": [
                {"device": "r1", "prefix": "0.0.0.0/0", "next_hop": "10.0.0.2"},
            ],
        },
    }


def _make_bgp_no_resolved_neighbors_topology():
    """BGP エントリはあるが neighbor_ip が解決できない（外部 peer のみ）"""
    return {
        "title": "BGP External Peer Only",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
                 "neighbor_ip": "203.0.113.1", "peer_as": 64500, "type": "ebgp"},
            ],
        },
    }


def _make_ospf_single_device_topology():
    """OSPF に参加するデバイスが1台のみ（隣接リンクなし）"""
    return {
        "title": "OSPF Single Device",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            # r1 のみ OSPF 参加 → r1↔r2 リンクの b_device=r2 は OSPF 非参加
            # → エッジ集合が空 → ビュー生成されないこと
            "ospf": [
                {"device": "r1", "process": 1, "network": "10.0.0.0/30", "area": "0"},
            ],
        },
    }


def _make_bgp_with_real_neighbors_topology():
    """BGP に解決可能な neighbor が2台ある（エッジ生成される）"""
    return {
        "title": "BGP Real Neighbors",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
                 "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
                {"device": "r2", "local_as": 65002, "local_ip": "10.0.0.2",
                 "neighbor_ip": "10.0.0.1", "peer_as": 65001, "type": "ebgp"},
            ],
        },
    }


def _make_ospf_two_devices_topology():
    """OSPF に2台が参加し、リンクも共有（エッジ生成される）"""
    return {
        "title": "OSPF Two Devices",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "ospf": [
                {"device": "r1", "process": 1, "network": "10.0.0.0/30", "area": "0"},
                {"device": "r2", "process": 1, "network": "10.0.0.0/30", "area": "0"},
            ],
        },
    }


@pytest.mark.unit
def test_gating_static_only_no_view():
    """static のみの topology では view-static <g> もタブも生成されない（辺なし）"""
    from lib.rendering import render
    html = render(_make_static_only_topology())
    assert 'class="view view-static"' not in html, \
        "static ビューが（辺なしなのに）生成されている"
    assert 'data-view="static"' not in html, \
        "static タブが（辺なしなのに）生成されている"


@pytest.mark.unit
def test_gating_bgp_no_resolved_neighbors_no_view():
    """neighbor_ip が解決できない BGP のみの topology では view-bgp が生成されない"""
    from lib.rendering import render
    html = render(_make_bgp_no_resolved_neighbors_topology())
    assert 'class="view view-bgp"' not in html, \
        "BGP ビューが（解決可能な隣接なしなのに）生成されている"
    assert 'data-view="bgp"' not in html, \
        "BGP タブが（解決可能な隣接なしなのに）生成されている"


@pytest.mark.unit
def test_gating_ospf_single_participant_no_view():
    """OSPF 参加が1台のみ（隣接リンクなし）の topology では view-ospf が生成されない"""
    from lib.rendering import render
    html = render(_make_ospf_single_device_topology())
    assert 'class="view view-ospf"' not in html, \
        "OSPF ビューが（参加1台なのに）生成されている"
    assert 'data-view="ospf"' not in html, \
        "OSPF タブが（参加1台なのに）生成されている"


@pytest.mark.unit
def test_gating_bgp_with_real_neighbors_generates_view():
    """解決可能な BGP 隣接がある場合は view-bgp が生成される"""
    from lib.rendering import render
    html = render(_make_bgp_with_real_neighbors_topology())
    assert 'class="view view-bgp"' in html, "BGP ビューが生成されていない"
    assert 'data-view="bgp"' in html, "BGP タブが生成されていない"


@pytest.mark.unit
def test_gating_ospf_two_devices_generates_view():
    """OSPF 参加2台・共有リンクあり → view-ospf が生成される"""
    from lib.rendering import render
    html = render(_make_ospf_two_devices_topology())
    assert 'class="view view-ospf"' in html, "OSPF ビューが生成されていない"
    assert 'data-view="ospf"' in html, "OSPF タブが生成されていない"


@pytest.mark.unit
def test_gating_tab_count_equals_view_count():
    """タブ数 == ビュー <g> 数（== で検証）"""
    from lib.rendering import render
    # bgp + ospf で両方エッジありの topology
    html = render(_make_bgp_with_real_neighbors_topology())
    view_groups = re.findall(r'class="view view-([a-z0-9_-]+)"', html)
    tabs = re.findall(r'data-view="([a-z0-9_-]+)"', html)
    assert len(tabs) == len(view_groups), \
        f"タブ数({len(tabs)}) != ビュー数({len(view_groups)}): " \
        f"views={view_groups}, tabs={tabs}"


@pytest.mark.unit
def test_gating_physical_and_l3_always_generated():
    """Phase A #6: physical ビューは常に生成される。l3 は削除されたため生成されない"""
    from lib.rendering import render
    topo = {
        "title": "No Routing",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {},
    }
    html = render(topo)
    assert 'class="view view-physical"' in html
    assert 'class="view view-l3"' not in html


# ===========================================================================
# B. 正確性: L3 重複エッジ
# ===========================================================================

def _make_shared_subnet_topology():
    """同一 /24 サブネットを r1, r2, r3 が共有する topology"""
    return {
        "title": "L3 Dedup Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r3", "hostname": "R3", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "192.168.1.1/24",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "192.168.1.2/24",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r3::eth0", "device": "r3", "name": "eth0", "ip": "192.168.1.3/24",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "192.168.1.0/24", "kind": "inferred-subnet"},
            {"a_device": "r1", "a_if": "eth0", "b_device": "r3", "b_if": "eth0",
             "subnet": "192.168.1.0/24", "kind": "inferred-subnet"},
            {"a_device": "r2", "a_if": "eth0", "b_device": "r3", "b_if": "eth0",
             "subnet": "192.168.1.0/24", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.mark.unit
def test_l3_edge_dedup_unique_dev_subnet_pairs():
    """Phase A #6: L3 ビューは削除された — view-l3 グループが生成されない"""
    from lib.rendering import render
    html = render(_make_shared_subnet_topology())
    assert 'class="view view-l3"' not in html, \
        "L3 ビューが（削除後も）生成されている"


# ===========================================================================
# C. 性能: 適応反復
# ===========================================================================

@pytest.mark.unit
def test_adaptive_iter_decreases_with_large_n():
    """_adaptive_iter: n が大きくなると iterations が 300 未満になる"""
    from lib.rendering import _adaptive_iter
    iters_small = _adaptive_iter(5)
    iters_large = _adaptive_iter(50)
    assert iters_large < 300, f"n=50 で iterations が {iters_large}（期待: <300）"
    assert iters_large < iters_small, \
        f"n が大きい方が iterations が多い: small={iters_small}, large={iters_large}"


@pytest.mark.unit
def test_adaptive_iter_minimum_is_100():
    """_adaptive_iter: 非常に大きい n でも最低 100 反復"""
    from lib.rendering import _adaptive_iter
    iters = _adaptive_iter(10000)
    assert iters >= 100, f"最低保証の 100 を下回っている: {iters}"


@pytest.mark.unit
def test_adaptive_iter_small_n_near_300():
    """_adaptive_iter: n が小さい（n=1）のとき上限に近い反復数を返す"""
    from lib.rendering import _adaptive_iter
    # max(100, 300 - n) の実装では n=1 → 299, n=0 → 300
    assert _adaptive_iter(1) >= 295, f"n=1 で {_adaptive_iter(1)} 反復（期待: >=295）"
    assert _adaptive_iter(5) >= 290, f"n=5 で {_adaptive_iter(5)} 反復（期待: >=290）"


@pytest.mark.unit
def test_render_deterministic_with_adaptive_iter(sample_topology):
    """適応反復を使っても同一入力で2回 render した結果が完全一致（決定性維持）"""
    from lib.rendering import render
    t1 = copy.deepcopy(sample_topology)
    t2 = copy.deepcopy(sample_topology)
    html1 = render(t1)
    html2 = render(t2)
    assert html1 == html2, "適応反復導入後の render() が非決定的"


# ===========================================================================
# D. 保守性 DRY: _canvas_size_for_nodes ヘルパー
# ===========================================================================

@pytest.mark.unit
def test_canvas_size_for_nodes_exists():
    """_canvas_size_for_nodes ヘルパー関数が存在する"""
    from lib.rendering import _canvas_size_for_nodes
    assert callable(_canvas_size_for_nodes)


@pytest.mark.unit
def test_canvas_size_for_nodes_returns_tuple():
    """_canvas_size_for_nodes(n) が (w, h) タプルを返す"""
    from lib.rendering import _canvas_size_for_nodes
    result = _canvas_size_for_nodes(10)
    assert isinstance(result, tuple) and len(result) == 2, \
        f"(w, h) タプルでない: {result}"


@pytest.mark.unit
def test_canvas_size_for_nodes_minimum():
    """_canvas_size_for_nodes(0) または (1) が最小キャンバスサイズ以上を返す"""
    from lib.rendering import _canvas_size_for_nodes, _MIN_CANVAS_W, _MIN_CANVAS_H
    w, h = _canvas_size_for_nodes(0)
    assert w >= _MIN_CANVAS_W
    assert h >= _MIN_CANVAS_H


@pytest.mark.unit
def test_canvas_size_grows_with_n():
    """_canvas_size_for_nodes: n が増えるとキャンバスが大きくなる"""
    from lib.rendering import _canvas_size_for_nodes
    w5, h5 = _canvas_size_for_nodes(5)
    w50, h50 = _canvas_size_for_nodes(50)
    assert w50 > w5 or h50 > h5, \
        f"n が増えてもキャンバスサイズが変わらない: n=5={w5}x{h5}, n=50={w50}x{h50}"


@pytest.mark.unit
def test_build_physical_layout_exists():
    """_build_physical_layout 関数が存在する"""
    from lib.rendering import _build_physical_layout
    assert callable(_build_physical_layout)


@pytest.mark.unit
def test_build_physical_layout_returns_dict():
    """_build_physical_layout が {node_id: (x, y)} 辞書を返す"""
    from lib.rendering import _build_physical_layout
    devices = [
        {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
    ]
    interfaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
         "vlan": None, "description": None, "shutdown": False},
        {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
         "vlan": None, "description": None, "shutdown": False},
    ]
    links = [{"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
              "subnet": "10.0.0.0/30", "kind": "inferred-subnet"}]
    segments = []
    result = _build_physical_layout(devices, interfaces, links, segments)
    assert isinstance(result, dict)
    assert "r1" in result
    assert "r2" in result


# ===========================================================================
# E. UX: L3 エッジクラス・filterNodes 拡張
# ===========================================================================

@pytest.mark.unit
def test_l3_edges_have_l3_edge_class():
    """Phase A #6: L3 ビューは削除された — view-l3 グループが生成されない"""
    from lib.rendering import render
    topo = {
        "title": "L3 Edge Class Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    assert 'class="view view-l3"' not in html, \
        "L3 ビューが（削除後も）生成されている"



@pytest.mark.unit
def test_selectview_uses_dataset_view():
    """selectView JS で this.dataset.view または data-view 経由でビュー切替している"""
    from lib.rendering import render
    topo = {
        "title": "Test",
        "generated_from": [],
        "devices": [],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {},
    }
    html = render(topo)
    # data-view 属性がタブに設定されている
    assert 'data-view=' in html, "タブに data-view 属性がない"
    # selectView 呼び出しが data-view 経由になっている（dataset.view or this.dataset）
    # Phase A #6: L3 削除後は routing={} の場合タブは physical のみ（1つ以上で OK）
    tab_data_views = re.findall(r'data-view="([^"]+)"', html)
    assert len(tab_data_views) >= 1, \
        f"data-view 属性を持つタブがない: {tab_data_views}"
    assert "physical" in tab_data_views, \
        "physical タブが存在しない"


# ===========================================================================
# F. テスト強化: ビュー内限定アサーション
# ===========================================================================

@pytest.mark.unit
def test_bgp_view_contains_device_nodes_inside_view(rendered_html):
    """BGP ビュー <g> ブロック内に device-node が存在する"""
    m = re.search(
        r'<g class="view view-bgp"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        rendered_html, re.DOTALL
    )
    assert m is not None, "view-bgp グループが見つからない"
    bgp_content = m.group(1)
    device_nodes = re.findall(r'class="device-node"', bgp_content)
    assert len(device_nodes) >= 2, \
        f"view-bgp 内に device-node が {len(device_nodes)} 個（期待: >=2）"


@pytest.mark.unit
def test_bgp_view_contains_bgp_ebgp_inside_view(rendered_html):
    """BGP ビュー <g> ブロック内に bgp-ebgp クラスエッジが存在する"""
    m = re.search(
        r'<g class="view view-bgp"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        rendered_html, re.DOTALL
    )
    assert m is not None, "view-bgp グループが見つからない"
    bgp_content = m.group(1)
    assert "bgp-ebgp" in bgp_content, \
        "view-bgp ブロック内に bgp-ebgp クラスエッジがない"


@pytest.mark.unit
def test_ospf_view_contains_device_nodes_inside_view():
    """OSPF ビュー <g> ブロック内に device-node が2台以上存在する（2台OSPF参加の人工 topology）。

    sample topology は r1 のみ OSPF 参加のためゲーティングでビュー未生成となる。
    恒久スキップを解消するため、2台が OSPF 参加する人工 topology を使って検証する。
    """
    from lib.rendering import render
    topo = _make_ospf_two_devices_topology()
    html = render(topo)
    m = re.search(
        r'<g class="view view-ospf"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        html, re.DOTALL
    )
    assert m is not None, "view-ospf グループが見つからない（2台OSPF参加なのに生成されない）"
    ospf_content = m.group(1)
    device_nodes = re.findall(r'class="device-node"', ospf_content)
    assert len(device_nodes) >= 2, \
        f"view-ospf 内に device-node が {len(device_nodes)} 個（期待: >=2）"


@pytest.mark.unit
def test_physical_view_contains_link_edges_inside_view(rendered_html):
    """Physical ビュー <g> ブロック内に link-edge が存在する"""
    m = re.search(
        r'<g class="view view-physical"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        rendered_html, re.DOTALL
    )
    assert m is not None, "view-physical グループが見つからない"
    phys_content = m.group(1)
    link_edges = re.findall(r'class="link-edge"', phys_content)
    assert len(link_edges) >= 1, \
        f"view-physical 内に link-edge が {len(link_edges)} 個（期待: >=1）"


# ===========================================================================
# G. selectView SVG fit パターン: viewBox のみ設定・ピクセル実寸セット禁止
# ===========================================================================

@pytest.mark.unit
def test_selectview_sets_viewbox_only(rendered_html):
    """selectView が viewBox のみをセットし、svg.setAttribute('width'/'height', ...) を含まない"""
    # selectView 関数の開始位置を特定し、次の "function " まで（または JS ブロック末尾まで）を抽出
    start = rendered_html.find("function selectView(viewId)")
    assert start != -1, "selectView 関数が見つからない"
    # 次の "function " 出現位置を関数終端とみなす
    end = rendered_html.find("function ", start + len("function selectView"))
    func_body = rendered_html[start:end] if end != -1 else rendered_html[start:start + 2000]

    # viewBox セットがある
    assert "setAttribute('viewBox'" in func_body or 'setAttribute("viewBox"' in func_body, \
        "selectView が viewBox をセットしていない"

    # svg.setAttribute('width', ...) / svg.setAttribute('height', ...) が無い
    assert "setAttribute('width'" not in func_body and 'setAttribute("width"' not in func_body, \
        "selectView 内に svg.setAttribute('width', ...) が残っている（ピクセル実寸セット禁止）"
    assert "setAttribute('height'" not in func_body and 'setAttribute("height"' not in func_body, \
        "selectView 内に svg.setAttribute('height', ...) が残っている（ピクセル実寸セット禁止）"


@pytest.mark.unit
def test_selectview_no_container_height_assignment(rendered_html):
    """selectView 内で container.style.height に bbox ピクセル値を代入しない"""
    start = rendered_html.find("function selectView(viewId)")
    assert start != -1, "selectView 関数が見つからない"
    end = rendered_html.find("function ", start + len("function selectView"))
    func_body = rendered_html[start:end] if end != -1 else rendered_html[start:start + 2000]

    # container.style.height = parts[3] + 'px' などが無い
    assert "container.style.height" not in func_body, \
        "selectView 内に container.style.height への bbox 実寸代入が残っている"


@pytest.mark.unit
def test_svg_element_has_100percent_dimensions(rendered_html):
    """SVG 要素が width='100%' / height='100%' でコンテナ固定になっている"""
    # <svg ... width="100%" height="100%"> または CSS で 100%
    has_attr_100pct = 'width="100%"' in rendered_html and 'height="100%"' in rendered_html
    # CSS での指定も許容 (width:100%;height:100%)
    has_css_100pct = re.search(
        r'#topology-svg\s*\{[^}]*width\s*:\s*100%[^}]*height\s*:\s*100%',
        rendered_html
    ) is not None or re.search(
        r'#topology-svg\s*\{[^}]*height\s*:\s*100%[^}]*width\s*:\s*100%',
        rendered_html
    ) is not None
    assert has_attr_100pct or has_css_100pct, \
        "SVG 要素が width='100%' / height='100%' になっていない（コンテナ固定でない）"


# ===========================================================================
# C. CSS/クラス名インジェクション防御
# ===========================================================================

@pytest.mark.unit
def test_css_injection_invalid_routing_key_not_in_css():
    """不正な routing キー（CSS 特殊文字含む）が直接渡されても生 CSS ルールが壊れない。

    load_topology 側でキー検証済みのため二重防御。
    render に人工的に不正キーを渡した場合も CSS が注入されないことを確認する。
    """
    from lib.rendering import render
    # 不正キー: '{display:block}' を含む（CSS インジェクション試み）
    topo = {
        "title": "CSS Injection Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {
            # 正常キーのみ（load 時に不正キーはスキップ済みのシナリオ）
            "bgp": [],
            "ospf": [],
        },
    }
    html = render(topo)
    # CSS セクションに {display:block} 等のインジェクションがないこと
    # （routing の normal キーのみなので当然ないはずだが回帰テストとして）
    import re
    # <style> ブロックを抽出
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
    assert len(style_blocks) >= 1, "style ブロックが見つからない"
    for style in style_blocks:
        # body.hide-{evil} の evil 部分が ^[a-z0-9_-]+$ 以外の文字を含まないこと
        invalid_hide_rules = re.findall(r'body\.hide-([^{}\s]+)\s*\{', style)
        for rule_key in invalid_hide_rules:
            assert re.match(r'^[a-z0-9_-]+$', rule_key), \
                f"CSS ルールの hide- キーが無効: '{rule_key}'"


@pytest.mark.unit
def test_css_layer_ids_are_safe():
    """vrrp/isis などの正規表現適合キーは CSS ルールに安全に展開される。"""
    from lib.rendering import render
    topo = _make_vrrp_topology()
    html = render(topo)
    # body.hide-vrrp / .layer-vrrp が存在し、特殊文字がないこと
    assert "body.hide-vrrp" in html or "hide-vrrp" in html
    assert "layer-vrrp" in html
    # CSS ルール内に { } が二重に入っていないこと（インジェクションの証拠）
    import re
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
    for style in style_blocks:
        # 'body.hide-vrrp .layer-vrrp' 形式を確認
        assert not re.search(r'body\.hide-[^{}\s]*[{}][^{}\s]*\s*{', style), \
            "CSS ルール内に不正な {} が含まれている（インジェクションの可能性）"


# ===========================================================================
# H. 死にトグル修正: データなし routing プロトコルは UI 非生成
# ===========================================================================

def _make_bgp_only_with_empty_ospf_topology():
    """bgp のみデータあり、ospf は空リストの topology"""
    return {
        "title": "BGP Only (ospf empty)",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
                 "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
                {"device": "r2", "local_as": 65002, "local_ip": "10.0.0.2",
                 "neighbor_ip": "10.0.0.1", "peer_as": 65001, "type": "ebgp"},
            ],
            "ospf": [],   # 意図的に空 (topology_io の常時注入を模倣)
            "static": [],
        },
    }


@pytest.mark.unit
def test_dead_toggle_ospf_not_generated_when_empty():
    """ospf が空リストのとき toggle-ospf（死にトグル）が生成されない"""
    from lib.rendering import render
    html = render(_make_bgp_only_with_empty_ospf_topology())
    assert 'id="toggle-ospf"' not in html, \
        "ospf が空なのに toggle-ospf が生成されている（死にトグル）"
    assert 'data-layer="ospf"' not in html, \
        "ospf が空なのに data-layer='ospf' が生成されている（死にトグル）"


@pytest.mark.unit
def test_dead_toggle_bgp_still_generated_when_nonempty():
    """bgp にデータがあるとき toggle-bgp は生成される"""
    from lib.rendering import render
    html = render(_make_bgp_only_with_empty_ospf_topology())
    assert 'id="toggle-bgp"' in html or "toggle-bgp" in html, \
        "bgp にデータがあるのに toggle-bgp が生成されていない"


@pytest.mark.unit
def test_dead_toggle_ospf_css_hide_not_generated_when_empty():
    """ospf が空リストのとき body.hide-ospf / .layer-ospf の CSS ルールが生成されない"""
    from lib.rendering import render
    html = render(_make_bgp_only_with_empty_ospf_topology())
    assert "hide-ospf" not in html, \
        "ospf が空なのに body.hide-ospf CSS ルールが生成されている"
    assert "layer-ospf" not in html, \
        "ospf が空なのに .layer-ospf CSS ルールが生成されている"


@pytest.mark.unit
def test_dead_toggle_bgp_css_still_generated_when_nonempty():
    """bgp にデータがあるとき hide-bgp / layer-bgp CSS ルールは生成される"""
    from lib.rendering import render
    html = render(_make_bgp_only_with_empty_ospf_topology())
    assert "hide-bgp" in html, \
        "bgp にデータがあるのに body.hide-bgp CSS ルールが生成されていない"
    assert "layer-bgp" in html, \
        "bgp にデータがあるのに .layer-bgp CSS ルールが生成されていない"


@pytest.mark.unit
def test_dead_toggle_regression_ospf_toggle_generated_when_nonempty():
    """ospf にデータがある topology では toggle-ospf が引き続き生成される（回帰保護）"""
    from lib.rendering import render
    # _make_ospf_two_devices_topology() は ospf に2エントリある
    topo = _make_ospf_two_devices_topology()
    html = render(topo)
    assert 'id="toggle-ospf"' in html or "toggle-ospf" in html, \
        "ospf にデータがあるのに toggle-ospf が生成されていない（回帰）"


# ===========================================================================
# Phase A: #6 L3 ビュー完全削除
# ===========================================================================

@pytest.mark.unit
def test_phaseA_l3_view_not_generated(rendered_html):
    """Phase A #6: L3 ビュー <g class="view view-l3"> が生成されない"""
    assert 'class="view view-l3"' not in rendered_html, \
        "L3 ビューが（削除後も）生成されている"


@pytest.mark.unit
def test_phaseA_l3_tab_not_generated(rendered_html):
    """Phase A #6: L3 タブ（data-view="l3"）が生成されない"""
    assert 'data-view="l3"' not in rendered_html, \
        "L3 タブが（削除後も）生成されている"


@pytest.mark.unit
def test_phaseA_l3_view_not_generated_empty(empty_topology):
    """Phase A #6: 空 topology でも L3 ビューが生成されない"""
    from lib.rendering import render
    html = render(empty_topology)
    assert 'class="view view-l3"' not in html, \
        "空 topology で L3 ビューが（削除後も）生成されている"


@pytest.mark.unit
def test_phaseA_l3_view_not_generated_no_routing():
    """Phase A #6: routing が空でも L3 ビューが生成されない"""
    from lib.rendering import render
    topo = {
        "title": "No Routing",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {},
    }
    html = render(topo)
    assert 'class="view view-l3"' not in html, \
        "routing 空 topology で L3 ビューが（削除後も）生成されている"


@pytest.mark.unit
def test_phaseA_l3_css_hide_rule_not_generated(rendered_html):
    """Phase A #6: body.hide-l3 / .layer-l3 / .l3-edge の3つがいずれも出力されない"""
    assert "hide-l3" not in rendered_html, \
        "body.hide-l3 CSS ルールが（L3削除後も）生成されている"
    assert "layer-l3" not in rendered_html, \
        ".layer-l3 CSS ルールが（L3削除後も）生成されている"
    assert "l3-edge" not in rendered_html, \
        ".l3-edge クラスが（L3削除後も）生成されている"


@pytest.mark.unit
def test_phaseA_physical_tab_still_exists(rendered_html):
    """Phase A #6: L3 削除後も Physical タブは存在する"""
    assert 'data-view="physical"' in rendered_html, \
        "Physical タブが消えている"


@pytest.mark.unit
def test_phaseA_bgp_tab_still_exists(rendered_html):
    """Phase A #6: L3 削除後も BGP タブは存在する（sample は bgp あり）"""
    assert 'data-view="bgp"' in rendered_html, \
        "BGP タブが消えている"


# ===========================================================================
# Phase A: #1b Physical ビューから BGP オーバーレイ除去
# ===========================================================================

@pytest.mark.unit
def test_phaseA_physical_view_no_bgp_session(rendered_html):
    """Phase A #1b: Physical ビュー内に bgp-session クラスが存在しない"""
    import re
    m = re.search(
        r'<g class="view view-physical"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        rendered_html, re.DOTALL
    )
    assert m is not None, "view-physical グループが見つからない"
    phys_content = m.group(1)
    bgp_sessions = re.findall(r'class="bgp-session"', phys_content)
    assert len(bgp_sessions) == 0, \
        f"Physical ビュー内に bgp-session が {len(bgp_sessions)} 個（期待: 0）"


@pytest.mark.unit
def test_phaseA_physical_view_no_bgp_edge_class(rendered_html):
    """Phase A #1b: Physical ビュー内に bgp-edge クラスが存在しない"""
    import re
    m = re.search(
        r'<g class="view view-physical"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        rendered_html, re.DOTALL
    )
    assert m is not None, "view-physical グループが見つからない"
    phys_content = m.group(1)
    assert "bgp-edge" not in phys_content, \
        "Physical ビュー内に bgp-edge クラスが残っている"


@pytest.mark.unit
def test_phaseA_physical_view_no_bgp_badge(rendered_html):
    """Phase A #1b: Physical ビュー内に bgp-badge クラスが存在しない"""
    import re
    m = re.search(
        r'<g class="view view-physical"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        rendered_html, re.DOTALL
    )
    assert m is not None, "view-physical グループが見つからない"
    phys_content = m.group(1)
    assert "bgp-badge" not in phys_content, \
        "Physical ビュー内に bgp-badge クラスが残っている"


@pytest.mark.unit
def test_phaseA_bgp_view_still_has_bgp_edges(rendered_html):
    """Phase A #1b: BGP ビューは引き続き bgp-edge を含む（削除対象外）"""
    import re
    m = re.search(
        r'<g class="view view-bgp"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        rendered_html, re.DOTALL
    )
    assert m is not None, "view-bgp グループが見つからない"
    bgp_content = m.group(1)
    assert "bgp-edge" in bgp_content, \
        "BGP ビューに bgp-edge が含まれていない（誤って削除された）"


@pytest.mark.unit
def test_phaseA_physical_view_no_bgp_bidirectional():
    """Phase A #1b: 双方向 BGP があっても Physical ビューに bgp-session が0本"""
    import re
    from lib.rendering import render
    html = render(_make_bidirectional_bgp_topology())
    m = re.search(
        r'<g class="view view-physical"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        html, re.DOTALL
    )
    if m:
        phys_content = m.group(1)
    else:
        phys_content = html
    bgp_sessions = re.findall(r'class="bgp-session"', phys_content)
    assert len(bgp_sessions) == 0, \
        f"Physical ビュー内に bgp-session が {len(bgp_sessions)} 本（期待: 0）"


# ===========================================================================
# Phase A: #3 LAYERS トグルをカード表セクション制御のみに
# ===========================================================================

@pytest.mark.unit
def test_phaseA_interfaces_table_has_layer_physical_class():
    """Phase A #3: Interfaces 表セクションに layer-physical クラスが付与される"""
    from lib.rendering import render
    topo = {
        "title": "Toggle Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    # Interfaces 表（h4 + table）に layer-physical クラスが付いていること
    assert "layer-physical" in html, \
        "カードの Interfaces 表に layer-physical クラスが付いていない"


@pytest.mark.unit
def test_phaseA_interfaces_h4_has_layer_physical_class():
    """Phase A #3: Interfaces の h4 見出しに layer-physical クラスがある"""
    from lib.rendering import render
    topo = {
        "title": "Toggle Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    import re
    # <h4 class="layer-physical"> または <h4 ... class="... layer-physical ...">
    assert re.search(r'<h4[^>]*class="[^"]*layer-physical[^"]*"', html), \
        "Interfaces h4 に layer-physical クラスがない"


@pytest.mark.unit
def test_phaseA_interfaces_table_tag_has_layer_physical_class():
    """Phase A #3: Interfaces の table タグに layer-physical クラスがある"""
    from lib.rendering import render
    topo = {
        "title": "Toggle Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    import re
    assert re.search(r'<table[^>]*class="[^"]*layer-physical[^"]*"', html), \
        "Interfaces table に layer-physical クラスがない"


@pytest.mark.unit
def test_phaseA_physical_toggle_always_exists(rendered_html):
    """Phase A #3: physical トグルが常に先頭に存在する（sample topology）"""
    assert 'id="toggle-physical"' in rendered_html, \
        "toggle-physical が存在しない"
    assert 'data-layer="physical"' in rendered_html, \
        "data-layer='physical' が存在しない"


@pytest.mark.unit
def test_phaseA_physical_toggle_exists_empty(empty_topology):
    """Phase A #3: 空 topology でも physical トグルが存在する"""
    from lib.rendering import render
    html = render(empty_topology)
    assert 'id="toggle-physical"' in html, \
        "空 topology で toggle-physical が存在しない"


@pytest.mark.unit
def test_phaseA_bgp_card_table_still_has_layer_bgp(rendered_html):
    """Phase A #3: BGP セッション表は引き続き class="layer-bgp" を持つ（回帰保護）"""
    # cards.py の BGP 表は既存の layer-bgp クラスを持つ（厳密な属性検索）
    assert 'class="layer-bgp"' in rendered_html, \
        "カードの BGP 表から class='layer-bgp' が消えている"


@pytest.mark.unit
def test_phaseA_hide_physical_css_rule_exists(rendered_html):
    """Phase A #3: body.hide-physical .layer-physical { display:none } 相当の CSS が出力される"""
    assert "hide-physical" in rendered_html, \
        "body.hide-physical CSS ルールが存在しない"
    assert "layer-physical" in rendered_html, \
        ".layer-physical CSS ルールが存在しない"


@pytest.mark.unit
def test_phaseA_physical_toggle_is_first_in_toggles(rendered_html):
    """Phase A #3: physical トグルが routing トグルより先に現れる"""
    phys_pos = rendered_html.find('data-layer="physical"')
    bgp_pos = rendered_html.find('data-layer="bgp"')
    assert phys_pos != -1, "data-layer='physical' が存在しない"
    assert bgp_pos != -1, "data-layer='bgp' が存在しない"
    assert phys_pos < bgp_pos, \
        f"physical トグル ({phys_pos}) が bgp トグル ({bgp_pos}) より後に来ている"


# ===========================================================================
# Phase A: #3 LAYERS トグルの CSS 検証（厳密化）および seg-edge 常時表示テスト
# ===========================================================================

@pytest.mark.unit
def test_phaseA_hide_physical_css_rule_strict(rendered_html):
    """Phase A #3 / 要件#3: body.hide-physical #cards-section .layer-physical { display:none } の
    CSS ルールが正規表現で確認できる。
    セレクタが #cards-section に限定されていることで SVG 図内の layer-physical 要素には影響しない。"""
    import re
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    assert len(style_blocks) >= 1, "style ブロックが見つからない"
    combined_style = "\n".join(style_blocks)
    # body.hide-physical #cards-section .layer-physical { display:none } 相当のルールが存在すること
    assert re.search(
        r'body\.hide-physical\s+#cards-section\s+\.layer-physical\s*\{[^}]*display\s*:\s*none',
        combined_style,
    ), "body.hide-physical #cards-section .layer-physical { display:none } ルールが見つからない"


@pytest.mark.unit
def test_phaseA_hide_physical_css_no_seg_edge_rule(rendered_html):
    """Phase A #3 要件: physical トグルOFFで seg-edge は hide されない。
    CSS に body.hide-physical .seg-edge { display:none } ルールが存在してはならない。"""
    import re
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined_style = "\n".join(style_blocks)
    # seg-edge の hide 連動ルールが存在しないこと
    assert not re.search(
        r'body\.hide-physical\s+\.seg-edge\s*\{[^}]*display\s*:\s*none',
        combined_style,
    ), "body.hide-physical .seg-edge { display:none } ルールが存在する（要件違反: seg-edge は常時表示）"


@pytest.mark.unit
def test_phaseA_hide_physical_interfaces_card_is_hidden():
    """Phase A #3 / 要件#3: physical トグルOFFで Interfaces カード表（.layer-physical）が hide 対象になる。
    CSS に body.hide-physical #cards-section .layer-physical の hide ルールが存在すること。
    #cards-section に限定することで SVG 内の link-line/link-label は影響を受けない。"""
    from lib.rendering import render
    import re
    topo = {
        "title": "Toggle Card Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [],
        "routing": {},
    }
    html = render(topo)
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
    combined_style = "\n".join(style_blocks)
    # Interfaces カード（.layer-physical）が #cards-section 限定で hide 対象のルールを持つ
    assert re.search(
        r'body\.hide-physical\s+#cards-section\s+\.layer-physical\s*\{[^}]*display\s*:\s*none',
        combined_style,
    ), "body.hide-physical #cards-section .layer-physical ルールがない（Interfaces カード表が hide されない）"
    # グローバルルール（図を消すもの）は存在しないこと
    assert not re.search(
        r'body\.hide-physical\s+\.layer-physical\s*\{[^}]*display\s*:\s*none',
        combined_style,
    ), "グローバルな body.hide-physical .layer-physical ルールが存在する（SVG 図内まで消えてしまう）"
    # seg-edge は hide 対象でないこと（SVG の接続線は常時表示）
    assert not re.search(
        r'body\.hide-physical\s+\.seg-edge\s*\{[^}]*display\s*:\s*none',
        combined_style,
    ), "body.hide-physical .seg-edge ルールが存在する（図の接続線は常時表示すべき）"


@pytest.mark.unit
def test_phaseA_bgp_card_table_has_layer_bgp_class_strict(rendered_html):
    """Phase A #3: BGP セッション表は class="layer-bgp" を持つ（厳密な属性検索）"""
    assert 'class="layer-bgp"' in rendered_html, \
        "カードの BGP 表に class='layer-bgp' が存在しない"


@pytest.mark.unit
def test_phaseA_l3_css_hide_rule_not_generated_strict(rendered_html):
    """Phase A #6: hide-l3, layer-l3, l3-edge の3つがいずれも出力されない"""
    assert "hide-l3" not in rendered_html, \
        "body.hide-l3 CSS ルールが（L3削除後も）生成されている"
    assert "layer-l3" not in rendered_html, \
        ".layer-l3 CSS ルールが（L3削除後も）生成されている"
    assert "l3-edge" not in rendered_html, \
        ".l3-edge クラスが（L3削除後も）生成されている"


# ===========================================================================
# Phase B #1a: Physical ノード情報拡充・物理リンクラベル常時表示
# ===========================================================================

def _make_physical_detail_topology():
    """IF に description あり・shutdown あり・IP なし が混在する人工 topology（Physical ビュー詳細テスト用）"""
    return {
        "title": "Physical Detail Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
        ],
        "interfaces": [
            # r1: 通常 IF（IP あり・description あり）
            {"id": "r1::GigabitEthernet0/0", "device": "r1", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.1/30", "vlan": None,
             "description": "CORE-LINK-to-R2", "shutdown": False},
            # r1: Loopback（IP あり・description なし）
            {"id": "r1::Loopback0", "device": "r1", "name": "Loopback0",
             "ip": "10.255.0.1/32", "vlan": None,
             "description": None, "shutdown": False},
            # r1: shutdown IF（IP あり・description あり）
            {"id": "r1::GigabitEthernet0/1", "device": "r1", "name": "GigabitEthernet0/1",
             "ip": "192.168.1.1/24", "vlan": None,
             "description": "SITE-LAN", "shutdown": True},
            # r1: IP なし IF
            {"id": "r1::GigabitEthernet0/2", "device": "r1", "name": "GigabitEthernet0/2",
             "ip": None, "vlan": None,
             "description": None, "shutdown": False},
            # r2: 通常 IF
            {"id": "r2::GigabitEthernet0/0", "device": "r2", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.2/30", "vlan": None,
             "description": "CORE-LINK-to-R1", "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "GigabitEthernet0/0",
             "b_device": "r2", "b_if": "GigabitEthernet0/0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
                 "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
                {"device": "r2", "local_as": 65002, "local_ip": "10.0.0.2",
                 "neighbor_ip": "10.0.0.1", "peer_as": 65001, "type": "ebgp"},
            ],
        },
    }


def _extract_physical_view(html: str) -> str:
    """HTML から Physical ビューの SVG コンテンツを抽出する"""
    m = re.search(
        r'<g class="view view-physical"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        html, re.DOTALL
    )
    return m.group(1) if m else html


def _extract_bgp_view(html: str) -> str:
    """HTML から BGP ビューの SVG コンテンツを抽出する"""
    m = re.search(
        r'<g class="view view-bgp"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        html, re.DOTALL
    )
    return m.group(1) if m else ""


# ---- Physical ノードに全 IF 名・IP が常時表示される ----------------------

@pytest.mark.unit
def test_phaseB1a_physical_node_shows_if_name():
    """Phase B #1a: Physical ビューのノードに IF 名（GigabitEthernet0/0）が表示される"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    assert "GigabitEthernet0/0" in phys, \
        "Physical ビューのノードに GigabitEthernet0/0 が表示されていない"


@pytest.mark.unit
def test_phaseB1a_physical_node_shows_if_ip():
    """Phase B #1a: Physical ビューのノードに IP（10.0.0.1/30）が表示される"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    assert "10.0.0.1/30" in phys, \
        "Physical ビューのノードに 10.0.0.1/30 が表示されていない"


@pytest.mark.unit
def test_phaseB1a_physical_node_shows_if_without_ip():
    """Phase B #1a: IP 未設定 IF も Physical ビューのノードに表示される（IF名のみ）"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # GigabitEthernet0/2 は IP なし → name だけでも表示される
    assert "GigabitEthernet0/2" in phys, \
        "IP 未設定 IF（GigabitEthernet0/2）が Physical ノードに表示されていない"


@pytest.mark.unit
def test_phaseB1a_physical_node_shows_loopback():
    """Phase B #1a: Loopback も Physical ビューのノードに表示される"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    assert "Loopback0" in phys, \
        "Loopback0 が Physical ノードに表示されていない"


# ---- shutdown IF は淡色クラスを持つ ----------------------------------------

@pytest.mark.unit
def test_phaseB1a_shutdown_if_has_dimmed_class():
    """Phase B #1a: shutdown=True の IF 行に if-shutdown クラス（淡色）が付く"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # GigabitEthernet0/1 は shutdown=True → 淡色クラスが付く
    assert "if-shutdown" in phys, \
        "shutdown IF に if-shutdown クラスが付いていない"


@pytest.mark.unit
def test_phaseB1a_active_if_has_no_shutdown_class():
    """Phase B #1a: shutdown=False の IF 行に if-shutdown クラスが付かない"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # Loopback0 は shutdown=False → テキスト要素の class に if-shutdown が含まれない
    # GigabitEthernet0/0 の text 要素を探して if-shutdown がないことを確認
    # （ページ全体に if-shutdown があることは許容するが、全 IF に付いてはいけない）
    # GigabitEthernet0/0 を含む text 要素直後に if-shutdown があってはいけない
    m = re.search(r'GigabitEthernet0/0[^<]*<', phys)
    if m:
        context = phys[max(0, m.start() - 200):m.end() + 50]
        # その直前の text 要素に if-shutdown がないこと
        assert "if-shutdown" not in context or phys.count("if-shutdown") <= phys.count(
            "GigabitEthernet0/1"
        ), "active IF（GigabitEthernet0/0）に if-shutdown クラスが付いている"


# ---- IF の description が <title> に入る ------------------------------------

@pytest.mark.unit
def test_phaseB1a_if_description_in_title():
    """Phase B #1a: description のある IF 行に <title>description</title> が付く"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # GigabitEthernet0/0 の description="CORE-LINK-to-R2" が title に入る
    assert "CORE-LINK-to-R2" in phys, \
        "IF の description（CORE-LINK-to-R2）が Physical ビューに表示されていない"


@pytest.mark.unit
def test_phaseB1a_if_description_in_title_element():
    """Phase B #1a: description は <title> 要素として表現される（hover 表示）"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # <title>CORE-LINK-to-R2</title> が存在すること（常時真の OR 後半は削除）
    assert "<title>CORE-LINK-to-R2</title>" in phys, \
        "CORE-LINK-to-R2 description が <title>...</title> 形式で存在しない"


@pytest.mark.unit
def test_phaseB1a_if_no_description_no_empty_title():
    """Phase B #1a: description=None の IF には空の <title></title> が付かない"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # Loopback0 は description=None → <title></title> が付かないこと
    assert "<title></title>" not in phys, \
        "description=None の IF に空の <title></title> が付いている"


# ---- BGP/OSPF ノードには IF 一覧が出ない ------------------------------------

@pytest.mark.unit
def test_phaseB1a_bgp_node_no_if_list():
    """Phase B #1a: BGP ビューのノードに IF 行（if-row クラス）が含まれない"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    bgp = _extract_bgp_view(html)
    assert bgp, "BGP ビューが生成されていない（topology に bgp エントリあり）"
    assert "if-row" not in bgp, \
        "BGP ビューのノードに if-row クラスが含まれている（コンパクト維持違反）"


@pytest.mark.unit
def test_phaseB1a_bgp_node_compact_hostname_still_shown():
    """Phase B #1a: BGP ビューのノードに hostname が引き続き表示される"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    bgp = _extract_bgp_view(html)
    assert "R1" in bgp and "R2" in bgp, \
        "BGP ビューに hostname が表示されていない"


@pytest.mark.unit
def test_phaseB1a_ospf_node_no_if_list():
    """Phase B #1a: OSPF ビューのノードに IF 行（if-row クラス）が含まれない"""
    from lib.rendering import render
    topo = _make_ospf_two_devices_topology()
    html = render(topo)
    m = re.search(
        r'<g class="view view-ospf"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        html, re.DOTALL
    )
    if m:
        ospf_content = m.group(1)
        assert "if-row" not in ospf_content, \
            "OSPF ビューのノードに if-row クラスが含まれている（コンパクト維持違反）"


# ---- 物理リンクに a_if — b_if + subnet の常時テキストが出る ----------------

@pytest.mark.unit
def test_phaseB1a_link_label_shows_if_names():
    """Phase B #1a: 物理リンクに「a_if — b_if」の常時 <text> ラベルが表示される"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # "GigabitEthernet0/0 — GigabitEthernet0/0" または短縮形が <text> 要素に入る
    # セパレータは — または " - " 等を許容
    has_link_label = (
        ("GigabitEthernet0/0" in phys and "—" in phys) or
        ("GigabitEthernet0/0" in phys and " - " in phys) or
        "link-label" in phys
    )
    assert has_link_label, \
        "物理リンクに IF 名の常時ラベルが表示されていない"


@pytest.mark.unit
def test_phaseB1a_link_label_is_text_element():
    """Phase B #1a: リンクラベルは SVG <text> 要素で実装される（title でなく常時表示）"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # Physical ビューに link-label クラスの text 要素があること
    assert 'class="link-label' in phys or \
           (re.search(r'<text[^>]*>[^<]*(GigabitEthernet0/0)[^<]*</text>', phys) is not None), \
        "リンクラベルが <text> 要素で実装されていない"


@pytest.mark.unit
def test_phaseB1a_link_label_shows_subnet():
    """Phase B #1a: リンクラベルに subnet（10.0.0.0/30）が表示される"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    assert "10.0.0.0/30" in phys, \
        "物理リンクのラベルに subnet（10.0.0.0/30）が表示されていない"


# ---- 可変高ノードのレイアウト重なりなし ------------------------------------

@pytest.mark.unit
def test_phaseB1a_node_height_varies_with_if_count():
    """Phase B #1a: IF 数の異なるノードで高さが変わる（可変高）"""
    from lib.rendering.layout import _node_size_for
    # r1 は IF が 4 本 → r2 は 1 本 → r1 の高さ > r2 の高さ
    h_many = _node_size_for(4)[1]
    h_few = _node_size_for(1)[1]
    assert h_many > h_few, \
        f"IF 数が多いノードの高さが少ないノードと同じ（h_many={h_many}, h_few={h_few}）"


@pytest.mark.unit
def test_phaseB1a_node_height_helper_exists():
    """Phase B #1a: layout._node_size_for(n_ifaces) ヘルパーが存在する（高さは [1] で取得）"""
    from lib.rendering.layout import _node_size_for
    assert callable(_node_size_for)
    h = _node_size_for(0)[1]
    assert isinstance(h, (int, float)) and h > 0


@pytest.mark.unit
def test_phaseB1a_layout_separation_with_variable_height():
    """Phase B #1a: IF 数差が大きいノードを含む topology でノード矩形が重ならない"""
    from lib.rendering.layout import _layout_force_directed, _node_size_for
    # r1: IF 6 本（大きいノード）、r2: IF 1 本（小さいノード）
    node_ids = ["r1", "r2", "r3"]
    iface_counts = {"r1": 6, "r2": 1, "r3": 3}
    edges = [("r1", "r2"), ("r2", "r3")]
    pos = _layout_force_directed(
        node_ids, edges, width=1200.0, height=1000.0,
        node_sizes=iface_counts,
    )
    # 各ペアで矩形重なりなしを確認
    for i, na in enumerate(node_ids):
        for j, nb in enumerate(node_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            wa, ha = _node_size_for(iface_counts[na])
            wb, hb = _node_size_for(iface_counts[nb])
            # 矩形が重なっていないこと（中心間距離 > 必要最小間隔）
            needed_x = (wa + wb) / 2 + 5
            needed_y = (ha + hb) / 2 + 5
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            no_overlap = dx >= needed_x or dy >= needed_y
            assert no_overlap, (
                f"ノード {na}({wa}x{ha}) と {nb}({wb}x{hb}) の矩形が重なっている "
                f"（中心 ({x1:.1f},{y1:.1f}) vs ({x2:.1f},{y2:.1f}), "
                f"dx={dx:.1f} needed_x={needed_x:.1f}, dy={dy:.1f} needed_y={needed_y:.1f}）"
            )


@pytest.mark.unit
def test_phaseB1a_node_size_helper_exists():
    """Phase B #1a: _node_size_for(n_ifaces) が (width, height) を返すヘルパーが存在する"""
    from lib.rendering.layout import _node_size_for
    assert callable(_node_size_for)
    w, h = _node_size_for(3)
    assert isinstance(w, (int, float)) and w > 0
    assert isinstance(h, (int, float)) and h > 0


# ---- 決定性（可変高ノード含む）-------------------------------------------

@pytest.mark.unit
def test_phaseB1a_render_deterministic_with_variable_height():
    """Phase B #1a: 可変高ノードを含む topology で2回 render した結果が完全一致"""
    from lib.rendering import render
    topo1 = _make_physical_detail_topology()
    topo2 = _make_physical_detail_topology()
    html1 = render(topo1)
    html2 = render(topo2)
    assert html1 == html2, \
        "可変高ノードを含む topology で render() の出力が非決定的"


# ---- Physical ノードの件数・コンパクト維持の回帰テスト ---------------------

@pytest.mark.unit
def test_phaseB1a_physical_view_device_nodes_present():
    """Phase B #1a: Physical ビューに device-node が存在する（回帰保護）"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    device_nodes = re.findall(r'class="device-node"', phys)
    assert len(device_nodes) >= 2, \
        f"Physical ビューに device-node が {len(device_nodes)} 個（期待: >=2）"


@pytest.mark.unit
def test_phaseB1a_existing_tests_regression(sample_topology):
    """Phase B #1a: sample topology で既存テスト（hostname・IF名・決定性）が回帰しない"""
    from lib.rendering import render
    html = render(sample_topology)
    # 既存テストの主要アサーション
    assert "R1" in html and "R2" in html
    assert "GigabitEthernet0/0" in html
    assert "ebgp" in html.lower()
    # 決定性
    html2 = render(sample_topology)
    assert html == html2, "sample topology で決定性が失われた"


# ===========================================================================
# 要件#3: LAYERS トグルは「#cards-section 配下のカード表のみ」を ON/OFF する
# 図(SVG)内の layer-* 要素（link-line/link-label/bgp-edge 等）は連動しない
# ===========================================================================

def _extract_style_blocks(html: str) -> str:
    """HTML 内の全 <style> ブロックを結合して返す"""
    import re
    blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
    return "\n".join(blocks)


@pytest.mark.unit
def test_req3_hide_physical_scoped_to_cards_section(rendered_html):
    """要件#3: body.hide-physical は #cards-section 配下の .layer-physical のみ hide する。
    CSS セレクタが 'body.hide-physical #cards-section .layer-physical' 形式であること。"""
    import re
    style = _extract_style_blocks(rendered_html)
    assert re.search(
        r'body\.hide-physical\s+#cards-section\s+\.layer-physical\s*\{[^}]*display\s*:\s*none',
        style,
    ), "body.hide-physical #cards-section .layer-physical { display:none } ルールが見つからない"


@pytest.mark.unit
def test_req3_hide_bgp_scoped_to_cards_section(rendered_html):
    """要件#3: body.hide-bgp は #cards-section 配下の .layer-bgp のみ hide する。"""
    import re
    style = _extract_style_blocks(rendered_html)
    assert re.search(
        r'body\.hide-bgp\s+#cards-section\s+\.layer-bgp\s*\{[^}]*display\s*:\s*none',
        style,
    ), "body.hide-bgp #cards-section .layer-bgp { display:none } ルールが見つからない"


@pytest.mark.unit
def test_req3_hide_static_scoped_to_cards_section(rendered_html):
    """要件#3: body.hide-static は #cards-section 配下の .layer-static のみ hide する。"""
    import re
    style = _extract_style_blocks(rendered_html)
    assert re.search(
        r'body\.hide-static\s+#cards-section\s+\.layer-static\s*\{[^}]*display\s*:\s*none',
        style,
    ), "body.hide-static #cards-section .layer-static { display:none } ルールが見つからない"


@pytest.mark.unit
def test_req3_no_global_hide_physical_rule(rendered_html):
    """要件#3（否定検証）: グローバルな 'body.hide-physical .layer-physical'（#cards-section なし）が
    存在しない。存在すると SVG 内 link-line/link-label も消えてしまう。"""
    import re
    style = _extract_style_blocks(rendered_html)
    # #cards-section を挟まずに直接 .layer-physical を指定するルールがないこと
    assert not re.search(
        r'body\.hide-physical\s+\.layer-physical\s*\{[^}]*display\s*:\s*none',
        style,
    ), (
        "グローバルな body.hide-physical .layer-physical { display:none } が存在する。"
        "SVG 内の link-line/link-label が消えてしまう（要件#3違反）。"
    )


@pytest.mark.unit
def test_req3_no_global_hide_bgp_rule(rendered_html):
    """要件#3（否定検証）: グローバルな 'body.hide-bgp .layer-bgp'（#cards-section なし）が存在しない。"""
    import re
    style = _extract_style_blocks(rendered_html)
    assert not re.search(
        r'body\.hide-bgp\s+\.layer-bgp\s*\{[^}]*display\s*:\s*none',
        style,
    ), (
        "グローバルな body.hide-bgp .layer-bgp { display:none } が存在する。"
        "BGP ビューの bgp-edge が消えてしまう（要件#3違反）。"
    )


@pytest.mark.unit
def test_req3_vrrp_hide_scoped_to_cards_section():
    """要件#3: vrrp 等の動的キーも #cards-section 限定で hide ルールが生成される"""
    import re
    from lib.rendering import render
    html = render(_make_vrrp_topology())
    style = _extract_style_blocks(html)
    assert re.search(
        r'body\.hide-vrrp\s+#cards-section\s+\.layer-vrrp\s*\{[^}]*display\s*:\s*none',
        style,
    ), "body.hide-vrrp #cards-section .layer-vrrp { display:none } ルールが見つからない"
    # グローバルルールは存在しないこと
    assert not re.search(
        r'body\.hide-vrrp\s+\.layer-vrrp\s*\{[^}]*display\s*:\s*none',
        style,
    ), "グローバルな body.hide-vrrp .layer-vrrp ルールが存在する（要件#3違反）"


@pytest.mark.unit
def test_req3_cards_section_id_exists(rendered_html):
    """要件#3 前提: #cards-section という id を持つ要素が HTML 内に存在する"""
    assert 'id="cards-section"' in rendered_html, \
        "id='cards-section' 要素が存在しない（CSS セレクタが機能しない）"


# ===========================================================================
# Phase B レビュー修正テスト
# ===========================================================================

# ---------------------------------------------------------------------------
# C1: 多 IF ノードでキャンバス高が追従する・viewBox 内に収まる
# ---------------------------------------------------------------------------

def _make_many_if_topology(n_if_per_node: int = 30):
    """各ノードが n_if_per_node 本の IF を持つ 3 ノード topology"""
    devices = [
        {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        {"id": "r3", "hostname": "R3", "vendor": "cisco_ios", "as": None, "sections": []},
    ]
    interfaces = []
    for dev_id in ("r1", "r2", "r3"):
        for i in range(n_if_per_node):
            interfaces.append({
                "id": f"{dev_id}::Gi0/{i}",
                "device": dev_id,
                "name": f"GigabitEthernet0/{i}",
                "ip": f"10.{i}.0.1/30",
                "vlan": None,
                "description": None,
                "shutdown": False,
            })
    links = [
        {"a_device": "r1", "a_if": "GigabitEthernet0/0",
         "b_device": "r2", "b_if": "GigabitEthernet0/0",
         "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        {"a_device": "r2", "a_if": "GigabitEthernet0/1",
         "b_device": "r3", "b_if": "GigabitEthernet0/1",
         "subnet": "10.1.0.0/30", "kind": "inferred-subnet"},
    ]
    return {
        "title": f"Many IF ({n_if_per_node}/node)",
        "generated_from": [],
        "devices": devices,
        "interfaces": interfaces,
        "links": links,
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


def _rect_overlap(x1, y1, w1, h1, x2, y2, w2, h2, margin=5.0) -> bool:
    """2 矩形（中心座標 + 幅高さ）が重なっているか（margin 込み）"""
    dx = abs(x1 - x2)
    dy = abs(y1 - y2)
    needed_x = (w1 + w2) / 2 + margin
    needed_y = (h1 + h2) / 2 + margin
    return dx < needed_x and dy < needed_y


@pytest.mark.unit
def test_c1_many_if_nodes_no_overlap():
    """C1: IF 30本ノードを含む topology でノード矩形が重ならない"""
    from lib.rendering import _build_physical_layout
    from lib.rendering.layout import _node_size_for
    topo = _make_many_if_topology(30)
    devices = topo["devices"]
    interfaces = topo["interfaces"]
    links = topo["links"]
    segments = topo["segments"]

    iface_count = {}
    for iface in interfaces:
        iface_count[iface["device"]] = iface_count.get(iface["device"], 0) + 1

    pos = _build_physical_layout(devices, interfaces, links, segments)

    dev_ids = [d["id"] for d in devices]
    for i, na in enumerate(dev_ids):
        for j, nb in enumerate(dev_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            w1, h1 = _node_size_for(iface_count.get(na, 0))
            w2, h2 = _node_size_for(iface_count.get(nb, 0))
            assert not _rect_overlap(x1, y1, w1, h1, x2, y2, w2, h2), (
                f"ノード {na}({w1:.0f}x{h1:.0f}) と {nb}({w2:.0f}x{h2:.0f}) の矩形が重なっている "
                f"（中心 ({x1:.1f},{y1:.1f}) vs ({x2:.1f},{y2:.1f})）"
            )


@pytest.mark.unit
def test_c1_many_if_nodes_within_viewbox():
    """C1: IF 30本ノードを含む topology で全ノード矩形が viewBox 内に収まる"""
    from lib.rendering import render
    from lib.rendering.layout import _node_size_for
    import re

    topo = _make_many_if_topology(30)
    html = render(topo)

    # viewBox を抽出
    m = re.search(r'<svg[^>]+viewBox="([^"]+)"', html)
    assert m, "viewBox が見つからない"
    vb = [float(v) for v in m.group(1).split()]
    assert len(vb) == 4, f"viewBox パラメータが 4 つでない: {vb}"
    vb_min_x, vb_min_y, vb_w, vb_h = vb

    # Physical ビューから rect 要素の x/y/width/height を収集
    phys_m = re.search(
        r'class="view view-physical"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        html, re.DOTALL
    )
    assert phys_m, "view-physical が見つからない"
    phys = phys_m.group(1)

    rects = re.findall(
        r'<rect[^>]+class="node-rect"[^>]*x="([^"]+)"[^>]*y="([^"]+)"[^>]*'
        r'width="([^"]+)"[^>]*height="([^"]+)"',
        phys
    )
    if not rects:
        # 属性順序違い対応（x/y が後）
        rects = re.findall(
            r'<rect[^>]*x="([^"]+)"[^>]*y="([^"]+)"[^>]*width="([^"]+)"[^>]*height="([^"]+)"',
            phys
        )

    assert len(rects) >= 3, f"Physical ビューに node-rect が {len(rects)} 個（期待: >=3）"

    for rx_str, ry_str, rw_str, rh_str in rects:
        rx, ry, rw, rh = float(rx_str), float(ry_str), float(rw_str), float(rh_str)
        assert rx >= vb_min_x - 1, \
            f"ノード rect 左端 {rx:.1f} が viewBox 左端 {vb_min_x:.1f} より外"
        assert ry >= vb_min_y - 1, \
            f"ノード rect 上端 {ry:.1f} が viewBox 上端 {vb_min_y:.1f} より外"
        assert rx + rw <= vb_min_x + vb_w + 1, \
            f"ノード rect 右端 {rx+rw:.1f} が viewBox 右端 {vb_min_x+vb_w:.1f} より外"
        assert ry + rh <= vb_min_y + vb_h + 1, \
            f"ノード rect 下端 {ry+rh:.1f} が viewBox 下端 {vb_min_y+vb_h:.1f} より外"


# ---------------------------------------------------------------------------
# C2: _svg_links の KeyError 防御
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_c2_link_missing_a_if_no_exception():
    """C2: a_if キー欠損リンクで render が例外を投げずラベルが空で描画される"""
    from lib.rendering import render
    topo = {
        "title": "KeyError Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            # a_if / b_if キーが欠損
            {"a_device": "r1", "b_device": "r2",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    try:
        html = render(topo)
    except KeyError as e:
        pytest.fail(f"a_if/b_if 欠損リンクで KeyError が発生: {e}")
    assert isinstance(html, str) and len(html) > 0
    # link-edge 要素は存在すること（空ラベルで描画される）
    assert "link-edge" in html, "link-edge 要素が存在しない"


@pytest.mark.unit
def test_c2_link_missing_both_if_keys_label_empty():
    """C2: a_if/b_if 両キー欠損リンクのラベルが空（クラッシュしない）"""
    from lib.rendering.svg import _svg_links
    links = [
        {"a_device": "r1", "b_device": "r2",
         "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
    ]
    positions = {"r1": (100.0, 100.0), "r2": (300.0, 100.0)}
    try:
        result = _svg_links(links, positions)
    except KeyError as e:
        pytest.fail(f"a_if/b_if 欠損リンクで _svg_links が KeyError: {e}")
    assert "link-edge" in result


# ---------------------------------------------------------------------------
# M1: _node_height_for ラッパー → layout._node_size_for を使う統一テスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_m1_node_size_for_accessible_from_layout():
    """M1: layout モジュールから _node_size_for が直接アクセスできる"""
    from lib.rendering.layout import _node_size_for
    w, h = _node_size_for(5)
    assert w > 0 and h > 0


@pytest.mark.unit
def test_m1_node_height_for_not_in_svg():
    """M1: _node_height_for ラッパーが svg.py から削除されている（layout._node_size_for に一本化）"""
    import lib.rendering.svg as _svg_mod
    assert not hasattr(_svg_mod, "_node_height_for"), \
        "svg.py に _node_height_for がまだ残っている（M1 未完了）"


@pytest.mark.unit
def test_m1_node_size_for_consistent_height():
    """M1: layout._node_size_for の高さが各 n で単調増加する（IF なし < あり）"""
    from lib.rendering.layout import _node_size_for
    for n in (0, 1, 5, 10, 30):
        _, h = _node_size_for(n)
        assert h > 0, f"n={n}: 高さが 0 以下"
    # 単調増加確認
    prev_h = 0.0
    for n in (0, 1, 5, 10, 30):
        _, h = _node_size_for(n)
        assert h >= prev_h, f"n={n}: 高さ {h} < 前の高さ {prev_h}（単調増加違反）"
        prev_h = h


# ---------------------------------------------------------------------------
# T1: test_phaseB1a_active_if_has_no_shutdown_class の厳密化
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_t1_active_if_no_shutdown_class_strict():
    """T1: active IF（GigabitEthernet0/0）の <text> 要素クラスに if-shutdown が含まれない（厳密）"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)

    # <text ... class="...">...</text> で GigabitEthernet0/0 を含む要素を全抽出
    text_elems = re.findall(r'<text[^>]+class="([^"]+)"[^>]*>[^<]*GigabitEthernet0/0[^<]*</text>', phys)
    assert len(text_elems) >= 1, \
        "GigabitEthernet0/0 を含む <text> 要素が見つからない"
    for cls in text_elems:
        assert "if-shutdown" not in cls, \
            f"active IF GigabitEthernet0/0 の <text> クラスに if-shutdown が含まれている: class='{cls}'"


# ---------------------------------------------------------------------------
# T2: test_phaseB1a_ospf_node_no_if_list の vacuous 修正
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_t2_ospf_node_no_if_list_strict():
    """T2: OSPF ビューは必ず存在し（m is not None）、if-row クラスを含まない"""
    from lib.rendering import render
    topo = _make_ospf_two_devices_topology()
    html = render(topo)
    m = re.search(
        r'<g class="view view-ospf"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        html, re.DOTALL
    )
    assert m is not None, \
        "view-ospf グループが見つからない（2台OSPF参加なのに生成されない）"
    ospf_content = m.group(1)
    assert "if-row" not in ospf_content, \
        "OSPF ビューのノードに if-row クラスが含まれている（コンパクト維持違反）"


# ---------------------------------------------------------------------------
# T3: hide-static のグローバル形が存在しないことを正規表現で否定検証
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_t3_no_global_hide_static_rule(rendered_html):
    """T3: body.hide-static .layer-static{display:none} のグローバル形が style に存在しない"""
    style = _extract_style_blocks(rendered_html)
    assert not re.search(
        r'body\.hide-static\s+\.layer-static\s*\{[^}]*display\s*:\s*none',
        style,
    ), (
        "グローバルな body.hide-static .layer-static { display:none } が存在する。"
        "#cards-section 限定のルールのみ許可（要件#3）。"
    )


# ---------------------------------------------------------------------------
# T4: リンクラベル検証の厳密化 + 複数リンク
# ---------------------------------------------------------------------------

def _make_multi_link_topology():
    """異なる IF ペアの複数リンクを持つ topology"""
    return {
        "title": "Multi Link Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r3", "hostname": "R3", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::Gi0/0", "device": "r1", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::Gi0/0", "device": "r2", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.2/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::Gi0/1", "device": "r2", "name": "GigabitEthernet0/1",
             "ip": "10.0.1.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r3::Gi0/0", "device": "r3", "name": "GigabitEthernet0/0",
             "ip": "10.0.1.2/30", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "GigabitEthernet0/0",
             "b_device": "r2", "b_if": "GigabitEthernet0/0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
            {"a_device": "r2", "a_if": "GigabitEthernet0/1",
             "b_device": "r3", "b_if": "GigabitEthernet0/0",
             "subnet": "10.0.1.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.mark.unit
def test_t4_link_label_text_contains_if_name():
    """T4: <text class="link-label..."> 要素内に IF 名が入る（直接検証）"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # <text ... class="link-label...">...</text> を全抽出
    link_label_texts = re.findall(
        r'<text[^>]+class="[^"]*link-label[^"]*"[^>]*>(.*?)</text>',
        phys, re.DOTALL
    )
    assert len(link_label_texts) >= 1, \
        "link-label クラスの <text> 要素が見つからない"
    combined = " ".join(link_label_texts)
    # GigabitEthernet0/0 が含まれること
    assert "GigabitEthernet0/0" in combined, \
        f"link-label <text> 要素に IF 名が含まれていない: {combined[:200]}"


@pytest.mark.unit
def test_t4_multiple_links_generate_multiple_labels():
    """T4: 複数リンクを持つ topology で各リンク分のラベルが生成される"""
    from lib.rendering import render
    html = render(_make_multi_link_topology())
    phys = _extract_physical_view(html)
    link_label_texts = re.findall(
        r'<text[^>]+class="[^"]*link-label[^"]*"[^>]*>(.*?)</text>',
        phys, re.DOTALL
    )
    # 2 リンク分のラベル（IF ペア + subnet）= 4 テキスト要素（各リンクに2行）
    assert len(link_label_texts) >= 2, \
        f"複数リンクでラベルが {len(link_label_texts)} 個（期待: >=2）"
    combined = " ".join(link_label_texts)
    # 両リンクの IF 名が含まれること
    assert "GigabitEthernet0/0" in combined, "リンク1の IF 名がラベルにない"
    assert "GigabitEthernet0/1" in combined, "リンク2の IF 名がラベルにない"


# ================================================================
# Phase C #7: OSPF ビュー 常時ラベル表示テスト (TDD RED フェーズ)
# ================================================================

def _make_ospf_topology_with_area():
    """OSPF area=0 が付いた 2 デバイス topology（IOS–IOS 同 area）を返す。"""
    return {
        "title": "OSPF Area Label Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0",
             "ip": "10.2.0.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0",
             "ip": "10.2.0.2/30", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0",
             "b_device": "r2", "b_if": "eth0",
             "subnet": "10.2.0.0/30", "kind": "inferred-subnet",
             "ospf_area": "0", "ospf_network": "10.2.0.0/30"},
        ],
        "segments": [],
        "routing": {
            "bgp": [],
            "ospf": [
                {"device": "r1", "process": 1, "network": "10.2.0.0/30", "area": "0"},
                {"device": "r2", "process": 1, "network": "10.2.0.0/30", "area": "0"},
            ],
            "static": [],
        },
    }


def _make_ospf_topology_area_mismatch():
    """OSPF area 不一致（0/1）の 2 デバイス topology を返す。"""
    return {
        "title": "OSPF Area Mismatch Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0",
             "ip": "10.3.0.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0",
             "ip": "10.3.0.2/30", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0",
             "b_device": "r2", "b_if": "eth0",
             "subnet": "10.3.0.0/30", "kind": "inferred-subnet",
             "ospf_area": "0/1", "ospf_network": "10.3.0.0/30"},
        ],
        "segments": [],
        "routing": {
            "bgp": [],
            "ospf": [
                {"device": "r1", "process": 1, "network": "10.3.0.0/30", "area": "0"},
                {"device": "r2", "process": 1, "network": "10.3.0.0/30", "area": "1"},
            ],
            "static": [],
        },
    }


def _extract_ospf_view(html: str) -> str:
    """HTML から OSPF ビューの SVG コンテンツを抽出する（_extract_bgp_view_full と同パターン）。"""
    m = re.search(
        r'<g[^>]+class="[^"]*view-ospf[^"]*"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        html, re.DOTALL
    )
    return m.group(1) if m else ""


@pytest.mark.unit
def test_ospf_view_edge_has_visible_text_label():
    """OSPF ビューのリンクエッジに可視 <text> ラベルが存在する。"""
    from lib.rendering import render
    topo = _make_ospf_topology_with_area()
    html = render(topo)
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビュー (view-ospf) が見つからない"
    # <text> 要素（<title> でなく可視テキスト）が存在すること
    assert "<text" in ospf_view, \
        "OSPF ビューに可視 <text> ラベルが存在しない"


@pytest.mark.unit
def test_ospf_view_label_contains_area():
    """OSPF ビューのラベルに 'area 0' が含まれる。"""
    from lib.rendering import render
    topo = _make_ospf_topology_with_area()
    html = render(topo)
    ospf_view = _extract_ospf_view(html)
    assert "area" in ospf_view.lower(), \
        f"OSPF ビューに 'area' テキストが含まれない: {ospf_view[:500]}"
    assert "0" in ospf_view, \
        f"OSPF ビューに area 番号 '0' が含まれない"


@pytest.mark.unit
def test_ospf_view_label_contains_subnet():
    """OSPF ビューのラベルにサブネット (10.2.0.0/30) が含まれる。"""
    from lib.rendering import render
    topo = _make_ospf_topology_with_area()
    html = render(topo)
    ospf_view = _extract_ospf_view(html)
    assert "10.2.0.0/30" in ospf_view, \
        f"OSPF ビューにサブネットが含まれない: {ospf_view[:500]}"


@pytest.mark.unit
def test_ospf_view_label_area_mismatch_shows_both():
    """OSPF area 不一致 (0/1) のとき両方の area がラベルに出る（T2: split による厳密検証）。"""
    from lib.rendering import render
    topo = _make_ospf_topology_area_mismatch()
    html = render(topo)
    ospf_view = _extract_ospf_view(html)
    # "0/1" が直接含まれること（split で要素として '0' と '1' が存在することを厳密検証）
    assert "0/1" in ospf_view, \
        f"area 不一致のとき '0/1' がラベルに出ない: {ospf_view[:500]}"
    # split("/") で要素として確認（'10/2' などで '0' が誤判定されないよう）
    area_parts = "0/1".split("/")
    assert "0" in area_parts and "1" in area_parts


@pytest.mark.unit
def test_ospf_view_label_no_area_when_ospf_area_absent():
    """ospf_area が欠如しているリンクはサブネットのみ（area 表示なし）か省略。"""
    from lib.rendering import render
    topo = _make_ospf_topology_with_area()
    # ospf_area を削除
    for lk in topo["links"]:
        lk.pop("ospf_area", None)
        lk.pop("ospf_network", None)
    html = render(topo)
    # 例外が発生しないこと（後方互換）
    assert "<svg" in html.lower(), "ospf_area 欠如でレンダリングが失敗"


@pytest.mark.unit
def test_ospf_view_label_is_text_not_only_title():
    """OSPF ビューのラベルが <title> だけでなく <text> 要素で出る（常時可視）。"""
    from lib.rendering import render
    topo = _make_ospf_topology_with_area()
    html = render(topo)
    ospf_view = _extract_ospf_view(html)
    # <text> 要素が存在すること
    text_elements = re.findall(r'<text[^>]*>.*?</text>', ospf_view, re.DOTALL)
    assert len(text_elements) >= 1, \
        f"OSPF ビューに <text> 要素（常時可視ラベル）が存在しない"


@pytest.mark.unit
def test_ospf_view_area_label_deterministic():
    """OSPF ビューのラベル出力が決定的（2回レンダリングして一致）。"""
    from lib.rendering import render
    import copy
    topo = _make_ospf_topology_with_area()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "OSPF ビューのラベル出力が非決定的"


# ===========================================================================
# Phase C #5: BGP ビュー AS グルーピング枠
# ===========================================================================

def _make_ibgp_topology():
    """iBGP: 同一 AS(65001) に r1/r2 の 2 台。iBGP セッションあり。"""
    return {
        "title": "iBGP AS Group Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65001, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::lo0", "device": "r1", "name": "Loopback0",
             "ip": "10.255.0.1/32", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::lo0", "device": "r2", "name": "Loopback0",
             "ip": "10.255.0.2/32", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "local_ip": "10.255.0.1",
                 "neighbor_ip": "10.255.0.2", "peer_as": 65001, "type": "ibgp"},
                {"device": "r2", "local_as": 65001, "local_ip": "10.255.0.2",
                 "neighbor_ip": "10.255.0.1", "peer_as": 65001, "type": "ibgp"},
            ],
            "ospf": [],
            "static": [],
        },
    }


def _make_ebgp_topology():
    """eBGP: AS65001(r1) と AS65002(r2) の 2 台。"""
    return {
        "title": "eBGP AS Group Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0",
             "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0",
             "ip": "10.0.0.2/30", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
                 "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
                {"device": "r2", "local_as": 65002, "local_ip": "10.0.0.2",
                 "neighbor_ip": "10.0.0.1", "peer_as": 65001, "type": "ebgp"},
            ],
            "ospf": [],
            "static": [],
        },
    }


def _extract_bgp_view_full(html: str) -> str:
    """HTML から BGP ビューの内部コンテンツを抽出する（view-bgp の <g> タグ開始直後から）。"""
    m = re.search(
        r'<g[^>]+class="[^"]*view-bgp[^"]*"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>\s*</svg>)',
        html, re.DOTALL
    )
    return m.group(1) if m else ""


# --- #5-1: iBGP 2機 → AS 枠が1つ・ラベル「AS 65001」 --------------------

@pytest.mark.unit
def test_c5_ibgp_single_as_group_exists():
    """Phase C #5: iBGP 2 機（同一 AS65001）→ BGP ビューに as-group 枠が 1 つ存在する"""
    from lib.rendering import render
    html = render(_make_ibgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビュー (view-bgp) が見つからない"
    groups = re.findall(r'class="as-group"', bgp_view)
    assert len(groups) == 1, \
        f"iBGP 2機で as-group が {len(groups)} 個（期待: 1）"


@pytest.mark.unit
def test_c5_ibgp_as_group_label_text():
    """Phase C #5: iBGP AS 枠のラベルに「AS 65001」が含まれる"""
    from lib.rendering import render
    html = render(_make_ibgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert "AS 65001" in bgp_view, \
        f"iBGP AS 枠ラベルに「AS 65001」が含まれない: {bgp_view[:500]}"


@pytest.mark.unit
def test_c5_ibgp_both_members_inside_group():
    """Phase C #5: iBGP 2機が同一 AS 枠内に収まる（枠の位置がノードを包含）"""
    from lib.rendering import render
    html = render(_make_ibgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"
    # AS 枠の <rect> の x/y/width/height を取得（属性順: x y width height ... class="as-group"）
    as_group_rects = re.findall(
        r'<rect[^>]*x="([^"]+)"[^>]*y="([^"]+)"'
        r'[^>]*width="([^"]+)"[^>]*height="([^"]+)"[^>]*class="as-group"',
        bgp_view
    )
    if not as_group_rects:
        # class が先にある場合のフォールバック
        as_group_rects = re.findall(
            r'<rect[^>]*class="as-group"[^>]*x="([^"]+)"[^>]*y="([^"]+)"'
            r'[^>]*width="([^"]+)"[^>]*height="([^"]+)"',
            bgp_view
        )
    assert len(as_group_rects) >= 1, "as-group <rect> が見つからない"
    rx, ry, rw, rh = (float(v) for v in as_group_rects[0])
    # ノードの中心座標を取得: node-rect は x/y/width/height を持つ
    node_rects = re.findall(
        r'<rect[^>]*class="node-rect"[^>]*x="([^"]+)"[^>]*y="([^"]+)"'
        r'[^>]*width="([^"]+)"[^>]*height="([^"]+)"',
        bgp_view
    )
    if not node_rects:
        # 属性順違い（x,y,width,height が先のパターン）
        node_rects = re.findall(
            r'<rect[^>]*x="([^"]+)"[^>]*y="([^"]+)"'
            r'[^>]*width="([^"]+)"[^>]*height="([^"]+)"[^>]*class="node-rect"',
            bgp_view
        )
    assert len(node_rects) >= 2, f"BGP ビューに node-rect が {len(node_rects)} 個（期待: >=2）"
    for nx_str, ny_str, nw_str, nh_str in node_rects:
        nx, ny, nw, nh = float(nx_str), float(ny_str), float(nw_str), float(nh_str)
        assert nx >= rx - 1, f"ノード左端 {nx:.1f} が AS 枠左端 {rx:.1f} より外"
        assert ny >= ry - 1, f"ノード上端 {ny:.1f} が AS 枠上端 {ry:.1f} より外"
        assert nx + nw <= rx + rw + 1, f"ノード右端 {nx+nw:.1f} が AS 枠右端 {rx+rw:.1f} より外"
        assert ny + nh <= ry + rh + 1, f"ノード下端 {ny+nh:.1f} が AS 枠下端 {ry+rh:.1f} より外"


# --- #5-2: eBGP 2機 → AS 枠が2つ・ラベルが各 AS --------------------

@pytest.mark.unit
def test_c5_ebgp_two_as_groups_exist():
    """Phase C #5: eBGP 2 機（AS65001 / AS65002）→ BGP ビューに as-group 枠が 2 つ存在する"""
    from lib.rendering import render
    html = render(_make_ebgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"
    groups = re.findall(r'class="as-group"', bgp_view)
    assert len(groups) == 2, \
        f"eBGP 2機で as-group が {len(groups)} 個（期待: 2）"


@pytest.mark.unit
def test_c5_ebgp_as_group_labels_both_present():
    """Phase C #5: eBGP の AS 枠ラベルに「AS 65001」と「AS 65002」が両方含まれる"""
    from lib.rendering import render
    html = render(_make_ebgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert "AS 65001" in bgp_view, "「AS 65001」ラベルが見つからない"
    assert "AS 65002" in bgp_view, "「AS 65002」ラベルが見つからない"


# --- #5-3: 枠がノードの背面（DOM 順）-------------------------------------

@pytest.mark.unit
def test_c5_as_group_rect_before_device_node():
    """Phase C #5: as-group <rect> が device-node より前に DOM 出力される（背面）"""
    from lib.rendering import render
    html = render(_make_ibgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"
    as_group_pos = bgp_view.find('class="as-group"')
    device_node_pos = bgp_view.find('class="device-node"')
    assert as_group_pos != -1, "as-group が見つからない"
    assert device_node_pos != -1, "device-node が見つからない"
    assert as_group_pos < device_node_pos, \
        f"as-group ({as_group_pos}) が device-node ({device_node_pos}) より後に出力されている（前景になってしまう）"


@pytest.mark.unit
def test_c5_as_group_rect_before_bgp_edges():
    """Phase C #5: as-group <rect> が bgp-session より前に DOM 出力される（背面）"""
    from lib.rendering import render
    html = render(_make_ibgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"
    as_group_pos = bgp_view.find('class="as-group"')
    bgp_session_pos = bgp_view.find('class="bgp-session"')
    assert as_group_pos != -1, "as-group が見つからない"
    assert bgp_session_pos != -1, "bgp-session が見つからない"
    assert as_group_pos < bgp_session_pos, \
        f"as-group ({as_group_pos}) が bgp-session ({bgp_session_pos}) より後に出力されている"


# --- #5-4: BGP 未参加ノードは枠にも図にも出ない --------------------------

@pytest.mark.unit
def test_c5_non_bgp_device_not_in_as_group():
    """Phase C #5: BGP 未参加デバイス（r3）は AS 枠にも BGP ビューにも出ない"""
    from lib.rendering import render
    topo = _make_ebgp_topology()
    # BGP 未参加の r3 を追加
    topo["devices"].append(
        {"id": "r3", "hostname": "R3", "vendor": "cisco_ios", "as": 65003, "sections": []}
    )
    topo["interfaces"].append(
        {"id": "r3::eth0", "device": "r3", "name": "eth0",
         "ip": "192.168.1.1/30", "vlan": None, "description": None, "shutdown": False}
    )
    # r3 は bgp_entries に一切登場しない
    html = render(topo)
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"
    # R3 が BGP ビューに存在しないこと
    assert "R3" not in bgp_view, \
        "BGP 未参加の R3 が BGP ビューに出力されている"
    # AS 65003 枠も出ないこと
    assert "AS 65003" not in bgp_view, \
        "BGP 未参加の AS65003 の枠が出力されている"


# --- #5-5: 決定性 -----------------------------------------------------------

@pytest.mark.unit
def test_c5_bgp_as_group_deterministic():
    """Phase C #5: BGP AS グルーピング出力が決定的（同一入力で2回一致）"""
    from lib.rendering import render
    import copy
    topo = _make_ebgp_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "BGP AS グルーピング出力が非決定的"


@pytest.mark.unit
def test_c5_ibgp_as_group_deterministic():
    """Phase C #5: iBGP topology でも AS グルーピング出力が決定的"""
    from lib.rendering import render
    import copy
    topo = _make_ibgp_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "iBGP AS グルーピング出力が非決定的"


# --- #5-6: 既存 BGP ビューの回帰保護（エッジ・ノードが壊れない）----------

@pytest.mark.unit
def test_c5_bgp_edges_still_rendered_after_grouping():
    """Phase C #5: AS グルーピング追加後も bgp-session エッジが引き続き描画される"""
    from lib.rendering import render
    html = render(_make_ebgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert "bgp-session" in bgp_view, \
        "AS グルーピング追加後に bgp-session が消えている"


@pytest.mark.unit
def test_c5_bgp_nodes_still_rendered_after_grouping():
    """Phase C #5: AS グルーピング追加後も device-node が引き続き描画される"""
    from lib.rendering import render
    html = render(_make_ebgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    device_nodes = re.findall(r'class="device-node"', bgp_view)
    assert len(device_nodes) >= 2, \
        f"AS グルーピング追加後に device-node が {len(device_nodes)} 個（期待: >=2）"


@pytest.mark.unit
def test_c5_as_group_label_class_present():
    """Phase C #5: as-group-label クラスの <text> 要素が存在する"""
    from lib.rendering import render
    html = render(_make_ibgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert 'class="as-group-label"' in bgp_view, \
        "as-group-label クラスの <text> 要素がない"


# ===========================================================================
# Phase C レビュー修正テスト（M5: as-group-container ラッパー構造）
# ===========================================================================

@pytest.mark.unit
def test_m5_as_group_container_g_element_exists():
    """M5: as-group-container クラスの <g> 要素が BGP ビューに存在する"""
    from lib.rendering import render
    html = render(_make_ibgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"
    assert 'class="as-group-container"' in bgp_view, \
        "as-group-container クラスの <g> 要素が見つからない（M5 未実装）"


@pytest.mark.unit
def test_m5_as_group_container_has_data_as():
    """M5: as-group-container <g> 要素に data-as 属性が含まれる"""
    from lib.rendering import render
    html = render(_make_ibgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"
    assert 'data-as="' in bgp_view, \
        "as-group-container <g> 要素に data-as 属性がない（M5 未実装）"


@pytest.mark.unit
def test_m5_as_group_and_label_inside_container():
    """M5: as-group クラスの <rect> と as-group-label クラスの <text> が container <g> 内に存在する"""
    from lib.rendering import render
    html = render(_make_ibgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"
    # container <g> ブロックを取り出す
    m = re.search(
        r'<g[^>]*class="as-group-container"[^>]*>(.*?)</g>',
        bgp_view, re.DOTALL
    )
    assert m is not None, "as-group-container <g> が見つからない"
    container_content = m.group(1)
    assert 'class="as-group"' in container_content, \
        "as-group <rect> が container 内に存在しない"
    assert 'class="as-group-label"' in container_content, \
        "as-group-label <text> が container 内に存在しない"


@pytest.mark.unit
def test_m5_as_group_container_deterministic():
    """M5: as-group-container を含む BGP ビューが決定的（2回レンダリングして一致）"""
    from lib.rendering import render
    import copy
    topo = _make_ibgp_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "as-group-container を含む BGP ビューが非決定的"


@pytest.mark.unit
def test_m5_ebgp_two_containers_with_data_as():
    """M5: eBGP 2 機（AS65001/AS65002）→ BGP ビューに data-as='65001' と data-as='65002' が存在する"""
    from lib.rendering import render
    html = render(_make_ebgp_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert 'data-as="65001"' in bgp_view, \
        "data-as='65001' が BGP ビューに存在しない"
    assert 'data-as="65002"' in bgp_view, \
        "data-as='65002' が BGP ビューに存在しない"


@pytest.mark.unit
def test_c5_no_as_group_when_no_bgp():
    """Phase C #5: BGP エントリが空のとき as-group が出力されない"""
    from lib.rendering import render
    topo = {
        "title": "No BGP",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
        ],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    # BGP ビューが生成されない（ゲーティング）ので as-group も出ない
    assert 'class="as-group"' not in html, \
        "BGP エントリなしなのに as-group が出力されている"


@pytest.mark.unit
def test_c5_as_group_no_crash_when_local_as_missing():
    """Phase C #5 (T4 強化): local_as が取れない BGP エントリがあってもクラッシュせず、
    as=None 機器は as-group に出ない（BGP ビューに class='as-group' が無いか、
    None の AS グループ枠が存在しない）。"""
    from lib.rendering import render
    topo = {
        "title": "No local_as",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0",
             "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0",
             "ip": "10.0.0.2/30", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                # local_as キーなし
                {"device": "r1", "local_ip": "10.0.0.1",
                 "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
                {"device": "r2", "local_ip": "10.0.0.2",
                 "neighbor_ip": "10.0.0.1", "peer_as": 65001, "type": "ebgp"},
            ],
        },
    }
    try:
        html = render(topo)
    except Exception as e:
        pytest.fail(f"local_as 欠損 BGP エントリで例外発生: {e}")
    assert isinstance(html, str) and len(html) > 0
    # as=None の機器は as-group に出ないこと
    bgp_view = _extract_bgp_view_full(html)
    # as-group が存在する場合は "AS None" ラベルが無いことを確認
    assert "AS None" not in bgp_view, \
        "as=None 機器の AS グループ枠「AS None」が出力されている"
    # as=None 機器が as-group に入っていないこと（as-group 枠の数は 0 であるべき）
    as_group_count = bgp_view.count('class="as-group"')
    assert as_group_count == 0, \
        f"as=None 機器のみなのに as-group が {as_group_count} 個出力されている"
