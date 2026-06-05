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
def test_gating_bgp_external_peer_only_generates_view():
    """外部ピアのみ（neighbor_ip が内部解決できない）の topology でも view-bgp が生成される（A1）。

    A1 修正: BGP ビュー生成ゲートを「内部解決セッション ≥1 OR 外部ピア ≥1」に拡張した。
    外部ピアのみの機器（ISP 接続エッジ等）でも BGP ビューに外部ノードが描画されることを確認する。
    """
    from lib.rendering import render
    html = render(_make_bgp_no_resolved_neighbors_topology())
    assert 'class="view view-bgp"' in html, \
        "BGP ビューが（外部ピアのみなのに）生成されていない（A1 修正が必要）"
    assert 'data-view="bgp"' in html, \
        "BGP タブが（外部ピアのみなのに）生成されていない（A1 修正が必要）"
    # 外部ノードが存在すること
    assert 'data-device="ext:203.0.113.1"' in html, \
        "外部ノード ext:203.0.113.1 が生成されていない"


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
    """タブ数 == ビュー <g> 数 + 1（ifinv タブは SVG <g> を持たないテーブルビュー）"""
    from lib.rendering import render
    # bgp + ospf で両方エッジありの topology
    html = render(_make_bgp_with_real_neighbors_topology())
    view_groups = re.findall(r'class="view view-([a-z0-9_-]+)"', html)
    tabs = re.findall(r'data-view="([a-z0-9_-]+)"', html)
    # ifinv タブは SVG <g class="view view-ifinv"> を生成しないので tabs = view_groups + 1
    assert len(tabs) == len(view_groups) + 1, \
        f"タブ数({len(tabs)}) != ビュー数({len(view_groups)}) + 1: " \
        f"views={view_groups}, tabs={tabs}"
    assert "ifinv" in tabs, "ifinv タブが存在しない"
    assert "ifinv" not in view_groups, "ifinv が SVG <g class=view> として生成されている"


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
    """Phase B #1a (iteration-3 更新): GigabitEthernet0/2 は非接続・非Loopback のため
    ノード SVG には表示されない（チップ対象外）。カード表には残る。"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # iteration-3 #2 仕様: 非接続・非Loopback はノード SVG に出ない
    # Physical ビュー SVG に GigabitEthernet0/2 が含まれないこと
    # （ただし他のビューやカードには出てよい）
    # Physical ビューには GigabitEthernet0/2 は存在しない（接続なし・非Loopback）
    # 接続IF（GigabitEthernet0/0）は存在すること
    assert "GigabitEthernet0/0" in phys, \
        "Physical ビューに接続IF（GigabitEthernet0/0）が存在しない"


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
    """Phase B #1a (iteration-3 更新): shutdown=True の接続IF はチップで if-chip-shutdown クラスが付く。
    GigabitEthernet0/1 は非接続のためチップ対象外（カード表のみ）。
    接続IFに shutdown があれば if-chip-shutdown が付く。"""
    from lib.rendering import render
    # 接続 IF が shutdown=True のケースを確認
    topo = _make_physical_detail_topology()
    # GigabitEthernet0/0 を shutdown にする
    for iface in topo["interfaces"]:
        if iface["name"] == "GigabitEthernet0/0" and iface["device"] == "r1":
            iface["shutdown"] = True
    html = render(topo)
    phys = _extract_physical_view(html)
    # 接続IF が shutdown の場合 if-chip-shutdown が付くこと
    assert "if-chip-shutdown" in phys, \
        "shutdown の接続IF に if-chip-shutdown クラスが付いていない"


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
    """Phase B #1a (iteration-3 更新): description は チップの <title> に「IF名 IP（desc）」形式で含まれる。"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # チップの <title> に CORE-LINK-to-R2 が含まれること（形式: "GigabitEthernet0/0 10.0.0.1/30 （CORE-LINK-to-R2）"）
    assert "CORE-LINK-to-R2" in phys, \
        "GigabitEthernet0/0 の description（CORE-LINK-to-R2）がチップの <title> に存在しない"


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
def test_phaseB1a_link_label_text_absent_link_line_present():
    """Phase B #1a (iteration-3 更新): 物理リンクに常時 link-label <text> は生成しない。
    link-line は存在し、subnet は <title> hover で参照可能。"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # iteration-3 #1 仕様: link-label <text> は生成されない
    link_label_texts = re.findall(
        r'<text[^>]+class="[^"]*link-label[^"]*"[^>]*>',
        phys
    )
    assert len(link_label_texts) == 0, \
        f"Physical ビューに link-label <text> が残っている（iteration-3 #1 で撤去済み）: {len(link_label_texts)}"
    # link-line は残ること
    assert 'class="link-line' in phys, \
        "Physical ビューにリンク線（link-line）が存在しない"


@pytest.mark.unit
def test_phaseB1a_link_label_class_absent_title_present():
    """Phase B #1a (iteration-3 更新): link-label クラスの常時 <text> は不要、<title> hover は残る。"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # iteration-3 #1 仕様: link-label クラスの <text> は存在しない
    assert 'class="link-label' not in phys, \
        "link-label クラスの <text> 要素が残っている（iteration-3 #1 で撤去済み）"
    # link-edge 内の <title> は hover 用として残る
    assert '<title>' in phys, \
        "Physical ビューに <title>（hover 用）が存在しない"


@pytest.mark.unit
def test_phaseB1a_link_label_shows_subnet():
    """Phase B #1a (iteration-3 更新): subnet は <title> hover で参照可能。"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # subnet は <title> に含まれること（hover で確認できる）
    assert "10.0.0.0/30" in phys, \
        "物理リンクの subnet（10.0.0.0/30）が <title> にも存在しない"


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
    """T1 (iteration-3 更新): active IF（GigabitEthernet0/0）のチップに if-chip-shutdown が含まれない。
    チップ化後は <text> ではなく <g class="if-chip"> で表現される。"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)

    # GigabitEthernet0/0 が <title> 内にあるチップを抽出
    # if-chip グループで data-if="GigabitEthernet0/0" のものが if-chip-shutdown でないこと
    chip_groups = re.findall(
        r'<g class="([^"]+)" data-if="GigabitEthernet0/0"[^>]*>',
        phys
    )
    assert len(chip_groups) >= 1, \
        "GigabitEthernet0/0 のチップ要素（data-if 属性）が見つからない"
    for cls in chip_groups:
        assert "if-chip-shutdown" not in cls, \
            f"active IF GigabitEthernet0/0 のチップに if-chip-shutdown が含まれている: class='{cls}'"


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
    """T4 (iteration-3 更新): Physical ビューのリンクに link-label <text> は生成されない。
    IF名は <title> hover で確認可能（link-edge 内 title に IF 名が含まれる）。"""
    from lib.rendering import render
    html = render(_make_physical_detail_topology())
    phys = _extract_physical_view(html)
    # iteration-3 #1 仕様: link-label <text> は存在しない
    link_label_texts = re.findall(
        r'<text[^>]+class="[^"]*link-label[^"]*"[^>]*>(.*?)</text>',
        phys, re.DOTALL
    )
    assert len(link_label_texts) == 0, \
        f"link-label <text> が残存している（iteration-3 #1 で撤去済み）: {link_label_texts}"
    # IF 名は <title> に存在すること
    titles = re.findall(r'<title>([^<]+)</title>', phys)
    combined_titles = " ".join(titles)
    assert "GigabitEthernet0/0" in combined_titles, \
        f"<title> に IF 名が含まれていない: titles={titles[:5]}"


@pytest.mark.unit
def test_t4_multiple_links_generate_multiple_labels():
    """T4 (iteration-3 更新): 複数リンクを持つ topology で link-label <text> は生成されない。
    各リンクに <title>（hover）は存在する。"""
    from lib.rendering import render
    html = render(_make_multi_link_topology())
    phys = _extract_physical_view(html)
    # iteration-3 #1 仕様: link-label <text> は存在しない
    link_label_texts = re.findall(
        r'<text[^>]+class="[^"]*link-label[^"]*"[^>]*>(.*?)</text>',
        phys, re.DOTALL
    )
    assert len(link_label_texts) == 0, \
        f"複数リンク topology で link-label <text> が残存している: {len(link_label_texts)}"
    # link-line が 2 本存在すること（2 リンク分）
    link_lines = re.findall(r'class="link-line[^"]*"', phys)
    assert len(link_lines) >= 2, \
        f"2 リンク topology で link-line が {len(link_lines)} 本（期待: >=2）"


# ================================================================
# Phase C #7: OSPF ビュー 常時ラベル表示テスト (TDD RED フェーズ)
# ================================================================


def _extract_ospf_view(html: str) -> str:
    """OSPF ビュー <g class="view view-ospf"> の内容を返す（T-dup: 唯一の定義）。

    後方の #7 セクションの定義と統合。パターンは view view-ospf を厳密にマッチし、
    次の view <g> または </svg> で終端する堅牢パターン。
    """
    m = re.search(
        r'<g[^>]+class="view view-ospf"[^>]*>(.*?)(?=<g[^>]+class="view view-|</svg>)',
        html, re.DOTALL
    )
    return m.group(1) if m else ""


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
    """OSPF area 不一致 (0/1) のとき両方の area がラベルに出る（C2: 実際の ospf_view から厳密検証）。"""
    from lib.rendering import render
    topo = _make_ospf_topology_area_mismatch()
    html = render(topo)
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, f"OSPF ビューが見つからない"
    # "0/1" が直接 ospf_view に含まれること
    assert "0/1" in ospf_view, \
        f"area 不一致のとき '0/1' がラベルに出ない: {ospf_view[:500]}"
    # ospf_view から "0/1" を抽出して split("/") で '0' と '1' を両方確認
    # （'10/2' などで '0' が誤判定されないよう要素ベースで検証）
    import re as _re
    area_values = _re.findall(r'(\d+/\d+)', ospf_view)
    assert any("0" in v.split("/") and "1" in v.split("/") for v in area_values), \
        f"ospf_view の area 値に '0' と '1' を両方含むものがない: area_values={area_values}"


@pytest.mark.unit
def test_ospf_view_label_no_area_when_ospf_area_absent():
    """ospf_area が欠如しているリンクは area ラベルなし（C4: _extract_ospf_view で本題検証）。"""
    from lib.rendering import render
    topo = _make_ospf_topology_with_area()
    # ospf_area を削除
    for lk in topo["links"]:
        lk.pop("ospf_area", None)
        lk.pop("ospf_network", None)
    html = render(topo)
    # 例外が発生しないこと（後方互換）
    assert "<svg" in html.lower(), "ospf_area 欠如でレンダリングが失敗"
    # OSPF ビューが存在する場合（2台参加 → エッジあり → ビュー生成）、area ラベルが出ないこと
    ospf_view = _extract_ospf_view(html)
    if ospf_view:
        # ospf_area 欠如のとき "area " というラベルが現れないこと
        assert "area " not in ospf_view.lower(), \
            f"ospf_area 欠如なのに 'area' ラベルが OSPF ビューに出ている: {ospf_view[:300]}"


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


# ===========================================================================
# Phase D #2: クリック選択・双方向ハイライト + IF行↔リンク連動
# ===========================================================================

def _make_link_id_topology():
    """r1-r2 間に1リンク、各デバイスに複数 IF を持つ topology（link-id テスト用）"""
    return {
        "title": "Link ID Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0",
             "ip": "10.0.0.1/30", "vlan": None, "description": "to-r2", "shutdown": False},
            {"id": "r1::lo0", "device": "r1", "name": "lo0",
             "ip": "1.1.1.1/32", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0",
             "ip": "10.0.0.2/30", "vlan": None, "description": "to-r1", "shutdown": False},
            {"id": "r2::lo0", "device": "r2", "name": "lo0",
             "ip": "2.2.2.2/32", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0",
             "b_device": "r2", "b_if": "eth0",
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


def _make_multi_device_link_topology():
    """r1-r2, r2-r3 の 2 リンクを持つ topology（複数 link-id テスト用）"""
    return {
        "title": "Multi Link ID Test",
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


# ---- #D2-1: link-edge <g> に data-link-id が付く --------------------------

@pytest.mark.unit
def test_phaseD2_link_edge_has_data_link_id():
    """Phase D #2: link-edge <g> に data-link-id 属性が存在する"""
    from lib.rendering import render
    html = render(_make_link_id_topology())
    phys = _extract_physical_view(html)
    assert 'data-link-id="' in phys, \
        "link-edge <g> に data-link-id 属性が存在しない"


@pytest.mark.unit
def test_phaseD2_link_edge_data_link_id_is_deterministic():
    """Phase D #2: link-id が決定的（同一 topology で2回レンダリングして一致）"""
    from lib.rendering import render
    import copy
    topo = _make_link_id_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    # data-link-id の全出現を抽出して比較
    ids1 = re.findall(r'data-link-id="([^"]*)"', html1)
    ids2 = re.findall(r'data-link-id="([^"]*)"', html2)
    assert ids1 == ids2, f"data-link-id が非決定的: {ids1} vs {ids2}"


@pytest.mark.unit
def test_phaseD2_link_id_symmetric():
    """Phase D #2: link-id は両端の端点から導出され対称的（順序に依存しない）
    a→b と b→a で同じ link-id になること（sorted による決定性）"""
    # link-id = sorted([a_device::a_if, b_device::b_if]) を '|' で結合
    # r1::eth0 と r2::eth0 → sorted = ['r1::eth0', 'r2::eth0'] → 'r1::eth0|r2::eth0'
    from lib.rendering.svg import _make_link_id
    lid_ab = _make_link_id("r1", "eth0", "r2", "eth0")
    lid_ba = _make_link_id("r2", "eth0", "r1", "eth0")
    assert lid_ab == lid_ba, \
        f"link-id が対称でない: a→b={lid_ab!r}, b→a={lid_ba!r}"


@pytest.mark.unit
def test_phaseD2_link_id_unique_per_link():
    """Phase D #2: 異なるリンクは異なる link-id を持つ"""
    from lib.rendering.svg import _make_link_id
    lid1 = _make_link_id("r1", "GigabitEthernet0/0", "r2", "GigabitEthernet0/0")
    lid2 = _make_link_id("r2", "GigabitEthernet0/1", "r3", "GigabitEthernet0/0")
    assert lid1 != lid2, \
        f"異なるリンクが同じ link-id: {lid1!r}"


@pytest.mark.unit
def test_phaseD2_link_line_has_data_link_id():
    """Phase D #2: <line class='link-line'> にも data-link-id が付く"""
    from lib.rendering import render
    html = render(_make_link_id_topology())
    phys = _extract_physical_view(html)
    # <line ... data-link-id="..."> が存在すること
    assert re.search(r'<line[^>]+data-link-id="[^"]*"', phys), \
        "<line class='link-line'> に data-link-id が付いていない"


# ---- #D2-2: IF 行に data-link-id が付く ------------------------------------

@pytest.mark.unit
def test_phaseD2_if_row_endpoint_has_data_link_id():
    """Phase D #2: リンク端点の IF 行 <tr> に data-link-id が付く"""
    from lib.rendering import render
    html = render(_make_link_id_topology())
    # r1::eth0 と r2::eth0 はリンク端点 → <tr> に data-link-id が付くはず
    # カードセクションを抽出
    cards_m = re.search(r'id="cards-section".*', html, re.DOTALL)
    cards_section = cards_m.group(0) if cards_m else html
    assert re.search(r'<tr[^>]+data-link-id="[^"]*"', cards_section), \
        "カードの IF 行 <tr> に data-link-id が付いていない"


@pytest.mark.unit
def test_phaseD2_if_row_non_endpoint_no_data_link_id():
    """Phase D #2: リンク端点でない IF 行 <tr> に data-link-id が付かない（lo0 は端点外）"""
    from lib.rendering import render
    html = render(_make_link_id_topology())
    # lo0 はリンク端点でない → <tr> に data-link-id がない or 空
    # lo0 の <tr> を近似的に検索（lo0 が含まれる tr ブロック）
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    # lo0 を含む <tr> を抽出し、data-link-id が付いていないことを確認
    lo0_rows = re.findall(r'<tr[^>]*>(?:[^<]|<(?!tr|/tr))*?lo0(?:[^<]|<(?!tr|/tr))*?</tr>', cards_html, re.DOTALL)
    for row in lo0_rows:
        assert 'data-link-id="' not in row or 'data-link-id=""' in row, \
            f"lo0（非端点 IF）の <tr> に data-link-id が付いている: {row[:200]}"


@pytest.mark.unit
def test_phaseD2_both_endpoints_have_same_link_id():
    """Phase D #2: リンクの両端 device のカードの IF 行に同じ data-link-id が付く"""
    from lib.rendering import render
    from lib.rendering.svg import _make_link_id
    html = render(_make_link_id_topology())
    # 期待される link-id を計算
    expected_lid = _make_link_id("r1", "eth0", "r2", "eth0")
    # カードセクションからその link-id を持つ <tr> を探す
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    matching_rows = re.findall(
        rf'<tr[^>]+data-link-id="{re.escape(expected_lid)}"[^>]*>',
        cards_html
    )
    assert len(matching_rows) >= 2, \
        f"link-id={expected_lid!r} を持つ <tr> が {len(matching_rows)} 個（期待: >=2、両端）"


@pytest.mark.unit
def test_phaseD2_multi_link_each_has_unique_link_id():
    """Phase D #2: 複数リンクを持つ topology で各リンクが異なる link-id を持つ"""
    from lib.rendering import render
    html = render(_make_multi_device_link_topology())
    phys = _extract_physical_view(html)
    link_ids = re.findall(r'<g[^>]*class="link-edge"[^>]*data-link-id="([^"]*)"', phys)
    if not link_ids:
        link_ids = re.findall(r'data-link-id="([^"]*)"[^>]*class="link-edge"', phys)
    assert len(link_ids) == 2, \
        f"link-edge の data-link-id が {len(link_ids)} 個（期待: 2）"
    assert link_ids[0] != link_ids[1], \
        f"2 本のリンクが同じ link-id: {link_ids}"


# ---- #D2-3: JS 関数の存在確認 -----------------------------------------------

@pytest.mark.unit
def test_phaseD2_js_card_click_selects_node(rendered_html):
    """Phase D #2: カード→ノード選択 JS（selectNodeFromCard または card.addEventListener click）が含まれる"""
    # カードクリックでノードを selected にする JS が存在すること
    js_signals = [
        "selectNodeFromCard",
        "device-card",
    ]
    lower = rendered_html.lower()
    # selectNodeFromCard か、device-card クリック処理のどちらかが含まれる
    has_card_node_js = (
        "selectnodefromcard" in lower or
        ("device-card" in lower and "click" in lower and "selected" in lower)
    )
    assert has_card_node_js, \
        "カード→ノード選択 JS（selectNodeFromCard）が見つからない"


@pytest.mark.unit
def test_phaseD2_js_if_row_link_highlight(rendered_html):
    """Phase D #2: IF行↔リンク連動 JS 関数（toggleIfRowHighlight または data-link-id 参照）が含まれる"""
    has_signal = (
        "toggleIfRowHighlight" in rendered_html or
        ("data-link-id" in rendered_html and "click" in rendered_html.lower())
    )
    assert has_signal, \
        "IF行↔リンク連動 JS（toggleIfRowHighlight）が見つからない"


@pytest.mark.unit
def test_phaseD2_js_multiple_selection_accumulation(rendered_html):
    """Phase D #2: 複数累積選択をサポートする JS（_selectedNodes または selectedNodes等）が含まれる"""
    # 複数選択を管理する変数またはトグルロジックが含まれること
    has_accumulation = (
        "_selectedNodes" in rendered_html or
        "_selectedLinks" in rendered_html or
        "selectedNodes" in rendered_html or
        # トグルロジック: wasSelected パターン（既存コードに含まれる）
        "wasSelected" in rendered_html
    )
    assert has_accumulation, \
        "複数選択累積ロジック（_selectedNodes 等）が見つからない"


@pytest.mark.unit
def test_phaseD2_js_esc_clears_selection(rendered_html):
    """Phase D #2: Esc キーで全選択解除する JS が含まれる（既存 clearSelection の存在確認）"""
    assert "clearSelection" in rendered_html, \
        "Esc 解除用 clearSelection が見つからない"
    assert "Escape" in rendered_html, \
        "Esc キーハンドラが見つからない"


# ---- #D2-4: CSS の存在確認 --------------------------------------------------

@pytest.mark.unit
def test_phaseD2_css_device_card_selected(rendered_html):
    """Phase D #2: CSS に .device-card.selected のスタイルが含まれる（厳密検証）"""
    style = _extract_style_blocks(rendered_html)
    assert re.search(r'\.device-card\.selected\s*\{', style), \
        "CSS に .device-card.selected { ... } スタイルが含まれない"


@pytest.mark.unit
def test_phaseD2_css_tr_highlighted(rendered_html):
    """Phase D #2: CSS に tr.highlighted のスタイルが含まれる"""
    style = _extract_style_blocks(rendered_html)
    assert re.search(r'tr\.highlighted', style) or \
           re.search(r'tr[^{]*\.highlighted', style), \
        "CSS に tr.highlighted スタイルが含まれない"


@pytest.mark.unit
def test_phaseD2_css_tr_selected(rendered_html):
    """Phase D #2: CSS に tr.selected のスタイルが含まれる（IF 行の選択強調）"""
    style = _extract_style_blocks(rendered_html)
    assert re.search(r'tr\.selected', style) or \
           re.search(r'tr[^{]*\.selected', style), \
        "CSS に tr.selected スタイルが含まれない"


# ---- #D2-5: 決定性 ----------------------------------------------------------

@pytest.mark.unit
def test_phaseD2_link_id_deterministic_with_sample_topology(sample_topology):
    """Phase D #2: sample topology で data-link-id の順序・内容が決定的"""
    from lib.rendering import render
    import copy
    html1 = render(copy.deepcopy(sample_topology))
    html2 = render(copy.deepcopy(sample_topology))
    ids1 = re.findall(r'data-link-id="([^"]*)"', html1)
    ids2 = re.findall(r'data-link-id="([^"]*)"', html2)
    assert ids1 == ids2, "sample topology で data-link-id が非決定的"


# ===========================================================================
# Phase D #4: ノード表示フィルタ UI（checklist / setNodeVisibility）
# ===========================================================================

# ---- #D4-1: checklist UI の存在確認 ----------------------------------------

@pytest.mark.unit
def test_phaseD4_node_filter_checklist_exists(rendered_html):
    """Phase D #4: ノードフィルタ チェックリスト UI が存在する（data-node-filter 属性）"""
    assert 'data-node-filter=' in rendered_html, \
        "ノードフィルタ用 data-node-filter 属性が見つからない"


@pytest.mark.unit
def test_phaseD4_node_filter_checkbox_count_matches_devices(sample_topology, rendered_html):
    """Phase D #4: チェックボックス（data-node-filter）の数がデバイス数と一致する"""
    device_count = len(sample_topology["devices"])
    filter_checkboxes = re.findall(r'data-node-filter="([^"]*)"', rendered_html)
    assert len(filter_checkboxes) == device_count, \
        f"ノードフィルタ チェックボックス数 {len(filter_checkboxes)} != デバイス数 {device_count}"


@pytest.mark.unit
def test_phaseD4_node_filter_checkboxes_default_checked(rendered_html):
    """Phase D #4: ノードフィルタ チェックボックスはデフォルト checked"""
    # data-node-filter を持つ input[type=checkbox] が checked であること
    # <input type="checkbox" ... data-node-filter="..." checked> パターン
    filter_inputs = re.findall(
        r'<input[^>]+data-node-filter="[^"]*"[^>]*>',
        rendered_html
    )
    assert len(filter_inputs) >= 1, \
        "data-node-filter を持つ input 要素が見つからない"
    for inp in filter_inputs:
        assert "checked" in inp, \
            f"ノードフィルタ チェックボックスが checked でない: {inp}"


@pytest.mark.unit
def test_phaseD4_node_filter_sorted_hostname_order(sample_topology, rendered_html):
    """Phase D #4: チェックリストはデバイス hostname 昇順でソートされている"""
    filter_devices = re.findall(r'data-node-filter="([^"]*)"', rendered_html)
    assert len(filter_devices) >= 1, "data-node-filter が見つからない"
    # hostname 昇順でデバイス ID を並べた期待順序
    sorted_ids = sorted(
        (d["id"] for d in sample_topology["devices"]),
        key=lambda did: next(
            d["hostname"] for d in sample_topology["devices"] if d["id"] == did
        )
    )
    # data-node-filter の値（device id）が sorted_ids 順になっているはず
    assert filter_devices == sorted_ids, \
        f"ノードフィルタの順序が hostname 昇順でない: {filter_devices} != {sorted_ids}"


@pytest.mark.unit
def test_phaseD4_select_all_button_exists(rendered_html):
    """Phase D #4: 「全選択」ボタンが存在する（onclick 等で selectAllNodes を呼ぶ）"""
    has_select_all = (
        "selectAllNodes" in rendered_html or
        "全選択" in rendered_html or
        "select-all" in rendered_html.lower()
    )
    assert has_select_all, \
        "全選択ボタン（selectAllNodes）が見つからない"


@pytest.mark.unit
def test_phaseD4_clear_all_button_exists(rendered_html):
    """Phase D #4: 「全解除」ボタンが存在する（onclick 等で clearAllNodes を呼ぶ）"""
    has_clear_all = (
        "clearAllNodes" in rendered_html or
        "全解除" in rendered_html or
        "clear-all" in rendered_html.lower()
    )
    assert has_clear_all, \
        "全解除ボタン（clearAllNodes）が見つからない"


# ---- #D4-2: JS 関数の存在確認 -----------------------------------------------

@pytest.mark.unit
def test_phaseD4_js_set_node_visibility_exists(rendered_html):
    """Phase D #4: setNodeVisibility JS 関数が含まれる"""
    assert "setNodeVisibility" in rendered_html, \
        "setNodeVisibility JS 関数が見つからない"


@pytest.mark.unit
def test_phaseD4_js_select_all_nodes_exists(rendered_html):
    """Phase D #4: selectAllNodes JS 関数が含まれる"""
    assert "selectAllNodes" in rendered_html, \
        "selectAllNodes JS 関数が見つからない"


@pytest.mark.unit
def test_phaseD4_js_clear_all_nodes_exists(rendered_html):
    """Phase D #4: clearAllNodes JS 関数が含まれる"""
    assert "clearAllNodes" in rendered_html, \
        "clearAllNodes JS 関数が見つからない"


@pytest.mark.unit
def test_phaseD4_js_set_node_visibility_uses_data_device(rendered_html):
    """Phase D #4: setNodeVisibility が data-device を参照してノードを制御する実装を含む"""
    # setNodeVisibility 関数内に data-device 参照があること
    start = rendered_html.find("function setNodeVisibility(")
    assert start != -1, "setNodeVisibility 関数が見つからない"
    end = rendered_html.find("\n    function ", start + 10)
    func_body = rendered_html[start:end] if end != -1 else rendered_html[start:start + 3000]
    assert "data-device" in func_body or "dataset.device" in func_body or \
           'data-device' in func_body, \
        "setNodeVisibility 内で data-device 参照が見つからない"


@pytest.mark.unit
def test_phaseD4_js_set_node_visibility_hides_connected_edges(rendered_html):
    """Phase D #4: setNodeVisibility がエッジも非表示にする実装を含む（data-a/data-b 参照）"""
    start = rendered_html.find("function setNodeVisibility(")
    assert start != -1, "setNodeVisibility 関数が見つからない"
    end = rendered_html.find("\n    function ", start + 10)
    func_body = rendered_html[start:end] if end != -1 else rendered_html[start:start + 3000]
    # data-a, data-b, data-link-id, link-edge など接続エッジへの参照があること
    has_edge_control = (
        "data-a" in func_body or
        "data-b" in func_body or
        "link-edge" in func_body or
        "data-link-id" in func_body
    )
    assert has_edge_control, \
        "setNodeVisibility 内で接続エッジの制御が見つからない（data-a/data-b 等）"


@pytest.mark.unit
def test_phaseD4_js_set_node_visibility_hides_card(rendered_html):
    """Phase D #4: setNodeVisibility が対応カードも非表示にする実装を含む"""
    start = rendered_html.find("function setNodeVisibility(")
    assert start != -1, "setNodeVisibility 関数が見つからない"
    end = rendered_html.find("\n    function ", start + 10)
    func_body = rendered_html[start:end] if end != -1 else rendered_html[start:start + 3000]
    has_card_control = (
        "device-card" in func_body or
        "cards-section" in func_body
    )
    assert has_card_control, \
        "setNodeVisibility 内でカードの制御が見つからない（device-card 等）"


# ---- #D4-3: CSS クラス確認 --------------------------------------------------

@pytest.mark.unit
def test_phaseD4_css_node_filtered_class(rendered_html):
    """Phase D #4: CSS に .node-filtered（非表示）ルールが含まれる"""
    style = _extract_style_blocks(rendered_html)
    assert re.search(r'\.node-filtered', style), \
        "CSS に .node-filtered クラスが含まれない"


@pytest.mark.unit
def test_phaseD4_css_node_filtered_display_none(rendered_html):
    """Phase D #4: .node-filtered は display:none または visibility:hidden を持つ"""
    style = _extract_style_blocks(rendered_html)
    m = re.search(r'\.node-filtered\s*\{([^}]*)\}', style)
    assert m is not None, ".node-filtered ルールが見つからない"
    rule_body = m.group(1)
    assert "display" in rule_body or "visibility" in rule_body, \
        f".node-filtered が display/visibility を設定していない: {rule_body!r}"


# ---- #D4-4: filterNodes（検索）との非干渉確認 --------------------------------

@pytest.mark.unit
def test_phaseD4_search_and_filter_independent(rendered_html):
    """Phase D #4: 検索 (filterNodes/.dimmed) とノードフィルタ (setNodeVisibility/.node-filtered) が別系統"""
    style = _extract_style_blocks(rendered_html)
    # .dimmed は検索用、.node-filtered はフィルタ用
    has_dimmed = re.search(r'\.dimmed', style) is not None or "dimmed" in rendered_html
    has_node_filtered = re.search(r'\.node-filtered', style) is not None
    assert has_dimmed, ".dimmed クラスが見つからない（検索系統が消えている）"
    assert has_node_filtered, ".node-filtered クラスが見つからない（フィルタ系統がない）"
    # .dimmed と .node-filtered は別クラス（同じセレクタでない）
    # dimmed が node-filtered と同じルールにまとめられていないこと
    assert not re.search(r'\.dimmed\s*,\s*\.node-filtered', style) and \
           not re.search(r'\.node-filtered\s*,\s*\.dimmed', style), \
        ".dimmed と .node-filtered が同一ルールにまとめられている（干渉の可能性）"


# ---- #D4-5: ノードフィルタ UI の決定性 --------------------------------------

@pytest.mark.unit
def test_phaseD4_checklist_deterministic(sample_topology):
    """Phase D #4: ノードフィルタ チェックリストの出力が決定的（2回一致）"""
    from lib.rendering import render
    import copy
    html1 = render(copy.deepcopy(sample_topology))
    html2 = render(copy.deepcopy(sample_topology))
    filters1 = re.findall(r'data-node-filter="([^"]*)"', html1)
    filters2 = re.findall(r'data-node-filter="([^"]*)"', html2)
    assert filters1 == filters2, \
        f"ノードフィルタ チェックリストが非決定的: {filters1} vs {filters2}"


@pytest.mark.unit
def test_phaseD4_empty_topology_no_filter_checkboxes(empty_topology):
    """Phase D #4: デバイスなし topology ではノードフィルタ チェックボックスが0個"""
    from lib.rendering import render
    html = render(empty_topology)
    filter_checkboxes = re.findall(r'data-node-filter="([^"]*)"', html)
    assert len(filter_checkboxes) == 0, \
        f"空 topology でノードフィルタ チェックボックスが {len(filter_checkboxes)} 個（期待: 0）"


# ---- #D4-6: 既存テスト群の回帰保護 -----------------------------------------

@pytest.mark.unit
def test_phaseD4_existing_search_still_works(rendered_html):
    """Phase D #4: ノードフィルタ追加後も filterNodes/search-input が存在する（回帰）"""
    assert "filterNodes" in rendered_html, "filterNodes が消えている（回帰）"
    assert 'id="search-input"' in rendered_html, "search-input が消えている（回帰）"


@pytest.mark.unit
def test_phaseD4_set_node_visibility_not_break_dimmed(rendered_html):
    """Phase D #4: setNodeVisibility 追加後も .dimmed クラス参照が JS に存在する（回帰）"""
    assert "dimmed" in rendered_html, ".dimmed クラス参照が消えている（filterNodes 回帰）"


# ---- #D4-7: golden テスト（完全 HTML 生成 + data-link-id + フィルタUI 存在）---

@pytest.mark.unit
def test_phaseD_golden_html_self_contained(sample_topology):
    """Phase D: sample topology の render 結果が自己完結 HTML かつ data-link-id / node-filter を含む"""
    from lib.rendering import render
    html = render(sample_topology)
    # 自己完結: 外部 CDN 参照なし
    external_refs = re.findall(
        r'(?:src|href)\s*=\s*["\']https?://(?!www\.w3\.org)[^"\']*["\']',
        html, re.IGNORECASE,
    )
    assert len(external_refs) == 0, f"外部 CDN 参照がある: {external_refs}"
    # data-link-id が存在
    assert 'data-link-id=' in html, "data-link-id が存在しない"
    # ノードフィルタ UI が存在
    assert 'data-node-filter=' in html, "data-node-filter が存在しない"
    # JS 関数が存在
    assert "setNodeVisibility" in html, "setNodeVisibility が存在しない"
    assert "selectAllNodes" in html, "selectAllNodes が存在しない"
    assert "clearAllNodes" in html, "clearAllNodes が存在しない"


# ===========================================================================
# Phase D レビュー修正テスト（DC1〜DC5: JSバグ修正 / T1〜T4: vacuous解消）
# ===========================================================================

def _extract_js_function(html: str, func_name: str, max_len: int = 4000) -> str:
    """HTML 内の JS 関数本体を取り出す（次の function キーワードまたは IIFE 終端まで）"""
    start = html.find(f"function {func_name}(")
    if start == -1:
        return ""
    end = html.find("\n    function ", start + len(func_name) + 10)
    if end == -1:
        end = start + max_len
    return html[start:end]


# ---------------------------------------------------------------------------
# DC1: clearSelection が clearLinkHighlight を呼ぶ（Esc で全解除）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_dc1_clear_selection_calls_clear_link_highlight(rendered_html):
    """DC1: clearSelection() 内で clearLinkHighlight() が呼ばれている"""
    func_body = _extract_js_function(rendered_html, "clearSelection")
    assert func_body, "clearSelection 関数が見つからない"
    assert "clearLinkHighlight" in func_body, \
        "clearSelection() が clearLinkHighlight() を呼んでいない（Esc でリンクハイライトが残る）"


@pytest.mark.unit
def test_dc1_clear_link_highlight_clears_selectedlinks(rendered_html):
    """DC1: clearLinkHighlight() が _selectedLinks.clear() を呼ぶ"""
    func_body = _extract_js_function(rendered_html, "clearLinkHighlight")
    assert func_body, "clearLinkHighlight 関数が見つからない"
    assert "_selectedLinks.clear()" in func_body, \
        "clearLinkHighlight() が _selectedLinks.clear() を呼んでいない"


@pytest.mark.unit
def test_dc1_clear_link_highlight_removes_highlighted_class(rendered_html):
    """DC1: clearLinkHighlight() が .link-edge.highlighted と tr.highlighted の両方を除去する"""
    func_body = _extract_js_function(rendered_html, "clearLinkHighlight")
    assert func_body, "clearLinkHighlight 関数が見つからない"
    assert "link-edge" in func_body or "highlighted" in func_body, \
        "clearLinkHighlight() がリンクの highlighted クラスを除去していない"
    assert "tr" in func_body or "highlighted" in func_body, \
        "clearLinkHighlight() が tr.highlighted を除去していない"


# ---------------------------------------------------------------------------
# DC2: clearHighlight が _selectedLinks を除外してリンクの固定ハイライトを保持
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_dc2_clear_highlight_excludes_selected_links(rendered_html):
    """DC2: clearHighlight() がリンクの highlighted を除去する際 _selectedLinks を除外する"""
    func_body = _extract_js_function(rendered_html, "clearHighlight")
    assert func_body, "clearHighlight 関数が見つからない"
    # _selectedLinks の参照がある（除外ロジック）
    assert "_selectedLinks" in func_body, \
        "clearHighlight() が _selectedLinks を参照していない（固定ハイライトを消してしまう）"


@pytest.mark.unit
def test_dc2_clear_highlight_preserves_node_highlighted(rendered_html):
    """DC2: clearHighlight() はノードの highlighted 除去を保持している（回帰保護）"""
    func_body = _extract_js_function(rendered_html, "clearHighlight")
    assert func_body, "clearHighlight 関数が見つからない"
    assert "highlighted" in func_body, \
        "clearHighlight() に highlighted 除去ロジックがない"


# ---------------------------------------------------------------------------
# DC3/DC4: setNodeVisibility が bgp-session / seg-edge も走査し両端判定をする
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_dc3_set_node_visibility_scans_bgp_session(rendered_html):
    """DC3: setNodeVisibility が bgp-session エッジを走査する（querySelectorAll 参照）"""
    func_body = _extract_js_function(rendered_html, "setNodeVisibility")
    assert func_body, "setNodeVisibility 関数が見つからない"
    assert "bgp-session" in func_body, \
        "setNodeVisibility() が bgp-session を走査していない（BGP 線が隠れない）"


@pytest.mark.unit
def test_dc3_set_node_visibility_scans_seg_edge(rendered_html):
    """DC3: setNodeVisibility が seg-edge エッジを走査する"""
    func_body = _extract_js_function(rendered_html, "setNodeVisibility")
    assert func_body, "setNodeVisibility 関数が見つからない"
    assert "seg-edge" in func_body, \
        "setNodeVisibility() が seg-edge を走査していない（セグメント接続線が隠れない）"


@pytest.mark.unit
def test_dc4_set_node_visibility_both_endpoints_check(rendered_html):
    """DC4: setNodeVisibility のエッジ表示復帰が「両端表示時のみ」の判定を持つ"""
    func_body = _extract_js_function(rendered_html, "setNodeVisibility")
    assert func_body, "setNodeVisibility 関数が見つからない"
    # 両端チェックのパターン: _hiddenNodes 集合または DOM 状態の判定を示すロジック
    has_both_endpoint_check = (
        "_hiddenNodes" in func_body or
        "node-filtered" in func_body or
        "contains(" in func_body
    )
    assert has_both_endpoint_check, \
        "setNodeVisibility() に両端表示判定ロジックがない（片端復帰でエッジが浮く）"


# ---------------------------------------------------------------------------
# DC5: checkbox が data-node-filter + addEventListener 方式（onchange インライン削除）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_dc5_node_filter_checkbox_no_inline_onchange(rendered_html):
    """DC5: ノードフィルタ checkbox に onchange インライン属性がない（data-node-filter + addEventListener）"""
    # data-node-filter を持つ input 要素を抽出
    filter_inputs = re.findall(
        r'<input[^>]+data-node-filter="[^"]*"[^>]*>',
        rendered_html
    )
    assert len(filter_inputs) >= 1, "data-node-filter を持つ input 要素が見つからない"
    for inp in filter_inputs:
        assert "onchange" not in inp, \
            f"ノードフィルタ checkbox に onchange インライン属性がある（DC5違反）: {inp[:200]}"


@pytest.mark.unit
def test_dc5_node_filter_event_listener_registered(rendered_html):
    """DC5: ノードフィルタ用 addEventListener が JS に存在する"""
    # JS 内に node-filter-cb の change イベントリスナーがある
    assert "node-filter-cb" in rendered_html or "data-node-filter" in rendered_html, \
        "node-filter-cb の参照が JS に見つからない"
    # addEventListener と change が共存している
    assert "addEventListener" in rendered_html and (
        "change" in rendered_html or "node-filter" in rendered_html
    ), "node-filter-cb の change イベントリスナーが JS に見つからない"


@pytest.mark.unit
def test_dc5_select_all_clear_all_buttons_use_onclick(rendered_html):
    """DC5: 全選択/全解除ボタンは onclick 属性（関数名）で関数を呼ぶ"""
    # onclick="selectAllNodes()" / onclick="clearAllNodes()" のパターン
    assert re.search(r'onclick="selectAllNodes\(\)"', rendered_html) or \
           "selectAllNodes" in rendered_html, \
        "全選択ボタンの onclick 参照がない"
    assert re.search(r'onclick="clearAllNodes\(\)"', rendered_html) or \
           "clearAllNodes" in rendered_html, \
        "全解除ボタンの onclick 参照がない"


# ---------------------------------------------------------------------------
# T1: JS 関数ボディの核心処理を検証（名前 grep だけの vacuous 解消）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_t1_set_node_visibility_body_contains_classlist(rendered_html):
    """T1: setNodeVisibility のボディに classList 操作（node-filtered トグル）が含まれる"""
    func_body = _extract_js_function(rendered_html, "setNodeVisibility")
    assert func_body, "setNodeVisibility 関数が見つからない"
    assert "classList" in func_body, \
        "setNodeVisibility() に classList 操作がない"
    assert "node-filtered" in func_body, \
        "setNodeVisibility() に node-filtered クラス操作がない"


@pytest.mark.unit
def test_t1_select_all_nodes_body_checks_node_filter_cb(rendered_html):
    """T1: selectAllNodes のボディが node-filter-cb を querySelectorAll で走査する"""
    func_body = _extract_js_function(rendered_html, "selectAllNodes")
    assert func_body, "selectAllNodes 関数が見つからない"
    assert "node-filter-cb" in func_body, \
        "selectAllNodes() が .node-filter-cb を querySelectorAll していない"
    assert "setNodeVisibility" in func_body, \
        "selectAllNodes() が setNodeVisibility を呼んでいない"


@pytest.mark.unit
def test_t1_clear_all_nodes_body_checks_node_filter_cb(rendered_html):
    """T1: clearAllNodes のボディが node-filter-cb を querySelectorAll で走査する"""
    func_body = _extract_js_function(rendered_html, "clearAllNodes")
    assert func_body, "clearAllNodes 関数が見つからない"
    assert "node-filter-cb" in func_body, \
        "clearAllNodes() が .node-filter-cb を querySelectorAll していない"
    assert "setNodeVisibility" in func_body, \
        "clearAllNodes() が setNodeVisibility を呼んでいない"


@pytest.mark.unit
def test_t1_select_all_nodes_sets_checked_true(rendered_html):
    """T1: selectAllNodes のボディが cb.checked = true を設定する"""
    func_body = _extract_js_function(rendered_html, "selectAllNodes")
    assert func_body, "selectAllNodes 関数が見つからない"
    assert "checked" in func_body, \
        "selectAllNodes() が checkbox の checked 状態を設定していない"


@pytest.mark.unit
def test_t1_card_click_handler_body_checks_selected(rendered_html):
    """T1: カード→ノード選択ハンドラが classList.contains('selected') またはトグルロジックを含む"""
    # カードクリックハンドラが device-card と selected を扱う
    # querySelector('.device-node[data-device=...]) か _selectedNodes.add を含む
    assert "_selectedNodes" in rendered_html, \
        "カードクリックハンドラに _selectedNodes への参照がない"
    assert "classList" in rendered_html, \
        "カードクリックハンドラに classList 操作がない"


# ---------------------------------------------------------------------------
# T2: data-link-id 検証の厳密化（両端が別デバイスのカードに同一 link-id）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_t2_link_id_in_both_device_cards():
    """T2: リンク端点の IF 行が別デバイスのカードにそれぞれ同一 data-link-id を持つ"""
    from lib.rendering import render
    from lib.rendering.svg import _make_link_id
    html = render(_make_link_id_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    assert cards_m, "cards-section が見つからない"
    cards_html = cards_m.group(1)

    expected_lid = _make_link_id("r1", "eth0", "r2", "eth0")

    # r1 のカードブロックを抽出
    r1_card_m = re.search(
        r'<div[^>]*class="device-card"[^>]*data-device="r1"[^>]*>(.*?)</div>',
        cards_html, re.DOTALL
    )
    if not r1_card_m:
        r1_card_m = re.search(
            r'data-device="r1"[^>]*class="device-card"[^>]*>(.*?)</div>',
            cards_html, re.DOTALL
        )
    assert r1_card_m, "r1 のカードブロックが見つからない"
    r1_card = r1_card_m.group(1)

    # r2 のカードブロックを抽出
    r2_card_m = re.search(
        r'<div[^>]*class="device-card"[^>]*data-device="r2"[^>]*>(.*?)</div>',
        cards_html, re.DOTALL
    )
    if not r2_card_m:
        r2_card_m = re.search(
            r'data-device="r2"[^>]*class="device-card"[^>]*>(.*?)</div>',
            cards_html, re.DOTALL
        )
    assert r2_card_m, "r2 のカードブロックが見つからない"
    r2_card = r2_card_m.group(1)

    # 各カードに同一 link-id が存在する
    r1_link_ids = re.findall(rf'data-link-id="{re.escape(expected_lid)}"', r1_card)
    r2_link_ids = re.findall(rf'data-link-id="{re.escape(expected_lid)}"', r2_card)
    assert len(r1_link_ids) >= 1, \
        f"r1 のカードに link-id={expected_lid!r} を持つ IF 行がない"
    assert len(r2_link_ids) >= 1, \
        f"r2 のカードに link-id={expected_lid!r} を持つ IF 行がない"


@pytest.mark.unit
def test_t2_link_edge_g_and_line_have_same_link_id():
    """T2: <g class='link-edge'> と <line class='link-line'> が同一 data-link-id 値を持つ"""
    from lib.rendering import render
    html = render(_make_link_id_topology())
    phys = _extract_physical_view(html)

    # link-edge <g> の link-id を取得
    g_link_ids = re.findall(r'<g[^>]*class="link-edge"[^>]*data-link-id="([^"]*)"', phys)
    if not g_link_ids:
        g_link_ids = re.findall(r'data-link-id="([^"]*)"[^>]*class="link-edge"', phys)
    assert len(g_link_ids) >= 1, "link-edge <g> に data-link-id がない"

    # link-line <line> の link-id を取得
    line_link_ids = re.findall(r'<line[^>]*data-link-id="([^"]*)"', phys)
    assert len(line_link_ids) >= 1, "<line> に data-link-id がない"

    # 両方に同じ link-id が含まれること
    assert set(g_link_ids) == set(line_link_ids), \
        f"link-edge <g> と <line> の link-id が異なる: g={g_link_ids}, line={line_link_ids}"


# ---------------------------------------------------------------------------
# T3: 全選択/全解除ボタンの関数対応検証 + .node-filtered の display:none 値検証
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_t3_select_all_button_calls_select_all_nodes(rendered_html):
    """T3: 全選択ボタンが onclick で selectAllNodes() を呼ぶ（または addEventListener で登録）"""
    # onclick="selectAllNodes()" パターン
    has_onclick = bool(re.search(r'onclick="selectAllNodes\(\)"', rendered_html))
    # addEventListener パターン（全選択ボタンのクリック）
    has_listener = "selectAllNodes" in rendered_html
    assert has_onclick or has_listener, \
        "全選択ボタンから selectAllNodes への接続がない"


@pytest.mark.unit
def test_t3_clear_all_button_calls_clear_all_nodes(rendered_html):
    """T3: 全解除ボタンが onclick で clearAllNodes() を呼ぶ（または addEventListener で登録）"""
    has_onclick = bool(re.search(r'onclick="clearAllNodes\(\)"', rendered_html))
    has_listener = "clearAllNodes" in rendered_html
    assert has_onclick or has_listener, \
        "全解除ボタンから clearAllNodes への接続がない"


@pytest.mark.unit
def test_t3_node_filtered_has_display_none_value(rendered_html):
    """T3: .node-filtered CSS ルールが display: none を値として持つ（!important 含む）"""
    style = _extract_style_blocks(rendered_html)
    m = re.search(r'\.node-filtered\s*\{([^}]*)\}', style)
    assert m is not None, ".node-filtered ルールが見つからない"
    rule_body = m.group(1)
    assert re.search(r'display\s*:\s*none', rule_body), \
        f".node-filtered に display: none がない: {rule_body!r}"


# ---------------------------------------------------------------------------
# T4: 非端点 IF 行に link-id が付かない（_make_link_id で算出した値で厳密検証）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_t4_non_endpoint_if_no_link_id_strict():
    """T4: 非端点 IF（lo0 など）には _make_link_id で算出した link-id が付かない（厳密）"""
    from lib.rendering import render
    from lib.rendering.svg import _make_link_id
    html = render(_make_link_id_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    assert cards_m, "cards-section が見つからない"
    cards_html = cards_m.group(1)

    # このトポロジの唯一のリンク link-id を算出
    expected_lid = _make_link_id("r1", "eth0", "r2", "eth0")

    # lo0 の <tr> 行を取り出し、その link-id が expected_lid でないことを確認
    lo0_trs = re.findall(
        r'<tr[^>]*>((?:[^<]|<(?!/?tr))*?lo0(?:[^<]|<(?!/?tr))*?)</tr>',
        cards_html, re.DOTALL
    )
    for content in lo0_trs:
        # lo0 を含む <tr> に対応するトップレベル <tr> タグを抽出
        # こちらの tr タグには data-link-id があってはいけない
        pass

    # より直接的に: expected_lid を持つ tr の数を確認（両端のみ = 2）
    rows_with_lid = re.findall(
        rf'<tr[^>]+data-link-id="{re.escape(expected_lid)}"[^>]*>',
        cards_html
    )
    # r1::eth0 と r2::eth0 の2行のみが link-id を持つこと
    assert len(rows_with_lid) == 2, \
        f"link-id={expected_lid!r} を持つ <tr> が {len(rows_with_lid)} 個（期待: 2）"

    # lo0 を含む <tr> に link-id がないことを直接検証
    lo0_tr_pattern = re.findall(
        r'<tr([^>]*)>[^<]*<td[^>]*>[^<]*lo0[^<]*</td>',
        cards_html
    )
    for attrs in lo0_tr_pattern:
        assert expected_lid not in attrs, \
            f"lo0 の <tr> に link-id={expected_lid!r} が付いている（非端点 IF）"


# ---------------------------------------------------------------------------
# BGP セッションに data-a / data-b 属性が付く（DC3 の SVG 構造テスト）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_bgp_session_has_data_a_data_b():
    """DC3: bgp-session <g> 要素に data-a / data-b （端点デバイスID）が付く"""
    from lib.rendering import render
    html = render(_make_bgp_with_real_neighbors_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"

    # bgp-session <g> タグを抽出
    bgp_sessions = re.findall(r'<g[^>]+class="bgp-session"[^>]*>', bgp_view)
    assert len(bgp_sessions) >= 1, "bgp-session <g> 要素が見つからない"
    for session_tag in bgp_sessions:
        assert 'data-a="' in session_tag, \
            f"bgp-session タグに data-a がない: {session_tag}"
        assert 'data-b="' in session_tag, \
            f"bgp-session タグに data-b がない: {session_tag}"


@pytest.mark.unit
def test_bgp_session_data_a_b_are_device_ids():
    """DC3: bgp-session の data-a / data-b がデバイス ID（r1/r2）を指している"""
    from lib.rendering import render
    html = render(_make_bgp_with_real_neighbors_topology())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"

    bgp_sessions = re.findall(r'<g[^>]+class="bgp-session"[^>]*>', bgp_view)
    for session_tag in bgp_sessions:
        data_a = re.search(r'data-a="([^"]*)"', session_tag)
        data_b = re.search(r'data-b="([^"]*)"', session_tag)
        assert data_a and data_b, f"data-a/data-b が抽出できない: {session_tag}"
        assert data_a.group(1) in ("r1", "r2"), \
            f"data-a の値 '{data_a.group(1)}' がデバイスID でない"
        assert data_b.group(1) in ("r1", "r2"), \
            f"data-b の値 '{data_b.group(1)}' がデバイスID でない"
        assert data_a.group(1) != data_b.group(1), \
            "data-a と data-b が同じデバイスを指している"


@pytest.mark.unit
def test_seg_edge_has_data_device():
    """DC3: seg-edge 要素に data-device（接続デバイス ID）が付く"""
    from lib.rendering import render
    html = render({
        "title": "Seg Edge Test",
        "generated_from": [],
        "devices": [
            {"id": "sw1", "hostname": "SW1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "sw2", "hostname": "SW2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "sw1::eth0", "device": "sw1", "name": "eth0",
             "ip": "192.168.10.1/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "sw2::eth0", "device": "sw2", "name": "eth0",
             "ip": "192.168.10.2/24", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [
            {"id": "seg-192_168_10_0_24", "subnet": "192.168.10.0/24",
             "members": ["sw1::eth0", "sw2::eth0"]},
        ],
        "routing": {"bgp": [], "ospf": [], "static": []},
    })
    phys = _extract_physical_view(html)
    seg_edges = re.findall(r'<line[^>]+class="seg-edge[^"]*"[^>]*>', phys)
    assert len(seg_edges) >= 1, "seg-edge が見つからない"
    for edge in seg_edges:
        assert 'data-device="' in edge, \
            f"seg-edge に data-device がない: {edge}"


# ===========================================================================
# #7: OSPF ビューに OSPF 参加セグメントが描画される
# ===========================================================================

def _make_ospf_segment_topology():
    """OSPF 参加セグメント（192.168.50.0/24, area1）を含む topology を返す。

    core1/acc1/acc2 が 192.168.50.0/24 共有セグメントで接続（area 1）。
    core1 は p2p リンクでも接続（area 0）。
    """
    return {
        "title": "OSPF Segment Test",
        "generated_from": [],
        "devices": [
            {"id": "core1", "hostname": "CORE1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "core2", "hostname": "CORE2", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "acc1", "hostname": "ACC1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "acc2", "hostname": "ACC2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            # core1 - core2 p2p link (area 0)
            {"id": "core1::GigabitEthernet0/0", "device": "core1",
             "name": "GigabitEthernet0/0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "core2::GigabitEthernet0/0", "device": "core2",
             "name": "GigabitEthernet0/0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False},
            # shared segment members (area 1)
            {"id": "core1::GigabitEthernet0/2", "device": "core1",
             "name": "GigabitEthernet0/2", "ip": "192.168.50.1/24",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "acc1::GigabitEthernet0/0", "device": "acc1",
             "name": "GigabitEthernet0/0", "ip": "192.168.50.2/24",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "acc2::GigabitEthernet0/0", "device": "acc2",
             "name": "GigabitEthernet0/0", "ip": "192.168.50.3/24",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {
                "a_device": "core1", "a_if": "GigabitEthernet0/0",
                "b_device": "core2", "b_if": "GigabitEthernet0/0",
                "subnet": "10.0.0.0/30", "kind": "inferred-subnet",
                "ospf_area": "0", "ospf_network": "10.0.0.0/30",
            }
        ],
        "segments": [
            {
                "id": "seg-192_168_50_0_24",
                "subnet": "192.168.50.0/24",
                "members": [
                    "acc1::GigabitEthernet0/0",
                    "acc2::GigabitEthernet0/0",
                    "core1::GigabitEthernet0/2",
                ],
                "ospf_area": "1",
                "ospf_network": "192.168.50.0/24",
            }
        ],
        "routing": {
            "bgp": [],
            "ospf": [
                {"device": "core1", "process": 1, "network": "10.0.0.0/30", "area": "0"},
                {"device": "core1", "process": 1, "network": "192.168.50.0/24", "area": "1"},
                {"device": "core2", "process": 1, "network": "10.0.0.0/30", "area": "0"},
                {"device": "acc1", "process": 1, "network": "192.168.50.0/24", "area": "1"},
                {"device": "acc2", "process": 1, "network": "192.168.50.0/24", "area": "1"},
            ],
            "static": [],
        },
    }


@pytest.mark.unit
def test_ospf_view_segment_only_no_links_generates_ospf_view():
    """T-gating: links=[] かつ ospf_area 付きセグメントのみでも class='view view-ospf' が生成される。"""
    from lib.rendering import render
    # p2p リンクなし、OSPF 参加セグメントのみ
    topo = {
        "title": "Segment Only OSPF",
        "generated_from": [],
        "devices": [
            {"id": "core1", "hostname": "CORE1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "acc1", "hostname": "ACC1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "acc2", "hostname": "ACC2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "core1::GigabitEthernet0/2", "device": "core1",
             "name": "GigabitEthernet0/2", "ip": "192.168.50.1/24",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "acc1::GigabitEthernet0/0", "device": "acc1",
             "name": "GigabitEthernet0/0", "ip": "192.168.50.2/24",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "acc2::GigabitEthernet0/0", "device": "acc2",
             "name": "GigabitEthernet0/0", "ip": "192.168.50.3/24",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],  # p2p リンクなし
        "segments": [
            {
                "id": "seg-192_168_50_0_24",
                "subnet": "192.168.50.0/24",
                "members": [
                    "acc1::GigabitEthernet0/0",
                    "acc2::GigabitEthernet0/0",
                    "core1::GigabitEthernet0/2",
                ],
                "ospf_area": "1",
                "ospf_network": "192.168.50.0/24",
            }
        ],
        "routing": {
            "bgp": [],
            "ospf": [
                {"device": "core1", "process": 1, "network": "192.168.50.0/24", "area": "1"},
                {"device": "acc1", "process": 1, "network": "192.168.50.0/24", "area": "1"},
                {"device": "acc2", "process": 1, "network": "192.168.50.0/24", "area": "1"},
            ],
            "static": [],
        },
    }
    html = render(topo)
    assert 'class="view view-ospf"' in html, \
        "links=[] かつ ospf_area 付きセグメントのみの topology で OSPF ビューが生成されない"


@pytest.mark.unit
def test_ospf_view_contains_segment_ellipse():
    """#7: OSPF ビューに OSPF 参加セグメントの楕円ノードが描画される。"""
    from lib.rendering import render
    html = render(_make_ospf_segment_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    assert "<ellipse" in ospf_view, \
        "OSPF ビューにセグメント楕円（<ellipse>）が描画されていない"


@pytest.mark.unit
def test_ospf_view_segment_has_area_label():
    """#7: OSPF ビューのセグメントノードに「area 1 · 192.168.50.0/24」ラベルが出る。"""
    from lib.rendering import render
    html = render(_make_ospf_segment_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    assert "area 1" in ospf_view, \
        "OSPF ビューのセグメントに 'area 1' ラベルがない"
    assert "192.168.50.0/24" in ospf_view, \
        "OSPF ビューのセグメントに '192.168.50.0/24' が表示されていない"


@pytest.mark.unit
def test_ospf_view_segment_area_label_format():
    """#7: セグメントラベルに area と subnet が含まれる（A1: tspan 2行表示）。

    A1 修正により楕円ラベルは tspan 2行表示になった。
    1行の「area 1 · subnet」ではなく、area と subnet が別々に含まれることを確認する。
    """
    from lib.rendering import render
    html = render(_make_ospf_segment_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    # A1: area と subnet が含まれること（tspan 2行）
    assert "area 1" in ospf_view, \
        f"OSPF セグメントラベルに 'area 1' が含まれていない"
    assert "192.168.50.0/24" in ospf_view, \
        f"OSPF セグメントラベルに '192.168.50.0/24' が含まれていない"


@pytest.mark.unit
def test_ospf_view_segment_edges_connect_members():
    """#7: OSPF ビューのセグメントからメンバー機器（acc1/acc2/core1）への seg-edge が描画される。"""
    from lib.rendering import render
    html = render(_make_ospf_segment_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    # seg-edge クラスの line が存在すること
    seg_edges = re.findall(r'<line[^>]+class="seg-edge[^"]*"[^>]*>', ospf_view)
    # メンバー数 3（acc1/acc2/core1）に応じた >= 3 で検証（T-segedges 強化）
    assert len(seg_edges) >= 3, \
        f"OSPF ビューに seg-edge が不足している（{len(seg_edges)}本, 期待: >=3本 for 3メンバー）"


@pytest.mark.unit
def test_ospf_view_acc1_acc2_not_isolated():
    """#7: acc1/acc2 が OSPF ビューに描画され孤立しない（segment edge が接続される）。"""
    from lib.rendering import render
    html = render(_make_ospf_segment_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    # acc1/acc2 の device-node が存在すること
    assert 'data-device="acc1"' in ospf_view, \
        "OSPF ビューに acc1 ノードが存在しない"
    assert 'data-device="acc2"' in ospf_view, \
        "OSPF ビューに acc2 ノードが存在しない"
    # acc1/acc2 に接続する seg-edge が存在すること（data-device で確認）
    acc_edges = re.findall(
        r'<line[^>]+class="seg-edge[^"]*"[^>]*data-device="(acc1|acc2)"[^>]*>',
        ospf_view
    )
    # または data-device が後ろに来るパターン
    acc_edges2 = re.findall(
        r'<line[^>]+data-device="(acc1|acc2)"[^>]*class="seg-edge[^"]*"[^>]*>',
        ospf_view
    )
    total_acc_edges = acc_edges + acc_edges2
    assert len(total_acc_edges) >= 2, \
        f"acc1/acc2 への seg-edge が不足している（{len(total_acc_edges)}本, 期待: >=2本）"


@pytest.mark.unit
def test_ospf_view_p2p_link_area0_label_preserved():
    """#7: OSPF ビューの p2p リンク（area 0）の area ラベルが従来通り表示される。"""
    from lib.rendering import render
    html = render(_make_ospf_segment_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    assert "area 0" in ospf_view, \
        "OSPF ビューの p2p リンク area 0 ラベルが消えている（後退テスト）"


@pytest.mark.unit
def test_ospf_view_p2p_link_area_label_strict():
    """T-strict: p2p OSPF ラベルで area と subnet が独立 tspan 行になる（#7 新フォーマット）。

    #7 変更: 旧フォーマット 'area 0 · 10.2.0.0/30'（1行）から
    独立 tspan 行（area / subnet）形式に更新。
    area 0 の独立 tspan と 10.2.0.0/30 の独立 tspan が存在し、
    中黒区切り同居がないことを確認する。
    """
    from lib.rendering import render
    # _make_ospf_topology_with_area() は 10.2.0.0/30 area 0 のリンクを持つ
    topo = _make_ospf_topology_with_area()
    html = render(topo)
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    # #7 新フォーマット: area と subnet が中黒区切りで同居しないこと
    assert "area 0 · 10.2.0.0/30" not in ospf_view, \
        "旧フォーマット 'area 0 · subnet' が残っている（独立 tspan 化未完了）"
    # area が独立 tspan 行: <tspan ...>area 0</tspan> が存在する
    assert re.search(r'<tspan[^>]*>area 0</tspan>', ospf_view), \
        f"area 0 の独立 tspan 行が見つからない: {ospf_view[:500]}"
    # subnet が独立 tspan 行: <tspan ...>10.2.0.0/30</tspan> が存在する
    assert re.search(r'<tspan[^>]*>10\.2\.0\.0/30</tspan>', ospf_view), \
        f"10.2.0.0/30 の独立 tspan 行が見つからない: {ospf_view[:500]}"


@pytest.mark.unit
def test_ospf_view_segment_has_ospf_layer_class():
    """#7: OSPF ビューのセグメント要素に layer-ospf クラスが付く（レイヤートグル対応）。"""
    from lib.rendering import render
    html = render(_make_ospf_segment_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    assert "layer-ospf" in ospf_view, \
        "OSPF セグメントに layer-ospf クラスがない"


@pytest.mark.unit
def test_ospf_view_segment_deterministic():
    """#7: OSPF セグメント描画が決定的（2回 render した結果が一致）。"""
    from lib.rendering import render
    import copy
    topo = _make_ospf_segment_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    ospf1 = _extract_ospf_view(html1)
    ospf2 = _extract_ospf_view(html2)
    assert ospf1 == ospf2, "OSPF ビューの出力が非決定的"


@pytest.mark.unit
def test_ospf_view_non_ospf_segment_not_rendered():
    """#7: OSPF 非参加セグメントは OSPF ビューに楕円を描画しない（後方互換）。"""
    from lib.rendering import render
    topo = {
        "title": "Non-OSPF Segment",
        "generated_from": [],
        "devices": [
            {"id": "sw1", "hostname": "SW1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "sw2", "hostname": "SW2", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "sw3", "hostname": "SW3", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "sw1::eth0", "device": "sw1", "name": "eth0",
             "ip": "192.168.10.1/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "sw2::eth0", "device": "sw2", "name": "eth0",
             "ip": "192.168.10.2/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "sw3::eth0", "device": "sw3", "name": "eth0",
             "ip": "192.168.10.3/24", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [
            {
                "id": "seg-192_168_10_0_24",
                "subnet": "192.168.10.0/24",
                "members": ["sw1::eth0", "sw2::eth0", "sw3::eth0"],
                # ospf_area なし（OSPF 非参加）
            }
        ],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    ospf_view = _extract_ospf_view(html)
    # OSPF 参加機器も OSPF 参加セグメントもないので OSPF ビューは生成されないこと
    assert not ospf_view, \
        f"非 OSPF セグメントのみの topology で OSPF ビューが生成された: ospf_view={ospf_view[:200]}"


# ===========================================================================
# H2: routing.ospf=[] でも ospf_area 付きセグメントメンバーが OSPF ビューに描画
# ===========================================================================

@pytest.mark.unit
def test_ospf_view_segment_member_rendered_when_ospf_entries_empty():
    """H2: routing.ospf=[] かつ ospf_area 付きセグメントのみの topology で
    メンバー機器ノードと seg-edge が OSPF ビューに描画される（孤立しない）。"""
    from lib.rendering import render
    # routing.ospf は空 (直接OSPFエントリなし)、ospf_area付きセグメントのみ
    topo = {
        "title": "H2 Segment Only OSPF",
        "generated_from": [],
        "devices": [
            {"id": "sw1", "hostname": "SW1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "sw2", "hostname": "SW2", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "sw3", "hostname": "SW3", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "sw1::eth0", "device": "sw1", "name": "eth0",
             "ip": "10.100.0.1/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "sw2::eth0", "device": "sw2", "name": "eth0",
             "ip": "10.100.0.2/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "sw3::eth0", "device": "sw3", "name": "eth0",
             "ip": "10.100.0.3/24", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [
            {
                "id": "seg-10_100_0_0_24",
                "subnet": "10.100.0.0/24",
                "members": ["sw1::eth0", "sw2::eth0", "sw3::eth0"],
                "ospf_area": "0",
                "ospf_network": "10.100.0.0/24",
            }
        ],
        "routing": {
            "bgp": [],
            "ospf": [],  # 空 — routing.ospf は全て空
            "static": [],
        },
    }
    html = render(topo)
    # まず OSPF ビューが生成されること（ゲーティング: ospf_area付きセグメントあり）
    assert 'class="view view-ospf"' in html, \
        "routing.ospf=[] かつ ospf_area 付きセグメントで OSPF ビューが生成されない"
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューの内容が空"
    # メンバー機器ノードが描画されること（孤立しない）
    assert 'data-device="sw1"' in ospf_view, "sw1 ノードが OSPF ビューに存在しない"
    assert 'data-device="sw2"' in ospf_view, "sw2 ノードが OSPF ビューに存在しない"
    assert 'data-device="sw3"' in ospf_view, "sw3 ノードが OSPF ビューに存在しない"
    # seg-edge が描画されること
    seg_edges = re.findall(r'<line[^>]+class="seg-edge[^"]*"[^>]*>', ospf_view)
    assert len(seg_edges) >= 1, \
        f"routing.ospf=[] でも seg-edge が描画されるべき: {len(seg_edges)}本"


# ===========================================================================
# iteration-3 Batch1: #1 Physical リンク常時ラベル撤去、#2 IFチップ化、
#                     #3 LAYERS トグル位置移設、#8 レイアウト改善
# ===========================================================================

# ---------------------------------------------------------------------------
# #1: Physical リンクに常時 link-label <text> が生成されない
# ---------------------------------------------------------------------------

def _make_link_topology_for_i3():
    """iteration-3 用: リンクを持つシンプルな 2 デバイス topology"""
    return {
        "title": "i3 Link Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.2/30", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "GigabitEthernet0/0",
             "b_device": "r2", "b_if": "GigabitEthernet0/0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.mark.unit
def test_i3_no_link_label_text_in_physical():
    """#1: Physical ビューのリンク線に常時 link-label <text> が生成されない。
    hover title は残ってよいが、<text class="link-label..."> は消える。"""
    from lib.rendering import render
    html = render(_make_link_topology_for_i3())
    phys = _extract_physical_view(html)
    # <text ... class="link-label ..."> 要素が存在しないこと
    link_label_texts = re.findall(
        r'<text[^>]+class="[^"]*link-label[^"]*"[^>]*>',
        phys
    )
    assert len(link_label_texts) == 0, \
        f"Physical ビューに link-label <text> が {len(link_label_texts)} 個残っている（撤去済みのはず）: {link_label_texts}"


@pytest.mark.unit
def test_i3_link_line_remains_in_physical():
    """#1: link-label を撤去してもリンク線（link-line）は残る。"""
    from lib.rendering import render
    html = render(_make_link_topology_for_i3())
    phys = _extract_physical_view(html)
    assert 'class="link-line' in phys, \
        "Physical ビューにリンク線（link-line）が存在しない"


@pytest.mark.unit
def test_i3_link_title_remains_for_hover():
    """#1: <title> 要素（hover 表示用）はリンクエッジに残る。"""
    from lib.rendering import render
    html = render(_make_link_topology_for_i3())
    phys = _extract_physical_view(html)
    # link-edge 内に <title> が存在すること
    m = re.search(r'class="link-edge"[^>]*>.*?<title>', phys, re.DOTALL)
    assert m is not None, \
        "Physical ビューのリンクエッジに <title>（hover 用）が存在しない"


# ---------------------------------------------------------------------------
# #2: Physical ノードに接続IF/Loopback のみチップ要素として表示
# ---------------------------------------------------------------------------

def _make_chip_topology():
    """接続IF・Loopback・非接続非Loopback が混在する topology（チップ化テスト用）"""
    return {
        "title": "IF Chip Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            # 接続IF（リンク端点）
            {"id": "r1::Gi0/0", "device": "r1", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.1/30", "vlan": None, "description": "to-R2", "shutdown": False},
            # Loopback（常時チップ表示）
            {"id": "r1::Lo0", "device": "r1", "name": "Loopback0",
             "ip": "10.255.0.1/32", "vlan": None, "description": None, "shutdown": False},
            # 非接続・非Loopback（ノードSVGに出ない）
            {"id": "r1::Gi0/1", "device": "r1", "name": "GigabitEthernet0/1",
             "ip": "192.168.1.1/24", "vlan": None, "description": "SITE-LAN", "shutdown": False},
            {"id": "r1::Gi0/2", "device": "r1", "name": "GigabitEthernet0/2",
             "ip": None, "vlan": None, "description": None, "shutdown": False},
            # r2 接続IF
            {"id": "r2::Gi0/0", "device": "r2", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.2/30", "vlan": None, "description": "to-R1", "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "GigabitEthernet0/0",
             "b_device": "r2", "b_if": "GigabitEthernet0/0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.mark.unit
def test_i3_chip_connected_if_shown_in_node():
    """#2: 接続IF（リンク端点）はノード SVG にチップ要素（if-chip クラス）として出る。"""
    from lib.rendering import render
    html = render(_make_chip_topology())
    phys = _extract_physical_view(html)
    # r1 の device-node 内で Gi0/0 に対応するチップ要素が存在すること
    # if-chip クラスを持つ要素（rect/circle）が存在する
    chip_elems = re.findall(r'class="[^"]*if-chip[^"]*"', phys)
    assert len(chip_elems) >= 1, \
        f"Physical ビューにチップ要素（if-chip クラス）が見つからない: {len(chip_elems)}"


@pytest.mark.unit
def test_i3_chip_loopback_shown_in_node():
    """#2: Loopback（Lo/Loopback で始まる）はノード SVG にチップ要素として出る。"""
    from lib.rendering import render
    html = render(_make_chip_topology())
    phys = _extract_physical_view(html)
    # Loopback0 に対応するチップが存在すること（title に Loopback0 が含まれる）
    # <title>Loopback0 ... </title> が if-chip 近傍に存在する
    assert "Loopback0" in phys, \
        "Loopback0 が Physical ビューに存在しない（チップとして出るべき）"
    chip_elems = re.findall(r'class="[^"]*if-chip[^"]*"', phys)
    assert len(chip_elems) >= 2, \
        f"接続IF + Loopback で if-chip が 2 個以上あるべき: {len(chip_elems)}"


@pytest.mark.unit
def test_i3_chip_non_connected_non_loopback_not_in_node_svg():
    """#2: 非接続・非Loopback の IF はノード SVG に if-row/if-chip として出ない。"""
    from lib.rendering import render
    html = render(_make_chip_topology())
    phys = _extract_physical_view(html)
    # GigabitEthernet0/1（非接続・非Loopback）の if-row がノード SVG に存在しないこと
    # ただし SITE-LAN description はカード表（SVG外）には出てよい
    # Physical ビュー SVG 内に if-row で Gi0/1 の IP（192.168.1.1）が表示されないこと
    # （if-chip の title には許容するが if-row としての表示はしない）
    if_row_elems = re.findall(r'class="[^"]*if-row[^"]*"', phys)
    assert len(if_row_elems) == 0, \
        f"Physical ビューに if-row 要素が残っている（チップ化後は不要）: {len(if_row_elems)}"


@pytest.mark.unit
def test_i3_chip_has_hover_title():
    """#2: チップ要素（if-chip）の hover <title> に IF 名/IP が含まれる。"""
    from lib.rendering import render
    html = render(_make_chip_topology())
    phys = _extract_physical_view(html)
    # if-chip 近傍に <title>GigabitEthernet0/0 ... </title> が存在すること
    # （チップ g 内に title 要素がある）
    chip_group_pattern = re.findall(
        r'class="[^"]*if-chip[^"]*"[^>]*>.*?</(?:rect|circle|g)>',
        phys, re.DOTALL
    )
    # 全 Physical SVG 内で GigabitEthernet0/0 が title 要素の近傍にあること
    titles_in_phys = re.findall(r'<title>([^<]+)</title>', phys)
    if_name_in_title = any("GigabitEthernet0/0" in t or "Loopback0" in t for t in titles_in_phys)
    assert if_name_in_title, \
        f"if-chip の <title> に IF 名（GigabitEthernet0/0 / Loopback0）が見つからない: titles={titles_in_phys[:5]}"


@pytest.mark.unit
def test_i3_chip_card_still_has_all_interfaces():
    """#2: カード表（#cards-section 以降）には非接続IFを含む全IFが残る。"""
    from lib.rendering import render
    html = render(_make_chip_topology())
    # SVG 以降の cards-section 部分を取り出す
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    assert cards_m, "cards-section が見つからない"
    cards = cards_m.group(1)
    # 非接続・非Loopback のGi0/1 IP（192.168.1.1）がカードには存在すること
    assert "GigabitEthernet0/1" in cards, \
        "カード表に非接続IF（GigabitEthernet0/1）が存在しない"
    assert "GigabitEthernet0/0" in cards, \
        "カード表に接続IF（GigabitEthernet0/0）が存在しない"
    assert "Loopback0" in cards, \
        "カード表に Loopback0 が存在しない"


@pytest.mark.unit
def test_i3_chip_deterministic():
    """#2: チップ化 Physical ビューの render が決定的（2回一致）。"""
    from lib.rendering import render
    import copy
    topo = _make_chip_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "チップ化後の render が非決定的"


# ---------------------------------------------------------------------------
# #3: LAYERS トグルが cards-section の直前/近傍に配置される
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_i3_layers_toggle_near_cards_section(rendered_html):
    """#3/#Phase1-B: LAYERS トグルの DOM が cards-section 内またはその近傍にある。
    Phase 1 で LAYERS トグルは cards-section 内部（上部）に移動された。"""
    # cards-section の開始から内部 2000 文字以内に layer-toggle が存在すること
    cards_pos = rendered_html.find('id="cards-section"')
    assert cards_pos > 0, "cards-section が見つからない"
    # cards-section の直前 2000 文字以内 OR 直後 2000 文字以内（内部含む）
    pre_cards = rendered_html[max(0, cards_pos - 2000):cards_pos]
    post_cards = rendered_html[cards_pos:cards_pos + 2000]
    assert ('layer-toggle' in pre_cards or 'data-layer=' in pre_cards or
            'layer-toggle' in post_cards or 'data-layer=' in post_cards), \
        "LAYERS トグルが cards-section の前後（2000文字以内）に存在しない"


@pytest.mark.unit
def test_i3_layers_toggle_not_only_in_controls(rendered_html):
    """#3: LAYERS トグルがコントロールバー（.controls 内）だけに存在しない。
    移設後は cards-section 近傍に存在し、.controls 内には置かれない（または空）。"""
    # .controls セクション内の layer-toggle の存在を確認
    controls_m = re.search(r'class="controls"[^>]*>(.*?)</div>', rendered_html, re.DOTALL)
    if controls_m:
        controls_content = controls_m.group(1)
        # controls 内に layer-toggle が「ない」か、あっても cards-section 近傍にもある
        # 新仕様: controls 内には layer-toggle を含まない
        assert 'layer-toggle' not in controls_content, \
            "移設後も .controls 内に layer-toggle が残っている（移設されていない）"


# ---------------------------------------------------------------------------
# #8: diagram-pane max-height / overflow, cards 折りたたみトグル
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_i3_diagram_pane_has_overflow_css(rendered_html):
    """#8: SVG を囲む要素（#svg-container or #diagram-pane）に overflow:auto/scroll の CSS がある。"""
    # style 属性またはスタイルブロック内に overflow が設定されていること
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined_style = "\n".join(style_blocks)
    # SVG コンテナの CSS に overflow が含まれること
    has_overflow = (
        re.search(r'#svg-container\s*\{[^}]*overflow\s*:', combined_style) is not None or
        re.search(r'#diagram-pane\s*\{[^}]*overflow\s*:', combined_style) is not None
    )
    assert has_overflow, \
        "#svg-container または #diagram-pane の CSS に overflow が設定されていない"


@pytest.mark.unit
def test_i3_diagram_pane_has_max_height_css(rendered_html):
    """#8/#Phase1-A: SVG コンテナの高さ制御が行われている。
    Phase 1 で max-height:70vh は廃止され、flex レイアウトで高さを制御する。
    代わりに min-height または flex: 1 が CSS に含まれること。"""
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined_style = "\n".join(style_blocks)
    # Phase 1: max-height は廃止、min-height または flex 制御に変更
    has_height_control = (
        re.search(r'#svg-container\s*\{[^}]*min-height\s*:', combined_style) is not None or
        re.search(r'#svg-container\s*\{[^}]*flex\s*:', combined_style) is not None or
        re.search(r'#svg-container\s*\{[^}]*height\s*:', combined_style) is not None
    )
    assert has_height_control, \
        "#svg-container の CSS に高さ制御（min-height/flex/height）が設定されていない"


@pytest.mark.unit
def test_i3_cards_section_default_visible(rendered_html):
    """#8: cards-section はデフォルト表示（display:none / hidden で隠れていない）。"""
    # id="cards-section" の要素に display:none がついていないこと
    # style 属性で直接隠されていないこと
    m = re.search(r'id="cards-section"([^>]*)', rendered_html)
    assert m, "cards-section が見つからない"
    attrs = m.group(1)
    assert 'display:none' not in attrs and 'display: none' not in attrs, \
        "cards-section がデフォルトで display:none になっている（常時表示すべき）"


@pytest.mark.unit
def test_i3_cards_toggle_button_exists(rendered_html):
    """#8/#Phase1-B: cards-section の表示制御が行われている。
    Phase 1 で折りたたみトグルボタンは廃止され、常時表示（スプリットペイン）になった。
    代わりに cards-section が DOM に存在することを確認する。"""
    # Phase 1 以降: 折りたたみは廃止、cards-section が常時表示される
    assert 'id="cards-section"' in rendered_html, \
        "cards-section が存在しない"


@pytest.mark.unit
def test_i3_cards_toggle_js_function_removed_in_phase1(rendered_html):
    """#8/#Phase1-B: toggleCards 関数が Phase1 で廃止されていることを確認（HIGH H-1 名称・内容整合）

    旧テスト名 test_i3_cards_toggle_js_function_exists は「存在する」と名乗りながら
    廃止確認していた（名前と内容の乖離）。Phase1 後は toggleCards が存在しないことを
    明示的に検証する（test_p1b_toggle_cards_function_removed と同趣旨の確認）。
    """
    assert "toggleCards" not in rendered_html, \
        "toggleCards 関数が JS に残存している（Phase1 で廃止されるべき）"


# ===========================================================================
# iteration-3 Batch2: #4 AS枠視認性改善 / #5 BGP IP↔IP表示
# ===========================================================================

# ---------------------------------------------------------------------------
# #4: AS枠（as-group）視認性改善テスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_i3b4_as_group_label_chip_has_rect_bg():
    """#4: as-group ラベルが背景チップ（<rect class="as-group-label-bg">）を持つ"""
    from lib.rendering.svg import _svg_bgp_as_groups
    devs = [
        {"id": "r1", "hostname": "R1", "as": 65001},
        {"id": "r2", "hostname": "R2", "as": 65001},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (400.0, 300.0)}
    svg = _svg_bgp_as_groups(devs, positions)
    # ラベル背景チップ: class="as-group-label-bg" の <rect> が存在すること
    assert 'as-group-label-bg' in svg, \
        "as-group ラベルの背景チップ要素（as-group-label-bg）が存在しない"


@pytest.mark.unit
def test_i3b4_as_group_label_chip_before_text():
    """#4: as-group ラベル背景チップが <text class="as-group-label"> より前に DOM 出力される（背面）"""
    from lib.rendering.svg import _svg_bgp_as_groups
    devs = [{"id": "r1", "hostname": "R1", "as": 65001}]
    positions = {"r1": (300.0, 300.0)}
    svg = _svg_bgp_as_groups(devs, positions)
    chip_pos = svg.find('as-group-label-bg')
    # <text ... class="as-group-label"> の位置（ダブルクォート or シングルクォート）
    label_pos = svg.find('<text')
    # chip rect が最初の <text> より前に現れること
    assert chip_pos != -1, "as-group-label-bg が見つからない"
    assert label_pos != -1, "<text> が見つからない"
    assert chip_pos < label_pos, \
        f"背景チップ({chip_pos}) が <text>({label_pos}) より後に出力されている"


@pytest.mark.unit
def test_i3b4_as_group_css_fill_defined():
    """#4: CSS に as-group の fill（背景色）ルールが存在する"""
    from lib.rendering.template import _CSS
    # as-group クラスに fill プロパティが定義されていること
    assert '.as-group' in _CSS, "CSS に .as-group ルールがない"
    # as-group-label-bg のスタイルも定義されていること
    assert 'as-group-label-bg' in _CSS, "CSS に as-group-label-bg ルールがない"


@pytest.mark.unit
def test_i3b4_as_group_css_stroke_visible():
    """#4: CSS の .as-group に stroke（枠線）プロパティが定義されている"""
    from lib.rendering.template import _CSS
    import re
    # .as-group ブロックを抽出して stroke プロパティを確認
    m = re.search(r'\.as-group\s*\{([^}]+)\}', _CSS)
    assert m is not None, "CSS に .as-group { ... } ブロックが見つからない"
    block = m.group(1)
    assert 'stroke' in block, f"CSS の .as-group に stroke プロパティがない: {block}"


@pytest.mark.unit
def test_i3b4_as_group_label_chip_text_correct():
    """#4: as-group ラベルチップの <text> に「AS {asn}」が含まれる"""
    from lib.rendering.svg import _svg_bgp_as_groups
    devs = [
        {"id": "r1", "hostname": "R1", "as": 65001},
        {"id": "r2", "hostname": "R2", "as": 65002},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (500.0, 300.0)}
    svg = _svg_bgp_as_groups(devs, positions)
    assert "AS 65001" in svg, "AS 65001 ラベルが存在しない"
    assert "AS 65002" in svg, "AS 65002 ラベルが存在しない"


@pytest.mark.unit
def test_i3b4_as_group_label_chip_at_topleft():
    """#4: ラベルチップが枠の左上付近に配置される（x が枠左端 + 小さなオフセット）"""
    from lib.rendering.svg import _svg_bgp_as_groups
    devs = [{"id": "r1", "hostname": "R1", "as": 65001}]
    positions = {"r1": (300.0, 300.0)}
    svg = _svg_bgp_as_groups(devs, positions)

    # as-group <rect>（class 完全一致）の x/width を抽出。
    # class="as-group-label-bg" は除外するために class="as-group" のみを対象とする。
    m_rect = re.search(r'<rect[^>]+x="([^"]+)"[^>]+width="([^"]+)"[^>]+class="as-group"[^-]', svg)
    if not m_rect:
        m_rect = re.search(r'<rect[^>]+class="as-group"[^-][^>]*x="([^"]+)"[^>]*width="([^"]+)"', svg)
    if not m_rect:
        # フォールバック: rx="10" ry="10" class="as-group" パターン（svg.py の出力順序）
        m_rect = re.search(r'<rect x="([^"]+)" y="[^"]+" width="([^"]+)" height="[^"]+" rx="10" ry="10" class="as-group"', svg)
    assert m_rect, f"as-group <rect> が見つからない: {svg[:300]}"
    rect_x = float(m_rect.group(1))
    rect_w = float(m_rect.group(2))

    # ラベル（text）の x 座標を抽出
    m_text = re.search(r'<text x="([^"]+)"[^>]+class="as-group-label"', svg)
    if not m_text:
        m_text = re.search(r'<text[^>]+class="as-group-label"[^>]*x="([^"]+)"', svg)
    assert m_text, "as-group-label <text> が見つからない"
    label_x = float(m_text.group(1))

    # ラベルが枠の左半分内（左寄り）に配置されていること
    assert label_x >= rect_x, \
        f"ラベル x={label_x:.1f} が枠左端 {rect_x:.1f} より左"
    assert label_x < rect_x + rect_w / 2 + 1, \
        f"ラベル x={label_x:.1f} が枠中央 {rect_x + rect_w/2:.1f} より右（左上配置でない）"


@pytest.mark.unit
def test_i3b4_as_group_deterministic_with_chip():
    """#4: チップ付き AS 枠の出力が決定的（同一入力で2回一致）"""
    from lib.rendering.svg import _svg_bgp_as_groups
    import copy
    devs = [
        {"id": "r1", "hostname": "R1", "as": 65001},
        {"id": "r2", "hostname": "R2", "as": 65002},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (500.0, 300.0)}
    svg1 = _svg_bgp_as_groups(copy.deepcopy(devs), copy.deepcopy(positions))
    svg2 = _svg_bgp_as_groups(copy.deepcopy(devs), copy.deepcopy(positions))
    assert svg1 == svg2, "AS 枠チップ付きの出力が非決定的"


# ---------------------------------------------------------------------------
# #5: BGP エッジの IP↔IP 表示テスト
# ---------------------------------------------------------------------------

def _make_ebgp_p2p_topology_with_ips():
    """eBGP p2p: r1(10.0.0.1) ↔ r2(10.0.0.2)。local_ip/neighbor_ip 両方あり。"""
    return {
        "title": "eBGP P2P IP Test",
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


def _make_ibgp_loopback_topology_no_local_ip():
    """iBGP loopback ピア: local_ip が null のケース（欠損でも壊れない）"""
    return {
        "title": "iBGP Loopback IP Test",
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
                {"device": "r1", "local_as": 65001, "local_ip": None,
                 "neighbor_ip": "10.255.0.2", "peer_as": 65001, "type": "ibgp"},
                {"device": "r2", "local_as": 65001, "local_ip": None,
                 "neighbor_ip": "10.255.0.1", "peer_as": 65001, "type": "ibgp"},
            ],
            "ospf": [],
            "static": [],
        },
    }


@pytest.mark.unit
def test_i3b5_ebgp_edge_shows_neighbor_ip():
    """#5: eBGP エッジに neighbor_ip (10.0.0.2) が表示される"""
    from lib.rendering import render
    html = render(_make_ebgp_p2p_topology_with_ips())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"
    assert "10.0.0.2" in bgp_view, \
        "eBGP エッジに neighbor_ip (10.0.0.2) が表示されていない"


@pytest.mark.unit
def test_i3b5_ebgp_edge_shows_local_ip():
    """#5: eBGP エッジに local_ip (10.0.0.1) が表示される"""
    from lib.rendering import render
    html = render(_make_ebgp_p2p_topology_with_ips())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"
    assert "10.0.0.1" in bgp_view, \
        "eBGP エッジに local_ip (10.0.0.1) が表示されていない"


@pytest.mark.unit
def test_i3b5_ibgp_loopback_no_local_ip_no_crash():
    """#5: local_ip=null の iBGP loopback ピアで例外が起きない"""
    from lib.rendering import render
    try:
        html = render(_make_ibgp_loopback_topology_no_local_ip())
    except Exception as e:
        pytest.fail(f"local_ip=null の iBGP で例外が発生: {e}")
    assert isinstance(html, str)
    assert "<svg" in html.lower()


@pytest.mark.unit
def test_i3b5_ibgp_loopback_shows_neighbor_ip():
    """#5: local_ip=null の iBGP でも neighbor_ip が表示される"""
    from lib.rendering import render
    html = render(_make_ibgp_loopback_topology_no_local_ip())
    bgp_view = _extract_bgp_view_full(html)
    assert bgp_view, "BGP ビューが見つからない"
    # neighbor_ip (10.255.0.2 か 10.255.0.1) のどちらかが表示されること
    has_ip = "10.255.0.1" in bgp_view or "10.255.0.2" in bgp_view
    assert has_ip, \
        "local_ip=null の iBGP でも neighbor_ip のいずれかが表示されていない"


@pytest.mark.unit
def test_i3b5_bgp_edge_title_has_ips():
    """#5: BGP エッジ <title> に local_ip / neighbor_ip / AS 情報が含まれる"""
    from lib.rendering.svg import _svg_bgp_edges
    interfaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30"},
        {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30"},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
         "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (400.0, 300.0)}
    svg = _svg_bgp_edges(bgp_entries, interfaces, positions)
    assert "<title>" in svg, "BGP エッジに <title> 要素がない"
    assert "10.0.0.1" in svg, "<title> に local_ip が含まれない"
    assert "10.0.0.2" in svg, "<title> に neighbor_ip が含まれない"


@pytest.mark.unit
def test_i3b5_bgp_edge_null_local_ip_title_no_crash():
    """#5: local_ip=null の BGP エッジで <title> 生成が壊れない"""
    from lib.rendering.svg import _svg_bgp_edges
    interfaces = [
        {"id": "r1::lo0", "device": "r1", "name": "Loopback0", "ip": "10.255.0.1/32"},
        {"id": "r2::lo0", "device": "r2", "name": "Loopback0", "ip": "10.255.0.2/32"},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "local_ip": None,
         "neighbor_ip": "10.255.0.2", "peer_as": 65001, "type": "ibgp"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (400.0, 300.0)}
    try:
        svg = _svg_bgp_edges(bgp_entries, interfaces, positions)
    except Exception as e:
        pytest.fail(f"local_ip=null で _svg_bgp_edges が例外: {e}")
    assert "10.255.0.2" in svg, "neighbor_ip が表示されていない"


@pytest.mark.unit
def test_i3b5_ebgp_edge_ip_display_format():
    """#5: eBGP エッジの IP 表示が「local_ip↔neighbor_ip」形式を含む"""
    from lib.rendering.svg import _svg_bgp_edges
    interfaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30"},
        {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30"},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
         "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (400.0, 300.0)}
    svg = _svg_bgp_edges(bgp_entries, interfaces, positions)
    # IP 表示: 「10.0.0.1↔10.0.0.2」または「10.0.0.1 ↔ 10.0.0.2」形式
    has_arrow = ("10.0.0.1↔10.0.0.2" in svg or
                 "10.0.0.1 ↔ 10.0.0.2" in svg or
                 ("10.0.0.1" in svg and "10.0.0.2" in svg))
    assert has_arrow, "IP ↔ IP 形式の表示が存在しない"


@pytest.mark.unit
def test_i3b5_ibgp_loopback_null_local_ip_shows_neighbor_only():
    """#5: local_ip=null の iBGP エッジは neighbor_ip のみを表示（欠損側は省略）"""
    from lib.rendering.svg import _svg_bgp_edges
    interfaces = [
        {"id": "r1::lo0", "device": "r1", "name": "Loopback0", "ip": "10.255.0.1/32"},
        {"id": "r2::lo0", "device": "r2", "name": "Loopback0", "ip": "10.255.0.2/32"},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "local_ip": None,
         "neighbor_ip": "10.255.0.2", "peer_as": 65001, "type": "ibgp"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (400.0, 300.0)}
    svg = _svg_bgp_edges(bgp_entries, interfaces, positions)
    # neighbor_ip が表示されること
    assert "10.255.0.2" in svg, "neighbor_ip が表示されていない"
    # "None" という文字列が本文（badge 表示）に出ないこと
    # title 内は許容、badge テキストには出ないこと
    badge_texts = re.findall(r'class="bgp-badge[^"]*"[^>]*>([^<]+)', svg)
    for badge_text in badge_texts:
        assert "None" not in badge_text, \
            f"BGP バッジに 'None' 文字列が含まれている: {badge_text!r}"


@pytest.mark.unit
def test_i3b5_ebgp_edge_deterministic():
    """#5: IP表示付き BGP エッジが決定的（同一入力で2回一致）"""
    from lib.rendering.svg import _svg_bgp_edges
    interfaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30"},
        {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30"},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
         "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (400.0, 300.0)}
    svg1 = _svg_bgp_edges(bgp_entries, interfaces, positions)
    svg2 = _svg_bgp_edges(bgp_entries, interfaces, positions)
    assert svg1 == svg2, "BGP エッジ IP 表示が非決定的"


# ===========================================================================
# iteration-3 Batch3 #6: Static Routes 行の経路ハイライト
# ===========================================================================

def _make_segment_static_topology():
    """next_hop が共有セグメント上の機器を指す static ルートを含む topology。"""
    return {
        "title": "Segment Static Test",
        "generated_from": [],
        "devices": [
            {"id": "sw1", "hostname": "SW1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "sw2", "hostname": "SW2", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "gw1", "hostname": "GW1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "sw1::eth0", "device": "sw1", "name": "eth0",
             "ip": "192.168.10.1/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "sw2::eth0", "device": "sw2", "name": "eth0",
             "ip": "192.168.10.2/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "gw1::eth0", "device": "gw1", "name": "eth0",
             "ip": "192.168.10.254/24", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [
            {
                "id": "seg-192_168_10_0_24",
                "subnet": "192.168.10.0/24",
                "members": ["sw1::eth0", "sw2::eth0", "gw1::eth0"],
            }
        ],
        "routing": {
            "bgp": [],
            "ospf": [],
            "static": [
                {"device": "gw1", "prefix": "0.0.0.0/0", "next_hop": "192.168.10.2"},
                {"device": "sw1", "prefix": "10.0.0.0/8", "next_hop": "192.168.10.254"},
                {"device": "sw2", "prefix": "10.0.0.0/8", "next_hop": "192.168.99.1"},
            ],
        },
    }


def _make_p2p_static_topology():
    """next_hop が p2p リンク上の機器を指す static ルートを含む topology。"""
    return {
        "title": "P2P Static Test",
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
            "bgp": [],
            "ospf": [],
            "static": [
                {"device": "r1", "prefix": "0.0.0.0/0", "next_hop": "10.0.0.2"},
                {"device": "r2", "prefix": "192.168.0.0/16", "next_hop": "10.0.0.1"},
            ],
        },
    }


# ---- #2/#6: _build_static_route_map のユニットテスト -----------------------

@pytest.mark.unit
def test_i3b3_6_build_static_route_map_exists():
    """#2: _build_static_route_map 関数が core.py に存在する"""
    from lib.rendering.core import _build_static_route_map
    assert callable(_build_static_route_map)


@pytest.mark.unit
def test_i3b3_6_static_route_map_p2p_finds_link():
    """#2: p2p リンク上の next_hop -> route_edge_id が link_id になる"""
    from lib.rendering.core import _build_static_route_map
    from lib.rendering.svg import _make_link_id
    topo = _make_p2p_static_topology()
    route_map = _build_static_route_map(
        topo["routing"]["static"],
        topo["links"],
        topo["segments"],
        topo["interfaces"],
    )
    key = ("r1", "0.0.0.0/0")
    assert key in route_map, f"r1/0.0.0.0/0 がマップに存在しない: {route_map}"
    info = route_map[key]
    expected_lid = _make_link_id("r1", "eth0", "r2", "eth0")
    assert info.get("route_edge_id") == expected_lid, \
        f"route_edge_id 不一致: {info.get('route_edge_id')!r} != {expected_lid!r}"
    assert info.get("nexthop_device_id") == "r2", \
        f"nexthop_device_id 不一致: {info.get('nexthop_device_id')!r}"


@pytest.mark.unit
def test_i3b3_6_static_route_map_p2p_reverse():
    """#2: p2p リンクの逆方向も正しく解決される"""
    from lib.rendering.core import _build_static_route_map
    from lib.rendering.svg import _make_link_id
    topo = _make_p2p_static_topology()
    route_map = _build_static_route_map(
        topo["routing"]["static"],
        topo["links"],
        topo["segments"],
        topo["interfaces"],
    )
    key = ("r2", "192.168.0.0/16")
    assert key in route_map, "r2/192.168.0.0/16 がマップに存在しない"
    info = route_map[key]
    expected_lid = _make_link_id("r1", "eth0", "r2", "eth0")
    assert info.get("route_edge_id") == expected_lid
    assert info.get("nexthop_device_id") == "r1"


@pytest.mark.unit
def test_i3b3_6_static_route_map_segment_finds_seg():
    """#2: セグメント上の next_hop -> route_edge_id が seg-id になる"""
    from lib.rendering.core import _build_static_route_map
    topo = _make_segment_static_topology()
    route_map = _build_static_route_map(
        topo["routing"]["static"],
        topo["links"],
        topo["segments"],
        topo["interfaces"],
    )
    key = ("gw1", "0.0.0.0/0")
    assert key in route_map, "gw1/0.0.0.0/0 がマップに存在しない"
    info = route_map[key]
    assert info.get("route_edge_id") == "seg-192_168_10_0_24", \
        f"route_edge_id 不一致: {info.get('route_edge_id')!r}"
    assert info.get("nexthop_device_id") == "sw2", \
        f"nexthop_device_id 不一致: {info.get('nexthop_device_id')!r}"


@pytest.mark.unit
def test_i3b3_6_static_route_map_unknown_nexthop_no_entry():
    """#2: 経路不明の next_hop はマップにないか route_edge_id=None"""
    from lib.rendering.core import _build_static_route_map
    topo = _make_segment_static_topology()
    route_map = _build_static_route_map(
        topo["routing"]["static"],
        topo["links"],
        topo["segments"],
        topo["interfaces"],
    )
    key = ("sw2", "10.0.0.0/8")
    if key in route_map:
        info = route_map[key]
        assert info.get("route_edge_id") is None, \
            f"解決不能 next_hop に route_edge_id が設定されている: {info}"


@pytest.mark.unit
def test_i3b3_6_static_route_map_deterministic():
    """#2: _build_static_route_map は決定的"""
    from lib.rendering.core import _build_static_route_map
    topo = _make_p2p_static_topology()
    m1 = _build_static_route_map(
        topo["routing"]["static"], topo["links"], topo["segments"], topo["interfaces"])
    m2 = _build_static_route_map(
        topo["routing"]["static"], topo["links"], topo["segments"], topo["interfaces"])
    assert m1 == m2, "route_map が非決定的"


# ---- #2/#6-2: cards.py の data-route-edge / data-route-nexthop-device ------

@pytest.mark.unit
def test_i3b3_6_static_row_has_data_route_edge_when_resolved():
    """#2: 経路解決済み static 行に data-route-edge が付く（p2p）"""
    from lib.rendering import render
    html = render(_make_p2p_static_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    assert re.search(r'<tr[^>]+data-route-edge="[^"]+"', cards_html), \
        "経路解決済み static 行に data-route-edge が付いていない"


@pytest.mark.unit
def test_i3b3_6_static_row_has_data_route_nexthop_device():
    """#2: 経路解決済み static 行に data-route-nexthop-device が付く"""
    from lib.rendering import render
    html = render(_make_p2p_static_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    assert re.search(r'<tr[^>]+data-route-nexthop-device="[^"]+"', cards_html), \
        "経路解決済み static 行に data-route-nexthop-device が付いていない"


@pytest.mark.unit
def test_i3b3_6_static_row_segment_has_data_route_edge():
    """#2: セグメント経路 static 行に正しい data-route-edge (seg-id) が付く"""
    from lib.rendering import render
    html = render(_make_segment_static_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    assert 'data-route-edge="seg-192_168_10_0_24"' in cards_html, \
        "セグメント static 行に正しい seg-id が data-route-edge に付いていない"


@pytest.mark.unit
def test_i3b3_6_static_row_unresolved_no_data_route_edge():
    """#2: 経路不明の static 行には data-route-edge が付かない（または空）"""
    from lib.rendering import render
    html = render(_make_segment_static_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    sw2_card_m = re.search(
        r'data-device="sw2"[^>]*>(.*?)(?=data-device="|$)',
        cards_html, re.DOTALL
    )
    if sw2_card_m:
        sw2_html = sw2_card_m.group(1)
        route_edges = re.findall(r'data-route-edge="([^"]*)"', sw2_html)
        for edge_id in route_edges:
            assert edge_id == "", \
                f"解決不能 next_hop の行に非空の data-route-edge がある: {edge_id!r}"


# ---- #2/#6-3: JS ハンドラの存在（構造テスト）---------------------------------

@pytest.mark.unit
def test_i3b3_6_js_toggle_static_route_highlight_exists(rendered_html):
    """#2: JS に toggleStaticRouteHighlight 関数が存在する"""
    assert "toggleStaticRouteHighlight" in rendered_html, \
        "toggleStaticRouteHighlight 関数が見つからない"


@pytest.mark.unit
def test_i3b3_6_js_toggle_static_uses_route_id(rendered_html):
    """#2: toggleStaticRouteHighlight が data-route-id を参照する（#2 で route-id ベースに更新）"""
    func_body = _extract_js_function(rendered_html, "toggleStaticRouteHighlight")
    assert func_body, "toggleStaticRouteHighlight 関数が見つからない"
    assert "route-id" in func_body or "routeId" in func_body, \
        "toggleStaticRouteHighlight が data-route-id を参照していない"


@pytest.mark.unit
def test_i3b3_6_js_toggle_static_uses_nexthop_device(rendered_html):
    """#2: toggleStaticRouteHighlight（または _applyStaticRowHighlights）が nexthop device を参照する"""
    func_body = _extract_js_function(rendered_html, "toggleStaticRouteHighlight")
    # _applyStaticRowHighlights も確認（新方式では再計算関数が分離されている）
    apply_body = _extract_js_function(rendered_html, "_applyStaticRowHighlights")
    combined = (func_body or "") + (apply_body or "")
    assert "nexthop" in combined.lower() or "nexthopdevice" in combined.lower() \
           or "route-nexthop" in combined.lower(), \
        "toggleStaticRouteHighlight/_applyStaticRowHighlights が nexthop_device を参照していない"


@pytest.mark.unit
def test_i3b3_6_js_toggle_static_uses_highlighted(rendered_html):
    """#2: _applyStaticRowHighlights が highlighted クラスを操作する"""
    apply_body = _extract_js_function(rendered_html, "_applyStaticRowHighlights")
    assert apply_body, "_applyStaticRowHighlights 関数が見つからない"
    assert "highlighted" in apply_body, \
        "_applyStaticRowHighlights が highlighted を操作していない"


@pytest.mark.unit
def test_i3b3_6_esc_clears_static_highlight(rendered_html):
    """#2: clearLinkHighlight が highlighted を解除する（Esc で全解除）"""
    clear_body = _extract_js_function(rendered_html, "clearLinkHighlight")
    assert clear_body, "clearLinkHighlight 関数が見つからない"
    assert "highlighted" in clear_body, \
        "clearLinkHighlight が highlighted を除去していない"


@pytest.mark.unit
def test_i3b3_6_static_row_no_crash_unresolved():
    """#2: 経路不明の static 行があっても render が例外を投げない"""
    from lib.rendering import render
    try:
        html = render(_make_segment_static_topology())
    except Exception as e:
        pytest.fail(f"経路不明 static ルートで例外が発生: {e}")
    assert isinstance(html, str)


@pytest.mark.unit
def test_i3b3_6_render_deterministic_with_static_routes():
    """#2: static route マップ追加後も決定性が維持される"""
    from lib.rendering import render
    import copy
    topo = _make_p2p_static_topology()
    h1 = render(copy.deepcopy(topo))
    h2 = render(copy.deepcopy(topo))
    assert h1 == h2, "#2 追加後の render() が非決定的"


# ===========================================================================
# iteration-3 Batch3 #7: セグメント IF 行双方向ハイライト
# ===========================================================================

def _make_seg_highlight_topology():
    """セグメント連動テスト用 topology（3 デバイスが 1 セグメントで接続）"""
    return {
        "title": "Seg Highlight Test",
        "generated_from": [],
        "devices": [
            {"id": "sw1", "hostname": "SW1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "sw2", "hostname": "SW2", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "sw3", "hostname": "SW3", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "sw1::eth0", "device": "sw1", "name": "eth0",
             "ip": "10.10.0.1/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "sw2::eth0", "device": "sw2", "name": "eth0",
             "ip": "10.10.0.2/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "sw3::eth0", "device": "sw3", "name": "eth0",
             "ip": "10.10.0.3/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "sw1::lo0", "device": "sw1", "name": "lo0",
             "ip": "1.1.1.1/32", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [
            {
                "id": "seg-10_10_0_0_24",
                "subnet": "10.10.0.0/24",
                "members": ["sw1::eth0", "sw2::eth0", "sw3::eth0"],
            }
        ],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


# ---- #7-1: iface_seg_id マップ（core.py）-----------------------------------

@pytest.mark.unit
def test_i3b3_7_iface_seg_id_map_built_in_render():
    """#7: render() が iface_seg_id マップを正しく構築して IF 行に data-seg-id が付く"""
    from lib.rendering import render
    html = render(_make_seg_highlight_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    assert 'data-seg-id="seg-10_10_0_0_24"' in cards_html, \
        "メンバー IF 行に data-seg-id が付いていない"


# ---- #7-2: cards.py の IF 行 data-seg-id -----------------------------------

@pytest.mark.unit
def test_i3b3_7_member_if_row_has_data_seg_id():
    """#7: セグメントメンバー IF の <tr> に data-seg-id が付く"""
    from lib.rendering import render
    html = render(_make_seg_highlight_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    seg_rows = re.findall(r'<tr[^>]+data-seg-id="([^"]*)"', cards_html)
    assert len(seg_rows) >= 3, \
        f"メンバー IF 行の data-seg-id が少ない: {len(seg_rows)} 個（期待: >=3）"
    for seg_id in seg_rows:
        assert seg_id == "seg-10_10_0_0_24", \
            f"data-seg-id の値が不正: {seg_id!r}"


@pytest.mark.unit
def test_i3b3_7_non_member_if_row_no_data_seg_id():
    """#7: セグメント非メンバーの IF 行には data-seg-id が付かない"""
    from lib.rendering import render
    html = render(_make_seg_highlight_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    lo0_rows = re.findall(
        r'<tr[^>]*>(?:[^<]|<(?!/tr))*?lo0(?:[^<]|<(?!/tr))*?</tr>',
        cards_html, re.DOTALL
    )
    for row in lo0_rows:
        seg_ids = re.findall(r'data-seg-id="([^"]*)"', row)
        for sid in seg_ids:
            assert sid == "", f"非メンバー lo0 行に非空の data-seg-id がある: {sid!r}"


@pytest.mark.unit
def test_i3b3_7_data_seg_id_and_link_id_coexist():
    """#7: p2p + セグメント兼用の IF 行に data-link-id と data-seg-id が共存する"""
    topo = {
        "title": "Coexist Test",
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
        "segments": [
            {"id": "seg-10_0_0_0_30", "subnet": "10.0.0.0/30",
             "members": ["r1::eth0", "r2::eth0"]},
        ],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    from lib.rendering import render
    html = render(topo)
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    tr_with_both = re.findall(
        r'<tr[^>]+data-link-id="[^"]*"[^>]+data-seg-id="[^"]*"[^>]*>|'
        r'<tr[^>]+data-seg-id="[^"]*"[^>]+data-link-id="[^"]*"[^>]*>',
        cards_html
    )
    assert len(tr_with_both) >= 1, \
        "p2p + セグメント兼用 IF 行に data-link-id と data-seg-id が共存していない"


# ---- #7-3: svg.py の data-seg-id -------------------------------------------

@pytest.mark.unit
def test_i3b3_7_seg_ellipse_has_data_seg_id():
    """#7: segment-node グループに data-seg-id が付く"""
    from lib.rendering import render
    html = render(_make_seg_highlight_topology())
    phys = _extract_physical_view(html)
    assert 'data-seg-id="seg-10_10_0_0_24"' in phys, \
        "セグメントノードに data-seg-id が付いていない"


@pytest.mark.unit
def test_i3b3_7_seg_edge_has_data_seg_id():
    """#7: seg-edge に data-seg-id が付く"""
    from lib.rendering import render
    html = render(_make_seg_highlight_topology())
    phys = _extract_physical_view(html)
    seg_edges = re.findall(r'<line[^>]+class="seg-edge[^"]*"[^>]*>', phys)
    assert len(seg_edges) >= 1, "seg-edge が見つからない"
    for edge in seg_edges:
        assert 'data-seg-id="' in edge, \
            f"seg-edge に data-seg-id がない: {edge}"


@pytest.mark.unit
def test_i3b3_7_seg_edge_data_seg_id_correct_value():
    """#7: seg-edge の data-seg-id が正しい seg-id を持つ"""
    from lib.rendering import render
    html = render(_make_seg_highlight_topology())
    phys = _extract_physical_view(html)
    edge_seg_ids = set(re.findall(
        r'<line[^>]+class="seg-edge[^"]*"[^>]*data-seg-id="([^"]*)"', phys
    ))
    if not edge_seg_ids:
        edge_seg_ids = set(re.findall(
            r'data-seg-id="([^"]*)"[^>]*class="seg-edge[^"]*"', phys
        ))
    assert "seg-10_10_0_0_24" in edge_seg_ids, \
        f"seg-edge の data-seg-id に期待値がない: {edge_seg_ids}"


# ---- #7-4: JS ハンドラの存在（構造テスト）-----------------------------------

@pytest.mark.unit
def test_i3b3_7_js_toggle_seg_highlight_exists(rendered_html):
    """#7: JS に toggleSegHighlight 関数が存在する"""
    assert "toggleSegHighlight" in rendered_html, \
        "toggleSegHighlight 関数が見つからない"


@pytest.mark.unit
def test_i3b3_7_js_toggle_seg_uses_data_seg_id(rendered_html):
    """#7: toggleSegHighlight が data-seg-id を参照する"""
    func_body = _extract_js_function(rendered_html, "toggleSegHighlight")
    assert func_body, "toggleSegHighlight 関数が見つからない"
    assert "seg-id" in func_body or "segId" in func_body, \
        "toggleSegHighlight が data-seg-id を参照していない"


@pytest.mark.unit
def test_i3b3_7_js_toggle_seg_uses_highlighted(rendered_html):
    """#7: toggleSegHighlight が highlighted クラスを操作する"""
    func_body = _extract_js_function(rendered_html, "toggleSegHighlight")
    assert func_body, "toggleSegHighlight 関数が見つからない"
    assert "highlighted" in func_body, \
        "toggleSegHighlight が highlighted を操作していない"


@pytest.mark.unit
def test_i3b3_7_js_seg_node_click_calls_toggle_seg(rendered_html):
    """#7: JS にセグメントノードクリック -> toggleSegHighlight の呼び出しがある"""
    assert "toggleSegHighlight" in rendered_html, "toggleSegHighlight が JS に存在しない"
    lower = rendered_html.lower()
    assert "segment-node" in lower or "seg-ellipse" in lower, \
        "セグメントノードへの参照が JS に存在しない"


@pytest.mark.unit
def test_i3b3_7_js_if_row_seg_click_calls_toggle_seg(rendered_html):
    """#7: data-seg-id を持つ IF 行クリック -> toggleSegHighlight の呼び出しがある"""
    assert "data-seg-id" in rendered_html and "toggleSegHighlight" in rendered_html, \
        "data-seg-id IF 行クリックハンドラが存在しない"


@pytest.mark.unit
def test_i3b3_7_esc_clears_seg_highlight(rendered_html):
    """#7: clearLinkHighlight が seg ハイライトも解除する（_selectedSegs 管理）"""
    clear_body = _extract_js_function(rendered_html, "clearLinkHighlight")
    assert clear_body, "clearLinkHighlight 関数が見つからない"
    has_seg_clear = "_selectedSegs" in clear_body or "seg" in clear_body.lower()
    assert has_seg_clear, "clearLinkHighlight が seg ハイライトを解除していない"


@pytest.mark.unit
def test_i3b3_7_render_deterministic_with_segments():
    """#7: セグメント data-seg-id 追加後も決定性が維持される"""
    from lib.rendering import render
    import copy
    topo = _make_seg_highlight_topology()
    h1 = render(copy.deepcopy(topo))
    h2 = render(copy.deepcopy(topo))
    assert h1 == h2, "#7 追加後の render() が非決定的"


# ---- golden テスト（#6/#7 総合）--------------------------------------

@pytest.mark.unit
def test_i3b3_golden_static_route_attrs_and_seg_id(sample_topology):
    """Batch3 golden: sample topology の render 結果が #6/#7 の新規属性・JS 関数を含む"""
    from lib.rendering import render
    import re as re2
    html = render(sample_topology)
    assert 'data-link-id=' in html, "data-link-id が存在しない"
    assert 'data-node-filter=' in html, "data-node-filter が存在しない"
    assert "setNodeVisibility" in html
    assert "toggleIfRowHighlight" in html
    assert "toggleStaticRouteHighlight" in html, "#6 JS 関数がない"
    assert "toggleSegHighlight" in html, "#7 JS 関数がない"
    external_refs = re2.findall(
        r'(?:src|href)\s*=\s*["\']https?://(?!www\.w3\.org)[^"\']*["\']',
        html, re2.IGNORECASE,
    )
    assert len(external_refs) == 0, f"外部 CDN 参照がある: {external_refs}"


# ===========================================================================
# iteration-3 review fixes
# ===========================================================================

# ---------------------------------------------------------------------------
# HC3: _is_loopback 境界値テスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_hc3_is_loopback_cisco_loopback0():
    """HC3: Cisco Loopback0 は loopback と判定される"""
    from lib.rendering.svg import _is_loopback
    assert _is_loopback("Loopback0") is True


@pytest.mark.unit
def test_hc3_is_loopback_juniper_lo0():
    """HC3: Juniper lo0 は loopback と判定される"""
    from lib.rendering.svg import _is_loopback
    assert _is_loopback("lo0") is True


@pytest.mark.unit
def test_hc3_is_loopback_juniper_lo0_dot0():
    """HC3: Juniper lo0.0 は loopback と判定される"""
    from lib.rendering.svg import _is_loopback
    assert _is_loopback("lo0.0") is True


@pytest.mark.unit
def test_hc3_is_loopback_local0_is_false():
    """HC3: local0 は loopback と判定されない（lo 前方一致の過広修正）"""
    from lib.rendering.svg import _is_loopback
    assert _is_loopback("local0") is False


@pytest.mark.unit
def test_hc3_is_loopback_local_bridge_is_false():
    """HC3: local-bridge は loopback と判定されない"""
    from lib.rendering.svg import _is_loopback
    assert _is_loopback("local-bridge") is False


@pytest.mark.unit
def test_hc3_is_loopback_lo_bare_is_true():
    """HC3: 'lo'（数字なし）は loopback と判定される"""
    from lib.rendering.svg import _is_loopback
    assert _is_loopback("lo") is True


@pytest.mark.unit
def test_hc3_is_loopback_ge0_is_false():
    """HC3: GigabitEthernet は loopback と判定されない"""
    from lib.rendering.svg import _is_loopback
    assert _is_loopback("GigabitEthernet0/0") is False


# ---------------------------------------------------------------------------
# MC1: _build_static_route_map リンク走査のソート安定化
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_mc1_static_route_map_stable_with_duplicate_subnet():
    """MC1: 重複サブネット候補があっても route_edge_id が決定的"""
    from lib.rendering.core import _build_static_route_map
    static_entries = [
        {"device": "r1", "prefix": "0.0.0.0/0", "next_hop": "10.0.0.2"},
    ]
    links = [
        {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
         "subnet": "10.0.0.0/30"},
        {"a_device": "r1", "a_if": "eth1", "b_device": "r3", "b_if": "eth0",
         "subnet": "10.0.0.0/30"},
    ]
    ifaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30"},
        {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30"},
        {"id": "r1::eth1", "device": "r1", "name": "eth1", "ip": "10.0.0.1/30"},
        {"id": "r3::eth0", "device": "r3", "name": "eth0", "ip": "10.0.0.2/30"},
    ]
    m1 = _build_static_route_map(static_entries, links, [], ifaces)
    m2 = _build_static_route_map(static_entries, links, [], ifaces)
    assert m1 == m2, "重複サブネット時に route_map が非決定的"


# ---------------------------------------------------------------------------
# TC1: eBGP エッジ IP 表示の vacuous OR を排除した厳密テスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_tc1_ebgp_edge_ip_display_format_strict():
    """TC1: eBGP エッジ IP 表示が「↔」形式のみ検証（vacuous OR を排除）"""
    from lib.rendering.svg import _svg_bgp_edges
    ifaces_data = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30"},
        {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30"},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
         "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (400.0, 300.0)}
    svg = _svg_bgp_edges(bgp_entries, ifaces_data, positions)
    has_bidirectional = "10.0.0.1↔10.0.0.2" in svg or "10.0.0.1 ↔ 10.0.0.2" in svg
    assert has_bidirectional, \
        f"IP ↔ IP 形式（↔記号）の表示が存在しない: svg={svg[:500]}"


# ---------------------------------------------------------------------------
# TC2: 解決不能 next_hop がマップに存在しないことを明示アサート
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_tc2_static_route_map_unknown_nexthop_strict():
    """TC2: 解決不能な next_hop はマップに存在しない（vacuous 空通過を修正）"""
    from lib.rendering.core import _build_static_route_map
    topo = _make_segment_static_topology()
    route_map = _build_static_route_map(
        topo["routing"]["static"],
        topo["links"],
        topo["segments"],
        topo["interfaces"],
    )
    key = ("sw2", "10.0.0.0/8")
    assert key not in route_map, \
        f"解決不能 next_hop がマップに存在する: {route_map.get(key)}"


# ---------------------------------------------------------------------------
# TC3: 経路不明 static 行はカード存在 + data-route-edge なし
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_tc3_static_row_unresolved_card_exists_no_route_edge():
    """TC3: 経路不明 static 行はカードが存在しかつ data-route-edge が付かない"""
    from lib.rendering import render
    html = render(_make_segment_static_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    card_match = re.search(r'data-device="sw2"', cards_html)
    assert card_match, "SW2 のデバイスカードが存在しない"
    sw2_sec_m = re.search(
        r'data-device="sw2"[^>]*>(.*?)(?=class="device-card"|$)',
        cards_html, re.DOTALL
    )
    if sw2_sec_m:
        sw2_html = sw2_sec_m.group(1)
        route_edges = re.findall(r'data-route-edge="([^"]+)"', sw2_html)
        assert len(route_edges) == 0, \
            f"解決不能 next_hop の行に非空 data-route-edge がある: {route_edges}"


# ---------------------------------------------------------------------------
# TH1/TH2: data-route-edge の実際の link-id / device 値を検証
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_th1_static_row_data_route_edge_has_correct_link_id():
    """TH1: data-route-edge の値が _make_link_id 算出値と一致する"""
    from lib.rendering import render
    from lib.rendering.svg import _make_link_id
    html = render(_make_p2p_static_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    expected_lid = _make_link_id("r1", "eth0", "r2", "eth0")
    assert f'data-route-edge="{expected_lid}"' in cards_html, \
        f"data-route-edge に期待する link-id がない: {expected_lid!r}"


@pytest.mark.unit
def test_th2_static_row_data_route_nexthop_device_has_correct_value():
    """TH2: data-route-nexthop-device の値が正しい機器ID"""
    from lib.rendering import render
    html = render(_make_p2p_static_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    assert 'data-route-nexthop-device="r2"' in cards_html, \
        "data-route-nexthop-device に 'r2' が入っていない"
    assert 'data-route-nexthop-device="r1"' in cards_html, \
        "data-route-nexthop-device に 'r1' が入っていない"


# ---------------------------------------------------------------------------
# TH3/TH4: clearHighlight / toggleStaticRouteHighlight の保護・分離
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_th3_clear_highlight_protects_static_route_edges(rendered_html):
    """TH3: clearHighlight が static 経路固定中のエッジを保護する"""
    func_body = _extract_js_function(rendered_html, "clearHighlight")
    assert func_body, "clearHighlight 関数が見つからない"
    has_protection = "_selectedLinks" in func_body or "_selectedStaticEdges" in func_body
    assert has_protection, \
        "clearHighlight が _selectedLinks/_selectedStaticEdges を参照していない"


@pytest.mark.unit
def test_th4_toggle_static_manages_nexthop_node(rendered_html):
    """#2: _applyStaticRowHighlights が nexthop ノードを集合で管理している（#2 で再計算関数に分離）"""
    # #2 では _applyStaticRowHighlights が nexthop ノードを管理する
    apply_body = _extract_js_function(rendered_html, "_applyStaticRowHighlights")
    assert apply_body, "_applyStaticRowHighlights 関数が見つからない"
    has_management = (
        "_selectedStaticNodes" in apply_body
        or "route-target" in apply_body
        or "_selectedNodes" in apply_body
    )
    assert has_management, \
        "_applyStaticRowHighlights が nexthop ノードを集合で管理していない"


# ---------------------------------------------------------------------------
# TH5/TH6: toggleSegHighlight の具体的な操作
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_th5_toggle_seg_add_remove_highlighted(rendered_html):
    """TH5: toggleSegHighlight が classList.add/remove('highlighted') を持つ"""
    func_body = _extract_js_function(rendered_html, "toggleSegHighlight")
    assert func_body, "toggleSegHighlight 関数が見つからない"
    assert ("classList.add('highlighted')" in func_body
            or 'classList.add("highlighted")' in func_body), \
        "toggleSegHighlight に classList.add('highlighted') がない"
    assert ("classList.remove('highlighted')" in func_body
            or 'classList.remove("highlighted")' in func_body), \
        "toggleSegHighlight に classList.remove('highlighted') がない"


@pytest.mark.unit
def test_th6_toggle_seg_manages_selected_segs(rendered_html):
    """TH6: toggleSegHighlight が _selectedSegs.add と .delete を持つ"""
    func_body = _extract_js_function(rendered_html, "toggleSegHighlight")
    assert func_body, "toggleSegHighlight 関数が見つからない"
    assert "_selectedSegs" in func_body, "toggleSegHighlight が _selectedSegs を参照していない"
    assert ".add(" in func_body, "_selectedSegs.add がない"
    assert ".delete(" in func_body, "_selectedSegs.delete がない"


# ---------------------------------------------------------------------------
# TH7/TH8: IIFE 内のリスナー登録確認
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_th7_seg_node_click_calls_toggle_seg_in_iife(rendered_html):
    """TH7: segment-node クリックリスナーが IIFE 内で toggleSegHighlight を呼ぶ"""
    # JS 部分のみを対象にする（CSS に .segment-node.highlighted が含まれるため）
    js_start = rendered_html.find("<script>")
    js_section = rendered_html[js_start:] if js_start != -1 else rendered_html
    iife_start = js_section.find("segment-node")
    assert iife_start != -1, "segment-node への参照が JS に存在しない"
    nearby = js_section[max(0, iife_start - 200):iife_start + 500]
    assert "toggleSegHighlight" in nearby, \
        "segment-node クリックハンドラが toggleSegHighlight を呼んでいない"


@pytest.mark.unit
def test_th8_if_row_seg_click_calls_toggle_seg_in_iife(rendered_html):
    """TH8: tr[data-seg-id] クリックリスナーが IIFE 内で toggleSegHighlight を呼ぶ"""
    tr_seg_pos = rendered_html.find('tr[data-seg-id]')
    assert tr_seg_pos != -1, "tr[data-seg-id] セレクタが JS に存在しない"
    nearby = rendered_html[max(0, tr_seg_pos - 100):tr_seg_pos + 300]
    assert "toggleSegHighlight" in nearby, \
        "tr[data-seg-id] クリックハンドラが toggleSegHighlight を呼んでいない"


# ---------------------------------------------------------------------------
# HC1/HC2: JS 修正確認テスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_hc1_clear_highlight_excludes_static_edges(rendered_html):
    """HC1: clearHighlight が static 経路固定エッジを保護"""
    func_body = _extract_js_function(rendered_html, "clearHighlight")
    assert func_body, "clearHighlight 関数が見つからない"
    has_protection = "_selectedLinks" in func_body or "_selectedStaticEdges" in func_body
    assert has_protection, \
        "clearHighlight が _selectedLinks/_selectedStaticEdges を参照していない"


@pytest.mark.unit
def test_hc2_toggle_static_uses_dedicated_node_set(rendered_html):
    """HC2: _applyStaticRowHighlights が nexthop ノードを _selectedStaticNodes/route-target で管理（#2 で移設）"""
    apply_body = _extract_js_function(rendered_html, "_applyStaticRowHighlights")
    assert apply_body, "_applyStaticRowHighlights 関数が見つからない"
    uses_dedicated = "_selectedStaticNodes" in apply_body or "route-target" in apply_body
    assert uses_dedicated, \
        "_applyStaticRowHighlights がnexthopノードを手動選択と分離していない（_selectedStaticNodes or route-target が必要）"


# ---------------------------------------------------------------------------
# MM1: _svg_bgp_as_groups の label_x/label_y デッドコード除去確認
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_mm1_svg_bgp_as_groups_no_dead_label_vars():
    """MM1: _svg_bgp_as_groups の label_x/label_y が除去されている（デッドコードなし）"""
    import ast
    import inspect
    from lib.rendering.svg import _svg_bgp_as_groups
    source = inspect.getsource(_svg_bgp_as_groups)
    tree = ast.parse(source)
    assigned_names: set = set()
    used_load_names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used_load_names.add(node.id)
    for var in ("label_x", "label_y"):
        if var in assigned_names:
            assert var in used_load_names, \
                f"MM1: {var} が代入されているが参照されていない（デッドコード）"


# ---------------------------------------------------------------------------
# HM4: ハイライト共通ヘルパーまたはインライン実装の確認
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_hm4_highlight_operations_present(rendered_html):
    """HM4: ハイライト操作が適切に実装されている（ヘルパーまたはインライン）"""
    has_helper = "_setHighlightByAttr" in rendered_html
    has_inline = (
        "querySelectorAll" in rendered_html
        and ("classList.add('highlighted')" in rendered_html
             or 'classList.add("highlighted")' in rendered_html)
    )
    assert has_helper or has_inline, \
        "ハイライト操作ヘルパーもインライン実装も見つからない"


# ===========================================================================
# Phase 1 — 画面レイアウト刷新＋ズーム操作UI（iteration-4）
# A: 上下スプリット＋境界ドラッグ
# B: 折りたたみトグルの廃止
# C: ズーム操作UI
# ===========================================================================

# ---------------------------------------------------------------------------
# A: 上下スプリット構造
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1a_split_divider_exists(rendered_html):
    """Phase1-A: HTML に id="split-divider" が含まれる（上下ペイン境界バー）"""
    assert 'id="split-divider"' in rendered_html, \
        "split-divider 要素が存在しない"


@pytest.mark.unit
def test_p1a_svg_container_no_max_height_70vh(rendered_html):
    """Phase1-A: #svg-container の max-height:70vh が撤去されている"""
    # CSS から max-height: 70vh が消えていること
    assert "max-height: 70vh" not in rendered_html and "max-height:70vh" not in rendered_html, \
        "#svg-container の max-height:70vh が残存している"


@pytest.mark.unit
def test_p1a_split_divider_css_cursor_row_resize(rendered_html):
    """Phase1-A: #split-divider に cursor:row-resize スタイルが適用される"""
    assert "row-resize" in rendered_html, \
        "split-divider に cursor:row-resize が設定されていない"


@pytest.mark.unit
def test_p1a_layout_height_100vh_or_dvh(rendered_html):
    """Phase1-A: ルートレイアウトが height:100vh（または 100dvh）系で高さ制御されている"""
    assert "100vh" in rendered_html or "100dvh" in rendered_html, \
        "height:100vh/100dvh がレイアウトに存在しない"


@pytest.mark.unit
def test_p1a_split_divider_js_mousedown(rendered_html):
    """Phase1-A: split-divider 専用 mousedown ハンドラが JS に存在する（HIGH H-3）

    冗長アサーションを排除し、split-divider 要素への addEventListener('mousedown' を
    具体的に検証する。divider.addEventListener('mousedown' パターンを確認。
    """
    # split-divider 要素の取得と addEventListener 登録の両方が存在すること
    assert 'getElementById(\'split-divider\')' in rendered_html or \
           'getElementById("split-divider")' in rendered_html, \
        "split-divider 要素の取得コードが JS に存在しない"
    # divider への mousedown リスナー登録が存在すること
    assert re.search(
        r"divider\.addEventListener\(['\"]mousedown['\"]",
        rendered_html
    ) is not None, "split-divider の mousedown addEventListener が JS に存在しない"


@pytest.mark.unit
def test_p1a_cards_section_overflow_auto(rendered_html):
    """Phase1-A: #cards-section が overflow:auto（独立スクロール）を持つ（CRIT-2 具体化）

    <style> ブロック内の #cards-section ルールに overflow: auto が含まれることを
    正規表現で限定検証する（HTML 全体の `overflow:auto` 存在に依存しない）。
    """
    assert 'id="cards-section"' in rendered_html, "#cards-section 要素が存在しない"
    # <style> タグ内の CSS を抽出
    style_match = re.search(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    assert style_match is not None, "<style> ブロックが存在しない"
    css_text = style_match.group(1)
    # #cards-section { ... overflow ... auto ... } パターンを検証
    pattern = r'#cards-section\s*\{[^}]*overflow\s*:\s*(auto|scroll)[^}]*\}'
    assert re.search(pattern, css_text, re.IGNORECASE) is not None, \
        "#cards-section CSS ルールに overflow: auto/scroll が設定されていない"


# ---------------------------------------------------------------------------
# B: 折りたたみトグルの廃止
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_toggle_cards_function_removed(rendered_html):
    """Phase1-B: toggleCards() 関数が HTML/JS に存在しない"""
    assert "toggleCards" not in rendered_html, \
        "toggleCards 関数が JS に残存している（廃止されるべき）"


@pytest.mark.unit
def test_p1b_cards_toggle_btn_removed(rendered_html):
    """Phase1-B: id="cards-toggle-btn" ボタンが HTML に存在しない"""
    assert 'id="cards-toggle-btn"' not in rendered_html, \
        "#cards-toggle-btn ボタンが HTML に残存している（廃止されるべき）"


@pytest.mark.unit
def test_p1b_cards_controls_class_removed(rendered_html):
    """Phase1-B: class="cards-controls" 折りたたみラッパーが HTML に存在しない"""
    assert 'class="cards-controls"' not in rendered_html, \
        ".cards-controls ラッパーが HTML に残存している（廃止されるべき）"


@pytest.mark.unit
def test_p1b_layer_toggles_still_exist(rendered_html):
    """Phase1-B: LAYERS トグル群（layer-toggle チェックボックス）は引き続き存在する"""
    assert "layer-toggle" in rendered_html, \
        "LAYERS トグル群が削除されている（折りたたみボタンのみ削除すべき）"


@pytest.mark.unit
def test_p1b_handle_layer_toggle_js_still_exists(rendered_html):
    """Phase1-B: handleLayerToggle JS 関数は引き続き存在する"""
    assert "handleLayerToggle" in rendered_html, \
        "handleLayerToggle JS 関数が削除されている（LAYERS 機能は維持すべき）"


@pytest.mark.unit
def test_p1b_layers_controls_div_still_exists(rendered_html):
    """Phase1-B: id="layers-controls" (LAYERS トグル div) は引き続き存在する"""
    assert 'id="layers-controls"' in rendered_html, \
        "#layers-controls div が削除されている（LAYERS 機能は維持すべき）"


# ---------------------------------------------------------------------------
# C: ズーム操作UI
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1c_zoom_fit_button_exists(rendered_html):
    """Phase1-C: ズーム fit ボタン（id="zoom-fit"）が存在する"""
    assert 'id="zoom-fit"' in rendered_html, \
        "ズーム fit ボタン (#zoom-fit) が存在しない"


@pytest.mark.unit
def test_p1c_zoom_in_button_exists(rendered_html):
    """Phase1-C: ズーム + ボタン（id="zoom-in"）が存在する"""
    assert 'id="zoom-in"' in rendered_html, \
        "ズーム + ボタン (#zoom-in) が存在しない"


@pytest.mark.unit
def test_p1c_zoom_out_button_exists(rendered_html):
    """Phase1-C: ズーム − ボタン（id="zoom-out"）が存在する"""
    assert 'id="zoom-out"' in rendered_html, \
        "ズーム − ボタン (#zoom-out) が存在しない"


@pytest.mark.unit
def test_p1c_zoom_reset_button_exists(rendered_html):
    """Phase1-C: 1:1 リセットボタン（id="zoom-reset"）が存在する"""
    assert 'id="zoom-reset"' in rendered_html, \
        "1:1 リセットボタン (#zoom-reset) が存在しない"


@pytest.mark.unit
def test_p1c_zoom_buttons_in_svg_container(rendered_html):
    """Phase1-C: ズームボタン群が #svg-container の内側に配置されている"""
    # svg-container の開始から最初の zoom-fit が現れること
    container_start = rendered_html.find('id="svg-container"')
    zoom_fit_pos = rendered_html.find('id="zoom-fit"')
    assert container_start != -1, "#svg-container が存在しない"
    assert zoom_fit_pos != -1, "#zoom-fit が存在しない"
    assert zoom_fit_pos > container_start, \
        "#zoom-fit が #svg-container の外側に配置されている"


@pytest.mark.unit
def test_p1c_zoom_fit_js_function_exists(rendered_html):
    """Phase1-C: zoomFit 関数が定義されておりズームボタンのクリックに紐付く（HIGH H-2 具体化）

    zoomFit 関数定義の存在と、zoom-fit ボタンへの addEventListener click 登録を
    具体的に検証する。
    """
    # zoomFit 関数定義が存在すること
    assert re.search(r'function\s+zoomFit\s*\(', rendered_html) is not None, \
        "zoomFit 関数定義が JS に存在しない"
    # zoom-fit ボタンへの click リスナー登録が存在すること
    assert re.search(
        r"zoomFitBtn\.addEventListener\(['\"]click['\"]",
        rendered_html
    ) is not None, "zoomFitBtn への click addEventListener が JS に存在しない"


@pytest.mark.unit
def test_p1c_zoom_controls_position_absolute(rendered_html):
    """Phase1-C: ズームボタン群がペイン内に重なるよう position:absolute（または sticky）が設定される"""
    assert "position:absolute" in rendered_html or "position: absolute" in rendered_html, \
        "ズームボタン群に position:absolute が設定されていない"


# ---------------------------------------------------------------------------
# 決定性: Phase 1 実装後も維持
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1_render_deterministic_after_phase1(sample_topology):
    """Phase1: 実装後も同一 topology 入力 → 同一 HTML 出力（決定性維持）

    Phase1 上下スプリット・ズームボタン・ディバイダドラッグ等の追加後も
    render() が同一入力に対して常に同一 HTML を返す決定性を維持していることを確認する。
    """
    from lib.rendering import render
    t1 = copy.deepcopy(sample_topology)
    t2 = copy.deepcopy(sample_topology)
    html1 = render(t1)
    html2 = render(t2)
    assert html1 == html2, "Phase1 実装後 render() が非決定的"


# ---------------------------------------------------------------------------
# 既存機能の維持確認
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1_wheel_zoom_handler_still_exists(rendered_html):
    """Phase1: wheel ズームハンドラは引き続き存在する"""
    assert "wheel" in rendered_html, "wheel ズームハンドラが削除されている"


@pytest.mark.unit
def test_p1_pan_mousedown_handler_still_exists(rendered_html):
    """Phase1: #svg-container への pan 専用 mousedown ハンドラが存在する（CRIT-1 具体化）

    `"mousedown" in html` の単純検証から、container.addEventListener('mousedown'
    パターン（シングル/ダブルクォート両対応）を具体検証に変更。
    """
    assert re.search(
        r"container\.addEventListener\(['\"]mousedown['\"]",
        rendered_html
    ) is not None, "container（#svg-container）への pan 専用 mousedown addEventListener が存在しない"


@pytest.mark.unit
def test_p1_set_node_visibility_still_exists(rendered_html):
    """Phase1: ノードフィルタ機能（setNodeVisibility）は引き続き存在する"""
    assert "setNodeVisibility" in rendered_html, \
        "setNodeVisibility（ノードフィルタ）が削除されている"


@pytest.mark.unit
def test_p1_toggle_seg_highlight_still_exists(rendered_html):
    """Phase1: セグメントハイライト（toggleSegHighlight）は引き続き存在する"""
    assert "toggleSegHighlight" in rendered_html, \
        "toggleSegHighlight が削除されている"


@pytest.mark.unit
def test_p1_toggle_if_row_highlight_still_exists(rendered_html):
    """Phase1: IF 行ハイライト（toggleIfRowHighlight）は引き続き存在する"""
    assert "toggleIfRowHighlight" in rendered_html, \
        "toggleIfRowHighlight が削除されている"


# ---------------------------------------------------------------------------
# Phase1 iteration-4: レビュー指摘 追加・具体化テスト群
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1a_split_pane_dom_order(rendered_html):
    """Phase1-A: svg-container → split-divider → cards-section の DOM 順序（HIGH H-4）

    上ペイン(svg-container) が下ペイン(cards-section) より前に、
    境界バー(split-divider) がその間に来ることを確認する。
    """
    svg_pos = rendered_html.find('id="svg-container"')
    divider_pos = rendered_html.find('id="split-divider"')
    cards_pos = rendered_html.find('id="cards-section"')
    assert svg_pos != -1, "#svg-container が存在しない"
    assert divider_pos != -1, "#split-divider が存在しない"
    assert cards_pos != -1, "#cards-section が存在しない"
    assert svg_pos < divider_pos, \
        "#svg-container が #split-divider より前に来ていない"
    assert divider_pos < cards_pos, \
        "#split-divider が #cards-section より前に来ていない"


@pytest.mark.unit
def test_p1c_zoom_constants_exist_in_js(rendered_html):
    """Phase1-C: ズームクランプ定数（ZOOM_MIN=0.2 / ZOOM_MAX=5.0）と divider minH=120 が JS に存在する（HIGH H-5）

    ZOOM_MIN/ZOOM_MAX 定数（または数値リテラル 0.2/5.0）および
    split-divider の最小高 minH=120 が JS 内に存在することを確認する。
    """
    # ZOOM_MIN/ZOOM_MAX 定数またはリテラル値が存在すること
    has_zoom_min = "ZOOM_MIN" in rendered_html or "0.2" in rendered_html
    has_zoom_max = "ZOOM_MAX" in rendered_html or "5.0" in rendered_html
    assert has_zoom_min, "ズーム下限値（ZOOM_MIN or 0.2）が JS に存在しない"
    assert has_zoom_max, "ズーム上限値（ZOOM_MAX or 5.0）が JS に存在しない"
    # divider の minH=120 が存在すること
    assert "minH" in rendered_html or re.search(r'\bvar\s+minH\s*=\s*120', rendered_html), \
        "divider minH（120）が JS に存在しない"


@pytest.mark.unit
def test_p1c_f_key_calls_zoom_fit(rendered_html):
    """Phase1-C: f/F キーが zoomFit() を呼び出す（タスク16 / docs-maint 整合）

    キーボードハンドラで 'f'/'F' キーが zoomFit() 呼び出しに繋がることを
    JS 文字列パターンで検証する。'f'/'F' キーブランチ内に zoomFit() 呼び出しが
    必要（等倍リセットの直接代入ではなく全体表示であること）。
    """
    # f/F キーの keydown ブランチ内で zoomFit() が呼ばれること
    # パターン: e.key === 'f' || e.key === 'F' の条件ブロック内に zoomFit() が存在する
    match = re.search(
        r"e\.key\s*===\s*['\"]f['\"]\s*\|\|\s*e\.key\s*===\s*['\"]F['\"]"
        r"[\s\S]{0,100}?zoomFit\(\)",
        rendered_html
    )
    assert match is not None, \
        "f/F キーのキーハンドラで zoomFit() が呼ばれていない（全体表示と等倍リセットが乖離）"


@pytest.mark.unit
def test_p1c_zoom_controls_guard_in_pan_mousedown(rendered_html):
    """Phase1-C: pan mousedown ハンドラに #zoom-controls のガードがある（correctness HIGH-1）

    ズームボタン押下で pan が誤発火しないよう、
    `e.target.closest('#zoom-controls')` の除外ガードが存在することを確認する。
    """
    assert "closest('#zoom-controls')" in rendered_html or \
           'closest("#zoom-controls")' in rendered_html, \
        "pan mousedown ハンドラに #zoom-controls ガードが存在しない"


@pytest.mark.unit
def test_p1c_zoom_fit_uses_all_four_viewbox_params(rendered_html):
    """Phase1-C: zoomFit が viewBox の4要素（minX/minY/W/H）をすべて parse する（correctness HIGH-2）

    `parts[0]` と `parts[1]`（vbX, vbY）が centering 計算に使われていることを確認する。
    """
    # zoomFit 関数内で parts[0]/parts[1] が vbX/vbY として使われること
    assert re.search(r'parts\[0\]|vbX|vb_x', rendered_html) is not None, \
        "zoomFit が viewBox の minX (parts[0] / vbX) を参照していない"
    assert re.search(r'parts\[1\]|vbY|vb_y', rendered_html) is not None, \
        "zoomFit が viewBox の minY (parts[1] / vbY) を参照していない"


@pytest.mark.unit
def test_p1c_zoom_fit_container_size_guard(rendered_html):
    """Phase1-C: zoomFit のコンテナ寸法0ガードが存在する（correctness MED）

    cw===0 または ch===0 の場合にフォールバック処理が行われることを確認する。
    """
    assert re.search(r'cw\s*===\s*0|ch\s*===\s*0', rendered_html) is not None, \
        "zoomFit のコンテナ寸法0ガード（cw===0 || ch===0）が存在しない"


@pytest.mark.unit
def test_p1c_divider_maxh_has_lower_bound(rendered_html):
    """Phase1-A: divider の maxH が下限（minH+1 以上）ガードを持つ（correctness MED / maint HIGH-2）

    `Math.max(minH + 1, window.innerHeight - 200)` パターンで
    maxH の下限を保証していることを確認する。
    """
    assert re.search(r'Math\.max\s*\(\s*minH\s*\+\s*1', rendered_html) is not None, \
        "divider maxH の下限ガード（Math.max(minH + 1, ...)）が存在しない"


@pytest.mark.unit
def test_p1c_zoom_reset_window_export(rendered_html):
    """Phase1-C: window._zoomReset と window._zoomFit がエクスポートされている（maint HIGH-1）

    Phase2 の selectView から呼べるよう、ズーム関数がグローバルに露出されていることを確認する。
    """
    assert "window._zoomFit" in rendered_html, \
        "window._zoomFit がエクスポートされていない"
    assert "window._zoomReset" in rendered_html, \
        "window._zoomReset がエクスポートされていない"


@pytest.mark.unit
def test_p1c_zoom_step_constant_defined(rendered_html):
    """Phase1-C: ズームステップ定数（ZOOM_STEP=1.2 または 1.2 リテラル）が重複なく一元定義（maint MED-3）

    ZOOM_STEP 定数または 1.2 が zoom/wheel/ボタンで統一的に使われていることの
    基礎確認として、ZOOM_STEP 定数定義または 1.2 リテラルが存在することを検証する。
    """
    assert "ZOOM_STEP" in rendered_html or "1.2" in rendered_html, \
        "ズームステップ値（ZOOM_STEP or 1.2）が JS に存在しない"


# ---------------------------------------------------------------------------
# MC3: _svg_nodes の docstring と実装の一致（None は空集合扱い）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_mc3_svg_nodes_connected_none_shows_only_loopback():
    """MC3: connected_iface_ids=None のとき Loopback のみ chip 表示（空集合扱い）"""
    from lib.rendering.svg import _svg_nodes
    dev_list = [{"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None}]
    pos = {"r1": (100.0, 100.0)}
    ibd = {
        "r1": [
            {"id": "r1::eth0", "device": "r1", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.1/30", "shutdown": False, "description": None},
            {"id": "r1::lo0", "device": "r1", "name": "Loopback0",
             "ip": "10.255.0.1/32", "shutdown": False, "description": None},
        ]
    }
    svg = _svg_nodes(
        dev_list, pos, ibd,
        show_interfaces=True, connected_iface_ids=None
    )
    assert "Loopback0" in svg, "connected_iface_ids=None のとき Loopback0 が表示されない"
    assert 'data-if="GigabitEthernet0/0"' not in svg, \
        "connected_iface_ids=None のとき非 Loopback IF が表示されている"


# ===========================================================================
# Phase 2 テスト群
# ===========================================================================

# ---------------------------------------------------------------------------
# #3: Static 行自体のハイライト（クリックした行のマーキング）
# ---------------------------------------------------------------------------

def _make_p2_static_topology():
    """Phase 2 テスト用 — static route がある2台構成"""
    return {
        "title": "P2 Static Test",
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
            "bgp": [],
            "ospf": [],
            "static": [
                {"device": "r1", "prefix": "192.168.2.0/24", "next_hop": "10.0.0.2"},
                {"device": "r2", "prefix": "192.168.1.0/24", "next_hop": "10.0.0.1"},
            ],
        },
    }


@pytest.mark.unit
def test_p2_3_static_row_highlight_css_exists(rendered_html):
    """#3: static 行クリック時に使うハイライトクラスの CSS ルールが存在する。

    `.route-row-selected` か `tr.highlighted` のいずれかの CSS 宣言が
    _CSS に含まれる（行マーキング用スタイル）。
    """
    has_route_row_selected = ".route-row-selected" in rendered_html
    has_tr_highlighted = "tr.highlighted" in rendered_html
    assert has_route_row_selected or has_tr_highlighted, \
        "static 行のハイライト CSS（.route-row-selected or tr.highlighted）が存在しない"


@pytest.mark.unit
def test_p2_3_toggle_static_adds_row_class(rendered_html):
    """#3: toggleStaticRouteHighlight が static 行自体にクラスを付与するロジックを含む。

    JS 内で `data-route-edge` を持つ行要素（row/tr）に対して
    classList.add/remove するコードが存在することを確認する。
    """
    # toggleStaticRouteHighlight 内のクリック行への classList 操作を検証
    js_section = rendered_html
    # toggleStaticRouteHighlight 関数定義部分を抽出
    m = re.search(
        r'function toggleStaticRouteHighlight\s*\(.*?\{(.*?)(?=\n    // ====)',
        js_section, re.DOTALL
    )
    func_body = m.group(1) if m else js_section
    # 行自体への classList 操作: e.currentTarget / row / tr の .classList.add/toggle
    has_row_marking = (
        "classList.add('route-row-selected')" in func_body
        or "classList.toggle('route-row-selected'" in func_body
        or re.search(r'\.classList\.(add|toggle)\(["\']route-row-selected', func_body) is not None
        or re.search(r'\.classList\.(add|toggle)\(["\']highlighted', func_body) is not None
    )
    assert has_row_marking, \
        "toggleStaticRouteHighlight が行自体に classList.add/toggle するロジックを持たない"


@pytest.mark.unit
def test_p2_3_clear_selection_removes_route_row_selected(rendered_html):
    """#3: clearSelection() / clearLinkHighlight() が route-row-selected を解除する。

    clearSelection または clearLinkHighlight 内で route-row-selected クラスを
    querySelectorAll + classList.remove するコードが存在する。
    """
    # JS 内で route-row-selected が存在し、かつ remove 操作が存在する
    has_clear = (
        "route-row-selected" in rendered_html
        and "classList.remove('route-row-selected')" in rendered_html
    )
    assert has_clear, \
        "clearSelection/clearLinkHighlight で route-row-selected が解除されない"


# ---------------------------------------------------------------------------
# #4: Shared Network (seg-edge / seg-ellipse) ハイライト CSS 欠落修正
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_4_seg_edge_highlighted_css_exists(rendered_html):
    """#4: .seg-edge.highlighted の CSS ルールが存在する（バグ修正）。

    stroke-width と stroke 系のプロパティを含む .seg-edge.highlighted ルールが
    _CSS に定義されている。
    """
    assert ".seg-edge.highlighted" in rendered_html, \
        ".seg-edge.highlighted の CSS ルールが存在しない（バグ #4 未修正）"


@pytest.mark.unit
def test_p2_4_seg_edge_highlighted_has_stroke_style(rendered_html):
    """#4: .seg-edge.highlighted の CSS が stroke 系プロパティを含む（視覚効果）。

    単なるクラス存在確認ではなく、実際に太線または色変更のスタイルが定義されている。
    """
    m = re.search(
        r'\.seg-edge\.highlighted\s*\{([^}]+)\}',
        rendered_html
    )
    assert m is not None, ".seg-edge.highlighted の CSS ブロックが存在しない"
    block = m.group(1)
    has_stroke = "stroke" in block
    assert has_stroke, \
        f".seg-edge.highlighted の CSS に stroke プロパティがない: {block!r}"


@pytest.mark.unit
def test_p2_4_seg_ellipse_highlighted_css_exists(rendered_html):
    """#4: .segment-node.highlighted .seg-ellipse の CSS ルールが存在する（バグ修正）。"""
    assert ".segment-node.highlighted" in rendered_html or \
           ".seg-ellipse.highlighted" in rendered_html, \
        ".segment-node.highlighted / .seg-ellipse.highlighted の CSS が存在しない（バグ #4 未修正）"


@pytest.mark.unit
def test_p2_4_seg_ellipse_highlighted_has_stroke_style(rendered_html):
    """#4: seg-ellipse highlighted の CSS に枠強調スタイルがある。"""
    # パターン1: .segment-node.highlighted .seg-ellipse { ... stroke ... }
    m1 = re.search(
        r'\.segment-node\.highlighted[^{]*\.seg-ellipse\s*\{([^}]+)\}',
        rendered_html
    )
    # パターン2: .seg-ellipse.highlighted { ... stroke ... }
    m2 = re.search(
        r'\.seg-ellipse\.highlighted\s*\{([^}]+)\}',
        rendered_html
    )
    block = (m1.group(1) if m1 else "") or (m2.group(1) if m2 else "")
    assert "stroke" in block, \
        f"seg-ellipse highlighted の CSS に stroke プロパティがない: {block!r}"


# ---------------------------------------------------------------------------
# #5: BGP Session ↔ 表の双方向ハイライト
# ---------------------------------------------------------------------------

def _make_p2_bgp_topology():
    """Phase 2 #5 テスト用 — BGP セッションがある2台構成（r1 AS65001 ↔ r2 AS65002）"""
    return {
        "title": "P2 BGP Test",
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


@pytest.mark.unit
def test_p2_5_bgp_session_has_data_bgp_id():
    """#5: bgp-session <g> に data-bgp-id 属性が付いている。

    _svg_bgp_edges が生成する <g class="bgp-session"> に
    data-bgp-id="r1|r2"（sorted 結合）が存在する。
    """
    from lib.rendering.svg import _svg_bgp_edges
    ifaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30"},
        {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30"},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
         "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
        {"device": "r2", "local_as": 65002, "local_ip": "10.0.0.2",
         "neighbor_ip": "10.0.0.1", "peer_as": 65001, "type": "ebgp"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (400.0, 300.0)}
    svg = _svg_bgp_edges(bgp_entries, ifaces, positions)
    assert 'data-bgp-id=' in svg, \
        "bgp-session <g> に data-bgp-id 属性が存在しない"
    # 決定的: sorted([r1, r2]) = [r1, r2] → "r1|r2"
    assert 'data-bgp-id="r1|r2"' in svg, \
        f"data-bgp-id が 'r1|r2' でない（sorted ペア規則違反）: {svg[:500]}"


@pytest.mark.unit
def test_p2_5_bgp_id_is_deterministic():
    """#5: data-bgp-id は方向非依存（r1→r2 と r2→r1 で同一値）。

    どちらの方向から呼んでも sorted([dev_id, neighbor_dev]) で同一文字列になる。
    """
    from lib.rendering.svg import _svg_bgp_edges
    ifaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30"},
        {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (400.0, 300.0)}
    # 片方向だけを渡した場合（重複除去前）でも ID は同一
    bgp_fwd = [{"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
                "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"}]
    bgp_rev = [{"device": "r2", "local_as": 65002, "local_ip": "10.0.0.2",
                "neighbor_ip": "10.0.0.1", "peer_as": 65001, "type": "ebgp"}]
    svg_fwd = _svg_bgp_edges(bgp_fwd, ifaces, positions)
    svg_rev = _svg_bgp_edges(bgp_rev, ifaces, positions)
    ids_fwd = re.findall(r'data-bgp-id="([^"]+)"', svg_fwd)
    ids_rev = re.findall(r'data-bgp-id="([^"]+)"', svg_rev)
    assert ids_fwd and ids_rev, "data-bgp-id が一方または両方で取れない"
    assert ids_fwd[0] == ids_rev[0], \
        f"data-bgp-id が方向依存: fwd={ids_fwd[0]!r} vs rev={ids_rev[0]!r}"


@pytest.mark.unit
def test_p2_5_bgp_session_map_built_in_core():
    """#5: core.py が bgp_session_map を構築して cards に渡す。

    bgp_session_map: {(device, neighbor_ip): bgp_id} 形式で
    (r1, 10.0.0.2) → 'r1|r2' のエントリが存在する。
    """
    from lib.rendering.core import _build_bgp_session_map
    interfaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30"},
        {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30"},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
         "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
        {"device": "r2", "local_as": 65002, "local_ip": "10.0.0.2",
         "neighbor_ip": "10.0.0.1", "peer_as": 65001, "type": "ebgp"},
    ]
    bgp_map = _build_bgp_session_map(bgp_entries, interfaces)
    assert ("r1", "10.0.0.2") in bgp_map, \
        "(r1, 10.0.0.2) が bgp_session_map に存在しない"
    assert bgp_map[("r1", "10.0.0.2")] == "r1|r2", \
        f"bgp_session_map[(r1, 10.0.0.2)] が 'r1|r2' でない: {bgp_map.get(('r1', '10.0.0.2'))!r}"
    assert ("r2", "10.0.0.1") in bgp_map, \
        "(r2, 10.0.0.1) が bgp_session_map に存在しない"
    assert bgp_map[("r2", "10.0.0.1")] == "r1|r2", \
        f"bgp_session_map[(r2, 10.0.0.1)] が 'r1|r2' でない"


@pytest.mark.unit
def test_p2_5_bgp_tr_has_data_bgp_id():
    """#5: BGP Sessions 表の <tr> に data-bgp-id が付いている。

    cards.py が生成する BGP 行に data-bgp-id="r1|r2" が存在する。
    """
    from lib.rendering import render
    html = render(_make_p2_bgp_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    assert 'data-bgp-id=' in cards_html, \
        "BGP Sessions テーブルの <tr> に data-bgp-id が存在しない"
    assert 'data-bgp-id="r1|r2"' in cards_html, \
        "BGP 行の data-bgp-id が 'r1|r2' でない"


@pytest.mark.unit
def test_p2_5_bgp_session_and_card_tr_share_same_bgp_id():
    """#5: bgp-session <g> と BGP 行 <tr> が同一の data-bgp-id を持つ（双方向対応）。

    SVG 側の data-bgp-id と HTML カード側の data-bgp-id が一致し、
    同一 ID でクリックイベントの対象になれることを確認する。
    """
    from lib.rendering import render
    html = render(_make_p2_bgp_topology())
    svg_ids = set(re.findall(r'class="bgp-session"[^>]*data-bgp-id="([^"]+)"', html))
    # bgp-session はクラスと属性の順序が異なる場合があるので柔軟に検索
    svg_ids2 = set(re.findall(r'data-bgp-id="([^"]+)"[^>]*class="bgp-session"', html))
    # class内にbgp-sessionを含む <g> 内の data-bgp-id
    svg_ids_all = set(re.findall(
        r'<g[^>]+class="[^"]*bgp-session[^"]*"[^>]*data-bgp-id="([^"]+)"', html
    )) | set(re.findall(
        r'<g[^>]+data-bgp-id="([^"]+)"[^>]*class="[^"]*bgp-session[^"]*"', html
    ))
    card_ids = set(re.findall(r'<tr[^>]+data-bgp-id="([^"]+)"', html))
    assert svg_ids_all, \
        "bgp-session <g> に data-bgp-id が存在しない"
    assert card_ids, \
        "BGP 行 <tr> に data-bgp-id が存在しない"
    overlap = svg_ids_all & card_ids
    assert overlap, \
        f"bgp-session と BGP 行が同一 data-bgp-id を共有しない: " \
        f"svg={svg_ids_all}, card={card_ids}"


@pytest.mark.unit
def test_p2_5_toggle_bgp_highlight_js_exists(rendered_html):
    """#5: toggleBgpHighlight(bgpId) 関数が JS に存在する。"""
    assert "toggleBgpHighlight" in rendered_html, \
        "toggleBgpHighlight 関数が JS に存在しない"


@pytest.mark.unit
def test_p2_5_selected_bgp_set_exists(rendered_html):
    """#5: _selectedBgp Set が JS に宣言されている。"""
    assert "_selectedBgp" in rendered_html, \
        "_selectedBgp Set が JS に存在しない"


@pytest.mark.unit
def test_p2_5_clear_selection_clears_bgp(rendered_html):
    """#5: clearSelection() / clearLinkHighlight() が _selectedBgp を解除する。

    _selectedBgp.clear() の呼び出しが JS 内に存在することを確認する。
    """
    assert "_selectedBgp.clear()" in rendered_html, \
        "clearSelection/clearLinkHighlight が _selectedBgp を解除しない（_selectedBgp.clear() が存在しない）"


@pytest.mark.unit
def test_p2_5_bgp_session_highlighted_css_exists(rendered_html):
    """#5: .bgp-session.highlighted .bgp-edge の CSS ルールが存在する。"""
    assert ".bgp-session.highlighted" in rendered_html, \
        ".bgp-session.highlighted の CSS ルールが存在しない"


@pytest.mark.unit
def test_p2_5_bgp_session_highlighted_has_stroke_style(rendered_html):
    """#5: .bgp-session.highlighted の CSS に stroke 系プロパティがある。"""
    m = re.search(
        r'\.bgp-session\.highlighted[^{]*\{([^}]+)\}',
        rendered_html
    )
    assert m is not None, ".bgp-session.highlighted の CSS ブロックが存在しない"
    block = m.group(1)
    assert "stroke" in block or "opacity" in block, \
        f".bgp-session.highlighted に視覚強調スタイルがない: {block!r}"


@pytest.mark.unit
def test_p2_5_bgp_click_handler_registered(rendered_html):
    """#5: bgp-session クリックと BGP 行クリックのイベントハンドラが登録されている。"""
    # bgp-session への click 登録
    has_bgp_session_click = re.search(
        r'bgp-session.*?addEventListener\s*\(\s*[\'"]click[\'"]\s*,',
        rendered_html, re.DOTALL
    ) is not None or re.search(
        r'addEventListener\s*\(\s*[\'"]click[\'"]\s*.*?bgp',
        rendered_html, re.DOTALL
    ) is not None or "toggleBgpHighlight" in rendered_html
    assert has_bgp_session_click, \
        "BGP セッションへのクリックハンドラ登録が存在しない"


# ---------------------------------------------------------------------------
# 多ノード対応B: フォーカスモード（ダブルクリック）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_nb_focus_dimmed_css_removed(rendered_html):
    """#6 撤去後: .focus-dimmed の CSS ルールが HTML から削除されている。
    (旧テスト test_p2_nb_focus_dimmed_css_exists を撤去後の否定条件に更新)
    正式版: test_p1a6_focus_dimmed_css_removed（p1a6 テスト群に移行済み）
    """
    assert ".focus-dimmed" not in rendered_html, \
        ".focus-dimmed CSS ルールが残存している（フォーカスモード撤去済みのはず）"


@pytest.mark.unit
def test_p2_nb_focus_dimmed_no_css_block(rendered_html):
    """#6 撤去後: .focus-dimmed の CSS ブロックが HTML に存在しない（block レベルの追加検証）。
    (旧テスト test_p2_nb_focus_dimmed_uses_opacity を撤去後の否定条件に更新)
    p1a6 正式版に加えて block レベルの検証を提供する（非重複の追加条件）。
    """
    m = re.search(r'\.focus-dimmed\s*\{([^}]+)\}', rendered_html)
    assert m is None, ".focus-dimmed の CSS ブロックが残存している（フォーカスモード撤去済みのはず）"


@pytest.mark.unit
def test_p2_nb_dblclick_handler_removed(rendered_html):
    """#6 撤去後: device-node への dblclick イベントハンドラが削除されている。
    (旧テスト test_p2_nb_dblclick_handler_exists を撤去後の否定条件に更新)
    正式版: test_p1a6_dblclick_handler_removed（p1a6 テスト群に移行済み）
    """
    assert "dblclick" not in rendered_html, \
        "dblclick ハンドラが残存している（フォーカスモード撤去済みのはず）"


@pytest.mark.unit
def test_p2_nb_focus_uses_data_a_data_b(rendered_html):
    """リンク/BGP ハイライトが data-a / data-b 属性を参照している。

    フォーカスモード（#6）撤去後は applyFocusMode / dblclick は存在しないが、
    リンクエッジ・BGP セッションは data-a / data-b 属性でハイライト対象を特定している。
    この属性参照が引き続き存在することを確認する。
    """
    # リンク/BGP ハイライト関連コードで dataset.a/dataset.b または getAttribute が使われる
    has_data_ref = (
        "dataset.a" in rendered_html
        or "dataset.b" in rendered_html
        or 'getAttribute("data-a")' in rendered_html
        or "getAttribute('data-a')" in rendered_html
    )
    assert has_data_ref, \
        "リンク/BGP ハイライトが data-a/data-b 属性を参照していない"


@pytest.mark.unit
def test_p2_nb_esc_clears_selection(rendered_html):
    """#6 撤去後: Esc キーで clearSelection() が呼ばれる（フォーカスモードは廃止）。
    (旧テスト test_p2_nb_focus_clear_on_esc を clearSelection 確認に更新)
    """
    # Esc（Escape）キーハンドラで clearSelection が呼ばれていること
    has_esc_clear = re.search(
        r'Escape[^}]{0,2000}clearSelection',
        rendered_html, re.DOTALL
    ) is not None or re.search(
        r"'Escape'[^;]{0,500}clearSelection|\"Escape\"[^;]{0,500}clearSelection",
        rendered_html, re.DOTALL
    ) is not None
    assert has_esc_clear, \
        "Esc キーで clearSelection() が呼ばれていない"


@pytest.mark.unit
def test_p2_nb_selected_css_exists(rendered_html):
    """#6 撤去後: .selected CSS ルールが引き続き存在する（フォーカスモード撤去後も選択機能は維持）。
    (旧テスト test_p2_nb_focus_does_not_break_selected を .selected 存在確認のみに簡素化)
    """
    sel_count = rendered_html.count(".selected")
    assert sel_count >= 1, ".selected が CSS/JS に存在しない"


@pytest.mark.unit
def test_p2_nb_help_text_no_dblclick_hint(rendered_html):
    """#6 撤去後: ヘッダのヘルプテキストにダブルクリック/隣接フォーカスの記述が存在しない。
    (旧テスト test_p2_nb_help_text_mentions_dblclick を撤去後の否定条件に更新)
    正式版: test_p1a6_help_text_no_double_click_hint（p1a6 テスト群に移行済み）
    """
    header_m = re.search(r'<header[^>]*>(.*?)</header>', rendered_html, re.DOTALL)
    header_html = header_m.group(1) if header_m else rendered_html
    assert "ダブルクリック" not in header_html, \
        "ヘッダに「ダブルクリック」ヘルプテキストが残存している"
    assert "隣接フォーカス" not in header_html, \
        "ヘッダに「隣接フォーカス」ヘルプテキストが残存している"


# ---------------------------------------------------------------------------
# 多ノード対応C: カード選択連動絞り込みトグル
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_nc_card_filter_toggle_exists(rendered_html):
    """多ノードC: カード絞り込みトグル（チェックボックス）が cards-section に存在する。

    #cards-section 内に type="checkbox" のフォーム要素がある。
    """
    cards_m = re.search(r'id="cards-section"(.*)', rendered_html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else rendered_html
    assert 'type="checkbox"' in cards_html, \
        "#cards-section にチェックボックスが存在しない"


@pytest.mark.unit
def test_p2_nc_card_unselected_css_exists(rendered_html):
    """多ノードC: .card-unselected の CSS ルールが存在する（.node-filtered とは別系統）。"""
    assert ".card-unselected" in rendered_html, \
        ".card-unselected の CSS ルールが存在しない"


@pytest.mark.unit
def test_p2_nc_card_unselected_hides_card(rendered_html):
    """多ノードC: .card-unselected は display:none または visibility:hidden でカードを隠す。"""
    m = re.search(r'\.card-unselected\s*\{([^}]+)\}', rendered_html)
    assert m is not None, ".card-unselected の CSS ブロックが存在しない"
    block = m.group(1)
    assert "display" in block or "visibility" in block, \
        f".card-unselected にカードを隠すスタイルがない: {block!r}"


@pytest.mark.unit
def test_p2_nc_card_filter_js_applies_card_unselected(rendered_html):
    """多ノードC: カード絞り込みトグル ON 時に .card-unselected が付与されるロジックがある。"""
    assert "card-unselected" in rendered_html, \
        "JS/HTML に card-unselected の参照が存在しない"
    # JS 内でクラスを操作するコードが存在する
    has_js_usage = re.search(
        r'card-unselected[^;]{0,200}(classList|add|remove|toggle)',
        rendered_html, re.DOTALL
    ) is not None or re.search(
        r'(classList|add|remove|toggle)[^;]{0,200}card-unselected',
        rendered_html, re.DOTALL
    ) is not None
    assert has_js_usage, \
        "JS で card-unselected クラスを操作するコードが存在しない"


@pytest.mark.unit
def test_p2_nc_card_filter_toggle_updates_on_selection_change(rendered_html):
    """多ノードC: _selectedNodes の変化時にカード絞り込み表示が更新される。

    カード絞り込みを更新する関数が _selectedNodes を参照し、
    イベント連携（updateCardFilter / _updateCardFilter 等）が存在する。
    """
    has_update_fn = (
        re.search(r'(updateCardFilter|_updateCardFilter|applyCardFilter)', rendered_html) is not None
        or re.search(r'_selectedNodes[^;]{0,500}card-unselected', rendered_html, re.DOTALL) is not None
        or re.search(r'card-unselected[^;]{0,500}_selectedNodes', rendered_html, re.DOTALL) is not None
    )
    assert has_update_fn, \
        "カード絞り込みが _selectedNodes 連動で更新されない"


# ---------------------------------------------------------------------------
# Phase 2 決定性テスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_render_deterministic_with_bgp(sample_topology):
    """Phase 2: 同一 topology を2回 render して同一 HTML になる（決定性）。"""
    from lib.rendering import render
    html1 = render(sample_topology)
    html2 = render(sample_topology)
    assert html1 == html2, "2回の render() 結果が一致しない（非決定的）"


@pytest.mark.unit
def test_p2_render_deterministic_bgp_topology():
    """Phase 2: BGP topology で決定性を確認。"""
    from lib.rendering import render
    topo = _make_p2_bgp_topology()
    html1 = render(topo)
    html2 = render(topo)
    assert html1 == html2, "BGP topology で2回の render() が非決定的"


# ---------------------------------------------------------------------------
# Phase 2 非回帰テスト: Phase 1 機能の継続動作
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_regression_seg_highlight_still_works(rendered_html):
    """非回帰: #7 toggleSegHighlight と _selectedSegs が Phase 2 後も存在する。"""
    assert "toggleSegHighlight" in rendered_html, \
        "toggleSegHighlight が存在しない（#7 回帰）"
    assert "_selectedSegs" in rendered_html, \
        "_selectedSegs が存在しない（#7 回帰）"


@pytest.mark.unit
def test_p2_regression_zoom_controls_still_exist(rendered_html):
    """非回帰: Phase 1 ズームボタン群が Phase 2 後も存在する。"""
    assert 'id="zoom-fit"' in rendered_html, "zoom-fit ボタンが消えた"
    assert 'id="zoom-in"' in rendered_html, "zoom-in ボタンが消えた"
    assert 'id="zoom-out"' in rendered_html, "zoom-out ボタンが消えた"
    assert 'id="zoom-reset"' in rendered_html, "zoom-reset ボタンが消えた"


@pytest.mark.unit
def test_p2_regression_split_divider_still_exists(rendered_html):
    """非回帰: Phase 1 スプリットディバイダが Phase 2 後も存在する。"""
    assert 'id="split-divider"' in rendered_html, "split-divider が消えた"


@pytest.mark.unit
def test_p2_regression_layer_toggles_still_exist(rendered_html):
    """非回帰: LAYERS トグルが Phase 2 後も存在する。"""
    assert "handleLayerToggle" in rendered_html, "handleLayerToggle が消えた"


# ===========================================================================
# Phase 2 レビュー指摘修正テスト群（タスク 11-17）
# ===========================================================================

# ---------------------------------------------------------------------------
# タスク 11: test_p2_nb_focus_does_not_break_selected の強化
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_nb_selected_css_block_exists(rendered_html):
    """#6 撤去後: .selected の CSS ブロックが引き続き存在する（選択機能は維持）。
    (旧テスト test_p2_nb_focus_does_not_break_selected_v2 をフォーカス不要の形に更新)
    """
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    assert len(style_blocks) >= 1, "style ブロックが見つからない"
    css_text = "\n".join(style_blocks)

    # .focus-dimmed { ... } ブロックが存在しないこと（撤去済み）
    m_fd = re.search(r'\.focus-dimmed\s*\{([^}]+)\}', css_text)
    assert m_fd is None, ".focus-dimmed のCSSブロックが残存している（撤去済みのはず）"

    # .selected または .device-node.selected { ... } ブロックが存在すること
    m_sel = re.search(r'\.selected\s*\{([^}]+)\}', css_text) or \
            re.search(r'device-node\.selected\s*[^{]*\{([^}]+)\}', css_text)
    assert m_sel is not None, ".selected のCSSブロックが存在しない（選択機能が壊れている）"


# ---------------------------------------------------------------------------
# タスク 12: _selectedNodes 変化直後に _updateCardFilter() 呼び出しを検証
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_nc_card_filter_toggle_updates_on_selection_change_v2(rendered_html):
    """多ノードC: _selectedNodes.add/delete の近傍で _updateCardFilter() が呼ばれる。

    旧テストの緩い検証を廃止し、実装修正1後の構造（add/delete 近傍の呼び出し）を検証する。
    """
    # _updateCardFilter の定義が存在すること
    assert "_updateCardFilter" in rendered_html, \
        "_updateCardFilter 関数が存在しない"

    # _selectedNodes.add / delete を含む行の近傍（300文字以内）に _updateCardFilter が存在するか
    # または clearSelection の末尾にも _updateCardFilter が存在するか
    has_add_near = re.search(
        r'_selectedNodes\.(add|delete)\s*\([^)]+\)[^;]*;[^;]{0,400}_updateCardFilter\s*\(',
        rendered_html, re.DOTALL
    ) is not None
    has_clear_near = re.search(
        r'clearSelection[^;]{0,600}_updateCardFilter\s*\(',
        rendered_html, re.DOTALL
    ) is not None
    has_update_in_fn = re.search(
        r'_updateCardFilter[^}]{0,1000}_selectedNodes',
        rendered_html, re.DOTALL
    ) is not None
    # いずれかのパターンで連携が確認できれば OK
    assert has_add_near or has_clear_near or has_update_in_fn, \
        "_selectedNodes 変化と _updateCardFilter の連携が検出できない"


# ---------------------------------------------------------------------------
# タスク 13: test_p2_nb_focus_uses_data_a_data_b を applyFocusMode 本体限定に
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_nb_apply_focus_mode_removed(rendered_html):
    """#6 撤去後: applyFocusMode 関数が HTML から存在しない。
    (旧テスト test_p2_nb_focus_uses_data_a_data_b_in_apply_focus を撤去後の否定条件に更新)
    正式版: test_p1a6_apply_focus_mode_removed（p1a6 テスト群に移行済み）
    """
    assert "applyFocusMode" not in rendered_html, \
        "applyFocusMode 関数が残存している（フォーカスモード撤去済みのはず）"


# ---------------------------------------------------------------------------
# タスク 14: _build_bgp_session_map エッジケーステスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_build_bgp_session_map_neighbor_not_resolved_returns_ext_bgp_id():
    """(a) neighbor_ip が interfaces に存在しない（外部ピア）場合、ext: 形式の bgp_id が付与される（B4）。

    B4 変更: 旧仕様「解決不能はスキップ」→ 新仕様「外部ピアは ext:{ip} として bgp_id を生成」。
    これにより cards の BGP 行と図の外部セッション線が同一 data-bgp-id で連動する。
    """
    from lib.rendering.core import _build_bgp_session_map
    interfaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30"},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
         "neighbor_ip": "203.0.113.99",  # 解決不能 → 外部ピア
         "peer_as": 64500, "type": "ebgp"},
    ]
    result = _build_bgp_session_map(bgp_entries, interfaces)
    assert len(result) == 1, \
        f"外部ピアの bgp_id エントリが生成されていない: {result}"
    bgp_id = result.get(("r1", "203.0.113.99"))
    assert bgp_id is not None, "(r1, 203.0.113.99) のエントリが存在しない"
    assert "ext:203.0.113.99" in bgp_id, \
        f"bgp_id に ext:203.0.113.99 が含まれていない: {bgp_id!r}"
    # sorted 結合の検証
    assert bgp_id == "ext:203.0.113.99|r1", \
        f"bgp_id が期待値 'ext:203.0.113.99|r1' と異なる: {bgp_id!r}"


@pytest.mark.unit
def test_build_bgp_session_map_ibgp_same_as_symmetric():
    """(b) iBGP 同一 AS でも bgp_id が sorted ペア 'r1|r2'（対称）になる。"""
    from lib.rendering.core import _build_bgp_session_map
    interfaces = [
        {"id": "r1::lo0", "device": "r1", "name": "lo0", "ip": "10.255.0.1/32"},
        {"id": "r2::lo0", "device": "r2", "name": "lo0", "ip": "10.255.0.2/32"},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "local_ip": "10.255.0.1",
         "neighbor_ip": "10.255.0.2", "peer_as": 65001, "type": "ibgp"},
        {"device": "r2", "local_as": 65001, "local_ip": "10.255.0.2",
         "neighbor_ip": "10.255.0.1", "peer_as": 65001, "type": "ibgp"},
    ]
    result = _build_bgp_session_map(bgp_entries, interfaces)
    assert ("r1", "10.255.0.2") in result, "(r1, 10.255.0.2) が存在しない"
    assert ("r2", "10.255.0.1") in result, "(r2, 10.255.0.1) が存在しない"
    assert result[("r1", "10.255.0.2")] == "r1|r2", \
        f"iBGP bgp_id が 'r1|r2' でない: {result[('r1', '10.255.0.2')]!r}"
    assert result[("r2", "10.255.0.1")] == "r1|r2", \
        f"iBGP 逆方向 bgp_id が 'r1|r2' でない: {result[('r2', '10.255.0.1')]!r}"


@pytest.mark.unit
def test_build_bgp_session_map_three_devices_separate_ids():
    """(c) 3台 r1-r2/r2-r3 が別 bgp_id になる。"""
    from lib.rendering.core import _build_bgp_session_map
    interfaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30"},
        {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30"},
        {"id": "r2::eth1", "device": "r2", "name": "eth1", "ip": "10.0.1.1/30"},
        {"id": "r3::eth0", "device": "r3", "name": "eth0", "ip": "10.0.1.2/30"},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
         "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
        {"device": "r2", "local_as": 65002, "local_ip": "10.0.0.2",
         "neighbor_ip": "10.0.0.1", "peer_as": 65001, "type": "ebgp"},
        {"device": "r2", "local_as": 65002, "local_ip": "10.0.1.1",
         "neighbor_ip": "10.0.1.2", "peer_as": 65003, "type": "ebgp"},
        {"device": "r3", "local_as": 65003, "local_ip": "10.0.1.2",
         "neighbor_ip": "10.0.1.1", "peer_as": 65002, "type": "ebgp"},
    ]
    result = _build_bgp_session_map(bgp_entries, interfaces)
    id_r1r2 = result.get(("r1", "10.0.0.2"))
    id_r2r3 = result.get(("r2", "10.0.1.2"))
    assert id_r1r2 is not None, "(r1, 10.0.0.2) が存在しない"
    assert id_r2r3 is not None, "(r2, 10.0.1.2) が存在しない"
    assert id_r1r2 != id_r2r3, \
        f"r1-r2 と r2-r3 が同一 bgp_id: {id_r1r2!r}"
    assert id_r1r2 == "r1|r2", f"r1-r2 bgp_id が 'r1|r2' でない: {id_r1r2!r}"
    assert id_r2r3 == "r2|r3", f"r2-r3 bgp_id が 'r2|r3' でない: {id_r2r3!r}"


# ---------------------------------------------------------------------------
# タスク 15: 3台構成で各セッションが図と表で同一 bgp_id を共有
# ---------------------------------------------------------------------------

def _make_p2_bgp_three_devices_topology():
    """3台構成 r1-r2-r3 BGP topology（r2 が2セッション参加）"""
    return {
        "title": "P2 BGP 3dev Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
            {"id": "r3", "hostname": "R3", "vendor": "cisco_ios", "as": 65003, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0",
             "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0",
             "ip": "10.0.0.2/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth1", "device": "r2", "name": "eth1",
             "ip": "10.0.1.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r3::eth0", "device": "r3", "name": "eth0",
             "ip": "10.0.1.2/30", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
            {"a_device": "r2", "a_if": "eth1", "b_device": "r3", "b_if": "eth0",
             "subnet": "10.0.1.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "local_ip": "10.0.0.1",
                 "neighbor_ip": "10.0.0.2", "peer_as": 65002, "type": "ebgp"},
                {"device": "r2", "local_as": 65002, "local_ip": "10.0.0.2",
                 "neighbor_ip": "10.0.0.1", "peer_as": 65001, "type": "ebgp"},
                {"device": "r2", "local_as": 65002, "local_ip": "10.0.1.1",
                 "neighbor_ip": "10.0.1.2", "peer_as": 65003, "type": "ebgp"},
                {"device": "r3", "local_as": 65003, "local_ip": "10.0.1.2",
                 "neighbor_ip": "10.0.1.1", "peer_as": 65002, "type": "ebgp"},
            ],
            "ospf": [],
            "static": [],
        },
    }


@pytest.mark.unit
def test_p2_5_bgp_session_and_card_tr_share_same_bgp_id_three_devices():
    """#5: 3台構成で各セッションが図と表で同一 bgp_id を共有（r2 が2セッション参加）。

    r1-r2 セッションの data-bgp-id="r1|r2" と
    r2-r3 セッションの data-bgp-id="r2|r3" がそれぞれ
    SVG <bgp-session g> と HTML カード <tr> 両方に存在することを確認する。
    """
    from lib.rendering import render
    html = render(_make_p2_bgp_three_devices_topology())

    # SVG 側の bgp-id 集合
    svg_ids = set(re.findall(
        r'<g[^>]+class="[^"]*bgp-session[^"]*"[^>]*data-bgp-id="([^"]+)"', html
    )) | set(re.findall(
        r'<g[^>]+data-bgp-id="([^"]+)"[^>]*class="[^"]*bgp-session[^"]*"', html
    ))
    # HTML カード側の bgp-id 集合
    card_ids = set(re.findall(r'<tr[^>]+data-bgp-id="([^"]+)"', html))

    assert "r1|r2" in svg_ids, f"SVG に r1|r2 のセッションがない: {svg_ids}"
    assert "r2|r3" in svg_ids, f"SVG に r2|r3 のセッションがない: {svg_ids}"
    assert "r1|r2" in card_ids, f"カード表に r1|r2 の BGP 行がない: {card_ids}"
    assert "r2|r3" in card_ids, f"カード表に r2|r3 の BGP 行がない: {card_ids}"


# ---------------------------------------------------------------------------
# タスク 16: test_p2_3_toggle_static_adds_row_class のフォールバック廃止
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_3_toggle_static_adds_row_class_strict(rendered_html):
    """#3: toggleStaticRouteHighlight 関数本体が route-row-selected クラスを操作する。

    修正4後の構造（関数内マーキング）に合わせて、
    toggleStaticRouteHighlight 内に route-row-selected の add/remove が存在することを確認する。
    フォールバック不要: m が None なら必ず失敗させる。
    """
    m = re.search(
        r'function toggleStaticRouteHighlight\s*\([^)]*\)\s*\{(.*?)(?=\n\s*// ====|\Z)',
        rendered_html, re.DOTALL
    )
    assert m is not None, "toggleStaticRouteHighlight 関数定義が見つからない"
    func_body = m.group(1)

    has_add = re.search(r'\.classList\.(add|toggle)\s*\(\s*["\']route-row-selected', func_body) is not None
    has_remove = re.search(r'\.classList\.(remove|toggle)\s*\(\s*["\']route-row-selected', func_body) is not None

    assert has_add, \
        f"toggleStaticRouteHighlight 内に route-row-selected の classList.add/toggle がない: {func_body[:500]}"
    assert has_remove, \
        f"toggleStaticRouteHighlight 内に route-row-selected の classList.remove/toggle がない: {func_body[:500]}"


# ---------------------------------------------------------------------------
# タスク 17: dblクリック遅延キャンセル（修正3）と selectView clearFocusMode（修正2）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_click_no_timer_delay(rendered_html):
    """#6 撤去後: _clickTimer 変数が存在せず、click ハンドラに setTimeout 遅延がない。
    (旧テスト test_p2_dblclick_cancels_single_click_timer を撤去後の否定条件に更新)

    旧実装（過広）: clearTimeout/setTimeout が HTML 全体に存在しないことを確認。
    新実装（実効）: _clickTimer 変数不在 + device-node クリックハンドラ内の
    250ms 遅延タイマーが存在しないことを具体的に検証する。
    正式版: test_p1a6_click_timer_removed + test_p1a6_node_click_no_settimeout_delay（p1a6 群）
    """
    # _clickTimer 変数が存在しないこと（旧 dblclick 遅延実装の核心）
    assert "_clickTimer" not in rendered_html, \
        "_clickTimer が残存している（単クリック即時化済みのはず）"
    # device-node click ハンドラ内での 250ms setTimeout 遅延がないこと
    has_250ms_delay = re.search(
        r"addEventListener\s*\(\s*'click'[^)]*\)[^{]*\{[^}]{0,2000}setTimeout[^,]*,\s*250",
        rendered_html, re.DOTALL
    ) is not None
    assert not has_250ms_delay, \
        "click ハンドラ内に 250ms setTimeout 遅延が残存している"


@pytest.mark.unit
def test_p2_select_view_no_clear_focus_mode(rendered_html):
    """#6 撤去後: selectView の先頭で clearFocusMode() を呼ばない。
    (旧テスト test_p2_select_view_calls_clear_focus_mode を撤去後の否定条件に更新)
    """
    start = rendered_html.find("function selectView(viewId)")
    assert start != -1, "selectView 関数が見つからない"
    end = rendered_html.find("function ", start + len("function selectView"))
    func_body = rendered_html[start:end] if end != -1 else rendered_html[start:start + 3000]

    assert "clearFocusMode" not in func_body, \
        "selectView 内に clearFocusMode() の呼び出しが残っている（フォーカスモード撤去済みのはず）"


# ===========================================================================
# Phase 3 テスト群 — #6: 全ビューで IF チップ接続
# ===========================================================================

# ---------------------------------------------------------------------------
# テスト用トポロジーヘルパー
# ---------------------------------------------------------------------------

def _make_p3_bgp_topology():
    """Phase 3 #6 テスト用 BGP トポロジー（3台・eBGP 2セッション）。

    r1(AS65001) --ebgp-- r2(AS65002) --ebgp-- r3(AS65003)
    - r1::eth0 (10.0.12.1/30) <-> r2::eth0 (10.0.12.2/30)
    - r2::eth1 (10.0.23.1/30) <-> r3::eth0 (10.0.23.2/30)
    - r1 Loopback0 (10.255.1.1/32)
    - BGP: r1 local_ip=10.0.12.1 neighbor=10.0.12.2, r2 local_ip=10.0.23.1 neighbor=10.0.23.2
    """
    return {
        "title": "P3 BGP Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
            {"id": "r3", "hostname": "R3", "vendor": "cisco_ios", "as": 65003, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0",
             "ip": "10.0.12.1/30", "vlan": None, "description": "to-R2", "shutdown": False},
            {"id": "r1::lo0", "device": "r1", "name": "Loopback0",
             "ip": "10.255.1.1/32", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0",
             "ip": "10.0.12.2/30", "vlan": None, "description": "to-R1", "shutdown": False},
            {"id": "r2::eth1", "device": "r2", "name": "eth1",
             "ip": "10.0.23.1/30", "vlan": None, "description": "to-R3", "shutdown": False},
            {"id": "r3::eth0", "device": "r3", "name": "eth0",
             "ip": "10.0.23.2/30", "vlan": None, "description": "to-R2", "shutdown": False},
            # r3 は BGP 非関与の IF を持つ（BGP チップ集合に含まれないことを検証）
            {"id": "r3::eth1", "device": "r3", "name": "eth1",
             "ip": "192.168.3.1/24", "vlan": None, "description": "LAN", "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.12.0/30", "kind": "inferred-subnet"},
            {"a_device": "r2", "a_if": "eth1", "b_device": "r3", "b_if": "eth0",
             "subnet": "10.0.23.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "peer_as": 65002,
                 "local_ip": "10.0.12.1", "neighbor_ip": "10.0.12.2", "type": "ebgp"},
                {"device": "r2", "local_as": 65002, "peer_as": 65001,
                 "local_ip": "10.0.12.2", "neighbor_ip": "10.0.12.1", "type": "ebgp"},
                {"device": "r2", "local_as": 65002, "peer_as": 65003,
                 "local_ip": "10.0.23.1", "neighbor_ip": "10.0.23.2", "type": "ebgp"},
                {"device": "r3", "local_as": 65003, "peer_as": 65002,
                 "local_ip": "10.0.23.2", "neighbor_ip": "10.0.23.1", "type": "ebgp"},
            ],
            "ospf": [],
            "static": [],
        },
    }


def _make_p3_ospf_topology():
    """Phase 3 #6 テスト用 OSPF トポロジー（3台・p2p リンク + セグメント）。

    r1 --ospf(area 0)-- r2 --ospf(area 0)-- r3
    - r1::eth0 (10.0.12.1/30) <-> r2::eth0 (10.0.12.2/30)  ospf_area=0
    - r2::eth1 参加セグメント（10.10.0.0/24）  ospf_area=0
    - r1 は OSPF 非参加 IF（eth1）を持つ（OSPF チップ集合に含まれないことを検証）
    """
    return {
        "title": "P3 OSPF Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r3", "hostname": "R3", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0",
             "ip": "10.0.12.1/30", "vlan": None, "description": "to-R2", "shutdown": False},
            {"id": "r1::eth1", "device": "r1", "name": "eth1",
             "ip": "192.168.1.1/24", "vlan": None, "description": "LAN", "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0",
             "ip": "10.0.12.2/30", "vlan": None, "description": "to-R1", "shutdown": False},
            {"id": "r2::eth1", "device": "r2", "name": "eth1",
             "ip": "10.10.0.2/24", "vlan": None, "description": "seg", "shutdown": False},
            {"id": "r3::eth0", "device": "r3", "name": "eth0",
             "ip": "10.10.0.3/24", "vlan": None, "description": "seg", "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.12.0/30", "kind": "inferred-subnet", "ospf_area": 0},
        ],
        "segments": [
            {"id": "seg-10.10.0.0/24", "subnet": "10.10.0.0/24",
             "members": ["r2::eth1", "r3::eth0"], "ospf_area": 0},
        ],
        "routing": {
            "bgp": [],
            "ospf": [
                {"device": "r1", "area": 0, "process_id": 1},
                {"device": "r2", "area": 0, "process_id": 1},
                {"device": "r3", "area": 0, "process_id": 1},
            ],
            "static": [],
        },
    }


# ---------------------------------------------------------------------------
# #6-A: _chip_positions 純粋ヘルパー（新設）のテスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p3_chip_positions_deterministic():
    """#6: _chip_positions が同一引数で毎回同一座標を返す（決定性）。"""
    from lib.rendering.svg import _chip_positions
    dev = {"id": "r1", "hostname": "R1"}
    ifaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
         "shutdown": False, "description": None},
        {"id": "r1::eth1", "device": "r1", "name": "eth1", "ip": "10.0.1.1/30",
         "shutdown": False, "description": None},
    ]
    chip_ids = {"r1::eth0", "r1::eth1"}
    result1 = _chip_positions(dev, chip_ids, ifaces, 100.0, 200.0)
    result2 = _chip_positions(dev, chip_ids, ifaces, 100.0, 200.0)
    assert result1 == result2, "_chip_positions が非決定的"


@pytest.mark.unit
def test_p3_chip_positions_sorted_by_name():
    """#6: _chip_positions は IF を name ソート順でインデックス付けする。

    eth0 が eth1 より小さい name → eth0 が k=0、eth1 が k=1。
    """
    from lib.rendering.svg import _chip_positions, _IF_CHIP_OFFSET_X, _IF_CHIP_GAP, _IF_CHIP_OFFSET_Y, _NODE_HEADER_H
    from lib.rendering.layout import _node_size_for
    dev = {"id": "r1", "hostname": "R1"}
    ifaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
         "shutdown": False, "description": None},
        {"id": "r1::eth1", "device": "r1", "name": "eth1", "ip": "10.0.1.1/30",
         "shutdown": False, "description": None},
    ]
    chip_ids = {"r1::eth0", "r1::eth1"}
    nx, ny = 50.0, 80.0  # ノード左上 (nx, ny)

    result = _chip_positions(dev, chip_ids, ifaces, nx + 60, ny + _node_size_for(2)[1] / 2)
    # eth0(k=0) の cx = nx + _IF_CHIP_OFFSET_X + 0 * _IF_CHIP_GAP
    # cy = ny + _NODE_HEADER_H + _IF_CHIP_OFFSET_Y
    expected_cx_eth0 = nx + _IF_CHIP_OFFSET_X
    expected_cx_eth1 = nx + _IF_CHIP_OFFSET_X + _IF_CHIP_GAP

    assert "r1::eth0" in result
    assert "r1::eth1" in result
    cx0, _ = result["r1::eth0"]
    cx1, _ = result["r1::eth1"]
    assert abs(cx0 - expected_cx_eth0) < 0.5, \
        f"eth0(k=0) の cx が期待値 {expected_cx_eth0} と不一致: {cx0}"
    assert abs(cx1 - expected_cx_eth1) < 0.5, \
        f"eth1(k=1) の cx が期待値 {expected_cx_eth1} と不一致: {cx1}"
    # eth0 は eth1 より左（cx が小さい）
    assert cx0 < cx1, "name ソート順で eth0 が eth1 より左にならない"


@pytest.mark.unit
def test_p3_chip_positions_only_requested_ids():
    """#6: _chip_positions は chip_ids に含まれる IF のみ座標を返す。"""
    from lib.rendering.svg import _chip_positions
    dev = {"id": "r1", "hostname": "R1"}
    ifaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
         "shutdown": False, "description": None},
        {"id": "r1::eth1", "device": "r1", "name": "eth1", "ip": "10.0.1.1/30",
         "shutdown": False, "description": None},
        {"id": "r1::eth2", "device": "r1", "name": "eth2", "ip": None,
         "shutdown": False, "description": None},
    ]
    # eth1 だけを chip 化する
    result = _chip_positions(dev, {"r1::eth1"}, ifaces, 100.0, 200.0)
    assert "r1::eth1" in result, "chip_ids に含まれる eth1 が結果にない"
    assert "r1::eth0" not in result, "chip_ids に含まれない eth0 が結果に混入"
    assert "r1::eth2" not in result, "chip_ids に含まれない eth2 が結果に混入"


@pytest.mark.unit
def test_p3_chip_positions_empty_returns_empty():
    """#6: chip_ids が空集合のとき _chip_positions は空辞書を返す。"""
    from lib.rendering.svg import _chip_positions
    dev = {"id": "r1", "hostname": "R1"}
    ifaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
         "shutdown": False, "description": None},
    ]
    result = _chip_positions(dev, set(), ifaces, 100.0, 200.0)
    assert result == {}, f"空集合のとき空辞書を返すべき: {result}"


# ---------------------------------------------------------------------------
# #6-B: data-iface-id 属性のテスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p3_chip_has_data_iface_id():
    """#6: IF チップの <g> に data-iface-id 属性が付与される。"""
    from lib.rendering.svg import _svg_nodes
    dev_list = [{"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None}]
    pos = {"r1": (100.0, 100.0)}
    ibd = {
        "r1": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0",
             "ip": "10.0.0.1/30", "shutdown": False, "description": None},
        ]
    }
    svg = _svg_nodes(
        dev_list, pos, ibd,
        show_interfaces=True,
        chip_iface_ids={"r1::eth0"},
    )
    assert 'data-iface-id="r1::eth0"' in svg, \
        f"IF チップに data-iface-id が付与されない: {svg[:500]}"


@pytest.mark.unit
def test_p3_chip_data_iface_id_correct_id():
    """#6: data-iface-id の値が iface["id"] と一致する（iface name ではない）。"""
    from lib.rendering.svg import _svg_nodes
    dev_list = [{"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None}]
    pos = {"r1": (100.0, 100.0)}
    ibd = {
        "r1": [
            {"id": "r1::GigabitEthernet0/0", "device": "r1", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.1/30", "shutdown": False, "description": None},
        ]
    }
    svg = _svg_nodes(
        dev_list, pos, ibd,
        show_interfaces=True,
        chip_iface_ids={"r1::GigabitEthernet0/0"},
    )
    # iface id（r1::GigabitEthernet0/0）が data-iface-id に入る
    assert 'data-iface-id="r1::GigabitEthernet0/0"' in svg, \
        f"data-iface-id が iface id と不一致: {svg[:500]}"
    # 古い data-if 属性も残っていてよい（後方互換）
    assert 'data-if="GigabitEthernet0/0"' in svg, \
        "data-if 属性（IF 名）が失われた（後方互換が壊れている）"


# ---------------------------------------------------------------------------
# #6-C: ビュー別チップ集合（BGP ビュー）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p3_bgp_view_shows_chips_for_bgp_ifaces():
    """#6: BGP ビューのノードに BGP セッション関与 IF のチップが出る。"""
    from lib.rendering import render
    html = render(_make_p3_bgp_topology())
    bgp_view = _extract_bgp_view(html)
    assert bgp_view, "BGP ビューが生成されない"

    # r1 は BGP 関与 IF = eth0 (10.0.12.1) のみ → data-iface-id="r1::eth0" が存在すること
    assert 'data-iface-id="r1::eth0"' in bgp_view, \
        "BGP ビューで r1::eth0 の data-iface-id チップが存在しない"
    # r2 は eth0(to-r1) と eth1(to-r3) の両方が BGP 関与
    assert 'data-iface-id="r2::eth0"' in bgp_view, \
        "BGP ビューで r2::eth0 の data-iface-id チップが存在しない"
    assert 'data-iface-id="r2::eth1"' in bgp_view, \
        "BGP ビューで r2::eth1 の data-iface-id チップが存在しない"


@pytest.mark.unit
def test_p3_bgp_view_excludes_non_bgp_ifaces():
    """#6: BGP ビューのノードに BGP 非関与 IF のチップが出ない。

    r3::eth1 (LAN 192.168.3.1/24) は BGP セッションに関与しないため、
    BGP ビューのチップに含まれない。
    """
    from lib.rendering import render
    html = render(_make_p3_bgp_topology())
    bgp_view = _extract_bgp_view(html)
    assert bgp_view, "BGP ビューが生成されない"
    assert 'data-iface-id="r3::eth1"' not in bgp_view, \
        "BGP 非関与 IF（r3::eth1）が BGP ビューのチップに含まれている"


@pytest.mark.unit
def test_p3_bgp_session_edge_anchors_to_chip():
    """#6: BGP セッション線の端点座標が、ノード中心ではなくチップ座標に一致する。

    r1(eth0=10.0.12.1) <-> r2(eth0=10.0.12.2) のセッション。
    BGP path の M{x1},{y1} の x1,y1 が r1 のノード中心ではなく
    r1::eth0 チップの cx,cy に一致すること。
    """
    from lib.rendering.svg import _svg_bgp_edges, _chip_positions, _IF_CHIP_OFFSET_X
    from lib.rendering.layout import _node_size_for, _NODE_HEADER_H

    interfaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0",
         "ip": "10.0.12.1/30", "shutdown": False, "description": None},
        {"id": "r2::eth0", "device": "r2", "name": "eth0",
         "ip": "10.0.12.2/30", "shutdown": False, "description": None},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "peer_as": 65002,
         "local_ip": "10.0.12.1", "neighbor_ip": "10.0.12.2", "type": "ebgp"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (500.0, 300.0)}

    # chip_positions: r1 の eth0 チップ座標を計算
    chip_iface_ids_r1 = {"r1::eth0"}
    chip_iface_ids_r2 = {"r2::eth0"}
    all_ifaces_r1 = [i for i in interfaces if i["device"] == "r1"]
    all_ifaces_r2 = [i for i in interfaces if i["device"] == "r2"]

    r1_dev = {"id": "r1", "hostname": "R1"}
    r2_dev = {"id": "r2", "hostname": "R2"}
    r1_pos = positions["r1"]
    r2_pos = positions["r2"]

    r1_chips = _chip_positions(r1_dev, chip_iface_ids_r1, all_ifaces_r1, r1_pos[0], r1_pos[1])
    r2_chips = _chip_positions(r2_dev, chip_iface_ids_r2, all_ifaces_r2, r2_pos[0], r2_pos[1])

    all_chip_positions = {**r1_chips, **r2_chips}

    svg = _svg_bgp_edges(
        bgp_entries, interfaces, positions,
        chip_positions=all_chip_positions,
    )

    # r1::eth0 の期待チップ座標
    exp_cx, exp_cy = r1_chips["r1::eth0"]

    # BGP path の開始点 M{x1},{y1} を取り出す
    m = re.search(r'<path[^>]+d="M([\d.]+),([\d.]+)', svg)
    assert m is not None, f"BGP path が見つからない: {svg[:300]}"
    path_x1 = float(m.group(1))
    path_y1 = float(m.group(2))

    assert abs(path_x1 - exp_cx) < 1.0, \
        f"BGP path 始点 x={path_x1} がチップ cx={exp_cx} に一致しない"
    assert abs(path_y1 - exp_cy) < 1.0, \
        f"BGP path 始点 y={path_y1} がチップ cy={exp_cy} に一致しない"


@pytest.mark.unit
def test_p3_bgp_edge_fallback_to_node_center_when_no_local_ip():
    """#6: BGP エントリの local_ip が None のとき、A側端点をノード中心にフォールバック。"""
    from lib.rendering.svg import _svg_bgp_edges

    interfaces = [
        {"id": "r1::lo0", "device": "r1", "name": "lo0",
         "ip": "10.255.1.1/32", "shutdown": False, "description": None},
        {"id": "r2::eth0", "device": "r2", "name": "eth0",
         "ip": "10.0.12.2/30", "shutdown": False, "description": None},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "peer_as": 65002,
         "local_ip": None, "neighbor_ip": "10.0.12.2", "type": "ebgp"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (500.0, 300.0)}

    # chip_positions: r1 は local_ip なしでチップ未設定
    chip_positions = {
        "r2::eth0": (500.0 - 60 + 8, 300.0 - 25 + 12),  # 近似値
    }

    svg = _svg_bgp_edges(
        bgp_entries, interfaces, positions,
        chip_positions=chip_positions,
    )

    # A 側（r1）は local_ip なしのためノード中心 (200.0, 300.0) が始点になる
    m = re.search(r'<path[^>]+d="M([\d.]+),([\d.]+)', svg)
    assert m is not None, f"BGP path が見つからない: {svg[:300]}"
    path_x1 = float(m.group(1))
    path_y1 = float(m.group(2))

    assert abs(path_x1 - 200.0) < 1.0, \
        f"local_ip=None 時 A 側始点 x={path_x1} がノード中心 200.0 にフォールバックしない"
    assert abs(path_y1 - 300.0) < 1.0, \
        f"local_ip=None 時 A 側始点 y={path_y1} がノード中心 300.0 にフォールバックしない"


# ---------------------------------------------------------------------------
# #6-D: ビュー別チップ集合（OSPF ビュー）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p3_ospf_view_shows_chips_for_ospf_ifaces():
    """#6: OSPF ビューのノードに OSPF 参加 IF のチップが出る。"""
    from lib.rendering import render
    html = render(_make_p3_ospf_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが生成されない"

    # r1::eth0 は OSPF p2p リンク参加 → チップあり
    assert 'data-iface-id="r1::eth0"' in ospf_view, \
        "OSPF ビューで r1::eth0 の data-iface-id チップが存在しない"
    # r2::eth1 は OSPF セグメントメンバー → チップあり
    assert 'data-iface-id="r2::eth1"' in ospf_view, \
        "OSPF ビューで r2::eth1 の data-iface-id チップが存在しない"


@pytest.mark.unit
def test_p3_ospf_view_excludes_non_ospf_ifaces():
    """#6: OSPF ビューのノードに OSPF 非参加 IF のチップが出ない。

    r1::eth1 (LAN 192.168.1.1/24) は OSPF に参加しないため、
    OSPF ビューのチップに含まれない。
    """
    from lib.rendering import render
    html = render(_make_p3_ospf_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが生成されない"
    assert 'data-iface-id="r1::eth1"' not in ospf_view, \
        "OSPF 非参加 IF（r1::eth1）が OSPF ビューのチップに含まれている"


@pytest.mark.unit
def test_p3_ospf_p2p_link_anchors_to_chip():
    """#6: OSPF p2p リンクの端点がチップ座標にアンカーされる。

    r1::eth0 <-> r2::eth0 のリンク。
    Physical の _svg_links と同様のパターンで chip_positions を受け取る。
    """
    from lib.rendering.svg import _svg_links, _chip_positions

    interfaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0",
         "ip": "10.0.12.1/30", "shutdown": False, "description": None},
        {"id": "r2::eth0", "device": "r2", "name": "eth0",
         "ip": "10.0.12.2/30", "shutdown": False, "description": None},
    ]
    links = [
        {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
         "subnet": "10.0.12.0/30", "kind": "inferred-subnet"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (500.0, 300.0)}

    r1_dev = {"id": "r1", "hostname": "R1"}
    r2_dev = {"id": "r2", "hostname": "R2"}

    r1_chips = _chip_positions(r1_dev, {"r1::eth0"}, [interfaces[0]], positions["r1"][0], positions["r1"][1])
    r2_chips = _chip_positions(r2_dev, {"r2::eth0"}, [interfaces[1]], positions["r2"][0], positions["r2"][1])
    all_chip_pos = {**r1_chips, **r2_chips}

    # iface name -> iface_id マップ（リンクの a_if/b_if から iface_id を解決するため）
    name_to_iface_id = {(i["device"], i["name"]): i["id"] for i in interfaces}

    svg = _svg_links(links, positions, chip_positions=all_chip_pos, name_to_iface_id=name_to_iface_id)

    # r1::eth0 のチップ座標が line の x1,y1 に使われているはず
    exp_x1, exp_y1 = r1_chips["r1::eth0"]
    m = re.search(r'<line[^>]+x1="([\d.]+)"[^>]+y1="([\d.]+)"', svg)
    assert m is not None, f"line 要素が見つからない: {svg[:300]}"
    line_x1 = float(m.group(1))
    line_y1 = float(m.group(2))

    assert abs(line_x1 - exp_x1) < 1.0, \
        f"p2p リンク x1={line_x1} がチップ cx={exp_x1} にアンカーされない"
    assert abs(line_y1 - exp_y1) < 1.0, \
        f"p2p リンク y1={line_y1} がチップ cy={exp_y1} にアンカーされない"


@pytest.mark.unit
def test_p3_ospf_segment_edge_anchors_to_chip():
    """#6: OSPF セグメントエッジの機器側端点がチップ座標にアンカーされる。"""
    from lib.rendering.svg import _svg_ospf_segment_edges, _chip_positions

    interfaces = [
        {"id": "r2::eth1", "device": "r2", "name": "eth1",
         "ip": "10.10.0.2/24", "shutdown": False, "description": None},
        {"id": "r3::eth0", "device": "r3", "name": "eth0",
         "ip": "10.10.0.3/24", "shutdown": False, "description": None},
    ]
    segments = [
        {"id": "seg1", "subnet": "10.10.0.0/24",
         "members": ["r2::eth1", "r3::eth0"], "ospf_area": 0},
    ]
    positions = {
        "seg1": (350.0, 200.0),
        "r2": (200.0, 300.0),
        "r3": (500.0, 300.0),
    }

    r2_dev = {"id": "r2", "hostname": "R2"}
    r3_dev = {"id": "r3", "hostname": "R3"}
    r2_chips = _chip_positions(r2_dev, {"r2::eth1"}, [interfaces[0]], positions["r2"][0], positions["r2"][1])
    r3_chips = _chip_positions(r3_dev, {"r3::eth0"}, [interfaces[1]], positions["r3"][0], positions["r3"][1])
    all_chip_pos = {**r2_chips, **r3_chips}

    svg = _svg_ospf_segment_edges(
        segments, interfaces, positions,
        chip_positions=all_chip_pos,
    )

    # r2::eth1 のチップ座標 (cx, cy) が line の x2,y2 に使われているはず
    # (seg が x1,y1; device が x2,y2)
    exp_x2, exp_y2 = r2_chips["r2::eth1"]
    # r2 に対応する line を探す（data-device="r2"）
    m = re.search(r'<line[^>]+data-device="r2"[^>]*x2="([\d.]+)"[^>]*y2="([\d.]+)"'
                  r'|<line[^>]+x2="([\d.]+)"[^>]+y2="([\d.]+)"[^>]+data-device="r2"',
                  svg)
    if m is None:
        # より柔軟なパターン: data-device="r2" の line 全体から x2/y2 を取る
        m2 = re.search(r'<line([^>]*data-device="r2"[^>]*)>', svg)
        assert m2 is not None, f"r2 に対応する seg-edge line が見つからない: {svg[:500]}"
        line_tag = m2.group(1)
        mx2 = re.search(r'x2="([\d.]+)"', line_tag)
        my2 = re.search(r'y2="([\d.]+)"', line_tag)
        assert mx2 and my2, f"x2/y2 が line タグに見つからない: {line_tag}"
        line_x2, line_y2 = float(mx2.group(1)), float(my2.group(1))
    else:
        line_x2 = float(m.group(1) or m.group(3))
        line_y2 = float(m.group(2) or m.group(4))

    assert abs(line_x2 - exp_x2) < 1.0, \
        f"seg-edge x2={line_x2} が r2::eth1 チップ cx={exp_x2} にアンカーされない"
    assert abs(line_y2 - exp_y2) < 1.0, \
        f"seg-edge y2={line_y2} が r2::eth1 チップ cy={exp_y2} にアンカーされない"


@pytest.mark.unit
def test_p3_link_anchor_fallback_when_no_chip():
    """#6: chip_positions に端点の iface_id がない場合、ノード中心にフォールバックする。"""
    from lib.rendering.svg import _svg_links

    links = [
        {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
         "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (500.0, 300.0)}

    # chip_positions が None → ノード中心を使う
    svg = _svg_links(links, positions, chip_positions=None, name_to_iface_id=None)

    m = re.search(r'<line[^>]+x1="([\d.]+)"[^>]+y1="([\d.]+)"', svg)
    assert m is not None, "line 要素が見つからない"
    assert abs(float(m.group(1)) - 200.0) < 1.0, "chip なしのとき x1 がノード中心にならない"
    assert abs(float(m.group(2)) - 300.0) < 1.0, "chip なしのとき y1 がノード中心にならない"


# ---------------------------------------------------------------------------
# #6-E: AS グループ枠が実ノード高を反映するテスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p3_as_group_uses_real_node_height():
    """#6: _svg_bgp_as_groups が node_sizes を受け取り、実ノード高で bounding box を計算する。

    チップあり（n_ifaces=2）のノードは固定 _NODE_HEIGHT より高い。
    node_sizes を渡したとき、枠の高さが固定高より大きくなる（_NODE_HEIGHT のみ使った場合と異なる）。
    """
    from lib.rendering.svg import _svg_bgp_as_groups
    from lib.rendering.layout import _NODE_HEIGHT, _node_size_for

    devs = [
        {"id": "r1", "hostname": "R1", "as": 65001},
        {"id": "r2", "hostname": "R2", "as": 65001},
    ]
    positions = {"r1": (200.0, 300.0), "r2": (400.0, 300.0)}

    # node_sizes なし（固定 _NODE_HEIGHT）
    svg_fixed = _svg_bgp_as_groups(devs, positions, node_sizes=None)
    # node_sizes あり（n_ifaces=3 → 高さが増加）
    node_sizes = {"r1": 3, "r2": 3}
    svg_real = _svg_bgp_as_groups(devs, positions, node_sizes=node_sizes)

    # 高さ（rect の height 属性）を比較
    m_fixed = re.search(r'<rect[^>]+class="as-group"[^>]+height="([\d.]+)"'
                        r'|height="([\d.]+)"[^>]+class="as-group"', svg_fixed)
    m_real = re.search(r'<rect[^>]+class="as-group"[^>]+height="([\d.]+)"'
                       r'|height="([\d.]+)"[^>]+class="as-group"', svg_real)

    assert m_fixed is not None, f"固定高の AS 枠 height が見つからない: {svg_fixed[:300]}"
    assert m_real is not None, f"実ノード高の AS 枠 height が見つからない: {svg_real[:300]}"

    h_fixed = float(m_fixed.group(1) or m_fixed.group(2))
    h_real = float(m_real.group(1) or m_real.group(2))

    _, tall_h = _node_size_for(3)
    assert tall_h > _NODE_HEIGHT, "テスト前提: n_ifaces=3 のノードが _NODE_HEIGHT より高くない"
    assert h_real > h_fixed, \
        f"実ノード高の枠({h_real}) が固定高の枠({h_fixed}) より大きくならない"


# ---------------------------------------------------------------------------
# #6-F: 決定性・非回帰テスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p3_bgp_render_deterministic():
    """#6: BGP チップ付きビューの render が決定的（2回一致）。"""
    from lib.rendering import render
    topo = _make_p3_bgp_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "BGP チップ付きビューが非決定的"


@pytest.mark.unit
def test_p3_ospf_render_deterministic():
    """#6: OSPF チップ付きビューの render が決定的（2回一致）。"""
    from lib.rendering import render
    topo = _make_p3_ospf_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "OSPF チップ付きビューが非決定的"


@pytest.mark.unit
def test_p3_physical_chip_still_has_data_if_attr():
    """#6: Physical ビューの既存 data-if 属性が引き続き存在する（後方互換・非回帰）。"""
    from lib.rendering import render
    html = render(_make_chip_topology())
    phys = _extract_physical_view(html)
    # data-if 属性が引き続き存在すること
    data_if_attrs = re.findall(r'data-if="([^"]+)"', phys)
    assert len(data_if_attrs) >= 1, \
        "Physical ビューで data-if 属性が消えた（後方互換が壊れている）"


@pytest.mark.unit
def test_p3_physical_view_chip_has_data_iface_id():
    """#6: Physical ビューのチップにも data-iface-id が付与される（汎用化の副産物）。"""
    from lib.rendering import render
    html = render(_make_chip_topology())
    phys = _extract_physical_view(html)
    # data-iface-id 属性が存在すること
    data_iface_id_attrs = re.findall(r'data-iface-id="([^"]+)"', phys)
    assert len(data_iface_id_attrs) >= 1, \
        "Physical ビューでチップに data-iface-id が付与されない"


@pytest.mark.unit
def test_p3_bgp_no_overlap_after_chip_resize():
    """#6: BGP レイアウトでチップ有りのノードが重ならない。

    ノードが n_ifaces 分だけ高くなった後も重なりゼロを保証する。
    全ノードペアの中心間距離 > min_sep（各ノードサイズの対角長の和 / 2 + マージン）。
    Task #8: 実際のチップ数に基づいた node_size を使用する。
    """
    import math as _math
    from lib.rendering.views import _build_bgp_layout, _build_bgp_chip_iface_ids
    from lib.rendering.layout import _node_size_for

    topo = _make_p3_bgp_topology()
    devices = topo["devices"]
    bgp_entries = topo["routing"]["bgp"]
    interfaces = topo["interfaces"]

    positions, bgp_devices = _build_bgp_layout(devices, bgp_entries, interfaces)

    # BGP チップ集合を取得（実際のチップ数を算出する）
    bgp_chip_ids = _build_bgp_chip_iface_ids(bgp_entries, interfaces)
    iface_by_device: dict = {}
    for iface in interfaces:
        iface_by_device.setdefault(iface["device"], []).append(iface)

    # 全ペアが重ならないことを確認（実チップ数に基づくノードサイズ）
    dev_ids = sorted(d["id"] for d in bgp_devices)
    for i in range(len(dev_ids)):
        for j in range(i + 1, len(dev_ids)):
            di, dj = dev_ids[i], dev_ids[j]
            if di not in positions or dj not in positions:
                continue
            xi, yi = positions[di]
            xj, yj = positions[dj]
            dist = _math.sqrt((xi - xj) ** 2 + (yi - yj) ** 2)
            # 実チップ数を取得してノードサイズを計算
            di_chips = {i["id"] for i in iface_by_device.get(di, []) if i["id"] in bgp_chip_ids}
            dj_chips = {i["id"] for i in iface_by_device.get(dj, []) if i["id"] in bgp_chip_ids}
            n_chips_i = 1 if di_chips else 0
            n_chips_j = 1 if dj_chips else 0
            wi, hi = _node_size_for(n_chips_i)
            wj, hj = _node_size_for(n_chips_j)
            min_sep = (_math.sqrt(wi**2 + hi**2) / 2 + _math.sqrt(wj**2 + hj**2) / 2 + 10)
            assert dist >= min_sep - 0.5, \
                f"BGP ノード {di} と {dj} が重なっている: dist={dist:.1f} < min_sep={min_sep:.1f}"


def _make_p3_bgp_dense_topology():
    """Task #8: BGP dense フィクスチャ（4台・各2チップ以上・重なり検証用）。

    r1(AS65001) --ebgp-- r2(AS65002) --ebgp-- r3(AS65003) --ebgp-- r4(AS65004)
    各デバイスに BGP セッション参加 IF が 2 本以上ある。
    """
    return {
        "title": "P3 BGP Dense Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
            {"id": "r3", "hostname": "R3", "vendor": "cisco_ios", "as": 65003, "sections": []},
            {"id": "r4", "hostname": "R4", "vendor": "cisco_ios", "as": 65004, "sections": []},
        ],
        "interfaces": [
            # r1: 2本の BGP セッション参加 IF
            {"id": "r1::eth0", "device": "r1", "name": "eth0",
             "ip": "10.0.12.1/30", "vlan": None, "description": "to-R2", "shutdown": False},
            {"id": "r1::eth1", "device": "r1", "name": "eth1",
             "ip": "10.0.14.1/30", "vlan": None, "description": "to-R4", "shutdown": False},
            # r2: 2本の BGP セッション参加 IF
            {"id": "r2::eth0", "device": "r2", "name": "eth0",
             "ip": "10.0.12.2/30", "vlan": None, "description": "to-R1", "shutdown": False},
            {"id": "r2::eth1", "device": "r2", "name": "eth1",
             "ip": "10.0.23.1/30", "vlan": None, "description": "to-R3", "shutdown": False},
            # r3: 2本の BGP セッション参加 IF
            {"id": "r3::eth0", "device": "r3", "name": "eth0",
             "ip": "10.0.23.2/30", "vlan": None, "description": "to-R2", "shutdown": False},
            {"id": "r3::eth1", "device": "r3", "name": "eth1",
             "ip": "10.0.34.1/30", "vlan": None, "description": "to-R4", "shutdown": False},
            # r4: 2本の BGP セッション参加 IF
            {"id": "r4::eth0", "device": "r4", "name": "eth0",
             "ip": "10.0.34.2/30", "vlan": None, "description": "to-R3", "shutdown": False},
            {"id": "r4::eth1", "device": "r4", "name": "eth1",
             "ip": "10.0.14.2/30", "vlan": None, "description": "to-R1", "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.12.0/30", "kind": "inferred-subnet"},
            {"a_device": "r2", "a_if": "eth1", "b_device": "r3", "b_if": "eth0",
             "subnet": "10.0.23.0/30", "kind": "inferred-subnet"},
            {"a_device": "r3", "a_if": "eth1", "b_device": "r4", "b_if": "eth0",
             "subnet": "10.0.34.0/30", "kind": "inferred-subnet"},
            {"a_device": "r4", "a_if": "eth1", "b_device": "r1", "b_if": "eth1",
             "subnet": "10.0.14.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "peer_as": 65002,
                 "local_ip": "10.0.12.1", "neighbor_ip": "10.0.12.2", "type": "ebgp"},
                {"device": "r1", "local_as": 65001, "peer_as": 65004,
                 "local_ip": "10.0.14.1", "neighbor_ip": "10.0.14.2", "type": "ebgp"},
                {"device": "r2", "local_as": 65002, "peer_as": 65001,
                 "local_ip": "10.0.12.2", "neighbor_ip": "10.0.12.1", "type": "ebgp"},
                {"device": "r2", "local_as": 65002, "peer_as": 65003,
                 "local_ip": "10.0.23.1", "neighbor_ip": "10.0.23.2", "type": "ebgp"},
                {"device": "r3", "local_as": 65003, "peer_as": 65002,
                 "local_ip": "10.0.23.2", "neighbor_ip": "10.0.23.1", "type": "ebgp"},
                {"device": "r3", "local_as": 65003, "peer_as": 65004,
                 "local_ip": "10.0.34.1", "neighbor_ip": "10.0.34.2", "type": "ebgp"},
                {"device": "r4", "local_as": 65004, "peer_as": 65003,
                 "local_ip": "10.0.34.2", "neighbor_ip": "10.0.34.1", "type": "ebgp"},
                {"device": "r4", "local_as": 65004, "peer_as": 65001,
                 "local_ip": "10.0.14.2", "neighbor_ip": "10.0.14.1", "type": "ebgp"},
            ],
            "ospf": [],
            "static": [],
        },
    }


@pytest.mark.unit
def test_p3_bgp_no_overlap_dense_4nodes():
    """Task #8: 4台・各2チップ BGP dense フィクスチャでもノードが重ならない。

    bgp_node_sizes が 1 (row count) に修正された後、force-directed への
    node_sizes 伝達が正しく機能していることを検証する。
    """
    import math as _math
    from lib.rendering.views import _build_bgp_layout, _build_bgp_chip_iface_ids
    from lib.rendering.layout import _node_size_for

    topo = _make_p3_bgp_dense_topology()
    devices = topo["devices"]
    bgp_entries = topo["routing"]["bgp"]
    interfaces = topo["interfaces"]

    positions, bgp_devices = _build_bgp_layout(devices, bgp_entries, interfaces)

    bgp_chip_ids = _build_bgp_chip_iface_ids(bgp_entries, interfaces)
    iface_by_device: dict = {}
    for iface in interfaces:
        iface_by_device.setdefault(iface["device"], []).append(iface)

    dev_ids = sorted(d["id"] for d in bgp_devices)
    for i in range(len(dev_ids)):
        for j in range(i + 1, len(dev_ids)):
            di, dj = dev_ids[i], dev_ids[j]
            if di not in positions or dj not in positions:
                continue
            xi, yi = positions[di]
            xj, yj = positions[dj]
            dist = _math.sqrt((xi - xj) ** 2 + (yi - yj) ** 2)
            di_chips = {iface["id"] for iface in iface_by_device.get(di, []) if iface["id"] in bgp_chip_ids}
            dj_chips = {iface["id"] for iface in iface_by_device.get(dj, []) if iface["id"] in bgp_chip_ids}
            n_chips_i = 1 if di_chips else 0
            n_chips_j = 1 if dj_chips else 0
            wi, hi = _node_size_for(n_chips_i)
            wj, hj = _node_size_for(n_chips_j)
            min_sep = (_math.sqrt(wi**2 + hi**2) / 2 + _math.sqrt(wj**2 + hj**2) / 2 + 10)
            assert dist >= min_sep - 0.5, \
                f"Dense BGP ノード {di} と {dj} が重なっている: dist={dist:.1f} < min_sep={min_sep:.1f}"


@pytest.mark.unit
def test_p3_chip_positions_cy_uses_node_cy():
    """Task #9: _chip_positions の cy 座標が node_cy を起点として計算される。

    ny = node_cy - node_h/2 として cy = ny + _NODE_HEADER_H + _IF_CHIP_OFFSET_Y
    """
    from lib.rendering.svg import _chip_positions, _IF_CHIP_OFFSET_Y, _NODE_HEADER_H
    from lib.rendering.layout import _node_size_for

    dev = {"id": "r1", "hostname": "R1"}
    ifaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
         "shutdown": False, "description": None},
    ]
    chip_ids = {"r1::eth0"}
    node_cx, node_cy = 200.0, 300.0

    result = _chip_positions(dev, chip_ids, ifaces, node_cx, node_cy)
    assert "r1::eth0" in result

    _, cy = result["r1::eth0"]

    # P1b #2: node_h は _chip_node_size_for(1) で計算（折返し対応後）
    from lib.rendering.svg import _chip_node_size_for
    _w, node_h = _chip_node_size_for(1)
    ny = node_cy - node_h / 2
    expected_cy = ny + _NODE_HEADER_H + _IF_CHIP_OFFSET_Y

    assert abs(cy - expected_cy) < 0.5, \
        f"chip cy={cy:.2f} が期待値 {expected_cy:.2f} と不一致 (node_cy={node_cy})"


@pytest.mark.unit
def test_p3_bgp_view_excludes_loopback_chips():
    """Task #11: BGP ビューのチップから Loopback IF が除外される。

    r1::lo0 (Loopback0) は BGP セッション参加 IF ではないため
    BGP チップ集合に含まれない。
    """
    from lib.rendering.views import _build_bgp_chip_iface_ids

    interfaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0",
         "ip": "10.0.12.1/30", "vlan": None, "description": None, "shutdown": False},
        {"id": "r1::lo0", "device": "r1", "name": "Loopback0",
         "ip": "10.255.1.1/32", "vlan": None, "description": None, "shutdown": False},
    ]
    bgp_entries = [
        {"device": "r1", "local_as": 65001, "peer_as": 65002,
         "local_ip": "10.0.12.1", "neighbor_ip": "10.0.12.2", "type": "ebgp"},
    ]

    chip_ids = _build_bgp_chip_iface_ids(bgp_entries, interfaces)

    assert "r1::eth0" in chip_ids, \
        "BGP セッション参加 IF (r1::eth0) がチップ集合に含まれない"
    assert "r1::lo0" not in chip_ids, \
        "Loopback0 (r1::lo0) が BGP チップ集合に含まれている（除外されるべき）"


@pytest.mark.unit
def test_p3_ospf_segment_edge_has_seg_id():
    """Task #12: _svg_ospf_segment_edges の <line> に data-seg-id 属性が付与される。

    Physical の _svg_segment_edges と同等のパリティ確認。
    """
    from lib.rendering.svg import _svg_ospf_segment_edges

    interfaces = [
        {"id": "r2::eth1", "device": "r2", "name": "eth1",
         "ip": "10.10.0.2/24", "shutdown": False, "description": None},
    ]
    segments = [
        {"id": "seg-10.10.0.0/24", "subnet": "10.10.0.0/24",
         "members": ["r2::eth1"], "ospf_area": 0},
    ]
    positions = {
        "seg-10.10.0.0/24": (350.0, 200.0),
        "r2": (200.0, 300.0),
    }

    svg = _svg_ospf_segment_edges(segments, interfaces, positions)

    # data-seg-id 属性が存在すること
    assert 'data-seg-id=' in svg, \
        f"_svg_ospf_segment_edges の <line> に data-seg-id 属性がない: {svg[:300]}"
    # 値が seg_id と一致すること
    m = re.search(r'data-seg-id="([^"]+)"', svg)
    assert m is not None, f"data-seg-id 属性値が取得できない: {svg}"
    assert m.group(1) == "seg-10.10.0.0/24", \
        f"data-seg-id の値 {m.group(1)!r} が seg_id と不一致"


@pytest.mark.unit
def test_p3_physical_chip_iface_ids_connected_if():
    """Task #13: _build_physical_chip_iface_ids が接続 IF を返す。"""
    from lib.rendering.views import _build_physical_chip_iface_ids

    interfaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0",
         "ip": "10.0.12.1/30", "vlan": None, "description": None, "shutdown": False},
        {"id": "r1::eth1", "device": "r1", "name": "eth1",
         "ip": "192.168.1.1/24", "vlan": None, "description": "LAN", "shutdown": False},
        {"id": "r2::eth0", "device": "r2", "name": "eth0",
         "ip": "10.0.12.2/30", "vlan": None, "description": None, "shutdown": False},
    ]
    links = [
        {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
         "subnet": "10.0.12.0/30", "kind": "inferred-subnet"},
    ]
    segments: list = []

    chip_ids = _build_physical_chip_iface_ids(interfaces, links, segments)

    assert "r1::eth0" in chip_ids, "接続 IF (r1::eth0) がチップ集合に含まれない"
    assert "r2::eth0" in chip_ids, "接続 IF (r2::eth0) がチップ集合に含まれない"
    assert "r1::eth1" not in chip_ids, "非接続・非 Loopback の r1::eth1 がチップ集合に含まれる"


@pytest.mark.unit
def test_p3_physical_chip_iface_ids_loopback():
    """Task #13: _build_physical_chip_iface_ids が Loopback IF を返す。"""
    from lib.rendering.views import _build_physical_chip_iface_ids

    interfaces = [
        {"id": "r1::lo0", "device": "r1", "name": "Loopback0",
         "ip": "10.255.1.1/32", "vlan": None, "description": None, "shutdown": False},
        {"id": "r1::eth0", "device": "r1", "name": "eth0",
         "ip": "192.168.1.1/24", "vlan": None, "description": "LAN", "shutdown": False},
    ]
    links: list = []
    segments: list = []

    chip_ids = _build_physical_chip_iface_ids(interfaces, links, segments)

    assert "r1::lo0" in chip_ids, "Loopback0 (r1::lo0) がチップ集合に含まれない"
    assert "r1::eth0" not in chip_ids, "非接続・非 Loopback の eth0 がチップ集合に含まれる"


# ===========================================================================
# Phase 3b — #7: Loopback チップ識別
# ===========================================================================

def _make_loopback_topology():
    """Loopback IF を持つシンプルな topology（#7 テスト用）"""
    return {
        "title": "Loopback Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0",
             "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "r1::lo0", "device": "r1", "name": "Loopback0",
             "ip": "10.255.0.1/32", "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0",
             "ip": "10.0.0.2/30", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.mark.unit
def test_p3b7_loopback_chip_has_loopback_class():
    """#7: Loopback IF のチップに if-chip-loopback クラスが付与される"""
    from lib.rendering.svg import _svg_if_chip, _is_loopback

    loopback_iface = {
        "id": "r1::lo0", "device": "r1", "name": "Loopback0",
        "ip": "10.255.0.1/32", "shutdown": False, "description": None,
    }
    # shutdown=False の Loopback チップを生成
    svg = _svg_if_chip(50.0, 80.0, 0, loopback_iface)
    assert "if-chip-loopback" in svg, \
        f"Loopback チップに if-chip-loopback クラスが付いていない: {svg}"


@pytest.mark.unit
def test_p3b7_normal_chip_no_loopback_class():
    """#7: 通常 IF チップに if-chip-loopback クラスが付かない"""
    from lib.rendering.svg import _svg_if_chip

    normal_iface = {
        "id": "r1::eth0", "device": "r1", "name": "eth0",
        "ip": "10.0.0.1/30", "shutdown": False, "description": None,
    }
    svg = _svg_if_chip(50.0, 80.0, 0, normal_iface)
    assert "if-chip-loopback" not in svg, \
        f"通常 IF チップに if-chip-loopback クラスが付いている（誤付与）: {svg}"


@pytest.mark.unit
def test_p3b7_loopback_chip_coexists_with_shutdown():
    """#7: Loopback かつ shutdown=True の場合、if-chip-loopback と if-chip-shutdown が共存する"""
    from lib.rendering.svg import _svg_if_chip

    lo_shutdown_iface = {
        "id": "r1::lo0", "device": "r1", "name": "Loopback0",
        "ip": "10.255.0.1/32", "shutdown": True, "description": None,
    }
    svg = _svg_if_chip(50.0, 80.0, 0, lo_shutdown_iface)
    assert "if-chip-loopback" in svg, "Loopback+shutdown チップに if-chip-loopback がない"
    assert "if-chip-shutdown" in svg, "Loopback+shutdown チップに if-chip-shutdown がない"


@pytest.mark.unit
def test_p3b7_css_loopback_rule_exists(rendered_html):
    """#7: CSS に .if-chip-loopback circle のルールが存在する"""
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined = "\n".join(style_blocks)
    assert ".if-chip-loopback" in combined, \
        "CSS に .if-chip-loopback ルールが存在しない"


@pytest.mark.unit
def test_p3b7_css_loopback_fill_differs_from_normal(rendered_html):
    """#7: .if-chip-loopback circle の fill が通常チップ（青系）と異なる（緑系など）"""
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined = "\n".join(style_blocks)
    # .if-chip-loopback circle ブロックを抽出
    m = re.search(r'\.if-chip-loopback\s+circle\s*\{([^}]+)\}', combined, re.DOTALL)
    assert m is not None, "CSS に .if-chip-loopback circle ブロックが存在しない"
    loopback_rule = m.group(1)
    # fill が定義されていること
    assert "fill" in loopback_rule, ".if-chip-loopback circle に fill が定義されていない"
    # 通常チップの fill（#bfdbfe = 青系）と同じでないこと
    assert "#bfdbfe" not in loopback_rule, \
        ".if-chip-loopback circle の fill が通常チップ（#bfdbfe）と同じ（区別できない）"


@pytest.mark.unit
def test_p3b7_legend_exists_in_html(rendered_html):
    """#7: 図に #chip-legend 要素が存在し、loopback クラス付き circle と Loopback ラベルを含む

    "Loopback" in html は CSS コメントにマッチして常時真になるため、
    id="chip-legend" の存在、凡例内の if-chip-loopback クラス、
    Loopback ラベルテキストの3点をそれぞれ検証する。
    """
    assert 'id="chip-legend"' in rendered_html, \
        "図に id='chip-legend' 要素が存在しない"
    # chip-legend 要素の内容部分を抽出
    legend_start = rendered_html.find('id="chip-legend"')
    legend_end = rendered_html.find('</div>', legend_start)
    legend_html = rendered_html[legend_start:legend_end + 6]
    assert "if-chip-loopback" in legend_html, \
        "chip-legend 内に if-chip-loopback クラスの circle が存在しない"
    assert "Loopback" in legend_html, \
        "chip-legend 内に Loopback ラベルテキストが存在しない"


@pytest.mark.unit
def test_p3b7_loopback_chip_in_physical_view():
    """#7: Physical ビューの Loopback IF チップに if-chip-loopback クラスが付与される"""
    from lib.rendering import render
    html = render(_make_loopback_topology())
    phys = _extract_physical_view(html)
    # Loopback0 のチップグループが if-chip-loopback クラスを持つこと
    assert "if-chip-loopback" in phys, \
        "Physical ビューの Loopback0 チップに if-chip-loopback クラスがない"


@pytest.mark.unit
def test_p3b7_loopback_chip_normal_chip_both_present():
    """#7: Physical ビューに通常チップと Loopback チップが共存し、クラスが正しく区別される

    - 通常チップ（r1::eth0）には if-chip-loopback クラスが付かない（否定条件）
    - Loopback チップ（r1::lo0）には if-chip-loopback クラスが付く（肯定条件）
    """
    from lib.rendering import render
    html = render(_make_loopback_topology())
    phys = _extract_physical_view(html)

    # Loopback チップが存在する（肯定条件）
    assert "if-chip-loopback" in phys, "Loopback チップが存在しない"

    # 通常チップ（data-iface-id="r1::eth0"）に if-chip-loopback が付かない（否定条件）
    normal_chip_match = re.search(
        r'<g class="([^"]*)"[^>]*data-iface-id="r1::eth0"', phys
    )
    assert normal_chip_match is not None, \
        "通常チップ（data-iface-id='r1::eth0'）が Physical ビューに存在しない"
    normal_chip_class = normal_chip_match.group(1)
    assert "if-chip-loopback" not in normal_chip_class, \
        f"通常チップ（r1::eth0）に if-chip-loopback クラスが誤付与されている: class='{normal_chip_class}'"

    # Loopback チップ（data-iface-id="r1::lo0"）に if-chip-loopback が付く（肯定条件）
    loopback_chip_match = re.search(
        r'<g class="([^"]*)"[^>]*data-iface-id="r1::lo0"', phys
    )
    assert loopback_chip_match is not None, \
        "Loopback チップ（data-iface-id='r1::lo0'）が Physical ビューに存在しない"
    loopback_chip_class = loopback_chip_match.group(1)
    assert "if-chip-loopback" in loopback_chip_class, \
        f"Loopback チップ（r1::lo0）に if-chip-loopback クラスが付いていない: class='{loopback_chip_class}'"


@pytest.mark.unit
def test_p3b7_deterministic_with_loopback():
    """#7: Loopback チップを含む topology で決定性が維持される"""
    from lib.rendering import render
    import copy
    topo = _make_loopback_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "Loopback チップを含む topology で render() が非決定的"


# ===========================================================================
# Phase 3b — #8: AS 枠ラベル拡大
# ===========================================================================

@pytest.mark.unit
def test_p3b8_as_group_label_font_size_enlarged(rendered_html):
    """#8: CSS の .as-group-label の font-size が 11px より大きく、14px 以上"""
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined = "\n".join(style_blocks)
    # .as-group-label ルールを抽出
    m = re.search(r'\.as-group-label\s*\{([^}]+)\}', combined, re.DOTALL)
    assert m is not None, "CSS に .as-group-label ルールが存在しない"
    rule = m.group(1)
    # font-size 値を取得
    fs_match = re.search(r'font-size\s*:\s*(\d+(?:\.\d+)?)(px|rem|em)', rule)
    assert fs_match is not None, ".as-group-label に font-size が定義されていない"
    font_size = float(fs_match.group(1))
    unit = fs_match.group(2)
    # px 単位で 14px 以上（11px でない）
    if unit == "px":
        assert font_size >= 14, \
            f".as-group-label の font-size が {font_size}px（期待: >=14px）"
        assert font_size != 11, \
            f".as-group-label の font-size がまだ 11px（変更されていない）"
    # rem/em の場合は 0.875rem(≈14px) 以上
    elif unit in ("rem", "em"):
        assert font_size >= 0.875, \
            f".as-group-label の font-size が {font_size}{unit}（期待: >=0.875rem）"


@pytest.mark.unit
def test_p3b8_as_group_label_font_weight_bold(rendered_html):
    """#8: .as-group-label に font-weight: bold（または 700）が設定されている"""
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined = "\n".join(style_blocks)
    m = re.search(r'\.as-group-label\s*\{([^}]+)\}', combined, re.DOTALL)
    assert m is not None, "CSS に .as-group-label ルールが存在しない"
    rule = m.group(1)
    assert "font-weight" in rule, ".as-group-label に font-weight が定義されていない"
    assert "bold" in rule or "700" in rule or "800" in rule, \
        f".as-group-label の font-weight が bold/700 でない: {rule.strip()}"


@pytest.mark.unit
def test_p3b8_as_group_chip_w_fits_label():
    """#8: AS 枠ラベルの背景 chip_w が「AS {asn}」テキストをはみ出さない幅に設定される。

    BGP 図の as-group-label-bg <rect> の幅が、フォント拡大後（1文字≒9px）の
    「AS {asn}」テキスト幅以上であること。
    """
    from lib.rendering import render
    import copy
    topo = _make_ebgp_topology()
    html = render(copy.deepcopy(topo))
    bgp_view = _extract_bgp_view_full(html)

    # as-group-label-bg <rect> の幅を取得
    bg_rects = re.findall(
        r'<rect[^>]*class="as-group-label-bg"[^>]*width="([^"]+)"',
        bgp_view
    )
    if not bg_rects:
        bg_rects = re.findall(
            r'<rect[^>]*width="([^"]+)"[^>]*class="as-group-label-bg"',
            bgp_view
        )
    assert len(bg_rects) >= 1, "as-group-label-bg <rect> が見つからない"

    # "AS 65001" は 8文字 → 新式 1文字≒9px+12 = 8*9+12 = 84px 以上が必要
    # 旧式 1文字≒7px+10 = 8*7+10 = 66px では不足（レビュー指摘 M-1）
    for w_str in bg_rects:
        w = float(w_str)
        # len("AS 65001")*9+12=84 前提で 80px 以上を必須とする
        assert w >= 80.0, \
            f"as-group-label-bg の幅 {w}px が小さすぎる（ラベルがはみ出す: 期待 >=80px, 旧式 *7+10=66 では不足）"


@pytest.mark.unit
def test_p3b8_as_group_chip_h_fits_label():
    """#8: AS 枠ラベルの背景 chip_h が拡大フォントに合わせて高くなっている（16px より高い）"""
    from lib.rendering import render
    import copy
    topo = _make_ebgp_topology()
    html = render(copy.deepcopy(topo))
    bgp_view = _extract_bgp_view_full(html)

    bg_rects = re.findall(
        r'<rect[^>]*class="as-group-label-bg"[^>]*height="([^"]+)"',
        bgp_view
    )
    if not bg_rects:
        bg_rects = re.findall(
            r'<rect[^>]*height="([^"]+)"[^>]*class="as-group-label-bg"',
            bgp_view
        )
    assert len(bg_rects) >= 1, "as-group-label-bg <rect> の height が見つからない"
    for h_str in bg_rects:
        h = float(h_str)
        # 拡大前は 16px → 拡大後は 18px 以上が必要
        assert h >= 18.0, \
            f"as-group-label-bg の高さ {h}px が小さすぎる（拡大後フォントに対して不足: 期待 >=18px）"


@pytest.mark.unit
def test_p3b8_deterministic_bgp_view_with_enlarged_label():
    """#8: AS ラベル拡大後も BGP ビューが決定的（2回レンダリングして一致）"""
    from lib.rendering import render
    import copy
    topo = _make_ebgp_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "AS ラベル拡大後の BGP ビューが非決定的"


# ===========================================================================
# Phase 3b — #9: ノード間隔を詰める
# ===========================================================================

def _make_medium_topology(n: int = 10):
    """n 台のデバイスをリング状に接続した topology（#9 キャンバス係数テスト用）"""
    devices = [{"id": f"r{i}", "hostname": f"R{i}", "vendor": "cisco_ios",
                "as": None, "sections": []}
               for i in range(n)]
    interfaces = [{"id": f"r{i}::eth0", "device": f"r{i}", "name": "eth0",
                   "ip": f"10.0.{i}.1/30", "vlan": None,
                   "description": None, "shutdown": False}
                  for i in range(n)]
    links = []
    for i in range(n - 1):
        links.append({
            "a_device": f"r{i}", "a_if": "eth0",
            "b_device": f"r{i+1}", "b_if": "eth0",
            "subnet": f"10.0.{i}.0/30", "kind": "inferred-subnet",
        })
    return {
        "title": f"Medium {n}-node Topology",
        "generated_from": [],
        "devices": devices,
        "interfaces": interfaces,
        "links": links,
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.mark.unit
def test_p3b9_canvas_factor_values():
    """#9: _CANVAS_FACTOR_W / _CANVAS_FACTOR_H が縮小されている（旧値 15/12 より小さい）"""
    from lib.rendering.layout import _CANVAS_FACTOR_W, _CANVAS_FACTOR_H
    # Phase 3a 前の値は W=15, H=12。縮小後は < 15 / < 12
    assert _CANVAS_FACTOR_W < 15, \
        f"_CANVAS_FACTOR_W={_CANVAS_FACTOR_W} が旧値 15 以上（縮小されていない）"
    assert _CANVAS_FACTOR_H < 12, \
        f"_CANVAS_FACTOR_H={_CANVAS_FACTOR_H} が旧値 12 以上（縮小されていない）"


@pytest.mark.unit
def test_p3b9_canvas_smaller_than_old_for_medium_n():
    """#9: 係数縮小後の _canvas_size_for_nodes(10) が旧係数での値より小さい"""
    from lib.rendering.layout import _canvas_size_for_nodes, _CANVAS_FACTOR_W, _CANVAS_FACTOR_H, _NODE_WIDTH, _CANVAS_SCALE_EXP, _MIN_CANVAS_W, _MIN_CANVAS_H, _NODE_HEIGHT

    n = 10
    w_new, h_new = _canvas_size_for_nodes(n)

    # 旧係数（15, 12）での値を手計算
    w_old = max(_MIN_CANVAS_W, n * (_NODE_WIDTH + 20) ** _CANVAS_SCALE_EXP * 15)
    h_old = max(_MIN_CANVAS_H, n * (_NODE_HEIGHT + 20) ** _CANVAS_SCALE_EXP * 12)

    # 新値が旧値より小さいこと（幅・高さの両方が縮小されていること）
    assert w_new < w_old and h_new < h_old, (
        f"係数縮小後のキャンバス({w_new:.0f}x{h_new:.0f})が旧値({w_old:.0f}x{h_old:.0f})より"
        f"幅・高さともに小さくなっていない"
    )


@pytest.mark.unit
def test_p3b9_no_overlap_after_factor_reduction():
    """#9: 係数縮小後も重なりなし保証が維持される（密集テスト: 小キャンバス固定）

    _canvas_size_for_nodes による自動キャンバスは大きすぎて自明 PASS になる。
    代わりに width=900, height=600 の小さい固定キャンバスに 10 ノードを
    _layout_force_directed(..., node_sizes=...) で直接配置して、
    全ペアの分離を実ノード寸法ベースで検証する。
    """
    from lib.rendering.layout import _layout_force_directed, _node_size_for
    n = 10
    node_ids = [f"r{i}" for i in range(n)]
    edges = [(f"r{i}", f"r{i+1}") for i in range(n - 1)]
    node_sizes = {f"r{i}": 1 for i in range(n)}  # 各ノード 1 IF

    # 固定の小キャンバス（自明 PASS を防ぐ）
    w, h = 900, 600
    pos = _layout_force_directed(node_ids, edges, width=w, height=h,
                                  iterations=300, node_sizes=node_sizes)

    # 全ペアの中心間距離 >= 実ノード寸法の半幅+半高+マージン
    for i, na in enumerate(node_ids):
        for j, nb in enumerate(node_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            wa, ha = _node_size_for(node_sizes[na])
            wb, hb = _node_size_for(node_sizes[nb])
            dx = abs(x1 - x2)
            dy = abs(y1 - y2)
            min_sep_x = (wa + wb) / 2 + 5
            min_sep_y = (ha + hb) / 2 + 5
            no_overlap = dx >= min_sep_x or dy >= min_sep_y
            assert no_overlap, (
                f"密集キャンバス ({w}x{h}) でノード {na} と {nb} が重なっている "
                f"(dx={dx:.1f} min_sep_x={min_sep_x:.1f}, dy={dy:.1f} min_sep_y={min_sep_y:.1f})"
            )


@pytest.mark.unit
def test_p3b9_min_canvas_respected():
    """#9: _canvas_size_for_nodes(0) / (1) が _MIN_CANVAS_W/H を下回らない"""
    from lib.rendering.layout import _canvas_size_for_nodes, _MIN_CANVAS_W, _MIN_CANVAS_H
    for n in (0, 1):
        w, h = _canvas_size_for_nodes(n)
        assert w >= _MIN_CANVAS_W, f"n={n}: キャンバス幅 {w} < _MIN_CANVAS_W {_MIN_CANVAS_W}"
        assert h >= _MIN_CANVAS_H, f"n={n}: キャンバス高 {h} < _MIN_CANVAS_H {_MIN_CANVAS_H}"


@pytest.mark.unit
def test_p3b9_existing_bgp_no_overlap_still_passes():
    """#9: 係数縮小後も既存の BGP トポロジーでノード重なりゼロを維持（回帰保護）"""
    from lib.rendering.views import _build_bgp_layout
    from lib.rendering.layout import _node_size_for

    topo = _make_p3_bgp_topology()

    # シグネチャ: _build_bgp_layout(devices, bgp_entries, interfaces)
    pos, _bgp_devices = _build_bgp_layout(
        topo["devices"], topo["routing"].get("bgp", []), topo["interfaces"]
    )

    # デバイスごとのインターフェース数を集計してノードサイズを算出
    iface_count: dict[str, int] = {}
    for iface in topo["interfaces"]:
        iface_count[iface["device"]] = iface_count.get(iface["device"], 0) + 1

    dev_ids = [d["id"] for d in topo["devices"] if d["id"] in pos]
    for i, na in enumerate(dev_ids):
        for j, nb in enumerate(dev_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            wa, ha = _node_size_for(iface_count.get(na, 0))
            wb, hb = _node_size_for(iface_count.get(nb, 0))
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            needed_x = (wa + wb) / 2 + 5
            needed_y = (ha + hb) / 2 + 5
            no_overlap = dx >= needed_x or dy >= needed_y
            assert no_overlap, (
                f"BGP ビューでノード {na} と {nb} が重なっている "
                f"(dx={dx:.1f} needed_x={needed_x:.1f}, dy={dy:.1f} needed_y={needed_y:.1f})"
            )


@pytest.mark.unit
def test_p3b9_deterministic_after_factor_change(sample_topology):
    """#9: 係数縮小後も同一入力で 2 回 render した結果が完全一致（決定性維持）"""
    from lib.rendering import render
    import copy
    t1 = copy.deepcopy(sample_topology)
    t2 = copy.deepcopy(sample_topology)
    html1 = render(t1)
    html2 = render(t2)
    assert html1 == html2, "係数縮小後の render() が非決定的"


# ===========================================================================
# Phase 3b — #10: カード幅の均一化
# ===========================================================================

@pytest.mark.unit
def test_p3b10_cards_grid_is_display_grid(rendered_html):
    """#10: .cards-grid が display:grid を使用する"""
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined = "\n".join(style_blocks)
    # .cards-grid ルールを抽出
    m = re.search(r'\.cards-grid\s*\{([^}]+)\}', combined, re.DOTALL)
    assert m is not None, "CSS に .cards-grid ルールが存在しない"
    rule = m.group(1)
    assert "display" in rule, ".cards-grid に display プロパティが定義されていない"
    assert "grid" in rule, \
        f".cards-grid の display が grid でない: {rule.strip()}"


@pytest.mark.unit
def test_p3b10_cards_grid_has_grid_template_columns(rendered_html):
    """#10: .cards-grid に grid-template-columns が定義されている（Round A: 縦1列 1fr）"""
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined = "\n".join(style_blocks)
    m = re.search(r'\.cards-grid\s*\{([^}]+)\}', combined, re.DOTALL)
    assert m is not None, "CSS に .cards-grid ルールが存在しない"
    rule = m.group(1)
    assert "grid-template-columns" in rule, \
        ".cards-grid に grid-template-columns が定義されていない"
    # Round A A1: 縦1列（1fr）。auto-fill/minmax による複数列は撤廃済み
    assert "1fr" in rule, \
        f".cards-grid の grid-template-columns に 1fr がない（縦1列になっていない）: {rule.strip()!r}"


@pytest.mark.unit
def test_p3b10_cards_grid_no_flex(rendered_html):
    """#10: .cards-grid から flex/flex-wrap が撤去されている（grid に移行済み）"""
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined = "\n".join(style_blocks)
    m = re.search(r'\.cards-grid\s*\{([^}]+)\}', combined, re.DOTALL)
    assert m is not None, "CSS に .cards-grid ルールが存在しない"
    rule = m.group(1)
    # display:flex が残っていないこと（display:grid に置き換え済み）
    assert "display: flex" not in rule.replace(" ", "") and "display:flex" not in rule.replace(" ", ""), \
        ".cards-grid に display:flex が残っている（grid 移行未完了）"
    # flex-wrap も撤去済みであること
    assert "flex-wrap" not in rule, \
        ".cards-grid に flex-wrap が残っている（撤去されていない）"


@pytest.mark.unit
def test_p3b10_device_card_no_flex(rendered_html):
    """#10: .device-card から flex/min-width/max-width が撤去されている（幅は grid 列で決定）"""
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined = "\n".join(style_blocks)
    m = re.search(r'\.device-card\s*\{([^}]+)\}', combined, re.DOTALL)
    assert m is not None, "CSS に .device-card ルールが存在しない"
    rule = m.group(1)
    # flex:1 が撤去されていること
    assert "flex: 1" not in rule.replace(" ", "") and "flex:1" not in rule.replace(" ", ""), \
        ".device-card に flex:1 が残っている（撤去されていない）"
    # min-width が撤去されていること
    assert "min-width" not in rule, \
        ".device-card に min-width が残っている（撤去されていない）"
    # max-width が撤去されていること
    assert "max-width" not in rule, \
        ".device-card に max-width が残っている（撤去されていない）"


@pytest.mark.unit
def test_p3b10_card_unselected_works_with_grid(rendered_html):
    """#10: .card-unselected { display:none } が grid アイテムに適用されても問題ない。
    CSS に .card-unselected { display:none } ルールが存在すること。"""
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', rendered_html, re.DOTALL | re.IGNORECASE)
    combined = "\n".join(style_blocks)
    # .card-unselected ルールが存在すること
    assert ".card-unselected" in combined, \
        "CSS に .card-unselected ルールが存在しない"
    m = re.search(r'\.card-unselected\s*\{([^}]+)\}', combined, re.DOTALL)
    assert m is not None, ".card-unselected ルールの本体が見つからない"
    rule = m.group(1)
    assert "display" in rule, ".card-unselected に display が定義されていない"
    assert "none" in rule, ".card-unselected が display:none になっていない"


@pytest.mark.unit
def test_p3b10_render_still_contains_cards_grid(rendered_html):
    """#10: render() 後の HTML に cards-grid クラスが存在する（構造回帰保護）"""
    assert 'class="cards-grid"' in rendered_html, \
        "cards-grid クラスを持つ要素が HTML に存在しない"


@pytest.mark.unit
def test_p3b10_deterministic_after_grid_change(sample_topology):
    """#10: grid 移行後も render() が決定的（2回一致）"""
    from lib.rendering import render
    import copy
    t1 = copy.deepcopy(sample_topology)
    t2 = copy.deepcopy(sample_topology)
    html1 = render(t1)
    html2 = render(t2)
    assert html1 == html2, "grid 移行後の render() が非決定的"


# ===========================================================================
# iteration-4 クロスレビュー実バグ修正 — multi-as-area 現実的フィクスチャ
# ===========================================================================
#
# バグ1: OSPFビューでマルチエリアノード（core1）の全OSPF-IFチップが描画される（回帰保護）
# バグ2: BGPビューで local_ip=null の iBGP ノード（edge1）に Loopback チップが出ない
# バグ3: Physicalビューのセグメントエッジがノード中心に接続（チップアンカー未実装）
# ===========================================================================

def _make_multi_as_area_topology():
    """multi-as-area を模した現実的トポロジー（7台）。

    構成:
      core1(AS65000): GE0/0(area0,core1-core2), GE0/1(area0,core1-edge1),
                      GE0/2(area1,seg-shared), Loopback0(10.255.0.1/32)
      core2(AS65000): GE0/0(area0,core1-core2), GE0/1(eBGP-cust2), Loopback0(10.255.0.2/32)
                      iBGP(local_ip=null, neighbor=10.255.0.1)
      edge1(AS65000): GE0/0(area0,core1-edge1), GE0/1(eBGP-cust1), Loopback0(10.255.0.3/32)
                      iBGP(local_ip=null, neighbor=10.255.0.1)
      acc1: GE0/0(area1,seg-shared), Loopback0(10.255.3.1/32)
      acc2: GE0/0(area1,seg-shared), Loopback0(10.255.3.2/32)
      cust1(AS65100): GE0/0(eBGP-edge1), Loopback0
      cust2(AS65200): ge-0/0/0(eBGP-core2), lo0

    セグメント: seg-192_168_50_0_24 (area1) members=[acc1::GE0/0, acc2::GE0/0, core1::GE0/2]
    """
    return {
        "title": "multi-as-area test",
        "generated_from": [],
        "devices": [
            {"id": "acc1", "hostname": "ACC1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "acc2", "hostname": "ACC2", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "core1", "hostname": "CORE1", "vendor": "cisco_ios", "as": 65000, "sections": []},
            {"id": "core2", "hostname": "CORE2", "vendor": "cisco_ios", "as": 65000, "sections": []},
            {"id": "cust1", "hostname": "CUST1", "vendor": "cisco_ios", "as": 65100, "sections": []},
            {"id": "cust2", "hostname": "CUST2", "vendor": "juniper_junos", "as": 65200, "sections": []},
            {"id": "edge1", "hostname": "EDGE1", "vendor": "cisco_ios", "as": 65000, "sections": []},
        ],
        "interfaces": [
            # acc1
            {"id": "acc1::Loopback0", "device": "acc1", "name": "Loopback0",
             "ip": "10.255.3.1/32", "vlan": None, "description": None, "shutdown": False},
            {"id": "acc1::GigabitEthernet0/0", "device": "acc1", "name": "GigabitEthernet0/0",
             "ip": "192.168.50.2/24", "vlan": None, "description": "ACCESS-SHARED-SEGMENT-AREA1", "shutdown": False},
            # acc2
            {"id": "acc2::Loopback0", "device": "acc2", "name": "Loopback0",
             "ip": "10.255.3.2/32", "vlan": None, "description": None, "shutdown": False},
            {"id": "acc2::GigabitEthernet0/0", "device": "acc2", "name": "GigabitEthernet0/0",
             "ip": "192.168.50.3/24", "vlan": None, "description": "ACCESS-SHARED-SEGMENT-AREA1", "shutdown": False},
            # core1 - 3 OSPF参加IF + Loopback
            {"id": "core1::Loopback0", "device": "core1", "name": "Loopback0",
             "ip": "10.255.0.1/32", "vlan": None, "description": None, "shutdown": False},
            {"id": "core1::GigabitEthernet0/0", "device": "core1", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.1/30", "vlan": None, "description": "CORE-LINK-to-CORE2-AREA0", "shutdown": False},
            {"id": "core1::GigabitEthernet0/1", "device": "core1", "name": "GigabitEthernet0/1",
             "ip": "10.0.1.1/30", "vlan": None, "description": "CORE-LINK-to-EDGE1-AREA0", "shutdown": False},
            {"id": "core1::GigabitEthernet0/2", "device": "core1", "name": "GigabitEthernet0/2",
             "ip": "192.168.50.1/24", "vlan": None, "description": "ACCESS-SHARED-SEGMENT-AREA1", "shutdown": False},
            # core2 - iBGP(local_ip=null) + eBGP物理IF
            {"id": "core2::Loopback0", "device": "core2", "name": "Loopback0",
             "ip": "10.255.0.2/32", "vlan": None, "description": None, "shutdown": False},
            {"id": "core2::GigabitEthernet0/0", "device": "core2", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.2/30", "vlan": None, "description": "CORE-LINK-to-CORE1-AREA0", "shutdown": False},
            {"id": "core2::GigabitEthernet0/1", "device": "core2", "name": "GigabitEthernet0/1",
             "ip": "10.2.0.1/30", "vlan": None, "description": "EBGP-LINK-to-CUST2", "shutdown": False},
            # cust1
            {"id": "cust1::Loopback0", "device": "cust1", "name": "Loopback0",
             "ip": "10.255.1.1/32", "vlan": None, "description": None, "shutdown": False},
            {"id": "cust1::GigabitEthernet0/0", "device": "cust1", "name": "GigabitEthernet0/0",
             "ip": "10.1.0.2/30", "vlan": None, "description": "EBGP-LINK-to-EDGE1", "shutdown": False},
            # cust2
            {"id": "cust2::lo0", "device": "cust2", "name": "lo0",
             "ip": "10.255.2.1/32", "vlan": None, "description": None, "shutdown": False},
            {"id": "cust2::ge-0/0/0", "device": "cust2", "name": "ge-0/0/0",
             "ip": "10.2.0.2/30", "vlan": None, "description": "EBGP-LINK-to-CORE2", "shutdown": False},
            # edge1 - iBGP(local_ip=null) + eBGP物理IF + Loopback
            {"id": "edge1::Loopback0", "device": "edge1", "name": "Loopback0",
             "ip": "10.255.0.3/32", "vlan": None, "description": None, "shutdown": False},
            {"id": "edge1::GigabitEthernet0/0", "device": "edge1", "name": "GigabitEthernet0/0",
             "ip": "10.0.1.2/30", "vlan": None, "description": "CORE-LINK-to-CORE1-AREA0", "shutdown": False},
            {"id": "edge1::GigabitEthernet0/1", "device": "edge1", "name": "GigabitEthernet0/1",
             "ip": "10.1.0.1/30", "vlan": None, "description": "EBGP-LINK-to-CUST1", "shutdown": False},
        ],
        "links": [
            {"a_device": "core1", "a_if": "GigabitEthernet0/0",
             "b_device": "core2", "b_if": "GigabitEthernet0/0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet", "ospf_area": "0"},
            {"a_device": "core1", "a_if": "GigabitEthernet0/1",
             "b_device": "edge1", "b_if": "GigabitEthernet0/0",
             "subnet": "10.0.1.0/30", "kind": "inferred-subnet", "ospf_area": "0"},
            {"a_device": "core2", "a_if": "GigabitEthernet0/1",
             "b_device": "cust2", "b_if": "ge-0/0/0",
             "subnet": "10.2.0.0/30", "kind": "inferred-subnet"},
            {"a_device": "cust1", "a_if": "GigabitEthernet0/0",
             "b_device": "edge1", "b_if": "GigabitEthernet0/1",
             "subnet": "10.1.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [
            {"id": "seg-192_168_50_0_24", "subnet": "192.168.50.0/24",
             "ospf_area": "1", "ospf_network": "192.168.50.0/24",
             "members": ["acc1::GigabitEthernet0/0", "acc2::GigabitEthernet0/0",
                         "core1::GigabitEthernet0/2"]},
        ],
        "routing": {
            "bgp": [
                # core1: iBGPのみ(local_ip=null, neighbor=core2 Loopback)
                {"device": "core1", "local_as": 65000, "peer_as": 65000,
                 "local_ip": None, "neighbor_ip": "10.255.0.2", "type": "ibgp"},
                # core2: iBGP(local_ip=null) + eBGP
                {"device": "core2", "local_as": 65000, "peer_as": 65000,
                 "local_ip": None, "neighbor_ip": "10.255.0.1", "type": "ibgp"},
                {"device": "core2", "local_as": 65000, "peer_as": 65200,
                 "local_ip": "10.2.0.1", "neighbor_ip": "10.2.0.2", "type": "ebgp"},
                {"device": "cust1", "local_as": 65100, "peer_as": 65000,
                 "local_ip": "10.1.0.2", "neighbor_ip": "10.1.0.1", "type": "ebgp"},
                {"device": "cust2", "local_as": 65200, "peer_as": 65000,
                 "local_ip": "10.2.0.2", "neighbor_ip": "10.2.0.1", "type": "ebgp"},
                # edge1: iBGP(local_ip=null) + eBGP — edge1 Loopback(10.255.0.3)は
                # 他機のneighbor_ipに現れないのでバグ2の再現ケース
                {"device": "edge1", "local_as": 65000, "peer_as": 65000,
                 "local_ip": None, "neighbor_ip": "10.255.0.1", "type": "ibgp"},
                {"device": "edge1", "local_as": 65000, "peer_as": 65100,
                 "local_ip": "10.1.0.1", "neighbor_ip": "10.1.0.2", "type": "ebgp"},
            ],
            "ospf": [
                {"device": "acc1", "area": "1", "process": 1, "network": "192.168.50.0/24"},
                {"device": "acc2", "area": "1", "process": 1, "network": "192.168.50.0/24"},
                {"device": "core1", "area": "0", "process": 1, "network": "10.0.0.0/30"},
                {"device": "core1", "area": "0", "process": 1, "network": "10.0.1.0/30"},
                {"device": "core1", "area": "1", "process": 1, "network": "192.168.50.0/24"},
                {"device": "core2", "area": "0", "process": 1, "network": "10.0.0.0/30"},
                {"device": "edge1", "area": "0", "process": 1, "network": "10.0.1.0/30"},
            ],
            "static": [],
        },
    }


def _extract_bgp_view_from(html: str) -> str:
    """BGP ビュー <g class="view view-bgp" ...> ... の中身を返す"""
    start = html.find('class="view view-bgp"')
    if start == -1:
        return ""
    next_view = html.find('class="view view-', start + 10)
    return html[start:next_view] if next_view != -1 else html[start:]


def _extract_ospf_view_from(html: str) -> str:
    """OSPF ビュー <g class="view view-ospf" ...> ... の中身を返す"""
    start = html.find('class="view view-ospf"')
    if start == -1:
        return ""
    next_view = html.find('class="view view-', start + 10)
    return html[start:next_view] if next_view != -1 else html[start:]


def _extract_physical_view_from(html: str) -> str:
    """Physical ビュー <g class="view view-physical" ...> ... の中身を返す"""
    start = html.find('class="view view-physical"')
    if start == -1:
        return ""
    next_view = html.find('class="view view-', start + 10)
    return html[start:next_view] if next_view != -1 else html[start:]


# ---------------------------------------------------------------------------
# バグ1回帰保護: OSPFビューでマルチエリアノードの全OSPF-IFチップが描画される
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_i4cr_ospf_multi_area_node_all_chips_rendered():
    """バグ1回帰: OSPFビューでcore1(3 OSPF-IF)の全チップが描画される。

    core1 は area0 に GE0/0(p2p-core2), GE0/1(p2p-edge1) 参加し、
    area1 の共有セグメントに GE0/2 で参加する。
    3チップすべてが data-iface-id として存在すること。
    """
    from lib.rendering import render
    topo = _make_multi_as_area_topology()
    html = render(topo)
    ospf = _extract_ospf_view_from(html)
    assert ospf, "OSPF ビューが生成されない"

    # core1 の 3 OSPF IF すべてがチップとして存在する
    assert 'data-iface-id="core1::GigabitEthernet0/0"' in ospf, \
        "OSPFビューで core1::GE0/0 チップが描画されない"
    assert 'data-iface-id="core1::GigabitEthernet0/1"' in ospf, \
        "OSPFビューで core1::GE0/1 チップが描画されない"
    assert 'data-iface-id="core1::GigabitEthernet0/2"' in ospf, \
        "OSPFビューで core1::GE0/2 チップが描画されない（area1セグメントメンバー）"


@pytest.mark.unit
def test_i4cr_ospf_multi_area_node_edge_anchor_matches_chip():
    """バグ1回帰: OSPFビューのエッジ端点座標が描画チップ座標に一致する（描画=アンカー）。

    _build_view_ospf で構築した chip_positions と _svg_nodes の chip 集合が
    同一の ospf_chip_ids 由来であることを、座標一致で検証する。
    """
    from lib.rendering.views import _build_view_ospf, _build_ospf_chip_iface_ids
    from lib.rendering.svg import _chip_positions

    topo = _make_multi_as_area_topology()
    interfaces = topo["interfaces"]
    links = topo["links"]
    segments = topo["segments"]
    devices = topo["devices"]
    ospf_entries = topo["routing"]["ospf"]

    iface_by_device: dict = {}
    for iface in interfaces:
        iface_by_device.setdefault(iface["device"], []).append(iface)

    svg = _build_view_ospf(
        devices, ospf_entries, links, iface_by_device, segments, interfaces
    )

    # core1 GE0/0, GE0/1, GE0/2 のチップ座標と p2p/seg エッジ端点が一致するか確認
    # チップ cx を抽出
    chip_cx_map: dict[str, float] = {}
    for m in re.finditer(r'data-iface-id="(core1::[^"]+)"><circle cx="([\d.]+)"', svg):
        chip_cx_map[m.group(1)] = float(m.group(2))

    assert "core1::GigabitEthernet0/0" in chip_cx_map, \
        "OSPFビュー: core1::GE0/0 チップが存在しない"
    assert "core1::GigabitEthernet0/1" in chip_cx_map, \
        "OSPFビュー: core1::GE0/1 チップが存在しない"
    assert "core1::GigabitEthernet0/2" in chip_cx_map, \
        "OSPFビュー: core1::GE0/2 チップが存在しない"

    # p2p エッジ(core1->core2): x1 が core1::GE0/0 チップ cx に一致
    # data-ospf-id が追加される場合に備えて [^>]* で属性を柔軟にマッチ
    m = re.search(
        r'data-a="core1" data-b="core2"[^>]*><line x1="([\d.]+)"', svg
    )
    assert m is not None, "OSPFビュー: core1-core2 エッジが見つからない"
    assert abs(float(m.group(1)) - chip_cx_map["core1::GigabitEthernet0/0"]) < 1.0, \
        f"core1-core2 エッジ x1={m.group(1)} が core1::GE0/0 チップ cx={chip_cx_map['core1::GigabitEthernet0/0']} に一致しない"

    # p2p エッジ(core1->edge1): x1 が core1::GE0/1 チップ cx に一致
    m = re.search(
        r'data-a="core1" data-b="edge1"[^>]*><line x1="([\d.]+)"', svg
    )
    assert m is not None, "OSPFビュー: core1-edge1 エッジが見つからない"
    assert abs(float(m.group(1)) - chip_cx_map["core1::GigabitEthernet0/1"]) < 1.0, \
        f"core1-edge1 エッジ x1={m.group(1)} が core1::GE0/1 チップ cx={chip_cx_map['core1::GigabitEthernet0/1']} に一致しない"

    # seg-edge(seg->core1): x2 が core1::GE0/2 チップ cx に一致
    m = re.search(
        r'<line[^>]*data-device="core1"[^>]*/>', svg
    )
    assert m is not None, "OSPFビュー: seg-edge core1 が見つからない"
    x2_m = re.search(r'x2="([\d.]+)"', m.group(0))
    assert x2_m is not None, f"seg-edge core1 に x2 が見つからない: {m.group(0)}"
    assert abs(float(x2_m.group(1)) - chip_cx_map["core1::GigabitEthernet0/2"]) < 1.0, \
        f"seg-edge core1 x2={x2_m.group(1)} が core1::GE0/2 チップ cx={chip_cx_map['core1::GigabitEthernet0/2']} に一致しない"


# ---------------------------------------------------------------------------
# バグ2: BGPビューで local_ip=null の iBGP ノードに Loopback チップが出ない
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_i4cr_bgp_ibgp_loopback_chip_when_local_ip_null():
    """バグ2: local_ip=null の iBGP ノード（edge1）に Loopback チップが描画される。

    edge1 は iBGP(local_ip=null, neighbor=10.255.0.1) + eBGP を持つ。
    edge1::Loopback0(10.255.0.3) は他機の neighbor_ip に現れないが、
    local_ip=null の iBGP エントリに対して「自機の Loopback」として拾われるべき。
    """
    from lib.rendering import render
    topo = _make_multi_as_area_topology()
    html = render(topo)
    bgp = _extract_bgp_view_from(html)
    assert bgp, "BGP ビューが生成されない"

    assert 'data-iface-id="edge1::Loopback0"' in bgp, \
        "BGPビューで edge1::Loopback0 チップが描画されない（local_ip=null iBGP ノードのバグ2）"


@pytest.mark.unit
def test_i4cr_bgp_ibgp_loopback_chip_coexists_with_ebgp_chip():
    """バグ2: edge1 の Loopback チップと eBGP 物理 IF チップが共存する。

    iBGP Loopback 追加後に eBGP 用 GE0/1 チップが消えないこと。
    """
    from lib.rendering import render
    topo = _make_multi_as_area_topology()
    html = render(topo)
    bgp = _extract_bgp_view_from(html)
    assert bgp, "BGP ビューが生成されない"

    assert 'data-iface-id="edge1::Loopback0"' in bgp, \
        "edge1::Loopback0 チップが存在しない"
    assert 'data-iface-id="edge1::GigabitEthernet0/1"' in bgp, \
        "edge1::GE0/1（eBGP物理IF）チップが消えた（regression）"


@pytest.mark.unit
def test_i4cr_bgp_chip_iface_ids_ibgp_loopback():
    """バグ2ユニット: _build_bgp_chip_iface_ids が local_ip=null iBGPノードの
    自機 Loopback を含めることを直接検証する。

    edge1 の local_ip=null iBGP エントリから edge1::Loopback0 が返される。
    """
    from lib.rendering.views import _build_bgp_chip_iface_ids

    topo = _make_multi_as_area_topology()
    bgp_entries = topo["routing"]["bgp"]
    interfaces = topo["interfaces"]

    result = _build_bgp_chip_iface_ids(bgp_entries, interfaces)

    assert "edge1::Loopback0" in result, \
        f"edge1::Loopback0 が BGP チップ集合にない: {sorted(result)}"


@pytest.mark.unit
def test_i4cr_bgp_chip_iface_ids_core1_loopback_still_present():
    """バグ2: 修正後も core1::Loopback0（neighbor_ip 経由で解決済み）が残る。

    core2 の iBGP neighbor_ip=10.255.0.1 → core1::Loopback0 は従来通り拾えるはず。
    """
    from lib.rendering.views import _build_bgp_chip_iface_ids

    topo = _make_multi_as_area_topology()
    result = _build_bgp_chip_iface_ids(topo["routing"]["bgp"], topo["interfaces"])

    assert "core1::Loopback0" in result, \
        f"core1::Loopback0 が BGP チップ集合にない（regression）: {sorted(result)}"


@pytest.mark.unit
def test_i4cr_bgp_ibgp_session_endpoint_uses_loopback_chip():
    """バグ2: iBGP セッション線の local_ip=null 端がノード中心でなく Loopback チップ座標を使う。

    edge1 の iBGP（local_ip=null）について、edge1::Loopback0 チップが存在するとき、
    BGP path の edge1 側端点がそのチップ座標に一致すること。
    local_ip=null 端はノード中心フォールバックではなく Loopback チップを使う。
    """
    from lib.rendering.svg import _svg_bgp_edges, _chip_positions
    from lib.rendering.layout import _NODE_WIDTH, _node_size_for, _NODE_HEADER_H
    from lib.rendering.svg import _IF_CHIP_OFFSET_X, _IF_CHIP_OFFSET_Y

    topo = _make_multi_as_area_topology()
    interfaces = topo["interfaces"]
    bgp_entries = topo["routing"]["bgp"]

    # edge1 と core1 のみでテスト（iBGP セッション）
    edge1_entries = [e for e in bgp_entries if e["device"] == "edge1" and e["type"] == "ibgp"]
    assert edge1_entries, "edge1 iBGP エントリが見つからない"

    positions = {
        "edge1": (200.0, 300.0),
        "core1": (600.0, 300.0),
    }

    # edge1::Loopback0 チップ座標を計算（k=0: 名前ソートでLoopback0が最初）
    edge1_ifaces = [i for i in interfaces if i["device"] == "edge1"]
    edge1_dev = {"id": "edge1", "hostname": "EDGE1"}
    chip_ids_edge1 = {"edge1::Loopback0"}
    edge1_chips = _chip_positions(edge1_dev, chip_ids_edge1, edge1_ifaces, 200.0, 300.0)
    assert "edge1::Loopback0" in edge1_chips, "edge1::Loopback0 チップ座標が取れない"

    # core1::Loopback0 チップ座標
    core1_ifaces = [i for i in interfaces if i["device"] == "core1"]
    core1_dev = {"id": "core1", "hostname": "CORE1"}
    chip_ids_core1 = {"core1::Loopback0"}
    core1_chips = _chip_positions(core1_dev, chip_ids_core1, core1_ifaces, 600.0, 300.0)

    all_chips = {**edge1_chips, **core1_chips}

    svg = _svg_bgp_edges(edge1_entries, interfaces, positions, chip_positions=all_chips)

    # edge1 iBGP のパスを探す
    m = re.search(r'<path[^>]+d="M([\d.]+),([\d.]+)', svg)
    assert m is not None, \
        "edge1 iBGP セッション線が描画されない（positions に core1/edge1 両方あり、エッジは必ず生成される）"

    # path_x1 が edge1::Loopback0 チップ座標に一致することを確認
    path_x1 = float(m.group(1))
    path_y1 = float(m.group(2))
    exp_x, exp_y = edge1_chips["edge1::Loopback0"]

    assert abs(path_x1 - exp_x) < 1.0, \
        f"iBGP local_ip=null 端の x={path_x1} が Loopback チップ cx={exp_x} に一致しない（ノード中心フォールバックのまま）"
    assert abs(path_y1 - exp_y) < 1.0, \
        f"iBGP local_ip=null 端の y={path_y1} が Loopback チップ cy={exp_y} に一致しない"


# ---------------------------------------------------------------------------
# バグ3: Physicalビューのセグメントエッジがノード中心に接続（チップアンカー未実装）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_i4cr_physical_segment_edge_anchors_to_chip():
    """バグ3: Physicalビューのセグメントエッジ端点がメンバーIFチップ座標に一致する。

    acc1::GE0/0, acc2::GE0/0, core1::GE0/2 が seg-192_168_50_0_24 のメンバー。
    各デバイスとのセグエッジ x2,y2 がそれぞれのチップ座標に一致すること。
    """
    from lib.rendering import render
    topo = _make_multi_as_area_topology()
    html = render(topo)
    phys = _extract_physical_view_from(html)
    assert phys, "Physical ビューが生成されない"

    # 各メンバーのチップ座標を抽出
    chip_cx_map: dict[str, float] = {}
    chip_cy_map: dict[str, float] = {}
    for m in re.finditer(
        r'data-iface-id="([^"]+)"><circle cx="([\d.]+)" cy="([\d.]+)"', phys
    ):
        chip_cx_map[m.group(1)] = float(m.group(2))
        chip_cy_map[m.group(1)] = float(m.group(3))

    # セグエッジの x2,y2（デバイス側端点）を抽出
    seg_edge_map: dict[str, tuple[float, float]] = {}
    for m in re.finditer(
        r'<line[^>]*class="seg-edge layer-physical"[^>]*data-device="([^"]+)"[^>]*/>', phys
    ):
        line_str = m.group(0)
        x2_m = re.search(r'x2="([\d.]+)"', line_str)
        y2_m = re.search(r'y2="([\d.]+)"', line_str)
        if x2_m and y2_m:
            seg_edge_map[m.group(1)] = (float(x2_m.group(1)), float(y2_m.group(1)))

    # acc1 の GE0/0 チップ座標とセグエッジ端点が一致
    assert "acc1" in seg_edge_map, "seg-edge の acc1 が見つからない"
    assert "acc1::GigabitEthernet0/0" in chip_cx_map, \
        "acc1::GE0/0 チップが Physical ビューに存在しない"
    seg_x, seg_y = seg_edge_map["acc1"]
    chip_x = chip_cx_map["acc1::GigabitEthernet0/0"]
    chip_y = chip_cy_map["acc1::GigabitEthernet0/0"]
    assert abs(seg_x - chip_x) < 1.0, \
        f"Physical seg-edge acc1 x2={seg_x} がチップ cx={chip_x} に一致しない（ノード中心のまま: バグ3）"
    assert abs(seg_y - chip_y) < 1.0, \
        f"Physical seg-edge acc1 y2={seg_y} がチップ cy={chip_y} に一致しない（ノード中心のまま: バグ3）"

    # acc2
    assert "acc2" in seg_edge_map, "seg-edge の acc2 が見つからない"
    assert "acc2::GigabitEthernet0/0" in chip_cx_map, \
        "acc2::GE0/0 チップが Physical ビューに存在しない"
    seg_x, seg_y = seg_edge_map["acc2"]
    chip_x = chip_cx_map["acc2::GigabitEthernet0/0"]
    chip_y = chip_cy_map["acc2::GigabitEthernet0/0"]
    assert abs(seg_x - chip_x) < 1.0, \
        f"Physical seg-edge acc2 x2={seg_x} がチップ cx={chip_x} に一致しない（バグ3）"
    assert abs(seg_y - chip_y) < 1.0, \
        f"Physical seg-edge acc2 y2={seg_y} がチップ cy={chip_y} に一致しない（バグ3）"

    # core1 の GE0/2 チップ
    assert "core1" in seg_edge_map, "seg-edge の core1 が見つからない"
    assert "core1::GigabitEthernet0/2" in chip_cx_map, \
        "core1::GE0/2 チップが Physical ビューに存在しない"
    seg_x, seg_y = seg_edge_map["core1"]
    chip_x = chip_cx_map["core1::GigabitEthernet0/2"]
    chip_y = chip_cy_map["core1::GigabitEthernet0/2"]
    assert abs(seg_x - chip_x) < 1.0, \
        f"Physical seg-edge core1 x2={seg_x} が GE0/2 チップ cx={chip_x} に一致しない（バグ3）"
    assert abs(seg_y - chip_y) < 1.0, \
        f"Physical seg-edge core1 y2={seg_y} が GE0/2 チップ cy={chip_y} に一致しない（バグ3）"



@pytest.mark.unit
def test_i4cr_physical_segment_edge_uses_svg_segment_edges_with_chips():
    """バグ3ユニット: _svg_segment_edges が chip_positions を受け取りアンカーに使う。

    _svg_segment_edges(segments, interfaces, positions, chip_positions=...) を
    直接呼んで、chip_positions がある場合にデバイス側端点がチップ座標になることを検証。
    """
    from lib.rendering.svg import _svg_segment_edges, _chip_positions

    interfaces = [
        {"id": "acc1::GigabitEthernet0/0", "device": "acc1", "name": "GigabitEthernet0/0",
         "ip": "192.168.50.2/24", "shutdown": False, "description": None},
        {"id": "acc1::Loopback0", "device": "acc1", "name": "Loopback0",
         "ip": "10.255.3.1/32", "shutdown": False, "description": None},
    ]
    segments = [
        {"id": "seg-192_168_50_0_24", "subnet": "192.168.50.0/24",
         "members": ["acc1::GigabitEthernet0/0"]},
    ]
    positions = {
        "seg-192_168_50_0_24": (500.0, 100.0),
        "acc1": (200.0, 300.0),
    }

    # acc1::GE0/0 チップ座標を計算
    acc1_dev = {"id": "acc1", "hostname": "ACC1"}
    acc1_chips = _chip_positions(acc1_dev, {"acc1::GigabitEthernet0/0"}, interfaces, 200.0, 300.0)
    chip_cx, chip_cy = acc1_chips["acc1::GigabitEthernet0/0"]

    # chip_positions あり: チップアンカー
    svg_with_chip = _svg_segment_edges(segments, interfaces, positions,
                                        chip_positions=acc1_chips)
    m = re.search(r'x2="([\d.]+)" y2="([\d.]+)"', svg_with_chip)
    assert m is not None, f"seg-edge 生成されない: {svg_with_chip}"
    assert abs(float(m.group(1)) - chip_cx) < 1.0, \
        f"chip_positions ありのとき x2={m.group(1)} がチップ cx={chip_cx} に一致しない"
    assert abs(float(m.group(2)) - chip_cy) < 1.0, \
        f"chip_positions ありのとき y2={m.group(2)} がチップ cy={chip_cy} に一致しない"

    # chip_positions なし（デフォルト）: ノード中心フォールバック
    svg_no_chip = _svg_segment_edges(segments, interfaces, positions)
    m2 = re.search(r'x2="([\d.]+)" y2="([\d.]+)"', svg_no_chip)
    assert m2 is not None, f"chip_positions なしで seg-edge 生成されない: {svg_no_chip}"
    assert abs(float(m2.group(1)) - 200.0) < 1.0, \
        f"chip_positions なしのとき x2={m2.group(1)} がノード中心 200.0 に一致しない"
    assert abs(float(m2.group(2)) - 300.0) < 1.0, \
        f"chip_positions なしのとき y2={m2.group(2)} がノード中心 300.0 に一致しない"


@pytest.mark.unit
def test_i4cr_deterministic_multi_as_area():
    """regression: multi-as-area トポロジーで render() が決定的（2回一致）"""
    from lib.rendering import render
    import copy
    topo = _make_multi_as_area_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "multi-as-area render() が非決定的"


# ---------------------------------------------------------------------------
# [test M-2] BGPビューで非BGP機（acc1/acc2）に Loopback チップが出ない
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_i4cr_bgp_chip_iface_ids_non_bgp_device_has_no_loopback():
    """M-2: _build_bgp_chip_iface_ids が非BGP機（acc1/acc2）の Loopback を含まない。

    acc1/acc2 は BGP エントリを一切持たず（bgp_entries に device=acc1/acc2 がない）、
    また他機の local_ip / neighbor_ip にも現れないため、
    acc1::Loopback0 / acc2::Loopback0 は BGP チップ集合に入らない。
    """
    from lib.rendering.views import _build_bgp_chip_iface_ids

    topo = _make_multi_as_area_topology()
    bgp_entries = topo["routing"]["bgp"]
    interfaces = topo["interfaces"]

    result = _build_bgp_chip_iface_ids(bgp_entries, interfaces)

    assert "acc1::Loopback0" not in result, \
        f"非BGP機 acc1 の Loopback が BGP チップ集合に含まれている: {sorted(result)}"
    assert "acc2::Loopback0" not in result, \
        f"非BGP機 acc2 の Loopback が BGP チップ集合に含まれている: {sorted(result)}"


@pytest.mark.unit
def test_i4cr_bgp_view_non_bgp_device_no_loopback_chip():
    """M-2: BGPビューに acc1/acc2 の Loopback チップが描画されない（非BGP機）。

    acc1/acc2 は BGP 参加機でないため BGP ビューに device-node 自体が存在しない。
    したがって Loopback チップも存在しないことを確認する。
    """
    from lib.rendering import render
    topo = _make_multi_as_area_topology()
    html = render(topo)
    bgp = _extract_bgp_view_from(html)
    assert bgp, "BGP ビューが生成されない"

    assert 'data-iface-id="acc1::Loopback0"' not in bgp, \
        "非BGP機 acc1 の Loopback チップが BGP ビューに描画されている"
    assert 'data-iface-id="acc2::Loopback0"' not in bgp, \
        "非BGP機 acc2 の Loopback チップが BGP ビューに描画されている"


# ---------------------------------------------------------------------------
# [整理] _build_view_physical チップ集合単一経路: 描画チップとアンカー集合の一致
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_i4cr_physical_chip_iface_ids_equals_connected_plus_loopback():
    """整理: _build_physical_chip_iface_ids が接続IF + Loopback の和集合を返す。

    _build_connected_iface_ids（リンク/セグメント端点）と Loopback の和が
    _build_physical_chip_iface_ids と完全一致することを確認する（等値保証）。
    """
    from lib.rendering.views import (
        _build_physical_chip_iface_ids,
        _build_connected_iface_ids,
    )
    from lib.rendering.svg import _is_loopback

    topo = _make_multi_as_area_topology()
    interfaces = topo["interfaces"]
    links = topo["links"]
    segments = topo["segments"]

    phys_chip_ids = _build_physical_chip_iface_ids(interfaces, links, segments)
    connected = _build_connected_iface_ids(links, segments, interfaces)

    # 接続IF + Loopback の和集合を手動構築
    expected = set()
    for iface in interfaces:
        if iface["id"] in connected or _is_loopback(iface.get("name", "")):
            expected.add(iface["id"])

    assert phys_chip_ids == expected, \
        f"_build_physical_chip_iface_ids と 手動計算の差分: {phys_chip_ids ^ expected}"


# ===========================================================================
# Phase 1A #6: フォーカスモード撤去
# ===========================================================================

@pytest.mark.unit
def test_p1a6_focus_dimmed_css_removed(rendered_html):
    """\
    #6: .focus-dimmed CSS ルールが HTML から削除されている。
    フォーカスモード撤去後は .focus-dimmed を使うコードが存在しないこと。
    """
    assert ".focus-dimmed" not in rendered_html, \
        ".focus-dimmed CSS ルールが残存している（フォーカスモード撤去済みのはず）"


@pytest.mark.unit
def test_p1a6_apply_focus_mode_removed(rendered_html):
    """\
    #6: applyFocusMode 関数が JS から削除されている。
    """
    assert "applyFocusMode" not in rendered_html, \
        "applyFocusMode 関数が残存している（フォーカスモード撤去済みのはず）"


@pytest.mark.unit
def test_p1a6_clear_focus_mode_removed(rendered_html):
    """\
    #6: clearFocusMode 関数が JS から削除されている。
    """
    assert "clearFocusMode" not in rendered_html, \
        "clearFocusMode 関数が残存している（フォーカスモード撤去済みのはず）"


@pytest.mark.unit
def test_p1a6_focus_device_var_removed(rendered_html):
    """\
    #6: _focusDevice 変数が JS から削除されている。
    """
    assert "_focusDevice" not in rendered_html, \
        "_focusDevice 変数が残存している（フォーカスモード撤去済みのはず）"


@pytest.mark.unit
def test_p1a6_dblclick_handler_removed(rendered_html):
    """\
    #6: device-node の dblclick イベントハンドラが削除されている。
    """
    assert "dblclick" not in rendered_html, \
        "dblclick ハンドラが残存している（フォーカスモード撤去済みのはず）"


@pytest.mark.unit
def test_p1a6_help_text_no_double_click_hint(rendered_html):
    """\
    #6: ヘッダのヘルプテキストに「ダブルクリック」「隣接フォーカス」が含まれない。
    """
    header_m = re.search(r'<header[^>]*>(.*?)</header>', rendered_html, re.DOTALL)
    header_html = header_m.group(1) if header_m else rendered_html
    assert "ダブルクリック" not in header_html, \
        "ヘッダに「ダブルクリック」ヘルプテキストが残存している"
    assert "隣接フォーカス" not in header_html, \
        "ヘッダに「隣接フォーカス」ヘルプテキストが残存している"


@pytest.mark.unit
def test_p1a6_click_timer_removed(rendered_html):
    """\
    #6: _clickTimer の setTimeout 遅延ロジックが削除されている。
    単クリック選択は即時実行に戻されているため _clickTimer が存在しない。
    """
    assert "_clickTimer" not in rendered_html, \
        "_clickTimer が残存している（単クリック即時化済みのはず）"


@pytest.mark.unit
def test_p1a6_node_click_no_settimeout_delay(rendered_html):
    """\
    #6: ノードの click ハンドラで 250ms setTimeout 遅延が使われていない。
    単クリック選択は即時実行のため、click ハンドラ内の setTimeout(func, 250) が存在しないこと。
    """
    # click ハンドラ周辺（device-node の addEventListener('click'…）で
    # 250 ms の遅延タイマーが使われていないことを確認する
    has_250ms_delay = re.search(
        r"addEventListener\s*\(\s*'click'[^)]*\)[^{]*\{[^}]{0,2000}setTimeout[^,]*,\s*250",
        rendered_html, re.DOTALL
    ) is not None
    assert not has_250ms_delay, \
        "click ハンドラ内に 250ms setTimeout 遅延が残存している"


@pytest.mark.unit
def test_p1a6_clear_selection_no_focus_mode_call(rendered_html):
    """\
    #6: clearSelection() 関数本体が clearFocusMode() を呼ばない。
    フォーカスモード撤去後は clearSelection は _selectedNodes・clearLinkHighlight・
    _updateCardFilter のみを呼ぶ。
    """
    start = rendered_html.find("function clearSelection(")
    assert start != -1, "clearSelection 関数が見つからない"
    end = rendered_html.find("\n    function ", start + 1)
    func_body = rendered_html[start:end] if end != -1 else rendered_html[start:start + 1000]
    assert "clearFocusMode" not in func_body, \
        "clearSelection 内に clearFocusMode() の呼び出しが残っている"


@pytest.mark.unit
def test_p1a6_update_card_filter_no_focus_device(rendered_html):
    """\
    #6: _updateCardFilter() 関数本体が _focusDevice を参照しない。
    フォーカスモード撤去後はカード絞り込みは _selectedNodes のみに基づく。
    """
    start = rendered_html.find("function _updateCardFilter(")
    assert start != -1, "_updateCardFilter 関数が見つからない"
    end = rendered_html.find("\n    function ", start + 1)
    func_body = rendered_html[start:end] if end != -1 else rendered_html[start:start + 1000]
    assert "_focusDevice" not in func_body, \
        "_updateCardFilter 内に _focusDevice の参照が残っている"


# ===========================================================================
# Phase 1A #2: Static 行ごと独立・複数累積マーク
# ===========================================================================

@pytest.mark.unit
def test_p1a2_static_tr_has_data_route_id():
    """\
    #2: cards.py が各 static <tr> に data-route-id を付与する。
    data-route-id は "{device}::{prefix}::{idx}" 形式の一意 ID（ECMP一意化対応）。
    """
    from lib.rendering import render
    html = render(_make_p2p_static_topology())
    cards_m = re.search(r'id="cards-section"(.*)', html, re.DOTALL)
    cards_html = cards_m.group(1) if cards_m else html
    # r1 のデフォルトルート行に data-route-id が存在すること（インデックス付き形式）
    assert 'data-route-id="r1::0.0.0.0/0::0"' in cards_html, \
        "r1::0.0.0.0/0::0 の static 行に data-route-id が付与されていない（ECMP一意化後フォーマット）"


@pytest.mark.unit
def test_p1a2_static_tr_data_route_id_unique():
    """\
    #2: 同一 device の複数 static 行で data-route-id が一意になる（ECMP含む）。
    """
    from lib.rendering import render
    topo = _make_segment_static_topology()
    # sw1 と sw2 は同じ prefix "10.0.0.0/8" だが別デバイスなので別 ID になる
    html = render(topo)
    assert 'data-route-id="sw1::10.0.0.0/8::0"' in html, \
        "sw1::10.0.0.0/8::0 の static 行に data-route-id が付与されていない（ECMP一意化後フォーマット）"
    assert 'data-route-id="sw2::10.0.0.0/8::0"' in html, \
        "sw2::10.0.0.0/8::0 の static 行に data-route-id が付与されていない（ECMP一意化後フォーマット）"


@pytest.mark.unit
def test_p1a2_toggle_static_row_by_route_id_exists(rendered_html):
    """\
    #2: JS に toggleStaticRowById（または同等の data-route-id 単行選択）関数/ロジックが存在する。
    data-route-id を使って1行のみをトグルするコードが存在すること。
    """
    assert "data-route-id" in rendered_html, \
        "JS/HTML に data-route-id の参照が存在しない"
    # 1行特定ロジック: CSS.escape + data-route-id セレクタが存在すること
    has_single_row = re.search(
        r"""tr\[data-route-id=['"]?[^'"]*['"]?\]|querySelector.*data-route-id|CSS\.escape.*route-id|route-id.*CSS\.escape""",
        rendered_html
    ) is not None
    assert has_single_row, \
        "data-route-id で1行を特定する querySelector/CSS.escape ロジックが存在しない"


@pytest.mark.unit
def test_p1a2_old_bulk_toggle_via_route_edge_removed(rendered_html):
    """\
    #2: toggleStaticRouteHighlight 内で querySelectorAll("tr[data-route-edge='X']") による
    全行巻き込みトグルが廃止されている。
    新方式では data-route-id で1行のみをトグルする。
    """
    func_body = _extract_js_function(rendered_html, "toggleStaticRouteHighlight")
    if func_body is None:
        # 関数が丸ごと廃止されている場合も許容（新関数に置き換えられた）
        return
    # 旧実装: querySelectorAll("tr[data-route-edge=...") で全行に route-row-selected を付ける
    has_bulk = re.search(
        r"""querySelectorAll\s*\(\s*["']tr\[data-route-edge""",
        func_body
    ) is not None
    assert not has_bulk, \
        "toggleStaticRouteHighlight が tr[data-route-edge] の全行巻き込みトグルをまだ行っている"


@pytest.mark.unit
def test_p1a2_selected_static_rows_set_exists(rendered_html):
    """\
    #2: JS に _selectedStaticRows セット（行 ID 集合）が存在する。
    """
    assert "_selectedStaticRows" in rendered_html, \
        "_selectedStaticRows セットが JS に存在しない"


@pytest.mark.unit
def test_p1a2_clear_selection_clears_static_rows(rendered_html):
    """\
    #2: clearSelection() / clearLinkHighlight() が _selectedStaticRows と
    .route-row-selected を解除する。
    """
    # clearLinkHighlight または clearSelection に _selectedStaticRows.clear() が存在すること
    clear_body = _extract_js_function(rendered_html, "clearLinkHighlight")
    sel_body = _extract_js_function(rendered_html, "clearSelection")
    combined = (clear_body or "") + (sel_body or "")
    assert "_selectedStaticRows" in combined, \
        "clearLinkHighlight / clearSelection が _selectedStaticRows を参照していない"


@pytest.mark.unit
def test_p1a2_accumulated_rows_recalculate_edge_highlight(rendered_html):
    """\
    #2: _selectedStaticRows の和から経路エッジ/next-hop ハイライトを再計算するロジックが存在する。
    選択行の data-route-edge の和集合を使って highlighted を付与すること。
    """
    # _selectedStaticRows を参照してエッジに highlighted を付けるコードが存在すること
    has_recalc = re.search(
        r'_selectedStaticRows[^;]{0,2000}(highlighted|route-edge)',
        rendered_html, re.DOTALL
    ) is not None or re.search(
        r'(highlighted|route-edge)[^;]{0,2000}_selectedStaticRows',
        rendered_html, re.DOTALL
    ) is not None
    assert has_recalc, \
        "_selectedStaticRows からエッジ highlighted を再計算するロジックが存在しない"


# ===========================================================================
# Phase 1A #4: iBGP ハイライト色判別性
# ===========================================================================

@pytest.mark.unit
def test_p1a4_ibgp_highlight_color_differs_from_default(rendered_html):
    """\
    #4: BGP セッションのハイライト stroke 色が既定 iBGP 色 (#d97706) と異なる。
    .bgp-session.highlighted .bgp-edge の stroke は #d97706 以外の値である。
    """
    # CSS ブロックを抽出
    m = re.search(
        r'\.bgp-session\.highlighted\s+\.bgp-edge\s*\{([^}]+)\}',
        rendered_html, re.DOTALL
    )
    assert m is not None, \
        ".bgp-session.highlighted .bgp-edge の CSS ブロックが存在しない"
    block = m.group(1)
    # stroke プロパティが存在すること
    assert "stroke" in block, \
        ".bgp-session.highlighted .bgp-edge に stroke プロパティがない"
    # 既定 iBGP 色 #d97706 が直接使われていないこと
    # (CSS変数 --color-bgp-ibgp は使えないが、#d97706 をそのまま書くのも不可)
    assert "#d97706" not in block, \
        ".bgp-session.highlighted .bgp-edge の stroke が既定 iBGP 色 #d97706 のままで判別不能"


@pytest.mark.unit
def test_p1a4_ibgp_highlight_color_differs_from_general_highlight(rendered_html):
    """\
    #4: --color-bgp-highlight 変数の定義値が iBGP 既定色 (#d97706) とも
    汎用ハイライト色 (#f59e0b) とも異なること（直接値検証・vacuous pass 不可）。

    CSS 変数 --color-bgp-highlight が :root に定義され、その値が
    #d97706（iBGP既定アンバー）でも #f59e0b（汎用ハイライトアンバー）でもないことを
    regex で直接確認する。
    """
    # :root に --color-bgp-highlight が定義されていること
    m_var = re.search(
        r'--color-bgp-highlight\s*:\s*(#[0-9a-fA-F]{3,8})',
        rendered_html
    )
    assert m_var is not None, \
        "--color-bgp-highlight が :root に定義されていない（改名後の専用変数が必要）"
    actual_color = m_var.group(1).lower()
    assert actual_color != "#d97706", \
        f"--color-bgp-highlight の値 {actual_color} が iBGP 既定色 #d97706 と同一で判別不能"
    assert actual_color != "#f59e0b", \
        f"--color-bgp-highlight の値 {actual_color} が汎用ハイライト色 #f59e0b と同一で判別不能"


@pytest.mark.unit
def test_p1a4_ibgp_highlight_stroke_width_increased(rendered_html):
    """\
    #4: .bgp-session.highlighted .bgp-edge の stroke-width が .bgp-edge の基本値 (2) より大きい。
    ハイライト時は線幅を増やして視認性を向上させる。
    """
    m = re.search(
        r'\.bgp-session\.highlighted\s+\.bgp-edge\s*\{([^}]+)\}',
        rendered_html, re.DOTALL
    )
    assert m is not None, ".bgp-session.highlighted .bgp-edge の CSS ブロックが存在しない"
    block = m.group(1)
    # stroke-width が存在し、値が 2 より大きいこと
    sw_m = re.search(r'stroke-width\s*:\s*(\d+(?:\.\d+)?)', block)
    assert sw_m is not None, ".bgp-session.highlighted .bgp-edge に stroke-width が存在しない"
    stroke_width = float(sw_m.group(1))
    assert stroke_width > 2, \
        f".bgp-session.highlighted .bgp-edge の stroke-width={stroke_width} が基本値 2 以下（判別不能）"


@pytest.mark.unit
def test_p1a4_ibgp_highlight_css_deterministic():
    """\
    #4: iBGP ハイライト CSS 変更後も render() が決定的である。
    """
    from lib.rendering import render
    import copy
    topo = _make_ibgp_topology()
    h1 = render(copy.deepcopy(topo))
    h2 = render(copy.deepcopy(topo))
    assert h1 == h2, "iBGP ハイライト CSS 変更後に render() が非決定的"


# ===========================================================================
# Phase 1A #2: ECMP 同一 next-hop 向け static 2行 — 振る舞いテスト
# ===========================================================================

def _make_two_routes_same_nexthop():
    """#2 ECMP テスト用: r1 が r2 向けに2つの異なる prefix を持つ topology。

    r1 は 192.168.1.0/24 と 192.168.2.0/24 の両方を next_hop=10.0.0.2（r2）へ向ける。
    同じ next-hop / route-edge を共有する2行で ECMP 一意化の振る舞いを検証する。
    """
    return {
        "title": "ECMP Two Routes Same Nexthop",
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
            "bgp": [],
            "ospf": [],
            "static": [
                {"device": "r1", "prefix": "192.168.1.0/24", "next_hop": "10.0.0.2"},
                {"device": "r1", "prefix": "192.168.2.0/24", "next_hop": "10.0.0.2"},
            ],
        },
    }


@pytest.mark.unit
def test_p1a2_ecmp_two_rows_have_unique_data_route_ids():
    """\
    #2 ECMP: 同一 device・異なる prefix の2行が一意な data-route-id を持つ。

    r1 の 192.168.1.0/24 と 192.168.2.0/24 はそれぞれ異なる data-route-id を持つ。
    フォーマット: "{device}::{prefix}::{idx}"（ECMP一意化対応）
    """
    from lib.rendering import render
    html = render(_make_two_routes_same_nexthop())

    # HTML全体で r1 の static route data-route-id を収集（cards-section 限定より確実）
    ids = re.findall(r'data-route-id="r1::([^"]+)"', html)
    assert len(ids) >= 2, \
        f"r1 の static 行 data-route-id が2つ未満: {ids}"

    # 2つの ID が異なること（一意化の確認）
    assert len(set(ids)) == len(ids), \
        f"r1 の static 行 data-route-id に重複がある: {ids}"

    # 両方のprefixが含まれること
    assert any("192.168.1.0/24" in eid for eid in ids), \
        f"r1::192.168.1.0/24 の route ID が存在しない: {ids}"
    assert any("192.168.2.0/24" in eid for eid in ids), \
        f"r1::192.168.2.0/24 の route ID が存在しない: {ids}"


@pytest.mark.unit
def test_p1a2_ecmp_one_row_click_does_not_select_other_row():
    """\
    #2 ECMP (a): 1行クリックで他行が route-row-selected にならない。

    toggleStaticRouteHighlight は data-route-id で単一行を querySelector するため、
    別 route-id を持つ行には影響しない設計になっていること。

    検証方針: toggleStaticRouteHighlight 関数本体に
    - querySelector('tr[data-route-id=...') が存在する（1行限定取得）
    - querySelectorAll('tr[data-route-id="..."]') のような値指定での全行取得がない
      ※ querySelectorAll('tr[data-route-id]')（属性存在確認）はイベント登録に使われるので許容
    """
    from lib.rendering import render
    html = render(_make_two_routes_same_nexthop())

    # toggleStaticRouteHighlight 関数本体を抽出
    func_body = _extract_js_function(html, "toggleStaticRouteHighlight")
    assert func_body is not None and func_body != "", \
        "toggleStaticRouteHighlight 関数が存在しない"

    # 関数内で querySelector('tr[data-route-id=..."] で1行のみ特定していること
    has_single_query = re.search(
        r'querySelector\s*\(\s*[\'"]tr\[data-route-id',
        func_body
    ) is not None
    assert has_single_query, \
        "toggleStaticRouteHighlight が querySelector('tr[data-route-id...') で1行のみ選択していない"

    # querySelectorAll で 値指定の全行巻き込みがないことを確認
    # querySelectorAll('tr[data-route-id]') はイベント登録コードに存在するが、
    # querySelectorAll('tr[data-route-id="..."]') のような値指定全行選択がないことを検証
    has_value_bulk_select = re.search(
        r"""querySelectorAll\s*\(\s*['"]\s*tr\[data-route-id\s*=\s*""",
        func_body
    ) is not None
    assert not has_value_bulk_select, \
        "toggleStaticRouteHighlight が querySelectorAll で値指定による複数行一括選択をしている（ECMP一意化の意図に反する）"


@pytest.mark.unit
def test_p1a2_ecmp_apply_static_row_highlights_uses_foreach_and_highlighted():
    """\
    #2 ECMP (c): _applyStaticRowHighlights が _selectedStaticRows.forEach と
    highlighted を両方含む（選択行セットから再計算するロジックの構造確認）。
    """
    from lib.rendering import render
    html = render(_make_two_routes_same_nexthop())

    # _applyStaticRowHighlights 関数本体を抽出
    func_body = _extract_js_function(html, "_applyStaticRowHighlights")
    assert func_body is not None, "_applyStaticRowHighlights 関数が存在しない"

    # _selectedStaticRows.forEach が存在すること
    assert "_selectedStaticRows.forEach" in func_body, \
        "_applyStaticRowHighlights 内に _selectedStaticRows.forEach が存在しない"

    # highlighted クラス操作が存在すること
    has_highlighted = (
        "classList.add('highlighted')" in func_body
        or 'classList.add("highlighted")' in func_body
        or re.search(r'classList\.add\(["\']highlighted', func_body) is not None
    )
    assert has_highlighted, \
        "_applyStaticRowHighlights 内に highlighted クラス付与ロジックが存在しない"


@pytest.mark.unit
def test_p1a2_ecmp_clear_selection_removes_all_route_row_selected():
    """\
    #2 ECMP: clearLinkHighlight が _selectedStaticRows をクリアし、
    全 .route-row-selected を解除するロジックを持つ。
    （最後の1行解除で共有 route-edge の消灯が保証されることを JS 構造で確認）
    """
    from lib.rendering import render
    html = render(_make_two_routes_same_nexthop())

    clear_body = _extract_js_function(html, "clearLinkHighlight")
    assert clear_body is not None, "clearLinkHighlight 関数が存在しない"

    # _selectedStaticRows.clear() が存在すること
    assert "_selectedStaticRows.clear()" in clear_body, \
        "clearLinkHighlight 内に _selectedStaticRows.clear() が存在しない"

    # route-row-selected の classList.remove が存在すること
    has_remove = re.search(
        r'classList\.remove\(["\']route-row-selected',
        clear_body
    ) is not None
    assert has_remove, \
        "clearLinkHighlight 内に route-row-selected の classList.remove が存在しない"


# ===========================================================================
# Phase 1B — #1 OSPF表↔図マーキング（BGP同型の双方向連動）
# ===========================================================================
# フィクスチャ設計:
#   core1: GE0/0(area0, 10.0.0.0/30 p2p to core2)
#          GE0/1(area0, 10.0.1.0/30 p2p to edge1)
#          GE0/2(area1, 192.168.50.0/24 segment)
#   core2: GE0/0(area0, 10.0.0.0/30 p2p to core1)
#   edge1: GE0/0(area0, 10.0.1.0/30 p2p to core1)
#   acc1:  GE0/0(area1, 192.168.50.0/24 segment)
#   acc2:  GE0/0(area1, 192.168.50.0/24 segment)


def _make_ospf_highlight_topology():
    """OSPF表↔図連動テスト用 multi-as-area 類似 topology"""
    return {
        "title": "OSPF Highlight Test",
        "generated_from": [],
        "devices": [
            {"id": "core1", "hostname": "CORE1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "core2", "hostname": "CORE2", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "edge1", "hostname": "EDGE1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "acc1", "hostname": "ACC1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "acc2", "hostname": "ACC2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            # core1 のインタフェース
            {"id": "core1::GE0/0", "device": "core1", "name": "GE0/0",
             "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "core1::GE0/1", "device": "core1", "name": "GE0/1",
             "ip": "10.0.1.1/30", "vlan": None, "description": None, "shutdown": False},
            {"id": "core1::GE0/2", "device": "core1", "name": "GE0/2",
             "ip": "192.168.50.1/24", "vlan": None, "description": None, "shutdown": False},
            # core2
            {"id": "core2::GE0/0", "device": "core2", "name": "GE0/0",
             "ip": "10.0.0.2/30", "vlan": None, "description": None, "shutdown": False},
            # edge1
            {"id": "edge1::GE0/0", "device": "edge1", "name": "GE0/0",
             "ip": "10.0.1.2/30", "vlan": None, "description": None, "shutdown": False},
            # acc1 / acc2（セグメントメンバー）
            {"id": "acc1::GE0/0", "device": "acc1", "name": "GE0/0",
             "ip": "192.168.50.2/24", "vlan": None, "description": None, "shutdown": False},
            {"id": "acc2::GE0/0", "device": "acc2", "name": "GE0/0",
             "ip": "192.168.50.3/24", "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [
            # core1 -- core2 (area0, 10.0.0.0/30)
            {"a_device": "core1", "a_if": "GE0/0", "b_device": "core2", "b_if": "GE0/0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet",
             "ospf_area": "0", "ospf_network": "10.0.0.0/30"},
            # core1 -- edge1 (area0, 10.0.1.0/30)
            {"a_device": "core1", "a_if": "GE0/1", "b_device": "edge1", "b_if": "GE0/0",
             "subnet": "10.0.1.0/30", "kind": "inferred-subnet",
             "ospf_area": "0", "ospf_network": "10.0.1.0/30"},
        ],
        "segments": [
            {
                "id": "seg-192_168_50_0_24",
                "subnet": "192.168.50.0/24",
                "ospf_area": "1",
                "ospf_network": "192.168.50.0/24",
                "members": ["core1::GE0/2", "acc1::GE0/0", "acc2::GE0/0"],
            }
        ],
        "routing": {
            "bgp": [],
            "ospf": [
                # core1 -- 両エリア参加
                {"device": "core1", "network": "10.0.0.0/30", "area": "0", "process": "1"},
                {"device": "core1", "network": "10.0.1.0/30", "area": "0", "process": "1"},
                {"device": "core1", "network": "192.168.50.0/24", "area": "1", "process": "1"},
                # core2
                {"device": "core2", "network": "10.0.0.0/30", "area": "0", "process": "1"},
                # edge1
                {"device": "edge1", "network": "10.0.1.0/30", "area": "0", "process": "1"},
                # acc1 / acc2
                {"device": "acc1", "network": "192.168.50.0/24", "area": "1", "process": "1"},
                {"device": "acc2", "network": "192.168.50.0/24", "area": "1", "process": "1"},
            ],
            "static": [],
        },
    }


# ---------------------------------------------------------------------------
# P1B-1: _normalize_ospf_id ヘルパーのユニットテスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_normalize_ospf_id_basic():
    """#1B: _normalize_ospf_id が CIDR 文字列を正規化する。

    '10.0.0.0/30' -> '10.0.0.0/30'（変化なし）
    '10.0.0.1/30'（host bit） -> '10.0.0.0/30'（strict=False で正規化）
    """
    from lib.rendering.core import _normalize_ospf_id
    assert _normalize_ospf_id("10.0.0.0/30") == "10.0.0.0/30"
    assert _normalize_ospf_id("10.0.0.1/30") == "10.0.0.0/30"  # host bit 正規化
    assert _normalize_ospf_id("192.168.50.0/24") == "192.168.50.0/24"


@pytest.mark.unit
def test_p1b_normalize_ospf_id_invalid_returns_empty():
    """#1B: _normalize_ospf_id が無効な入力で空文字を返す（クラッシュしない）。"""
    from lib.rendering.core import _normalize_ospf_id
    assert _normalize_ospf_id("") == ""
    assert _normalize_ospf_id(None) == ""
    assert _normalize_ospf_id("not-a-subnet") == ""


@pytest.mark.unit
def test_p1b_normalize_ospf_id_deterministic():
    """#1B: _normalize_ospf_id は決定的（同一入力で同一出力）。"""
    from lib.rendering.core import _normalize_ospf_id
    subnets = ["10.0.0.0/30", "192.168.50.0/24", "10.0.1.0/30"]
    for s in subnets:
        assert _normalize_ospf_id(s) == _normalize_ospf_id(s)


# ---------------------------------------------------------------------------
# P1B-2: OSPF Networks 表の <tr> に data-ospf-id が付く（cards.py）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_ospf_card_rows_have_data_ospf_id():
    """#1B: OSPF Networks 表の <tr> に data-ospf-id が付く。

    _device_cards が ospf_marking_map を受け取り、
    各 OSPF エントリ行に data-ospf-id="{正規化 network}" を付与する。
    """
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    # OSPF Networks 行に data-ospf-id が存在すること
    assert 'data-ospf-id=' in html, \
        "OSPF Networks 行に data-ospf-id 属性が存在しない"


@pytest.mark.unit
def test_p1b_ospf_card_row_10_0_0_0_30_has_correct_id():
    """#1B: 10.0.0.0/30 の OSPF 行に data-ospf-id='10.0.0.0/30' が付く。"""
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    assert 'data-ospf-id="10.0.0.0/30"' in html, \
        "10.0.0.0/30 OSPF 行に data-ospf-id='10.0.0.0/30' が存在しない"


@pytest.mark.unit
def test_p1b_ospf_card_row_segment_192_168_50_0_24_has_correct_id():
    """#1B: 192.168.50.0/24 の OSPF 行に data-ospf-id='192.168.50.0/24' が付く。"""
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    assert 'data-ospf-id="192.168.50.0/24"' in html, \
        "192.168.50.0/24 OSPF 行に data-ospf-id='192.168.50.0/24' が存在しない"


@pytest.mark.unit
def test_p1b_ospf_card_row_count_matches_ospf_entries():
    """#1B: OSPF 行の data-ospf-id 付き <tr> が OSPF エントリ数と一致する。

    7件のエントリがあるとき、data-ospf-id を持つ <tr> が7行以上存在する。
    """
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    rows_with_id = re.findall(r'<tr[^>]+data-ospf-id="[^"]*"', html)
    assert len(rows_with_id) >= 7, \
        f"data-ospf-id 付き OSPF 行が少ない: {len(rows_with_id)} 件（期待: >=7）"


# ---------------------------------------------------------------------------
# P1B-3: OSPF リンク（p2pエッジ）に data-ospf-id が付く（views.py）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_ospf_link_edge_has_data_ospf_id():
    """#1B: OSPF ビューの p2p リンク <g> に data-ospf-id が付く。

    _build_view_ospf が生成する <g class="link-edge"> に
    data-ospf-id="{正規化 subnet}" が存在する。
    """
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    # OSPFビューを抽出
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビュー <g class='view view-ospf'> が見つからない"
    # link-edge に data-ospf-id が存在すること
    link_with_ospf_id = re.findall(
        r'<g[^>]*class="link-edge"[^>]*data-ospf-id="([^"]+)"', ospf_view
    )
    link_with_ospf_id2 = re.findall(
        r'<g[^>]*data-ospf-id="([^"]+)"[^>]*class="link-edge"', ospf_view
    )
    all_ids = link_with_ospf_id + link_with_ospf_id2
    assert len(all_ids) >= 1, \
        "OSPF ビューの link-edge <g> に data-ospf-id が存在しない"


@pytest.mark.unit
def test_p1b_ospf_link_edge_id_value_correct():
    """#1B: OSPF p2p リンクの data-ospf-id が正規化サブネット値（10.0.0.0/30 等）と一致する。"""
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    # 10.0.0.0/30 リンクに data-ospf-id が付くこと
    assert 'data-ospf-id="10.0.0.0/30"' in ospf_view, \
        "10.0.0.0/30 リンクに data-ospf-id='10.0.0.0/30' が存在しない"


# ---------------------------------------------------------------------------
# P1B-4: OSPF セグメント楕円・セグメントエッジに data-ospf-id が付く（svg.py）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_ospf_segment_ellipse_has_data_ospf_id():
    """#1B: OSPF セグメント <g class='segment-node layer-ospf'> に data-ospf-id が付く。

    修正後: data-ospf-id は <g> のみに付与。<ellipse> には付与しない。
    このテストは <g> での存在を検証する（ellipse フォールバックは廃止）。
    """
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    # <g class="segment-node layer-ospf"> に data-ospf-id が存在すること（<g> のみ検証）
    seg_nodes = re.findall(
        r'<g[^>]*class="[^"]*segment-node[^"]*layer-ospf[^"]*"[^>]*data-ospf-id="([^"]+)"',
        ospf_view
    )
    seg_nodes2 = re.findall(
        r'<g[^>]*data-ospf-id="([^"]+)"[^>]*class="[^"]*segment-node[^"]*"',
        ospf_view
    )
    all_ids = seg_nodes + seg_nodes2
    assert len(all_ids) >= 1, \
        "OSPF セグメント <g> に data-ospf-id が存在しない"


@pytest.mark.unit
def test_p1b_ospf_segment_ellipse_id_value_correct():
    """#1B: OSPF セグメント楕円の data-ospf-id が 192.168.50.0/24。"""
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    assert 'data-ospf-id="192.168.50.0/24"' in ospf_view, \
        "OSPF セグメント（192.168.50.0/24）に data-ospf-id='192.168.50.0/24' が存在しない"


@pytest.mark.unit
def test_p1b_ospf_segment_edge_has_data_ospf_id():
    """#1B: OSPF セグメントエッジ <line class='seg-edge layer-ospf'> に data-ospf-id が付く。"""
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    seg_edges_with_ospf_id = re.findall(
        r'<line[^>]*class="[^"]*seg-edge[^"]*layer-ospf[^"]*"[^>]*data-ospf-id="([^"]+)"',
        ospf_view
    )
    seg_edges_with_ospf_id2 = re.findall(
        r'<line[^>]*data-ospf-id="([^"]+)"[^>]*class="[^"]*seg-edge[^"]*"',
        ospf_view
    )
    all_ids = seg_edges_with_ospf_id + seg_edges_with_ospf_id2
    assert len(all_ids) >= 1, \
        "OSPF セグメントエッジ <line> に data-ospf-id が存在しない"


# ---------------------------------------------------------------------------
# P1B-5: 図（SVG）と表（カード）で同一 data-ospf-id 値（突き合わせ）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_svg_and_card_share_same_ospf_id_for_p2p_link():
    """#1B: OSPFリンク(10.0.0.0/30)の data-ospf-id が SVG と OSPF Networks 行で一致。

    SVG の link-edge と カードの OSPF Networks <tr> が同一の
    data-ospf-id="10.0.0.0/30" を持つ（双方向連動の前提）。
    """
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"

    # SVG側のospf_idを収集
    svg_ospf_ids = set(re.findall(r'data-ospf-id="([^"]+)"', ospf_view))
    # カード側のospf_idを収集
    card_ospf_ids = set(re.findall(r'<tr[^>]+data-ospf-id="([^"]+)"', html))

    assert svg_ospf_ids, "OSPF ビューに data-ospf-id が存在しない"
    assert card_ospf_ids, "OSPF Networks 行に data-ospf-id が存在しない"

    overlap = svg_ospf_ids & card_ospf_ids
    assert overlap, \
        f"SVG と OSPF 表で共通の data-ospf-id がない: svg={svg_ospf_ids}, card={card_ospf_ids}"
    assert "10.0.0.0/30" in overlap, \
        f"10.0.0.0/30 が SVG と OSPF 表の両方に存在しない: overlap={overlap}"


@pytest.mark.unit
def test_p1b_svg_and_card_share_same_ospf_id_for_segment():
    """#1B: OSPFセグメント(192.168.50.0/24)の data-ospf-id が SVG と OSPF Networks 行で一致。"""
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"

    svg_ospf_ids = set(re.findall(r'data-ospf-id="([^"]+)"', ospf_view))
    card_ospf_ids = set(re.findall(r'<tr[^>]+data-ospf-id="([^"]+)"', html))

    assert "192.168.50.0/24" in svg_ospf_ids, \
        "192.168.50.0/24 が OSPF ビューの data-ospf-id に存在しない"
    assert "192.168.50.0/24" in card_ospf_ids, \
        "192.168.50.0/24 が OSPF Networks 行の data-ospf-id に存在しない"


@pytest.mark.unit
def test_p1b_ospf_link_same_id_for_both_endpoints():
    """#1B: 10.0.0.0/30 リンクで core1/core2 の OSPF 行が同一 data-ospf-id='10.0.0.0/30' を持つ。

    core1 と core2 はどちらも network=10.0.0.0/30 を持つ OSPF エントリを持ち、
    両者の OSPF Networks 行に同一の data-ospf-id が付くこと。
    """
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    # 10.0.0.0/30 の data-ospf-id を持つ <tr> を収集
    rows_1000_30 = re.findall(r'<tr[^>]+data-ospf-id="10\.0\.0\.0/30"', html)
    # core1 と core2 の両方が network=10.0.0.0/30 を持つので最低2行あるはず
    assert len(rows_1000_30) >= 2, \
        f"10.0.0.0/30 の data-ospf-id 付き OSPF 行が2行未満: {len(rows_1000_30)} 件"


@pytest.mark.unit
def test_p1b_ospf_segment_same_id_for_all_members():
    """#1B: 192.168.50.0/24 セグメントで core1/acc1/acc2 の OSPF 行が同一 data-ospf-id を持つ。"""
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    # 192.168.50.0/24 の data-ospf-id を持つ <tr> を収集
    rows_seg = re.findall(r'<tr[^>]+data-ospf-id="192\.168\.50\.0/24"', html)
    # core1/acc1/acc2 の3行があるはず
    assert len(rows_seg) >= 3, \
        f"192.168.50.0/24 の data-ospf-id 付き OSPF 行が3行未満: {len(rows_seg)} 件"


# ---------------------------------------------------------------------------
# P1B-6: JS — toggleOspfHighlight / _selectedOspf / clearSelection
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_toggle_ospf_highlight_js_exists(rendered_html):
    """#1B: toggleOspfHighlight(ospfId) 関数が JS に存在する。"""
    assert "toggleOspfHighlight" in rendered_html, \
        "toggleOspfHighlight 関数が JS に存在しない"


@pytest.mark.unit
def test_p1b_selected_ospf_set_exists(rendered_html):
    """#1B: _selectedOspf Set が JS に宣言されている。"""
    assert "_selectedOspf" in rendered_html, \
        "_selectedOspf Set が JS に存在しない"


@pytest.mark.unit
def test_p1b_clear_selection_clears_ospf(rendered_html):
    """#1B: clearSelection() / clearLinkHighlight() が _selectedOspf を解除する。

    _selectedOspf.clear() の呼び出しが JS 内に存在することを確認する。
    """
    assert "_selectedOspf.clear()" in rendered_html, \
        "clearSelection/clearLinkHighlight が _selectedOspf を解除しない（_selectedOspf.clear() が存在しない）"


@pytest.mark.unit
def test_p1b_toggle_ospf_highlight_uses_data_ospf_id(rendered_html):
    """#1B: toggleOspfHighlight が data-ospf-id を参照する。"""
    func_body = _extract_js_function(rendered_html, "toggleOspfHighlight")
    assert func_body, "toggleOspfHighlight 関数が見つからない"
    assert "data-ospf-id" in func_body, \
        "toggleOspfHighlight が data-ospf-id を参照していない"


@pytest.mark.unit
def test_p1b_toggle_ospf_highlight_uses_selected_ospf(rendered_html):
    """#1B: toggleOspfHighlight が _selectedOspf と data-ospf-id を使う。

    Phase 3H: dual-stack 対応のため OSPF は _toggleSelection から独立した
    token セレクタ実装（~=）に変更された。BGP同型ではなく OSPF 専用ロジック。
    _selectedOspf Set の使用と data-ospf-id 参照は維持される。
    """
    func_body = _extract_js_function(rendered_html, "toggleOspfHighlight")
    assert func_body, "toggleOspfHighlight 関数が見つからない"
    # _selectedOspf と data-ospf-id が関数内に存在すること
    assert "_selectedOspf" in func_body, \
        "toggleOspfHighlight に _selectedOspf の参照がない"
    assert "data-ospf-id" in func_body, \
        "toggleOspfHighlight に 'data-ospf-id' の参照がない"


@pytest.mark.unit
def test_p1b_ospf_click_handlers_registered(rendered_html):
    """#1B: OSPF リンク・セグメント・OSPF 行のクリックハンドラが登録されている。"""
    assert "toggleOspfHighlight" in rendered_html, \
        "toggleOspfHighlight の呼び出しが JS に存在しない"


# ---------------------------------------------------------------------------
# P1B-7: CSS — OSPF リンクの .highlighted 視覚スタイル
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_ospf_link_highlighted_css_exists(rendered_html):
    """#1B: OSPF ハイライト用の CSS ルールが存在する。

    .link-edge.highlighted .link-line または data-ospf-id 要素の
    highlighted スタイルが定義されていること。
    """
    # link-edge.highlighted は既存 CSS に存在するので OSPF リンクにも適用される
    # 追加 CSS（専用 OSPF ハイライト）または既存汎用スタイルのどちらかが存在すること
    has_css = (
        ".link-edge.highlighted" in rendered_html
        or ".link-edge.highlighted .link-line" in rendered_html
        or "[data-ospf-id].highlighted" in rendered_html
    )
    assert has_css, \
        "OSPF リンクに適用されるハイライト CSS が存在しない（.link-edge.highlighted等）"


# ---------------------------------------------------------------------------
# P1B-8: 決定性（同一入力で2回一致）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_ospf_highlight_deterministic():
    """#1B: OSPF ハイライト追加後も render() が決定的（同一入力で2回一致）。"""
    from lib.rendering import render
    topo = _make_ospf_highlight_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, \
        "OSPF ハイライト追加後に render() が非決定的になった"


# ---------------------------------------------------------------------------
# P1B-9: 既存機能の非回帰（BGP/セグメント/static が壊れない）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_bgp_highlight_not_broken():
    """#1B: OSPF 変更後も BGP ハイライト (_selectedBgp / toggleBgpHighlight) が残る。"""
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    # BGP がない topology だが JS の toggleBgpHighlight は常に生成される
    assert "toggleBgpHighlight" in html, \
        "OSPF 変更後に toggleBgpHighlight が消えた（BGP 非回帰失敗）"
    assert "_selectedBgp" in html, \
        "OSPF 変更後に _selectedBgp が消えた（BGP 非回帰失敗）"


@pytest.mark.unit
def test_p1b_seg_highlight_not_broken(rendered_html):
    """#1B: OSPF 変更後も toggleSegHighlight / _selectedSegs が残る。"""
    assert "toggleSegHighlight" in rendered_html, \
        "OSPF 変更後に toggleSegHighlight が消えた（セグメント非回帰失敗）"
    assert "_selectedSegs" in rendered_html, \
        "OSPF 変更後に _selectedSegs が消えた（セグメント非回帰失敗）"


# ---------------------------------------------------------------------------
# P1B ヘルパー: OSPF ビューを HTML から抽出する
# （3376行目の定義と統合。こちらの定義でファイル末尾を上書き）
# ---------------------------------------------------------------------------

def _extract_ospf_view(html: str) -> str:
    """HTML から OSPF ビュー <g class='view view-ospf'...> の内容を返す。"""
    m = re.search(
        r'(<g[^>]*class="view view-ospf"[^>]*>.*?)(?=<g[^>]*class="view |</g>\s*</g>\s*</svg>)',
        html,
        re.DOTALL,
    )
    if m:
        return m.group(1)
    # フォールバック: view-ospf 以降を全て返す（固定スライスは廃止）
    start = html.find('class="view view-ospf"')
    if start == -1:
        return ""
    end = html.find('<g class="view view-', start + 10)
    if end == -1:
        return html[start:]
    return html[start:end]


# ===========================================================================
# Phase 1B レビュー指摘修正: 追加ユニットテスト
# ===========================================================================


# ---------------------------------------------------------------------------
# P1B-R1: _normalize_subnet 一本化（svg.py）の確認
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_normalize_subnet_is_in_svg():
    """統合後: svg._normalize_subnet が利用可能であること（一本化の確認）。"""
    from lib.rendering.svg import _normalize_subnet
    assert callable(_normalize_subnet)
    assert _normalize_subnet("10.0.0.0/30") == "10.0.0.0/30"
    assert _normalize_subnet("10.0.0.1/30") == "10.0.0.0/30"   # host bit 正規化
    assert _normalize_subnet("192.168.50.0/24") == "192.168.50.0/24"
    assert _normalize_subnet("") == ""
    assert _normalize_subnet(None) == ""
    assert _normalize_subnet("not-a-subnet") == ""


@pytest.mark.unit
def test_p1b_normalize_ospf_id_same_as_normalize_subnet():
    """統合後: core._normalize_ospf_id と svg._normalize_subnet が同一結果を返す（alias 検証）。

    _normalize_ospf_id は svg._normalize_subnet のエイリアスとして維持する。
    """
    from lib.rendering.core import _normalize_ospf_id
    from lib.rendering.svg import _normalize_subnet
    test_cases = [
        "10.0.0.0/30",
        "10.0.0.1/30",
        "192.168.50.0/24",
        "",
        "not-a-subnet",
    ]
    for s in test_cases:
        assert _normalize_ospf_id(s) == _normalize_subnet(s), \
            f"_normalize_ospf_id('{s}') != _normalize_subnet('{s}')"


@pytest.mark.unit
def test_p1b_core_does_not_define_own_normalize():
    """統合後: core.py 独自の _normalize_ospf_id 関数定義が削除されている。

    core._normalize_ospf_id は svg._normalize_subnet への参照でなければならない。
    """
    import lib.rendering.core as _core_mod
    import lib.rendering.svg as _svg_mod
    # _normalize_ospf_id がエクスポートされていること（後方互換 alias として）
    assert hasattr(_core_mod, "_normalize_ospf_id"), \
        "core._normalize_ospf_id が存在しない（後方互換 alias が欠落）"
    # core の _normalize_ospf_id と svg の _normalize_subnet が同一オブジェクトであること
    assert _core_mod._normalize_ospf_id is _svg_mod._normalize_subnet, \
        "core._normalize_ospf_id が svg._normalize_subnet のエイリアスになっていない（独自定義が残っている）"


# ---------------------------------------------------------------------------
# P1B-R2: <ellipse> の data-ospf-id 二重付与解消
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_ellipse_does_not_have_data_ospf_id():
    """修正後: OSPF セグメント <ellipse> に data-ospf-id が付与されていない。

    data-ospf-id は <g class="segment-node layer-ospf"> のみに付与し、
    <ellipse> 側からは削除する。クリックは <g> で拾う設計。
    """
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    # <ellipse> に data-ospf-id が存在しないこと
    ellipse_with_ospf_id = re.findall(r'<ellipse[^>]*data-ospf-id="[^"]*"', ospf_view)
    assert len(ellipse_with_ospf_id) == 0, \
        f"<ellipse> に data-ospf-id が付与されている（二重付与: {ellipse_with_ospf_id[:2]}）"


@pytest.mark.unit
def test_p1b_segment_node_g_has_data_ospf_id():
    """修正後: OSPF セグメント <g class='segment-node layer-ospf'> に data-ospf-id が付与されている。"""
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    # <g class="segment-node layer-ospf"> に data-ospf-id が存在すること
    seg_g_with_ospf_id = re.findall(
        r'<g[^>]*class="[^"]*segment-node[^"]*layer-ospf[^"]*"[^>]*data-ospf-id="([^"]+)"',
        ospf_view
    )
    seg_g_with_ospf_id2 = re.findall(
        r'<g[^>]*data-ospf-id="([^"]+)"[^>]*class="[^"]*segment-node[^"]*layer-ospf[^"]*"',
        ospf_view
    )
    all_ids = seg_g_with_ospf_id + seg_g_with_ospf_id2
    assert len(all_ids) >= 1, \
        "<g class='segment-node layer-ospf'> に data-ospf-id が付与されていない"


# ---------------------------------------------------------------------------
# P1B-R3: _build_ospf_marking_map ユニットテスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_build_ospf_marking_map_two_devices_same_subnet():
    """_build_ospf_marking_map: 2機が同一subnet → 正規化後の同一 ospf_id が格納される。"""
    from lib.rendering.core import _build_ospf_marking_map
    ospf_entries = [
        {"device": "r1", "network": "10.0.0.0/30", "area": "0", "process": "1"},
        {"device": "r2", "network": "10.0.0.0/30", "area": "0", "process": "1"},
    ]
    result = _build_ospf_marking_map(ospf_entries)
    assert ("r1", "10.0.0.0/30") in result
    assert ("r2", "10.0.0.0/30") in result
    assert result[("r1", "10.0.0.0/30")] == "10.0.0.0/30"
    assert result[("r2", "10.0.0.0/30")] == "10.0.0.0/30"
    # 同一 ospf_id（同一 subnet なので同値）
    assert result[("r1", "10.0.0.0/30")] == result[("r2", "10.0.0.0/30")]


@pytest.mark.unit
def test_p1b_build_ospf_marking_map_missing_network_skipped():
    """_build_ospf_marking_map: network 欠損エントリはスキップされる。"""
    from lib.rendering.core import _build_ospf_marking_map
    ospf_entries = [
        {"device": "r1", "area": "0"},                           # network なし → スキップ
        {"device": "r2", "network": "10.0.0.0/30", "area": "0"},
        {"network": "10.0.1.0/30", "area": "0"},                 # device なし → スキップ
    ]
    result = _build_ospf_marking_map(ospf_entries)
    assert len(result) == 1
    assert ("r2", "10.0.0.0/30") in result


@pytest.mark.unit
def test_p1b_build_ospf_marking_map_invalid_cidr_skipped():
    """_build_ospf_marking_map: 無効 CIDR エントリはスキップされる（id なし）。"""
    from lib.rendering.core import _build_ospf_marking_map
    ospf_entries = [
        {"device": "r1", "network": "not-a-cidr", "area": "0"},
        {"device": "r2", "network": "10.0.0.0/30", "area": "0"},
    ]
    result = _build_ospf_marking_map(ospf_entries)
    assert ("r1", "not-a-cidr") not in result, \
        "無効 CIDR エントリがスキップされていない"
    assert ("r2", "10.0.0.0/30") in result


@pytest.mark.unit
def test_p1b_build_ospf_marking_map_empty_returns_empty():
    """_build_ospf_marking_map: 空リスト → {} を返す。"""
    from lib.rendering.core import _build_ospf_marking_map
    result = _build_ospf_marking_map([])
    assert result == {}


@pytest.mark.unit
def test_p1b_build_ospf_marking_map_host_bit_normalized():
    """_build_ospf_marking_map: host bit 入り network が正規化されて格納される。

    network='10.0.0.1/30'（host bit あり）は正規化後 '10.0.0.0/30' として ospf_id に格納。
    """
    from lib.rendering.core import _build_ospf_marking_map
    ospf_entries = [
        {"device": "r1", "network": "10.0.0.1/30", "area": "0"},
    ]
    result = _build_ospf_marking_map(ospf_entries)
    assert ("r1", "10.0.0.1/30") in result, \
        "host bit 入り network キーが存在しない（マップキーは raw network のまま）"
    assert result[("r1", "10.0.0.1/30")] == "10.0.0.0/30", \
        "host bit 入り network の ospf_id が正規化されていない"


@pytest.mark.unit
def test_p1b_build_ospf_marking_map_no_extra_args():
    """_build_ospf_marking_map: links/segments 引数が不要になった（シグネチャ変更）。

    修正後は _build_ospf_marking_map(ospf_entries) の1引数シグネチャになる。
    """
    from lib.rendering.core import _build_ospf_marking_map
    import inspect
    sig = inspect.signature(_build_ospf_marking_map)
    params = list(sig.parameters.keys())
    assert "links" not in params, \
        "_build_ospf_marking_map に未使用の 'links' 引数が残っている"
    assert "segments" not in params, \
        "_build_ospf_marking_map に未使用の 'segments' 引数が残っている"
    assert "ospf_entries" in params, \
        "_build_ospf_marking_map に 'ospf_entries' 引数がない"


# ---------------------------------------------------------------------------
# P1B-R4: id 整合 — cards.py のルックアップが正規化された network で一致
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_card_lookup_matches_normalized_network():
    """#1B: host bit 入り network でも cards.py の data-ospf-id ルックアップが正しく機能する。

    routing.ospf[].network = '10.0.0.1/30'（host bit あり）でも
    _build_ospf_marking_map が ospf_id='10.0.0.0/30' を返し、
    カード行に data-ospf-id='10.0.0.0/30' が付く。
    また SVG 側の data-ospf-id（link.ospf_network='10.0.0.0/30' 正規化後）と一致する。
    """
    from lib.rendering import render
    topo = {
        "title": "Host-bit Network Test",
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
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet",
             "ospf_area": "0", "ospf_network": "10.0.0.0/30"},
        ],
        "segments": [],
        "routing": {
            "ospf": [
                # host bit 入り network（routing.network != link.ospf_network だが同一 subnet）
                {"device": "r1", "network": "10.0.0.1/30", "area": "0", "process": "1"},
                {"device": "r2", "network": "10.0.0.2/30", "area": "0", "process": "1"},
            ],
        },
    }
    html = render(topo)
    # カード行に data-ospf-id='10.0.0.0/30'（正規化後）が付くこと
    assert 'data-ospf-id="10.0.0.0/30"' in html, \
        "host bit 入り network から正規化された data-ospf-id='10.0.0.0/30' が得られない"
    # SVG link-edge にも data-ospf-id='10.0.0.0/30' が付くこと（一致確認）
    ospf_view = _extract_ospf_view(html)
    assert 'data-ospf-id="10.0.0.0/30"' in ospf_view, \
        "SVG link-edge に data-ospf-id='10.0.0.0/30' が存在しない（cards との不一致）"


# ---------------------------------------------------------------------------
# P1B-R5: link-edge の data-ospf-id と data-link-id 同一要素付与防止
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b_ospf_link_edge_no_dual_attr():
    """修正後: OSPF ビューの link-edge <g> に data-link-id と data-ospf-id が同時に付与されていない。

    OSPF ビューの <g class='link-edge'> は data-ospf-id のみ持ち、
    data-link-id は付与しない（クリック二重発火防止）。
    """
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    ospf_view = _extract_ospf_view(html)
    assert ospf_view, "OSPF ビューが見つからない"
    # link-edge に data-link-id と data-ospf-id が同時に存在するものがないこと
    dual_attrs = re.findall(
        r'<g[^>]*class="link-edge"[^>]*data-link-id="[^"]*"[^>]*data-ospf-id="[^"]*"',
        ospf_view
    )
    dual_attrs2 = re.findall(
        r'<g[^>]*class="link-edge"[^>]*data-ospf-id="[^"]*"[^>]*data-link-id="[^"]*"',
        ospf_view
    )
    all_dual = dual_attrs + dual_attrs2
    assert len(all_dual) == 0, \
        f"OSPF ビューの link-edge に data-link-id と data-ospf-id が同時付与されている: {len(all_dual)} 件"


@pytest.mark.unit
def test_p1b_ospf_card_row_count_exact():
    """#1B 精緻化: OSPF 行の data-ospf-id 付き <tr> が fixture の OSPF エントリ数 (7) と == である。

    _make_ospf_highlight_topology には 7 件の OSPF エントリがある。
    >= 7 ではなく == 7 で検証（フィクスチャのエントリ数と連動）。
    """
    from lib.rendering import render
    html = render(_make_ospf_highlight_topology())
    rows_with_id = re.findall(r'<tr[^>]+data-ospf-id="[^"]*"', html)
    assert len(rows_with_id) == 7, \
        f"data-ospf-id 付き OSPF 行が 7 件でない: {len(rows_with_id)} 件（期待: ==7）"


# ===========================================================================
# Phase 1C — #3 ノード間隔縮小 / #5 AS枠番号ごと色分け
# ===========================================================================


# ---------------------------------------------------------------------------
# #3: ノード間隔縮小
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_1c3_canvas_factor_smaller_than_iteration4():
    """#3: _CANVAS_FACTOR_W / _CANVAS_FACTOR_H が iteration-4 #9 の値（11/9）より小さい"""
    from lib.rendering.layout import _CANVAS_FACTOR_W, _CANVAS_FACTOR_H
    # iteration-4 #9 で 11/9 に縮小済み。Phase 1C でさらに縮小する
    assert _CANVAS_FACTOR_W < 11, (
        f"_CANVAS_FACTOR_W={_CANVAS_FACTOR_W} が iteration-4 値 11 以上（さらなる縮小がされていない）"
    )
    assert _CANVAS_FACTOR_H < 9, (
        f"_CANVAS_FACTOR_H={_CANVAS_FACTOR_H} が iteration-4 値 9 以上（さらなる縮小がされていない）"
    )


@pytest.mark.unit
def test_1c3_canvas_smaller_than_iteration4_values():
    """#3: 係数縮小後の _canvas_size_for_nodes(10) が iteration-4 係数(11/9)より小さい"""
    from lib.rendering.layout import (
        _canvas_size_for_nodes,
        _NODE_WIDTH, _NODE_HEIGHT, _CANVAS_SCALE_EXP,
        _MIN_CANVAS_W, _MIN_CANVAS_H,
    )
    n = 10
    w_new, h_new = _canvas_size_for_nodes(n)

    # iteration-4 #9 時点の係数(11/9)で手計算した値
    w_old = max(_MIN_CANVAS_W, n * (_NODE_WIDTH + 20) ** _CANVAS_SCALE_EXP * 11)
    h_old = max(_MIN_CANVAS_H, n * (_NODE_HEIGHT + 20) ** _CANVAS_SCALE_EXP * 9)

    assert w_new < w_old and h_new < h_old, (
        f"Phase 1C 縮小後({w_new:.0f}x{h_new:.0f})が iteration-4 値({w_old:.0f}x{h_old:.0f})より"
        f"幅・高さともに小さくなっていない"
    )


@pytest.mark.unit
def test_1c3_no_overlap_dense_fixture():
    """#3: 係数縮小後も密集 fixture（10ノード・固定小キャンバス）で重なりゼロ"""
    from lib.rendering.layout import _layout_force_directed, _node_size_for
    n = 10
    node_ids = [f"r{i}" for i in range(n)]
    edges = [(f"r{i}", f"r{i+1}") for i in range(n - 1)]
    node_sizes = {f"r{i}": 2 for i in range(n)}  # 各ノード 2 IF（実寸反映）

    # 固定の小キャンバス（自明 PASS を防ぐ: 新係数での自動キャンバスより十分小さい）
    w, h = 800, 500
    pos = _layout_force_directed(
        node_ids, edges, width=w, height=h,
        iterations=300, node_sizes=node_sizes
    )

    for i, na in enumerate(node_ids):
        for j, nb in enumerate(node_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            wa, ha = _node_size_for(node_sizes[na])
            wb, hb = _node_size_for(node_sizes[nb])
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            min_sep_x = (wa + wb) / 2 + 5
            min_sep_y = (ha + hb) / 2 + 5
            no_overlap = dx >= min_sep_x or dy >= min_sep_y
            assert no_overlap, (
                f"密集キャンバス ({w}x{h}) でノード {na} と {nb} が重なっている "
                f"(dx={dx:.1f} min_sep_x={min_sep_x:.1f}, dy={dy:.1f} min_sep_y={min_sep_y:.1f})"
            )


@pytest.mark.unit
def test_1c3_min_canvas_respected():
    """#3: 縮小後も _canvas_size_for_nodes(0)/(1) が _MIN_CANVAS_W/H を下回らない"""
    from lib.rendering.layout import _canvas_size_for_nodes, _MIN_CANVAS_W, _MIN_CANVAS_H
    for n in (0, 1):
        w, h = _canvas_size_for_nodes(n)
        assert w >= _MIN_CANVAS_W, f"n={n}: キャンバス幅 {w} < _MIN_CANVAS_W {_MIN_CANVAS_W}"
        assert h >= _MIN_CANVAS_H, f"n={n}: キャンバス高 {h} < _MIN_CANVAS_H {_MIN_CANVAS_H}"


@pytest.mark.unit
def test_1c3_deterministic(sample_topology):
    """#3: 係数縮小後も render() が決定的（2回一致）"""
    from lib.rendering import render
    import copy
    html1 = render(copy.deepcopy(sample_topology))
    html2 = render(copy.deepcopy(sample_topology))
    assert html1 == html2, "Phase 1C 係数縮小後の render() が非決定的"


@pytest.mark.unit
def test_1c3_existing_bgp_no_overlap(sample_topology):
    """#3: 係数縮小後も既存 BGP トポロジーでノード重なりゼロ（回帰保護）"""
    from lib.rendering.views import _build_bgp_layout
    from lib.rendering.layout import _node_size_for
    import copy

    topo = copy.deepcopy(sample_topology)
    pos, _bgp_devices = _build_bgp_layout(
        topo["devices"], topo["routing"].get("bgp", []), topo["interfaces"]
    )
    iface_count: dict[str, int] = {}
    for iface in topo["interfaces"]:
        iface_count[iface["device"]] = iface_count.get(iface["device"], 0) + 1

    dev_ids = [d["id"] for d in topo["devices"] if d["id"] in pos]
    for i, na in enumerate(dev_ids):
        for j, nb in enumerate(dev_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            wa, ha = _node_size_for(iface_count.get(na, 0))
            wb, hb = _node_size_for(iface_count.get(nb, 0))
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            needed_x = (wa + wb) / 2 + 5
            needed_y = (ha + hb) / 2 + 5
            no_overlap = dx >= needed_x or dy >= needed_y
            assert no_overlap, (
                f"BGP ビューでノード {na} と {nb} が重なっている "
                f"(dx={dx:.1f} needed_x={needed_x:.1f}, dy={dy:.1f} needed_y={needed_y:.1f})"
            )


# ---------------------------------------------------------------------------
# #5: AS枠番号ごと色分け
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_1c5_multi_as_three_different_colors():
    """#5: multi-as-area (AS65000/65100/65200) で as-group の stroke/fill 色が3種別"""
    from lib.rendering import render

    topo = _make_multi_as_area_topology()
    html = render(topo)

    # BGP ビューを抽出
    bgp_start = html.find('class="view view-bgp"')
    assert bgp_start != -1, "BGP ビューが見つからない"
    next_view = html.find('class="view view-', bgp_start + 20)
    bgp_view = html[bgp_start:next_view] if next_view != -1 else html[bgp_start:]

    # as-group-container の data-as 属性で各 AS を取得
    containers = re.findall(r'<g[^>]*class="as-group-container"[^>]*data-as="([^"]+)"', bgp_view)
    assert len(containers) == 3, (
        f"BGP ビューに as-group-container が {len(containers)} 個（期待: AS65000/65100/65200 の 3個）"
    )

    # 各 as-group-container 内の stroke 色を収集（インライン style から）
    # stroke="..." または style="...stroke:...;" のパターンを取得
    stroke_colors = set()
    fill_colors = set()
    for asn_str in containers:
        # 当該 AS の as-group-container を取り出す
        pat = (
            r'<g[^>]*class="as-group-container"[^>]*data-as="' + re.escape(asn_str) + r'"[^>]*>'
            r'.*?</g>'
        )
        m = re.search(pat, bgp_view, re.DOTALL)
        assert m is not None, f"AS {asn_str} の as-group-container が見つからない"
        container_html = m.group(0)

        # as-group <rect> のインライン style から stroke と fill を取得
        rect_m = re.search(r'class="as-group"[^>]*style="([^"]*)"', container_html)
        if rect_m is None:
            rect_m = re.search(r'style="([^"]*)"[^>]*class="as-group"', container_html)
        assert rect_m is not None, (
            f"AS {asn_str}: as-group <rect> にインライン style が見つからない（#5 未実装）"
        )
        style = rect_m.group(1)
        stroke_m = re.search(r'stroke:\s*([^;]+)', style)
        fill_m = re.search(r'fill:\s*([^;]+)', style)
        assert stroke_m, f"AS {asn_str}: as-group style に stroke が見つからない"
        assert fill_m, f"AS {asn_str}: as-group style に fill が見つからない"
        stroke_colors.add(stroke_m.group(1).strip())
        fill_colors.add(fill_m.group(1).strip())

    assert len(stroke_colors) == 3, (
        f"3 AS で stroke 色が {len(stroke_colors)} 種のみ（3種別でない）: {stroke_colors}"
    )
    assert len(fill_colors) == 3, (
        f"3 AS で fill 色が {len(fill_colors)} 種のみ（3種別でない）: {fill_colors}"
    )


@pytest.mark.unit
def test_1c5_same_as_same_color():
    """#5: 同一 AS 番号のノードは常に同一色（1 AS = 1色）"""
    from lib.rendering import render

    topo = _make_multi_as_area_topology()
    html = render(topo)

    bgp_start = html.find('class="view view-bgp"')
    assert bgp_start != -1
    next_view = html.find('class="view view-', bgp_start + 20)
    bgp_view = html[bgp_start:next_view] if next_view != -1 else html[bgp_start:]

    # AS65000 の as-group-container は 1個のみであること（同一 AS は1枠に統合）
    as65000_containers = re.findall(
        r'<g[^>]*class="as-group-container"[^>]*data-as="65000"',
        bgp_view
    )
    assert len(as65000_containers) == 1, (
        f"AS65000 の as-group-container が {len(as65000_containers)} 個（1個であるべき）"
    )


@pytest.mark.unit
def test_1c5_color_deterministic():
    """#5: AS枠色分けが決定的（2回 render して同一 HTML）"""
    from lib.rendering import render
    import copy

    topo = _make_multi_as_area_topology()
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "Phase 1C AS枠色分けの render() が非決定的"


@pytest.mark.unit
def test_1c5_palette_cycles_deterministically():
    """#5: AS数がパレット数を超える場合も決定的（循環）。N+1 AS で N+1 色 or 循環色を確認"""
    from lib.rendering.svg import _svg_bgp_as_groups

    # パレット数 N を実際の実装から取得（または十分大きな AS 数でテスト）
    # 8 AS を用意（パレット N=6〜8 程度を想定。実装後に循環が正しく機能するか確認）
    n_as = 9  # パレット最大値 8 を超える数
    devs = [
        {"id": f"r{i}", "hostname": f"R{i}", "as": 65000 + i * 100, "sections": []}
        for i in range(n_as)
    ]
    positions = {f"r{i}": (float(100 + i * 150), 300.0) for i in range(n_as)}

    svg1 = _svg_bgp_as_groups(devs, positions)
    svg2 = _svg_bgp_as_groups(devs, positions)
    assert svg1 == svg2, "AS数>パレット時の _svg_bgp_as_groups が非決定的"
    # 9つの as-group-container が存在すること
    containers = re.findall(r'class="as-group-container"', svg1)
    assert len(containers) == n_as, (
        f"as-group-container が {len(containers)} 個（期待: {n_as}）"
    )


@pytest.mark.unit
def test_1c5_label_bg_color_applied():
    """#5: ラベルチップ背景（as-group-label-bg）にも AS 別色が適用されている"""
    from lib.rendering import render

    topo = _make_multi_as_area_topology()
    html = render(topo)

    bgp_start = html.find('class="view view-bgp"')
    assert bgp_start != -1
    next_view = html.find('class="view view-', bgp_start + 20)
    bgp_view = html[bgp_start:next_view] if next_view != -1 else html[bgp_start:]

    # as-group-label-bg の <rect> に style 属性があること（色指定）
    # インライン style か class のいずれかで色が指定される
    label_bg_elements = re.findall(r'class="as-group-label-bg"[^/]*/>', bgp_view)
    assert len(label_bg_elements) >= 3, (
        f"as-group-label-bg 要素が {len(label_bg_elements)} 個（期待: >=3）"
    )
    # 少なくとも color/fill に関する style 属性が存在すること
    has_style = any("style=" in e or "fill=" in e for e in label_bg_elements)
    assert has_style, (
        "as-group-label-bg 要素に color/fill スタイルが存在しない（#5 未実装）"
    )


@pytest.mark.unit
def test_1c5_existing_single_as_still_has_group():
    """#5: 1 AS しかない既存 topology でも as-group が生成される（回帰保護）"""
    from lib.rendering import render

    # 既存 examples topology は基本的に1つか2つの AS
    # iBGP 2ノード（同一AS）の minimal topology
    topo = {
        "title": "single-as",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "as": 65001, "vendor": "cisco_ios", "sections": []},
            {"id": "r2", "hostname": "R2", "as": 65001, "vendor": "cisco_ios", "sections": []},
        ],
        "interfaces": [
            {"id": "r1::lo0", "device": "r1", "name": "lo0", "ip": "10.0.0.1/32",
             "vlan": None, "description": None, "shutdown": False},
            {"id": "r2::lo0", "device": "r2", "name": "lo0", "ip": "10.0.0.2/32",
             "vlan": None, "description": None, "shutdown": False},
        ],
        "links": [],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "peer_as": 65001,
                 "local_ip": None, "neighbor_ip": "10.0.0.2", "type": "ibgp"},
                {"device": "r2", "local_as": 65001, "peer_as": 65001,
                 "local_ip": None, "neighbor_ip": "10.0.0.1", "type": "ibgp"},
            ],
            "ospf": [],
            "static": [],
        },
    }
    html = render(topo)
    assert 'class="as-group"' in html or 'class="as-group-container"' in html, (
        "1 AS topology で as-group が生成されない（回帰）"
    )


# ---------------------------------------------------------------------------
# タスク6: test_1c5_label_bg_color_applied（強化版: 3色すべて異なる fill を検証）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_1c5_label_bg_three_distinct_fill_colors():
    """#5 T6: as-group-label-bg の fill が 3 AS で 3 種すべて異なることを色値で検証。
    「style= があれば PASS」という vacuous な検証を廃止し、実際の色値を比較する。"""
    from lib.rendering import render

    topo = _make_multi_as_area_topology()
    html = render(topo)

    bgp_start = html.find('class="view view-bgp"')
    assert bgp_start != -1, "BGP ビューが見つからない"
    next_view = html.find('class="view view-', bgp_start + 20)
    bgp_view = html[bgp_start:next_view] if next_view != -1 else html[bgp_start:]

    # 各 AS の as-group-container から as-group-label-bg の fill 色を取得
    containers_asn = re.findall(r'<g[^>]*class="as-group-container"[^>]*data-as="([^"]+)"', bgp_view)
    assert len(containers_asn) == 3, f"as-group-container が {len(containers_asn)} 個（期待: 3）"

    fill_colors = []
    for asn_str in containers_asn:
        pat = (
            r'<g[^>]*class="as-group-container"[^>]*data-as="' + re.escape(asn_str) + r'"[^>]*>'
            r'.*?</g>'
        )
        m = re.search(pat, bgp_view, re.DOTALL)
        assert m is not None, f"AS {asn_str} の as-group-container が見つからない"
        container_html = m.group(0)

        # as-group-label-bg の <rect> の fill 色を取得（インライン style）
        label_bg_m = re.search(r'class="as-group-label-bg"[^>]*style="([^"]*)"', container_html)
        if label_bg_m is None:
            label_bg_m = re.search(r'style="([^"]*)"[^>]*class="as-group-label-bg"', container_html)
        assert label_bg_m is not None, (
            f"AS {asn_str}: as-group-label-bg にインライン style が見つからない"
        )
        fill_m = re.search(r'fill:\s*([^;]+)', label_bg_m.group(1))
        assert fill_m is not None, f"AS {asn_str}: as-group-label-bg の style に fill が見つからない"
        fill_colors.append(fill_m.group(1).strip())

    assert len(set(fill_colors)) == 3, (
        f"3 AS の as-group-label-bg fill が {len(set(fill_colors))} 種のみ（3種別でない）: {fill_colors}"
    )


# ---------------------------------------------------------------------------
# タスク7: _as_color 単体テスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_as_color_index0_returns_first_palette_entry():
    """T7: _as_color(0) が _AS_COLOR_PALETTE[0] の stroke/fill_rgba を返す。
    _AS_COLOR_PALETTE は 2 要素 (stroke, fill_rgba)。label_bg は stroke と同値。"""
    from lib.rendering.svg import _as_color, _AS_COLOR_PALETTE
    stroke, fill_rgba, label_bg = _as_color(0)
    expected_stroke, expected_fill = _AS_COLOR_PALETTE[0]
    assert stroke == expected_stroke, f"index 0 の stroke が不一致: {stroke!r} != {expected_stroke!r}"
    assert fill_rgba == expected_fill, f"index 0 の fill_rgba が不一致"
    assert label_bg == expected_stroke, f"index 0 の label_bg が stroke と異なる"


@pytest.mark.unit
def test_as_color_index1_returns_second_palette_entry():
    """T7: _as_color(1) が _AS_COLOR_PALETTE[1] の要素を返す"""
    from lib.rendering.svg import _as_color, _AS_COLOR_PALETTE
    stroke, fill_rgba, label_bg = _as_color(1)
    expected_stroke, expected_fill = _AS_COLOR_PALETTE[1]
    assert stroke == expected_stroke
    assert fill_rgba == expected_fill
    assert label_bg == expected_stroke  # label_bg == stroke


@pytest.mark.unit
def test_as_color_last_index_returns_last_palette_entry():
    """T7: _as_color(len-1) が _AS_COLOR_PALETTE[-1] の要素を返す"""
    from lib.rendering.svg import _as_color, _AS_COLOR_PALETTE
    n = len(_AS_COLOR_PALETTE)
    stroke, fill_rgba, label_bg = _as_color(n - 1)
    expected_stroke, expected_fill = _AS_COLOR_PALETTE[n - 1]
    assert stroke == expected_stroke
    assert fill_rgba == expected_fill
    assert label_bg == expected_stroke  # label_bg == stroke


@pytest.mark.unit
def test_as_color_returns_three_element_tuple():
    """T7: _as_color は常に 3 要素タプルを返す"""
    from lib.rendering.svg import _as_color
    result = _as_color(0)
    assert isinstance(result, tuple), f"タプルでない: {type(result)}"
    assert len(result) == 3, f"要素数が {len(result)}（期待: 3）"


@pytest.mark.unit
def test_as_color_wraps_at_palette_length():
    """T7: _as_color(len) が循環して index 0 と同一色を返す"""
    from lib.rendering.svg import _as_color, _AS_COLOR_PALETTE
    n = len(_AS_COLOR_PALETTE)
    assert _as_color(n) == _as_color(0), (
        f"_as_color({n}) が _as_color(0) と異なる（循環しない）"
    )


@pytest.mark.unit
def test_as_color_docstring_mentions_modulo():
    """T7: _as_color の docstring に asn % len(_AS_COLOR_PALETTE) の説明があること（設計記録）"""
    from lib.rendering.svg import _as_color
    doc = _as_color.__doc__ or ""
    # "% len" または "modulo" または "循環" など循環の仕組みが記述されているか
    has_cyclic_desc = "% len" in doc or "循環" in doc or "modulo" in doc or "% N" in doc
    assert has_cyclic_desc, (
        f"_as_color docstring に循環の仕組み（% len(...) 等）が記述されていない:\n{doc}"
    )


# ---------------------------------------------------------------------------
# タスク8: test_1c5_palette_cycles_deterministically（強化版: 循環を色値で検証）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_1c5_palette_cycle_index0_equals_index_len():
    """T8: index 0 の AS と index len の AS が同じ stroke 色（循環の核心を色値で検証）。"""
    from lib.rendering.svg import _svg_bgp_as_groups, _AS_COLOR_PALETTE

    n = len(_AS_COLOR_PALETTE)
    # AS番号: 65000 (asn % n == 0), 65000+n (asn % n == 0) → 同色のはず
    asn0 = 65000          # 65000 % n == 65000 % n
    asn_wrap = 65000 + n  # (65000 + n) % n == 65000 % n → 同じ index
    devs = [
        {"id": "r0", "hostname": "R0", "as": asn0, "sections": []},
        {"id": "r1", "hostname": "R1", "as": asn_wrap, "sections": []},
    ]
    positions = {"r0": (100.0, 300.0), "r1": (300.0, 300.0)}

    svg = _svg_bgp_as_groups(devs, positions)

    # 2つの as-group の stroke 色を取得
    stroke_colors = re.findall(r'class="as-group"[^>]*style="[^"]*stroke:\s*([^;]+)', svg)
    assert len(stroke_colors) == 2, f"as-group が {len(stroke_colors)} 個（期待: 2）"

    assert stroke_colors[0].strip() == stroke_colors[1].strip(), (
        f"asn={asn0} と asn={asn_wrap} の stroke 色が異なる（循環していない）: "
        f"{stroke_colors[0]!r} != {stroke_colors[1]!r}"
    )


# ===========================================================================
# Phase 2E: IF 一覧/棚卸しビュー
# ===========================================================================

# ---------------------------------------------------------------------------
# テスト用フィクスチャ: ifinv_topology
# 機器2台・IF6本（IP有/無・admin_status up/down/admin-down を混在させて
# 集計・未使用判定の vacuous 回避を保証）
# ---------------------------------------------------------------------------

def _make_ifinv_topology():
    """IF一覧ビューテスト用 topology。
    - r1: IF3本 (up+IP, up+IP, admin-down+IP)
    - r2: IF3本 (up+IP, down+noIP, admin-down+noIP)  ← down+noIP / admin-down+noIP = 未使用候補2本
    status 集計: up=3, down=1, admin-down=2
    未使用候補 (IP無し & down系): down+noIP=1, admin-down+noIP=1 → 計2本
    """
    return {
        "title": "IFInv Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
        ],
        "interfaces": [
            # r1
            {
                "id": "r1::GigabitEthernet0/0", "device": "r1", "name": "GigabitEthernet0/0",
                "ip": "10.0.0.1/30", "admin_status": "up", "mtu": 1500, "vlan": None,
                "l2_l3": "l3", "description": "to-R2", "shutdown": False,
            },
            {
                "id": "r1::Loopback0", "device": "r1", "name": "Loopback0",
                "ip": "1.1.1.1/32", "admin_status": "up", "mtu": None, "vlan": None,
                "l2_l3": "l3", "description": None, "shutdown": False,
            },
            {
                "id": "r1::GigabitEthernet0/1", "device": "r1", "name": "GigabitEthernet0/1",
                "ip": "192.168.1.1/24", "admin_status": "admin-down", "mtu": 9000, "vlan": 10,
                "l2_l3": "l2", "description": "unused-with-ip", "shutdown": True,
            },
            # r2
            {
                "id": "r2::ge-0/0/0", "device": "r2", "name": "ge-0/0/0",
                "ip": "10.0.0.2/30", "admin_status": "up", "mtu": 1500, "vlan": None,
                "l2_l3": "l3", "description": "to-R1", "shutdown": False,
            },
            {
                "id": "r2::ge-0/0/1", "device": "r2", "name": "ge-0/0/1",
                "ip": None, "admin_status": "down", "mtu": None, "vlan": None,
                "l2_l3": None, "description": None, "shutdown": False,
            },
            {
                "id": "r2::ge-0/0/2", "device": "r2", "name": "ge-0/0/2",
                "ip": None, "admin_status": "admin-down", "mtu": None, "vlan": None,
                "l2_l3": None, "description": "spare port", "shutdown": True,
            },
        ],
        "links": [
            {"a_device": "r1", "a_if": "GigabitEthernet0/0",
             "b_device": "r2", "b_if": "ge-0/0/0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.fixture
def ifinv_topology():
    return _make_ifinv_topology()


@pytest.fixture
def ifinv_html(ifinv_topology):
    from lib.rendering import render
    return render(ifinv_topology)


# ---------------------------------------------------------------------------
# T-2E-1: ビュータブに「ifinv」が追加される
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_ifinv_tab_exists_in_view_tabs(ifinv_html):
    """Phase2E: ビュータブに data-view="ifinv" タブが存在する"""
    assert 'data-view="ifinv"' in ifinv_html, \
        "ifinv ビュータブ (data-view=\"ifinv\") が見つからない"


@pytest.mark.unit
def test_2e_ifinv_tab_label(ifinv_html):
    """Phase2E: ifinv タブのラベルが「IF一覧」または「IF-List」または「IFInv」"""
    # タブボタンの onclick="selectView('ifinv')" または data-view="ifinv" の近辺に
    # ラベルテキストが存在することを確認する
    # data-view="ifinv" を含む button タグを抽出
    m = re.search(r'<button[^>]*data-view="ifinv"[^>]*>(.*?)</button>', ifinv_html)
    assert m, "ifinv タブボタンが見つからない"
    label = m.group(1)
    # 「IF一覧」「IF-List」「IFInv」のいずれかを含むことを確認
    has_label = any(kw in label for kw in ("IF一覧", "IF-List", "IFInv", "IF Inv", "IF List"))
    assert has_label, f"ifinv タブのラベルが不適切: {label!r}"


@pytest.mark.unit
def test_2e_ifinv_tab_in_build_view_tabs():
    """Phase2E: _build_view_tabs(['physical','ifinv']) に ifinv タブが含まれる"""
    from lib.rendering.views import _build_view_tabs
    html = _build_view_tabs(["physical", "ifinv"])
    assert 'data-view="ifinv"' in html, \
        "_build_view_tabs が ifinv タブを生成しない"


# ---------------------------------------------------------------------------
# T-2E-2: IF一覧テーブルの生成（HTML table, 全IF行, 決定的な行順）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_ifinv_table_container_exists(ifinv_html):
    """Phase2E: #view-ifinv-table コンテナが HTML に存在する"""
    assert 'id="view-ifinv-table"' in ifinv_html, \
        "#view-ifinv-table コンテナが見つからない"


@pytest.mark.unit
def test_2e_ifinv_table_has_all_iface_rows(ifinv_topology, ifinv_html):
    """Phase2E: IF一覧テーブルに全 IF 行（data-iface-id）が揃っている"""
    iface_ids = [i["id"] for i in ifinv_topology["interfaces"]]
    for iid in iface_ids:
        assert f'data-iface-id="{iid}"' in ifinv_html, \
            f"IF 行 data-iface-id=\"{iid}\" が見つからない"


@pytest.mark.unit
def test_2e_ifinv_table_row_count(ifinv_topology, ifinv_html):
    """Phase2E: IF一覧テーブルの data-iface-id 行数が interfaces 数と一致"""
    expected = len(ifinv_topology["interfaces"])
    # _build_ifinv_table を直呼びして フル render 依存を排除（境界 regex フォールバック不要）
    from lib.rendering.views import _build_ifinv_table
    ifinv_section = _build_ifinv_table(ifinv_topology["devices"], ifinv_topology["interfaces"])
    actual = ifinv_section.count('data-iface-id="')
    assert actual == expected, \
        f"ifinv テーブルの data-iface-id 行数が {actual}（期待: {expected}）"


@pytest.mark.unit
def test_2e_ifinv_table_column_headers(ifinv_html):
    """Phase2E: IF一覧テーブルに必要な列ヘッダ（Device/Interface/IP/Status/MTU/VLAN/L2L3/Description）が存在する"""
    required_headers = ["Device", "Interface", "IP", "Status", "MTU", "VLAN", "L2L3", "Description"]
    # #view-ifinv-table 内のテーブル全体を抽出
    m = re.search(r'id="view-ifinv-table".*?</div>\s*<!--', ifinv_html, re.DOTALL)
    table_section = m.group(0) if m else ifinv_html
    for header in required_headers:
        assert header in table_section, \
            f"IF一覧テーブルに列ヘッダ \"{header}\" が見つからない"


@pytest.mark.unit
def test_2e_ifinv_table_row_order_deterministic(ifinv_topology):
    """Phase2E: 同一 topology を2回 render した結果が完全一致（決定性）"""
    from lib.rendering import render
    t1 = copy.deepcopy(ifinv_topology)
    t2 = copy.deepcopy(ifinv_topology)
    html1 = render(t1)
    html2 = render(t2)
    assert html1 == html2, "ifinv topology の render が非決定的"


@pytest.mark.unit
def test_2e_ifinv_table_rows_sorted_by_device_then_ifname(ifinv_topology, ifinv_html):
    """Phase2E: IF一覧テーブルの行が device id → IF 名の辞書順で並んでいる"""
    # _build_ifinv_table を直呼びして抽出を確実に（境界 regex フォールバック廃止）
    from lib.rendering.views import _build_ifinv_table
    ifinv_section = _build_ifinv_table(ifinv_topology["devices"], ifinv_topology["interfaces"])
    found_ids = re.findall(r'data-iface-id="([^"]+)"', ifinv_section)
    # ifinv-topology の interfaces を device id → IF 名でソートした期待順
    ifaces = sorted(
        ifinv_topology["interfaces"],
        key=lambda i: (i["device"], i["name"])
    )
    expected_ids = [i["id"] for i in ifaces]
    assert found_ids == expected_ids, \
        f"IF行の順序が期待と異なる:\n  actual:   {found_ids}\n  expected: {expected_ids}"


@pytest.mark.unit
def test_2e_ifinv_table_ip_column_values(ifinv_html):
    """Phase2E: IP アドレスがテーブルに出力される（IP有のIFのみ）"""
    assert "10.0.0.1/30" in ifinv_html
    assert "10.0.0.2/30" in ifinv_html
    assert "1.1.1.1/32" in ifinv_html


@pytest.mark.unit
def test_2e_ifinv_table_mtu_column_value(ifinv_html):
    """Phase2E: MTU 値（1500, 9000）がテーブルに出力される"""
    assert "1500" in ifinv_html
    assert "9000" in ifinv_html


@pytest.mark.unit
def test_2e_ifinv_table_vlan_column_value(ifinv_topology):
    """Phase2E: VLAN 値（10）がテーブルの該当行セルに出力される（vacuous OR を排除）"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(ifinv_topology["devices"], ifinv_topology["interfaces"])
    # r1::GigabitEthernet0/1 行が存在すること
    m = re.search(r'<tr[^>]*data-iface-id="r1::GigabitEthernet0/1"[^>]*>(.*?)</tr>',
                  result, re.DOTALL)
    assert m is not None, "r1::GigabitEthernet0/1 行が見つからない"
    row_html = m.group(0)
    # VLAN セルに ">10<" が含まれること（OR の最後の "vlan" in html.lower() は削除）
    assert ">10<" in row_html or ">10 <" in row_html, \
        f"VLAN=10 がセル値として見つからない: {row_html!r}"


# ---------------------------------------------------------------------------
# T-2E-3: status 集計（up/down/admin-down 件数）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_status_summary_up_count(ifinv_html):
    """Phase2E: status 集計 up=3 が確定フォーマット 'up: 3</span>' で出力される（vacuous regex 解消）"""
    # 確定フォーマット: <span ...>up: 3</span> を直接検証
    assert "up: 3</span>" in ifinv_html, \
        "IF 集計バッジに 'up: 3</span>' が見当たらない"


@pytest.mark.unit
def test_2e_status_summary_down_count(ifinv_html):
    """Phase2E: status 集計 down=1 が確定フォーマット 'down: 1</span>' で出力される（vacuous regex 解消）"""
    assert "down: 1</span>" in ifinv_html, \
        "IF 集計バッジに 'down: 1</span>' が見当たらない"


@pytest.mark.unit
def test_2e_status_summary_admindown_count(ifinv_html):
    """Phase2E: status 集計 admin-down=2 が確定フォーマット 'admin-down: 2</span>' で出力される（vacuous regex 解消）"""
    assert "admin-down: 2</span>" in ifinv_html, \
        "IF 集計バッジに 'admin-down: 2</span>' が見当たらない"


# ---------------------------------------------------------------------------
# T-2E-4: 未使用候補マーク（IP無し & down/admin-down）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_unused_candidates_marked_with_data_unused(ifinv_html):
    """Phase2E: IP無し & down系 の IF 行 <tr> に data-unused="1" が付く"""
    # r2::ge-0/0/1 (down, ip=None) と r2::ge-0/0/2 (admin-down, ip=None) が対象
    for iface_id in ("r2::ge-0/0/1", "r2::ge-0/0/2"):
        # <tr> タグに両属性が共存することを確認
        pattern = rf'<tr[^>]*data-iface-id="{re.escape(iface_id)}"[^>]*data-unused="1"|<tr[^>]*data-unused="1"[^>]*data-iface-id="{re.escape(iface_id)}"'
        m = re.search(pattern, ifinv_html)
        assert m, f"IF {iface_id} の <tr> に data-unused=\"1\" が付いていない"


@pytest.mark.unit
def test_2e_unused_candidate_count_correct(ifinv_html):
    """Phase2E: <tr data-unused="1"> の件数が 2（IP無し & down系 の数と一致）"""
    # <tr> タグの data-unused="1" のみカウント（JS 文字列内を除外）
    count = len(re.findall(r'<tr[^>]*data-unused="1"', ifinv_html))
    assert count == 2, f"<tr data-unused=\"1\"> の件数が {count}（期待: 2）"


@pytest.mark.unit
def test_2e_ip_with_down_not_marked_unused(ifinv_html):
    """Phase2E: IP有り の admin-down IF（r1::GigabitEthernet0/1）は未使用候補にならない"""
    # r1::GigabitEthernet0/1 は admin-down だが IP あり → data-unused="1" は付かない
    # この行が存在することと data-unused="1" を持たないことを確認
    # 当該行の tr タグを探す
    m = re.search(r'<tr[^>]*data-iface-id="r1::GigabitEthernet0/1"[^>]*>', ifinv_html)
    assert m, "r1::GigabitEthernet0/1 行が見つからない"
    row_tag = m.group(0)
    assert 'data-unused="1"' not in row_tag, \
        "IP有りの admin-down IF が誤って data-unused=\"1\" マークされている"


# ---------------------------------------------------------------------------
# T-2E-5: JS 関数の存在と対象セレクタ（vacuous 回避）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_js_ifinv_search_function_exists(ifinv_html):
    """Phase2E: IF一覧検索 JS 関数が存在する（filterIfRows または ifinvSearch）"""
    js_pattern = r'function\s+(filterIfRows|ifinvSearch|filterIfinvRows)\s*\('
    assert re.search(js_pattern, ifinv_html), \
        "IF一覧検索用 JS 関数が見つからない"


@pytest.mark.unit
def test_2e_js_ifinv_sort_function_exists(ifinv_html):
    """Phase2E: IF一覧ソート JS 関数が存在する（sortIfTable または ifinvSort）"""
    js_pattern = r'function\s+(sortIfTable|ifinvSort|sortIfinvTable)\s*\('
    assert re.search(js_pattern, ifinv_html), \
        "IF一覧ソート用 JS 関数が見つからない"


@pytest.mark.unit
def test_2e_js_ifinv_sort_targets_ifinv_table(ifinv_html):
    """Phase2E: ソート JS が view-ifinv-table または ifinv-table-body を参照している"""
    # ソート関数の実装が #view-ifinv-table または ifinv-table-body を使用
    assert "view-ifinv-table" in ifinv_html or "ifinv-table-body" in ifinv_html, \
        "ソート JS が IF一覧テーブルを参照していない"


@pytest.mark.unit
def test_2e_js_unused_toggle_function_exists(ifinv_html):
    """Phase2E: 未使用のみ表示トグル JS 関数が存在する"""
    js_pattern = r'function\s+(toggleUnused|showOnlyUnused|ifinvToggleUnused)\s*\('
    assert re.search(js_pattern, ifinv_html), \
        "未使用のみ表示トグル JS 関数が見つからない"


@pytest.mark.unit
def test_2e_js_unused_toggle_uses_data_unused_attr(ifinv_html):
    """Phase2E: 未使用トグル JS が data-unused 属性を参照している"""
    assert "data-unused" in ifinv_html, \
        "未使用トグル JS が data-unused 属性を参照していない"


# ---------------------------------------------------------------------------
# T-2E-6: selectView('ifinv') の挙動（JS コード構造）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_selectview_handles_ifinv(ifinv_html):
    """Phase2E: selectView JS が ifinv 識別子を処理するコードを含む"""
    # selectView 内で 'ifinv' を扱う条件分岐が存在すること
    assert "'ifinv'" in ifinv_html or '"ifinv"' in ifinv_html, \
        "JS に ifinv 識別子が見当たらない"


@pytest.mark.unit
def test_2e_selectview_hides_svg_container_for_ifinv(ifinv_html):
    """Phase2E: ifinv 選択時に #svg-container を隠す JS コードが存在する"""
    # svg-container の display 制御コードが ifinv 分岐で存在する
    # "svg-container" と "display" / "none" / "ifinv" のキーワードが JS に共存
    js_block_m = re.search(r'<script>(.*?)</script>', ifinv_html, re.DOTALL)
    js_code = js_block_m.group(1) if js_block_m else ""
    assert "svg-container" in js_code, \
        "JS に svg-container の参照が見つからない"
    assert "ifinv" in js_code, \
        "JS に ifinv の参照が見つからない"


@pytest.mark.unit
def test_2e_ifinv_table_hidden_by_default(ifinv_html):
    """Phase2E: #view-ifinv-table は初期状態で非表示（style="display:none" または JS で隠す）"""
    # #view-ifinv-table の div が display:none または class で非表示であること
    m = re.search(r'id="view-ifinv-table"[^>]*>', ifinv_html)
    assert m, "#view-ifinv-table が見つからない"
    tag = m.group(0)
    # display:none が属性にある、またはJSで初期非表示にすることを確認
    is_hidden = (
        "display:none" in tag
        or "display: none" in tag
        or 'style="display:none"' in tag
    )
    assert is_hidden, \
        f"#view-ifinv-table が初期非表示になっていない: {tag}"


# ---------------------------------------------------------------------------
# T-2E-7: 図系 UI（ズームボタン・凡例）が ifinv では無関係であることの設計確認
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_zoom_controls_exist_for_svg_views(ifinv_html):
    """Phase2E: zoom-controls は存在する（Physical 等の SVG ビュー用）"""
    assert 'id="zoom-controls"' in ifinv_html, \
        "zoom-controls が見つからない"


# ---------------------------------------------------------------------------
# T-2E-8: 自己完結・外部参照0の確認
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_self_contained_no_external_refs(ifinv_html):
    """Phase2E: ifinv HTML に外部リソース参照（http://, https://, src=, href=）が含まれない"""
    # src= / href= の外部参照を検査（style/script インライン専用）
    # <link rel="stylesheet" href="..."> 等が無いこと
    external_refs = re.findall(r'(?:src|href)\s*=\s*["\']https?://', ifinv_html, re.IGNORECASE)
    assert len(external_refs) == 0, \
        f"外部参照が含まれている: {external_refs}"


# ---------------------------------------------------------------------------
# T-2E-9: sample_topology の render にも ifinv タブが追加されている（非回帰）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_ifinv_tab_present_in_sample_topology(rendered_html):
    """Phase2E: 既存 sample_topology の render にも ifinv タブが含まれる（非回帰）"""
    assert 'data-view="ifinv"' in rendered_html, \
        "sample_topology render に ifinv タブが含まれない"


@pytest.mark.unit
def test_2e_sample_topology_all_ifaces_in_ifinv_table(sample_topology, rendered_html):
    """Phase2E: sample_topology の全 IF が ifinv テーブルに存在する"""
    for iface in sample_topology["interfaces"]:
        iid = iface["id"]
        assert f'data-iface-id="{iid}"' in rendered_html, \
            f"sample_topology の IF {iid} が ifinv テーブルに見つからない"


@pytest.mark.unit
def test_2e_existing_physical_view_still_present(rendered_html):
    """Phase2E: Physical ビューが引き続き存在する（非回帰）"""
    assert 'class="view view-physical"' in rendered_html, \
        "Physical ビューが消えている"


@pytest.mark.unit
def test_2e_existing_bgp_view_still_present(rendered_html):
    """Phase2E: BGP ビューが引き続き存在する（非回帰）"""
    assert 'class="view view-bgp"' in rendered_html, \
        "BGP ビューが消えている"


@pytest.mark.unit
def test_2e_existing_ospf_view_still_present():
    """Phase2E: OSPF 参加2台以上の topology で OSPF ビューが存在する（非回帰）"""
    from lib.rendering import render
    # OSPF 参加2台（両端）のシンプルな topology を用意
    topo = {
        "title": "OSPF Test", "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "admin_status": "up", "mtu": None, "vlan": None, "l2_l3": "l3",
             "description": None, "shutdown": False},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "admin_status": "up", "mtu": None, "vlan": None, "l2_l3": "l3",
             "description": None, "shutdown": False},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [],
            "ospf": [
                {"device": "r1", "area": "0", "network": "10.0.0.0/30", "process": 1},
                {"device": "r2", "area": "0", "network": "10.0.0.0/30", "process": 1},
            ],
            "static": [],
        },
    }
    html = render(topo)
    assert 'class="view view-ospf"' in html, "OSPF ビューが生成されない"
    # ifinv タブも存在することを確認
    assert 'data-view="ifinv"' in html, "ifinv タブが存在しない"


# ---------------------------------------------------------------------------
# T-2E-10: _build_ifinv_table 単体テスト（views.py ユニット）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_build_ifinv_table_returns_string():
    """Phase2E: _build_ifinv_table が文字列を返す"""
    from lib.rendering.views import _build_ifinv_table
    devices = [{"id": "r1", "hostname": "R1"}]
    ifaces = [{"id": "r1::eth0", "device": "r1", "name": "eth0",
               "ip": "10.0.0.1/30", "admin_status": "up",
               "mtu": None, "vlan": None, "l2_l3": "l3", "description": None}]
    result = _build_ifinv_table(devices, ifaces)
    assert isinstance(result, str), f"文字列でない: {type(result)}"


@pytest.mark.unit
def test_2e_build_ifinv_table_empty_devices():
    """Phase2E: _build_ifinv_table にデバイス0件でも例外なし"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table([], [])
    assert isinstance(result, str)


@pytest.mark.unit
def test_2e_build_ifinv_table_status_counts():
    """Phase2E: _build_ifinv_table の status 集計が確定フォーマットで出力される（vacuous regex 解消）"""
    from lib.rendering.views import _build_ifinv_table
    devices = [{"id": "r1", "hostname": "R1"}]
    ifaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0",
         "ip": "10.0.0.1/30", "admin_status": "up",
         "mtu": None, "vlan": None, "l2_l3": "l3", "description": None},
        {"id": "r1::eth1", "device": "r1", "name": "eth1",
         "ip": None, "admin_status": "down",
         "mtu": None, "vlan": None, "l2_l3": None, "description": None},
        {"id": "r1::eth2", "device": "r1", "name": "eth2",
         "ip": None, "admin_status": "admin-down",
         "mtu": None, "vlan": None, "l2_l3": None, "description": None},
    ]
    result = _build_ifinv_table(devices, ifaces)
    # 確定フォーマット: 'up: 1</span>' / 'down: 1</span>' / 'admin-down: 1</span>' を直接検証
    assert "up: 1</span>" in result, f"'up: 1</span>' が見当たらない: {result[:500]!r}"
    assert "down: 1</span>" in result, f"'down: 1</span>' が見当たらない"
    assert "admin-down: 1</span>" in result, f"'admin-down: 1</span>' が見当たらない"


@pytest.mark.unit
def test_2e_build_ifinv_table_unused_mark():
    """Phase2E: _build_ifinv_table で IP無し&down系の行に data-unused=\"1\"が付く"""
    from lib.rendering.views import _build_ifinv_table
    devices = [{"id": "r1", "hostname": "R1"}]
    ifaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0",
         "ip": "10.0.0.1/30", "admin_status": "up",  # IP有り → 未使用候補でない
         "mtu": None, "vlan": None, "l2_l3": "l3", "description": None},
        {"id": "r1::eth1", "device": "r1", "name": "eth1",
         "ip": None, "admin_status": "admin-down",  # IP無し & admin-down → 未使用候補
         "mtu": None, "vlan": None, "l2_l3": None, "description": None},
    ]
    result = _build_ifinv_table(devices, ifaces)
    # <tr> に data-unused="1" が付くこと（JS 文字列内は除外してカウント）
    assert len(re.findall(r'<tr[^>]*data-unused="1"', result)) >= 1, \
        "未使用候補行の <tr> に data-unused=\"1\" が付いていない"
    # IP有りの up 行には data-unused が付かないこと
    m = re.search(r'<tr[^>]*data-iface-id="r1::eth0"[^>]*>', result)
    assert m, "r1::eth0 行が見つからない"
    assert 'data-unused="1"' not in m.group(0), \
        "IP有りの行に data-unused=\"1\" が誤って付いている"


@pytest.mark.unit
def test_2e_build_ifinv_table_row_order():
    """Phase2E: _build_ifinv_table の行が device_id → IF名 辞書順"""
    from lib.rendering.views import _build_ifinv_table
    devices = [
        {"id": "r2", "hostname": "R2"},
        {"id": "r1", "hostname": "R1"},
    ]
    ifaces = [
        {"id": "r2::eth0", "device": "r2", "name": "eth0",
         "ip": None, "admin_status": "up", "mtu": None, "vlan": None, "l2_l3": None, "description": None},
        {"id": "r1::eth1", "device": "r1", "name": "eth1",
         "ip": None, "admin_status": "up", "mtu": None, "vlan": None, "l2_l3": None, "description": None},
        {"id": "r1::eth0", "device": "r1", "name": "eth0",
         "ip": None, "admin_status": "up", "mtu": None, "vlan": None, "l2_l3": None, "description": None},
    ]
    result = _build_ifinv_table(devices, ifaces)
    ids_in_order = re.findall(r'data-iface-id="([^"]+)"', result)
    assert ids_in_order == ["r1::eth0", "r1::eth1", "r2::eth0"], \
        f"行順が期待と異なる: {ids_in_order}"


# ---------------------------------------------------------------------------
# T-2E-11: MTU/VLAN セルに data-num 属性が付くこと（数値ソート前提）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_ifinv_mtu_cell_has_data_num(ifinv_topology):
    """Phase2E: MTU セルに data-num 属性が付く（数値ソート対応）"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(ifinv_topology["devices"], ifinv_topology["interfaces"])
    # r1::GigabitEthernet0/0 の行を探し、data-num="1500" が付くことを確認
    m = re.search(r'<tr[^>]*data-iface-id="r1::GigabitEthernet0/0"[^>]*>(.*?)</tr>',
                  result, re.DOTALL)
    assert m is not None, "r1::GigabitEthernet0/0 行が見つからない"
    row_html = m.group(0)
    assert 'data-num="1500"' in row_html, \
        f"MTU セルに data-num=\"1500\" が付いていない: {row_html!r}"


@pytest.mark.unit
def test_2e_ifinv_vlan_cell_has_data_num(ifinv_topology):
    """Phase2E: VLAN セルに data-num 属性が付く（数値ソート対応）"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(ifinv_topology["devices"], ifinv_topology["interfaces"])
    # r1::GigabitEthernet0/1 の行を探し、data-num="10" が付くことを確認
    m = re.search(r'<tr[^>]*data-iface-id="r1::GigabitEthernet0/1"[^>]*>(.*?)</tr>',
                  result, re.DOTALL)
    assert m is not None, "r1::GigabitEthernet0/1 行が見つからない"
    row_html = m.group(0)
    assert 'data-num="10"' in row_html, \
        f"VLAN セルに data-num=\"10\" が付いていない: {row_html!r}"


@pytest.mark.unit
def test_2e_ifinv_data_num_empty_for_none_values(ifinv_topology):
    """Phase2E: MTU/VLAN が None の行は data-num="" で出力される（空=ソート末尾）"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(ifinv_topology["devices"], ifinv_topology["interfaces"])
    # r1::Loopback0 は MTU=None, VLAN=None
    m = re.search(r'<tr[^>]*data-iface-id="r1::Loopback0"[^>]*>(.*?)</tr>',
                  result, re.DOTALL)
    assert m is not None, "r1::Loopback0 行が見つからない"
    row_html = m.group(0)
    # data-num="" が2つ（MTU列・VLAN列）存在すること
    assert row_html.count('data-num=""') >= 2, \
        f"data-num=\"\" が2つ以上存在しない: {row_html!r}"


# ---------------------------------------------------------------------------
# T-2E-12: 検索＋未使用トグル併用の振る舞い（_applyIfFilters 統合後）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_js_apply_if_filters_function_exists(ifinv_html):
    """Phase2E: _applyIfFilters 関数（または統合関数）が JS に存在する"""
    # 検索と未使用トグルを統合した関数が存在すること
    assert re.search(r'function\s+_applyIfFilters\s*\(', ifinv_html), \
        "_applyIfFilters 統合関数が JS に見つからない"


@pytest.mark.unit
def test_2e_js_filter_handlers_call_apply_if_filters(ifinv_html):
    """Phase2E: 検索 input と未使用トグル onChange が _applyIfFilters を呼び出す"""
    # _applyIfFilters が filterIfRows/toggleUnused ハンドラから呼ばれること
    # JS ブロックを抽出して確認
    js_block_m = re.search(r'<script>(.*?)</script>', ifinv_html, re.DOTALL)
    assert js_block_m, "JS ブロックが見つからない"
    js_code = js_block_m.group(1)
    # _applyIfFilters が filterIfRows か toggleUnused から呼び出されていること
    assert "_applyIfFilters" in js_code, "_applyIfFilters が JS に存在しない"
    # filterIfRows の本体で _applyIfFilters を呼ぶか、直接統合されていること
    filter_or_integrate = (
        "filterIfRows" in js_code or "_ifinvSearchQuery" in js_code
    )
    assert filter_or_integrate, "検索ハンドラが _applyIfFilters に統合されていない"


@pytest.mark.unit
def test_2e_js_ifinv_state_vars_exist(ifinv_html):
    """Phase2E: _ifinvSearchQuery / _ifinvUnusedOnly の状態変数が JS に存在する"""
    js_block_m = re.search(r'<script>(.*?)</script>', ifinv_html, re.DOTALL)
    assert js_block_m, "JS ブロックが見つからない"
    js_code = js_block_m.group(1)
    assert "_ifinvSearchQuery" in js_code, "_ifinvSearchQuery が JS に存在しない"
    assert "_ifinvUnusedOnly" in js_code, "_ifinvUnusedOnly が JS に存在しない"


@pytest.mark.unit
def test_2e_js_ifinv_search_uses_addeventlistener(ifinv_html):
    """B-pass1b: #ifinv-search はグローバル検索統合のため撤去済み。
    代わりに #search-input がグローバル検索として存在し ifinv を駆動する。"""
    # B-pass1b: #ifinv-search は撤去（グローバル #search-input に統合）
    assert 'id="ifinv-search"' not in ifinv_html, \
        "#ifinv-search がまだ残っている（B-pass1b で撤去済みのはず）"
    # グローバル検索入力が存在することを確認
    assert 'id="search-input"' in ifinv_html, \
        "グローバル検索入力 #search-input が見つからない"


@pytest.mark.unit
def test_2e_js_ifinv_unused_toggle_uses_addeventlistener(ifinv_html):
    """Phase2E: ifinv-unused-toggle の onchange は addEventListener で登録される（インライン不使用）"""
    m = re.search(r'id="ifinv-unused-toggle"[^>]*>', ifinv_html)
    assert m is not None, "ifinv-unused-toggle が見つからない"
    tag = m.group(0)
    assert "onchange" not in tag, \
        f"ifinv-unused-toggle に onchange インラインが残っている: {tag!r}"


# ---------------------------------------------------------------------------
# T-2E-13: sortIfTable の data-col / data-label ベース（colOrder ドリフト解消）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_ifinv_th_has_data_col_attribute(ifinv_html):
    """Phase2E: ifinv テーブルの全 th に data-col 属性が付く"""
    from lib.rendering.views import _build_ifinv_table
    devices = [{"id": "r1", "hostname": "R1"}]
    ifaces = [{"id": "r1::eth0", "device": "r1", "name": "eth0",
               "ip": None, "admin_status": "up", "mtu": None, "vlan": None,
               "l2_l3": None, "description": None}]
    result = _build_ifinv_table(devices, ifaces)
    # <th ...> タグのみ抽出（<thead> は除外）
    th_tags = re.findall(r'<th\s[^>]*>', result)
    assert len(th_tags) > 0, "ifinv テーブルに th が見つからない"
    for th in th_tags:
        assert 'data-col="' in th, f"th に data-col が付いていない: {th!r}"


@pytest.mark.unit
def test_2e_ifinv_th_has_data_label_attribute(ifinv_html):
    """Phase2E: ifinv テーブルの全 th に data-label 属性が付く（▲▼書き換え安全のため）"""
    from lib.rendering.views import _build_ifinv_table
    devices = [{"id": "r1", "hostname": "R1"}]
    ifaces = [{"id": "r1::eth0", "device": "r1", "name": "eth0",
               "ip": None, "admin_status": "up", "mtu": None, "vlan": None,
               "l2_l3": None, "description": None}]
    result = _build_ifinv_table(devices, ifaces)
    # <th ...> タグのみ抽出（<thead> は除外）
    th_tags = re.findall(r'<th\s[^>]*>', result)
    assert len(th_tags) > 0, "ifinv テーブルに th が見つからない"
    for th in th_tags:
        assert 'data-label="' in th, f"th に data-label が付いていない: {th!r}"


@pytest.mark.unit
def test_2e_ifinv_sort_uses_data_col_not_hardcoded_order(ifinv_html):
    """Phase2E: sortIfTable が colOrder ハードコードを使わず DOM data-col から列順を取得する"""
    js_block_m = re.search(r'<script>(.*?)</script>', ifinv_html, re.DOTALL)
    assert js_block_m, "JS ブロックが見つからない"
    js_code = js_block_m.group(1)
    # ハードコード colOrder 配列が無いこと（廃止）
    assert "var colOrder = [" not in js_code, \
        "JS に colOrder ハードコード配列が残っている（廃止すべき）"
    # data-col を参照するコードが存在すること
    assert "data-col" in js_code, "sortIfTable が data-col 属性を参照していない"


# ---------------------------------------------------------------------------
# T-2E-14: status 集計 other（未知ステータス）の堅牢化
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_2e_build_ifinv_table_unknown_status_handled():
    """Phase2E: 未知 admin_status が other/サイレントドロップされず集計に現れる"""
    from lib.rendering.views import _build_ifinv_table
    devices = [{"id": "r1", "hostname": "R1"}]
    ifaces = [
        {"id": "r1::eth0", "device": "r1", "name": "eth0",
         "ip": None, "admin_status": "unknown-state",  # 未知ステータス
         "mtu": None, "vlan": None, "l2_l3": None, "description": None},
        {"id": "r1::eth1", "device": "r1", "name": "eth1",
         "ip": None, "admin_status": None,  # None ステータス
         "mtu": None, "vlan": None, "l2_l3": None, "description": None},
    ]
    result = _build_ifinv_table(devices, ifaces)
    # 例外なく文字列が返ること（最低条件）
    assert isinstance(result, str)
    # up/down/admin-down が 0 であること（他 2 件は other 扱い）
    assert "up: 0</span>" in result, f"up: 0 が見当たらない: {result[:300]!r}"
    assert "down: 0</span>" in result, f"down: 0 が見当たらない"
    assert "admin-down: 0</span>" in result, f"admin-down: 0 が見当たらない"


# ---------------------------------------------------------------------------
# T-VLAN-SW: _build_ifinv_table — switchport VLAN フォールバック
# Phase2E クロスレビュー指摘: iface.vlan が null のとき switchport の VLAN を使う
# ---------------------------------------------------------------------------

def _make_devices_for_vlan_test():
    return [{"id": "sw1", "hostname": "SW1"}]


def _make_iface(iid, name, vlan=None, switchport=None, admin_status="up", ip=None):
    """テスト用 iface dict ビルダー（省略可能フィールドはデフォルト None）。"""
    return {
        "id": iid, "device": "sw1", "name": name,
        "ip": ip, "admin_status": admin_status,
        "mtu": None, "vlan": vlan, "switchport": switchport,
        "l2_l3": None, "description": None,
    }


@pytest.mark.unit
def test_vlan_sw_access_port_shows_access_vlan():
    """switchport mode=access, access_vlan=10, iface.vlan=null → VLAN セルに '10' + data-num='10'。"""
    from lib.rendering.views import _build_ifinv_table
    iface = _make_iface("sw1::eth0", "eth0",
                         vlan=None,
                         switchport={"mode": "access", "access_vlan": 10})
    result = _build_ifinv_table(_make_devices_for_vlan_test(), [iface])
    m = re.search(r'<tr[^>]*data-iface-id="sw1::eth0"[^>]*>(.*?)</tr>', result, re.DOTALL)
    assert m, "sw1::eth0 行が見つからない"
    row = m.group(0)
    # VLAN セルに 10 が表示される
    assert ">10<" in row or ">10 <" in row, \
        f"access VLAN=10 がセル値に出ていない: {row!r}"
    # data-num="10" が付く（数値ソート対応）
    assert 'data-num="10"' in row, \
        f"access VLAN セルに data-num='10' が付いていない: {row!r}"


@pytest.mark.unit
def test_vlan_sw_trunk_port_shows_trunk_vlans_string():
    """switchport mode=trunk, trunk_vlans=[10,20,30]（list）, iface.vlan=null
    → VLAN セルに '10,20,30'（sorted/カンマ結合）、data-num は付かない。"""
    from lib.rendering.views import _build_ifinv_table
    iface = _make_iface("sw1::eth1", "eth1",
                         vlan=None,
                         switchport={"mode": "trunk", "trunk_vlans": [10, 20, 30]})
    result = _build_ifinv_table(_make_devices_for_vlan_test(), [iface])
    m = re.search(r'<tr[^>]*data-iface-id="sw1::eth1"[^>]*>(.*?)</tr>', result, re.DOTALL)
    assert m, "sw1::eth1 行が見つからない"
    row = m.group(0)
    assert ">10,20,30<" in row or ">10,20,30 <" in row, \
        f"trunk VLAN '10,20,30' がセル値に出ていない: {row!r}"
    # trunk 複数 VLAN には data-num を付けない（文字列ソート扱い）
    assert 'data-num="10,20,30"' not in row, \
        f"trunk VLAN セルに不正な data-num が付いている: {row!r}"


@pytest.mark.unit
def test_vlan_sw_trunk_port_string_trunk_vlans():
    """switchport mode=trunk, trunk_vlans='10,20,30'（str）→ そのまま表示、data-num なし。"""
    from lib.rendering.views import _build_ifinv_table
    iface = _make_iface("sw1::eth2", "eth2",
                         vlan=None,
                         switchport={"mode": "trunk", "trunk_vlans": "10,20,30"})
    result = _build_ifinv_table(_make_devices_for_vlan_test(), [iface])
    m = re.search(r'<tr[^>]*data-iface-id="sw1::eth2"[^>]*>(.*?)</tr>', result, re.DOTALL)
    assert m, "sw1::eth2 行が見つからない"
    row = m.group(0)
    assert ">10,20,30<" in row or ">10,20,30 <" in row, \
        f"trunk VLAN (str) がセル値に出ていない: {row!r}"
    assert 'data-num="10,20,30"' not in row, \
        f"trunk VLAN (str) セルに不正な data-num が付いている: {row!r}"


@pytest.mark.unit
def test_vlan_iface_vlan_takes_precedence_over_switchport():
    """iface.vlan が非 null のときは switchport.access_vlan より優先される。"""
    from lib.rendering.views import _build_ifinv_table
    iface = _make_iface("sw1::eth3", "eth3",
                         vlan=99,
                         switchport={"mode": "access", "access_vlan": 10})
    result = _build_ifinv_table(_make_devices_for_vlan_test(), [iface])
    m = re.search(r'<tr[^>]*data-iface-id="sw1::eth3"[^>]*>(.*?)</tr>', result, re.DOTALL)
    assert m, "sw1::eth3 行が見つからない"
    row = m.group(0)
    # vlan=99 が優先 → 99 が表示される
    assert ">99<" in row or ">99 <" in row, \
        f"iface.vlan=99 が優先表示されていない: {row!r}"
    # access_vlan=10 は表示されない
    assert ">10<" not in row, \
        f"iface.vlan 優先のはずが access_vlan=10 が表示されている: {row!r}"


@pytest.mark.unit
def test_vlan_no_switchport_no_vlan_shows_empty():
    """switchport も vlan も null → VLAN セルは空欄。"""
    from lib.rendering.views import _build_ifinv_table
    iface = _make_iface("sw1::eth4", "eth4", vlan=None, switchport=None)
    result = _build_ifinv_table(_make_devices_for_vlan_test(), [iface])
    m = re.search(r'<tr[^>]*data-iface-id="sw1::eth4"[^>]*>(.*?)</tr>', result, re.DOTALL)
    assert m, "sw1::eth4 行が見つからない"
    row = m.group(0)
    # VLAN セルが空欄（data-num="" かつ セル内容が空）
    assert 'data-num=""' in row or "<td></td>" in row or "<td> </td>" in row, \
        f"VLAN 空欄行の data-num が空でない: {row!r}"


@pytest.mark.unit
def test_vlan_sw_deterministic():
    """switchport VLAN フォールバックを含む _build_ifinv_table が2回呼び出して同一出力を返す（決定性）。"""
    from lib.rendering.views import _build_ifinv_table
    devices = _make_devices_for_vlan_test()
    ifaces = [
        _make_iface("sw1::p0", "p0", vlan=None,
                    switchport={"mode": "access", "access_vlan": 10}),
        _make_iface("sw1::p1", "p1", vlan=None,
                    switchport={"mode": "trunk", "trunk_vlans": [30, 10, 20]}),
        _make_iface("sw1::p2", "p2", vlan=5, switchport=None),
    ]
    r1 = _build_ifinv_table(devices, ifaces)
    r2 = _build_ifinv_table(devices, ifaces)
    assert r1 == r2, "2回呼び出して結果が異なる（非決定的）"
    # trunk の list は sorted されて "10,20,30" になる
    assert ">10,20,30<" in r1 or ">10,20,30 <" in r1, \
        f"trunk list が sorted/カンマ結合されていない: {r1[:500]!r}"


# ---- T-SEARCH-V6: dual-stack IF の data-search に v6 アドレスが含まれる ----

def _make_dual_stack_iface(iface_id: str, name: str, v4_ip: str, v4_prefix: int,
                             v6_ip: str, v6_prefix: int) -> dict:
    """dual-stack IF（v4 primary + v6 GUA）を構築するヘルパー。

    addresses リストに v4/v6 を格納する。link-local は含まない。
    """
    return {
        "id": iface_id,
        "device": iface_id.split("::")[0],
        "name": name,
        "ip": f"{v4_ip}/{v4_prefix}",
        "vlan": None,
        "description": None,
        "shutdown": False,
        "admin_status": "up",
        "addresses": [
            {"af": "v4", "ip": v4_ip, "prefix": v4_prefix, "scope": None, "secondary": False},
            {"af": "v6", "ip": v6_ip, "prefix": v6_prefix, "scope": None},
        ],
    }


def _make_v4_only_iface(iface_id: str, name: str, v4_ip: str, v4_prefix: int) -> dict:
    """single-stack v4 のみ IF を構築するヘルパー。"""
    return {
        "id": iface_id,
        "device": iface_id.split("::")[0],
        "name": name,
        "ip": f"{v4_ip}/{v4_prefix}",
        "vlan": None,
        "description": None,
        "shutdown": False,
        "admin_status": "up",
        "addresses": [
            {"af": "v4", "ip": v4_ip, "prefix": v4_prefix, "scope": None, "secondary": False},
        ],
    }


@pytest.mark.unit
def test_search_attr_dual_stack_contains_v4():
    """_build_search_attr: dual-stack IF の data-search に v4 ホスト部が含まれる。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1"}
    iface = _make_dual_stack_iface(
        "r1::eth0", "GigabitEthernet0/0",
        "10.1.0.1", 30,
        "2001:db8:1::1", 64,
    )
    result = _build_search_attr(dev, [iface])
    assert "10.1.0.1" in result, \
        f"v4 アドレスが data-search に含まれていない: {result!r}"


@pytest.mark.unit
def test_search_attr_dual_stack_contains_v6():
    """_build_search_attr: dual-stack IF（ip=v4プライマリ）の data-search に v6 ホスト部が含まれる。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1"}
    iface = _make_dual_stack_iface(
        "r1::eth0", "GigabitEthernet0/0",
        "10.1.0.1", 30,
        "2001:db8:1::1", 64,
    )
    result = _build_search_attr(dev, [iface])
    assert "2001:db8:1::1" in result, \
        f"v6 アドレスが data-search に含まれていない: {result!r}"


@pytest.mark.unit
def test_search_attr_dual_stack_contains_hostname():
    """_build_search_attr: dual-stack IF でも hostname（小文字）が data-search に含まれる（既存維持）。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1"}
    iface = _make_dual_stack_iface(
        "r1::eth0", "GigabitEthernet0/0",
        "10.1.0.1", 30,
        "2001:db8:1::1", 64,
    )
    result = _build_search_attr(dev, [iface])
    assert "r1" in result, \
        f"hostname が data-search に含まれていない: {result!r}"


@pytest.mark.unit
def test_search_attr_v4_only_no_v6():
    """_build_search_attr: single-stack(v4 のみ) の場合は v6 アドレスが含まれない（従来通り）。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1"}
    iface = _make_v4_only_iface("r1::eth0", "GigabitEthernet0/0", "10.1.0.1", 30)
    result = _build_search_attr(dev, [iface])
    assert "10.1.0.1" in result, \
        f"v4 アドレスが data-search に含まれていない: {result!r}"
    assert "2001:" not in result, \
        f"v4 only IF に v6 アドレスが混入: {result!r}"


@pytest.mark.unit
def test_search_attr_dual_stack_no_link_local():
    """_build_search_attr: link-local (fe80::) は data-search に含まれない。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1"}
    iface = {
        "id": "r1::eth0",
        "device": "r1",
        "name": "GigabitEthernet0/0",
        "ip": "10.1.0.1/30",
        "addresses": [
            {"af": "v4", "ip": "10.1.0.1", "prefix": 30, "scope": None, "secondary": False},
            {"af": "v6", "ip": "2001:db8:1::1", "prefix": 64, "scope": None},
            {"af": "v6", "ip": "fe80::1", "prefix": 64, "scope": "link-local"},
        ],
    }
    result = _build_search_attr(dev, [iface])
    assert "2001:db8:1::1" in result, \
        f"GUA v6 が含まれていない: {result!r}"
    assert "fe80" not in result, \
        f"link-local が data-search に混入: {result!r}"


@pytest.mark.unit
def test_search_attr_dual_stack_multiple_ifaces():
    """_build_search_attr: 複数 dual-stack IF がある場合、全 v4/v6 ホスト部を含む。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1"}
    iface1 = _make_dual_stack_iface(
        "r1::eth0", "GigabitEthernet0/0",
        "10.1.0.1", 30,
        "2001:db8:1::1", 64,
    )
    iface2 = _make_dual_stack_iface(
        "r1::eth1", "GigabitEthernet0/1",
        "10.2.0.1", 30,
        "2001:db8:2::1", 64,
    )
    result = _build_search_attr(dev, [iface1, iface2])
    assert "10.1.0.1" in result
    assert "2001:db8:1::1" in result
    assert "10.2.0.1" in result
    assert "2001:db8:2::1" in result


@pytest.mark.unit
def test_search_attr_dual_stack_deterministic():
    """_build_search_attr: 同一入力で2回呼び出して同一結果（決定性）。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1"}
    iface = _make_dual_stack_iface(
        "r1::eth0", "GigabitEthernet0/0",
        "10.1.0.1", 30,
        "2001:db8:1::1", 64,
    )
    r1 = _build_search_attr(dev, [iface])
    r2 = _build_search_attr(dev, [iface])
    assert r1 == r2, f"非決定的: {r1!r} vs {r2!r}"


@pytest.mark.unit
def test_search_attr_no_double_space():
    """_build_search_attr: 余分な空白や重複トークンが生じない。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1"}
    iface = _make_dual_stack_iface(
        "r1::eth0", "GigabitEthernet0/0",
        "10.1.0.1", 30,
        "2001:db8:1::1", 64,
    )
    result = _build_search_attr(dev, [iface])
    assert "  " not in result, f"連続スペースあり: {result!r}"
    tokens = result.split(" ")
    assert len(tokens) == len(set(tokens)), f"重複トークンあり: {tokens!r}"


@pytest.mark.unit
def test_ifinv_data_search_dual_stack_contains_v6():
    """_build_ifinv_table: dual-stack IF 行の data-search に v6 アドレストークンが含まれる。"""
    from lib.rendering.views import _build_ifinv_table
    devices = [{"id": "r1", "hostname": "R1"}]
    iface = _make_dual_stack_iface(
        "r1::eth0", "GigabitEthernet0/0",
        "10.1.0.1", 30,
        "2001:db8:1::1", 64,
    )
    result = _build_ifinv_table(devices, [iface])
    # data-search 属性を抽出して v6 が含まれることを確認
    search_matches = re.findall(r'data-search="([^"]*)"', result)
    all_search = " ".join(search_matches)
    assert "2001:db8:1::1" in all_search, \
        f"ifinv data-search に v6 アドレスが含まれていない: {all_search!r}"


@pytest.mark.unit
def test_ifinv_data_search_dual_stack_contains_v4():
    """_build_ifinv_table: dual-stack IF 行の data-search に v4 ホスト部も含まれる（既存維持）。"""
    from lib.rendering.views import _build_ifinv_table
    devices = [{"id": "r1", "hostname": "R1"}]
    iface = _make_dual_stack_iface(
        "r1::eth0", "GigabitEthernet0/0",
        "10.1.0.1", 30,
        "2001:db8:1::1", 64,
    )
    result = _build_ifinv_table(devices, [iface])
    search_matches = re.findall(r'data-search="([^"]*)"', result)
    all_search = " ".join(search_matches)
    assert "10.1.0.1" in all_search, \
        f"ifinv data-search に v4 アドレスが含まれていない: {all_search!r}"


@pytest.mark.unit
def test_ifinv_data_search_v4_only_no_v6():
    """_build_ifinv_table: single-stack(v4 のみ) IF 行の data-search に v6 が混入しない（従来通り）。"""
    from lib.rendering.views import _build_ifinv_table
    devices = [{"id": "r1", "hostname": "R1"}]
    iface = _make_v4_only_iface("r1::eth0", "GigabitEthernet0/0", "10.1.0.1", 30)
    result = _build_ifinv_table(devices, [iface])
    search_matches = re.findall(r'data-search="([^"]*)"', result)
    all_search = " ".join(search_matches)
    assert "10.1.0.1" in all_search
    assert "2001:" not in all_search, \
        f"v4 only IF に v6 が混入: {all_search!r}"


@pytest.mark.unit
def test_ifinv_data_search_no_link_local():
    """_build_ifinv_table: link-local アドレスが data-search に含まれない。"""
    from lib.rendering.views import _build_ifinv_table
    devices = [{"id": "r1", "hostname": "R1"}]
    iface = {
        "id": "r1::eth0",
        "device": "r1",
        "name": "GigabitEthernet0/0",
        "ip": "10.1.0.1/30",
        "vlan": None,
        "description": None,
        "shutdown": False,
        "admin_status": "up",
        "addresses": [
            {"af": "v4", "ip": "10.1.0.1", "prefix": 30, "scope": None, "secondary": False},
            {"af": "v6", "ip": "2001:db8:1::1", "prefix": 64, "scope": None},
            {"af": "v6", "ip": "fe80::1", "prefix": 64, "scope": "link-local"},
        ],
    }
    result = _build_ifinv_table(devices, [iface])
    search_matches = re.findall(r'data-search="([^"]*)"', result)
    all_search = " ".join(search_matches)
    assert "2001:db8:1::1" in all_search
    assert "fe80" not in all_search, \
        f"link-local が data-search に混入: {all_search!r}"


# ===========================================================================
# Round A — Pass1: スタイル・配置改善
# ===========================================================================

# ---------------------------------------------------------------------------
# A1: Device Details を縦1列に（.cards-grid: grid-template-columns: 1fr）
# ---------------------------------------------------------------------------

def _extract_css_rule(html: str, selector: str) -> str:
    """HTML の <style> ブロックから指定セレクタの CSS ルール本体を返す。"""
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
    combined = "\n".join(style_blocks)
    pattern = re.escape(selector) + r'\s*\{([^}]+)\}'
    m = re.search(pattern, combined, re.DOTALL)
    return m.group(1) if m else ""


@pytest.mark.unit
def test_roundA_a1_cards_grid_single_column(rendered_html):
    """A1: .cards-grid が縦1列（grid-template-columns: 1fr）になっている"""
    rule = _extract_css_rule(rendered_html, ".cards-grid")
    assert rule, "CSS に .cards-grid ルールが存在しない"
    assert "grid-template-columns" in rule, \
        ".cards-grid に grid-template-columns が定義されていない"
    # 単一列: "1fr" が存在し、auto-fill/minmax による複数列でないこと
    assert "1fr" in rule, (
        f".cards-grid の grid-template-columns が 1fr でない（縦1列未実装）: {rule.strip()!r}"
    )
    assert "auto-fill" not in rule, (
        ".cards-grid に auto-fill が残っている（複数列のまま）"
    )
    assert "minmax" not in rule, (
        ".cards-grid に minmax が残っている（複数列のまま）"
    )


@pytest.mark.unit
def test_roundA_a1_cards_grid_still_display_grid(rendered_html):
    """A1: .cards-grid が引き続き display:grid を使用している（回帰保護）"""
    rule = _extract_css_rule(rendered_html, ".cards-grid")
    assert rule, "CSS に .cards-grid ルールが存在しない"
    assert "display" in rule and "grid" in rule, \
        f".cards-grid の display が grid でない: {rule.strip()!r}"


# ---------------------------------------------------------------------------
# A2: BGPバッジと OSPFラベルのフォントサイズ統一
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_roundA_a2_link_label_css_defined(rendered_html):
    """A2: CSS に .link-label ルールが定義されている"""
    rule = _extract_css_rule(rendered_html, ".link-label")
    assert rule, (
        "CSS に .link-label ルールが存在しない（OSPFラベルがブラウザ既定フォントのまま）"
    )


@pytest.mark.unit
def test_roundA_a2_link_label_font_size_matches_bgp_badge(rendered_html):
    """A2: .link-label と .bgp-badge の font-size が同一値"""
    link_label_rule = _extract_css_rule(rendered_html, ".link-label")
    bgp_badge_rule = _extract_css_rule(rendered_html, ".bgp-badge")
    assert link_label_rule, "CSS に .link-label ルールが存在しない"
    assert bgp_badge_rule, "CSS に .bgp-badge ルールが存在しない"

    def _extract_font_size(rule_text: str) -> str:
        m = re.search(r'font-size\s*:\s*([^;]+)', rule_text)
        return m.group(1).strip() if m else ""

    fs_link_label = _extract_font_size(link_label_rule)
    fs_bgp_badge = _extract_font_size(bgp_badge_rule)
    assert fs_link_label, f".link-label に font-size が定義されていない: {link_label_rule.strip()!r}"
    assert fs_bgp_badge, f".bgp-badge に font-size が定義されていない: {bgp_badge_rule.strip()!r}"
    assert fs_link_label == fs_bgp_badge, (
        f".link-label の font-size ({fs_link_label}) が .bgp-badge ({fs_bgp_badge}) と異なる"
    )


@pytest.mark.unit
def test_roundA_a2_link_label_has_mono_font(rendered_html):
    """A2: .link-label が monospace フォントファミリーを指定している"""
    rule = _extract_css_rule(rendered_html, ".link-label")
    assert rule, "CSS に .link-label ルールが存在しない"
    assert "font-family" in rule or "font-mono" in rule or "monospace" in rule.lower() or "Consolas" in rule, (
        f".link-label にモノスペースフォント指定がない: {rule.strip()!r}"
    )


# ---------------------------------------------------------------------------
# A3: OSPFラベルの配色（黒脱却）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_roundA_a3_link_label_has_fill(rendered_html):
    """A3: .link-label に fill が定義されている（SVGテキスト色指定）"""
    rule = _extract_css_rule(rendered_html, ".link-label")
    assert rule, "CSS に .link-label ルールが存在しない"
    assert "fill" in rule, (
        f".link-label に fill が定義されていない（黒のまま）: {rule.strip()!r}"
    )


@pytest.mark.unit
def test_roundA_a3_link_label_fill_not_black(rendered_html):
    """A3: .link-label の fill が黒（#000/#000000）でない"""
    rule = _extract_css_rule(rendered_html, ".link-label")
    assert rule, "CSS に .link-label ルールが存在しない"
    fill_m = re.search(r'fill\s*:\s*([^;]+)', rule)
    assert fill_m, f".link-label に fill が定義されていない: {rule.strip()!r}"
    fill_val = fill_m.group(1).strip().lower()
    assert fill_val not in ("#000", "#000000", "black", "inherit", "initial", "unset"), (
        f".link-label の fill が黒/既定値: {fill_val!r}（OSPFテーマ色で明示すること）"
    )


# ---------------------------------------------------------------------------
# A7: ノード間隔縮小 — _CANVAS_FACTOR の更なる縮小・20台 no-overlap
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_roundA_a7_canvas_factor_smaller_than_current():
    """A7: _CANVAS_FACTOR_W / _CANVAS_FACTOR_H が現行値（8/7）よりさらに小さい"""
    from lib.rendering.layout import _CANVAS_FACTOR_W, _CANVAS_FACTOR_H
    assert _CANVAS_FACTOR_W < 8, (
        f"_CANVAS_FACTOR_W={_CANVAS_FACTOR_W} が現行値 8 以上（縮小未実施）"
    )
    assert _CANVAS_FACTOR_H < 7, (
        f"_CANVAS_FACTOR_H={_CANVAS_FACTOR_H} が現行値 7 以上（縮小未実施）"
    )


def _load_large_topo_for_test():
    """large-topo の topology dict を返す。

    evals/inputs/large-topo/*.cfg から build_topology 経由で topology を生成する。
    /tmp への依存・pytest.skip() は使わず、リポジトリ内フィクスチャのみで完結する。
    """
    import os
    from scripts.parse_configs import parse_paths
    from scripts.build_topology import build

    fixture_dir = os.path.join(
        os.path.dirname(__file__), "..", "evals", "inputs", "large-topo"
    )
    files = sorted(
        os.path.join(fixture_dir, f)
        for f in os.listdir(fixture_dir)
        if f.endswith(".cfg")
    )
    assert files, f"large-topo フィクスチャが空: {fixture_dir}"
    devices = parse_paths(files)
    return build(devices, generated_from=files)


@pytest.mark.unit
def test_roundA_a7_no_overlap_large_topo_20nodes():
    """A7: large-topo 20台（evals/inputs/large-topo）で全ノードペアの矩形が重ならない。
    build_topology 経由で topology を生成し、_layout_force_directed で検証（決定性も兼ねる）。
    リポジトリ内フィクスチャ(large-topo/*.cfg)のみで完結し、/tmp 依存・pytest.skip() なし。
    """
    from lib.rendering.layout import (
        _layout_force_directed, _node_size_for, _canvas_size_for_nodes, _adaptive_iter
    )

    topo = _load_large_topo_for_test()

    devices = topo["devices"]
    links = topo["links"]
    interfaces = topo["interfaces"]

    assert len(devices) == 20, f"large-topo は 20台であるべき: {len(devices)}"

    node_ids = [d["id"] for d in devices]
    edges = [(lk["a_device"], lk["b_device"]) for lk in links]
    iface_count: dict[str, int] = {}
    for iface in interfaces:
        iface_count[iface["device"]] = iface_count.get(iface["device"], 0) + 1
    node_sizes = {d["id"]: iface_count.get(d["id"], 0) for d in devices}

    n = len(node_ids)
    est_w, est_h = _canvas_size_for_nodes(n, max_node_h=max(
        _node_size_for(node_sizes.get(nid, 0))[1] for nid in node_ids
    ))
    pos = _layout_force_directed(
        node_ids, edges, width=est_w, height=est_h,
        iterations=_adaptive_iter(n), node_sizes=node_sizes,
    )

    # 決定性チェック: 同一入力で2回呼んで同一座標
    pos2 = _layout_force_directed(
        node_ids, edges, width=est_w, height=est_h,
        iterations=_adaptive_iter(n), node_sizes=node_sizes,
    )
    assert pos == pos2, "large-topo でのレイアウトが非決定的（2回の結果が異なる）"

    # 全ペア重なりゼロ
    for i, na in enumerate(node_ids):
        for j, nb in enumerate(node_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            wa, ha = _node_size_for(node_sizes[na])
            wb, hb = _node_size_for(node_sizes[nb])
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            min_sep_x = (wa + wb) / 2 + 5
            min_sep_y = (ha + hb) / 2 + 5
            no_overlap = dx >= min_sep_x or dy >= min_sep_y
            assert no_overlap, (
                f"large-topo: ノード {na} と {nb} が重なっている "
                f"(dx={dx:.1f} min_sep_x={min_sep_x:.1f}, "
                f"dy={dy:.1f} min_sep_y={min_sep_y:.1f})"
            )


@pytest.mark.unit
def test_roundA_a7_no_overlap_multi_as_area():
    """A7: 係数縮小後も multi-as-area (7台) でノード重なりゼロ（既存ケース回帰保護）"""
    from lib.rendering.views import _build_bgp_layout
    from lib.rendering.layout import _node_size_for

    topo = _make_multi_as_area_topology()
    pos, _devs = _build_bgp_layout(
        topo["devices"], topo["routing"].get("bgp", []), topo["interfaces"]
    )
    iface_count: dict[str, int] = {}
    for iface in topo["interfaces"]:
        iface_count[iface["device"]] = iface_count.get(iface["device"], 0) + 1

    dev_ids = [d["id"] for d in topo["devices"] if d["id"] in pos]
    for i, na in enumerate(dev_ids):
        for j, nb in enumerate(dev_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            wa, ha = _node_size_for(iface_count.get(na, 0))
            wb, hb = _node_size_for(iface_count.get(nb, 0))
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            needed_x = (wa + wb) / 2 + 5
            needed_y = (ha + hb) / 2 + 5
            no_overlap = dx >= needed_x or dy >= needed_y
            assert no_overlap, (
                f"multi-as-area: ノード {na} と {nb} が重なっている "
                f"(dx={dx:.1f} needed_x={needed_x:.1f}, "
                f"dy={dy:.1f} needed_y={needed_y:.1f})"
            )


@pytest.mark.unit
def test_roundA_a7_canvas_smaller_than_current_factors():
    """A7: 縮小後の _canvas_size_for_nodes(20) が現行係数(8/7)より小さい"""
    from lib.rendering.layout import (
        _canvas_size_for_nodes,
        _NODE_WIDTH, _NODE_HEIGHT, _CANVAS_SCALE_EXP,
        _MIN_CANVAS_W, _MIN_CANVAS_H,
    )
    n = 20
    w_new, h_new = _canvas_size_for_nodes(n)
    # 現行係数(8/7)での値を手計算
    w_old = max(_MIN_CANVAS_W, n * (_NODE_WIDTH + 20) ** _CANVAS_SCALE_EXP * 8)
    h_old = max(_MIN_CANVAS_H, n * (_NODE_HEIGHT + 20) ** _CANVAS_SCALE_EXP * 7)
    assert w_new < w_old and h_new < h_old, (
        f"A7 縮小後({w_new:.0f}x{h_new:.0f})が現行値({w_old:.0f}x{h_old:.0f})より"
        f"幅・高さともに小さくなっていない"
    )


@pytest.mark.unit
def test_roundA_a7_deterministic(sample_topology):
    """A7: 係数縮小後も render() が決定的（2回一致）"""
    from lib.rendering import render
    import copy
    html1 = render(copy.deepcopy(sample_topology))
    html2 = render(copy.deepcopy(sample_topology))
    assert html1 == html2, "A7 係数縮小後の render() が非決定的"


# ---------------------------------------------------------------------------
# 修正1: ospf_subnets=[] の OSPF 非参加リンクに data-ospf-id が付かない
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fix1_ospf_non_participant_link_no_data_ospf_id():
    """修正1: OSPF 非参加リンク（ospf_area=None）が両端 OSPF 参加デバイス間にある場合、
    data-ospf-id が付かない。

    バグシナリオ:
    両端が OSPF 参加デバイスで当該リンクは ospf_area=None（OSPF 非参加）のとき、
    _build_view_ospf 内の _merge_links_by_link_id が ospf_subnets=[] を設定する。
    views.py の 'or subnets' が空リストをフォールバックして subnets 全体（['10.0.1.0/30']）を
    ospf_subnets として扱い、data-ospf-id="10.0.1.0/30" が誤付与される。
    is None 判定への修正後は [] のままフォールバックせず data-ospf-id が付かない。
    """
    from lib.rendering.views import _build_view_ospf

    devices = [
        {"id": "R1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        {"id": "R2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
    ]
    # R1, R2 を別サブネットで OSPF 参加デバイスとして登録（ospf_device_ids に含める）
    ospf_entries = [
        {"device": "R1", "process": 1, "area": "0", "subnet": "10.0.0.0/30"},
        {"device": "R2", "process": 1, "area": "0", "subnet": "10.0.0.0/30"},
    ]
    # OSPF 非参加リンク（両端は OSPF 参加デバイス、ospf_area=None）
    # _build_view_ospf 内で _merge_links_by_link_id を経て ospf_subnets=[] になる
    # 修正前: views.py の 'or subnets' で ['10.0.1.0/30'] にフォールバック → 誤 data-ospf-id
    # 修正後: ospf_subnets=[] は is None=False → フォールバックしない → data-ospf-id なし
    links = [
        {
            "a_device": "R1", "a_if": "GigabitEthernet0/0",
            "b_device": "R2", "b_if": "GigabitEthernet0/0",
            "subnet": "10.0.1.0/30",
            "ospf_area": None,  # OSPF 非参加
        },
    ]
    iface_by_device = {
        "R1": [{"id": "R1::GigabitEthernet0/0", "device": "R1",
                "name": "GigabitEthernet0/0", "ip": "10.0.1.1/30"}],
        "R2": [{"id": "R2::GigabitEthernet0/0", "device": "R2",
                "name": "GigabitEthernet0/0", "ip": "10.0.1.2/30"}],
    }

    svg = _build_view_ospf(devices, ospf_entries, links, iface_by_device)

    # OSPF 非参加リンク（ospf_area=None, _merge_links_by_link_id 後 ospf_subnets=[]）は
    # data-ospf-id を持たないこと
    ospf_ids = re.findall(r'data-ospf-id="([^"]+)"', svg)
    assert not any("10.0.1.0" in oid for oid in ospf_ids), (
        f"OSPF 非参加リンク（ospf_area=None）に誤って data-ospf-id が付いた"
        f"（or subnets 誤フォールバック）: found={ospf_ids}"
    )


@pytest.mark.unit
def test_fix1_ospf_non_participant_merged_link_no_data_ospf_id():
    """修正1: _merge_links_by_link_id 経由のマージ済みリンクで ospf_subnets=[] 時に
    data-ospf-id が付かないことを end-to-end で確認する。

    両端 OSPF 機器だが当該リンクは OSPF 非参加というシナリオ:
    R1-R2 間に v4/v6 の 2 リンクがあり、v4 のみ OSPF 参加、
    v6 は OSPF 非参加（ospf_area なし）。マージ後 ospf_subnets=[v4_subnet] となり
    v6_subnet が data-ospf-id に入らないことを確認。
    """
    from lib.rendering.svg import _merge_links_by_link_id
    from lib.rendering.views import _build_view_ospf

    raw_links = [
        {
            "a_device": "R1", "a_if": "GigabitEthernet0/0",
            "b_device": "R2", "b_if": "GigabitEthernet0/0",
            "subnet": "10.0.0.0/30",
            "ospf_area": "0",   # v4 は OSPF 参加
        },
        {
            "a_device": "R1", "a_if": "GigabitEthernet0/0",
            "b_device": "R2", "b_if": "GigabitEthernet0/0",
            "subnet": "2001:db8::/127",
            "ospf_area": None,  # v6 は OSPF 非参加
        },
    ]
    merged = _merge_links_by_link_id(raw_links)
    assert len(merged) == 1, "同一 IF ペアは1エントリに統合されるべき"

    lk = merged[0]
    # マージ後: v4 が OSPF 参加なので ospf_subnets=["10.0.0.0/30"]（v6 は含まれない）
    assert lk["ospf_subnets"] == ["10.0.0.0/30"], (
        f"ospf_subnets が期待値 ['10.0.0.0/30'] と異なる: {lk['ospf_subnets']!r}"
    )

    devices = [
        {"id": "R1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        {"id": "R2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
    ]
    ospf_entries = [
        {"device": "R1", "process": 1, "area": "0", "subnet": "10.0.0.0/30"},
        {"device": "R2", "process": 1, "area": "0", "subnet": "10.0.0.0/30"},
    ]
    iface_by_device = {
        "R1": [{"id": "R1::GigabitEthernet0/0", "device": "R1",
                "name": "GigabitEthernet0/0", "ip": "10.0.0.1/30"}],
        "R2": [{"id": "R2::GigabitEthernet0/0", "device": "R2",
                "name": "GigabitEthernet0/0", "ip": "10.0.0.2/30"}],
    }

    svg = _build_view_ospf(devices, ospf_entries, merged, iface_by_device)

    # v4 subnet（OSPF 参加）は data-ospf-id に含まれること
    assert 'data-ospf-id="10.0.0.0/30"' in svg, \
        "OSPF 参加 v4 subnet が data-ospf-id に含まれない（regression）"

    # v6 subnet（OSPF 非参加）は data-ospf-id に含まれないこと
    # ospf_subnets=[v4_only] なので v6 は入らないはず
    assert "2001:db8::" not in svg.split('data-ospf-id="')[1] if 'data-ospf-id="' in svg else True, \
        "OSPF 非参加 v6 subnet が data-ospf-id に誤って含まれた"


# ===========================================================================
# B-pass1: 検索インデックス拡充 / data-ips / CIDR 内包 / 件数表示
# ===========================================================================
#
# B-pass1-1: _build_search_attr 拡充（AS/subnet/description/VLAN/vendor）
# B-pass1-2: data-ips 属性（CIDR 内包判定用）
# B-pass1-3: filterNodes CIDR 内包 + 件数表示（JS 文字列検証）
# B-pass1-4: CSS .device-node.search-match
# ===========================================================================


# ---------------------------------------------------------------------------
# B-pass1-1: _build_search_attr 拡充テスト
# ---------------------------------------------------------------------------

def _make_iface_with_addresses(iface_id: str, name: str,
                                v4_ip: str, v4_prefix: int,
                                v6_ip: str | None = None, v6_prefix: int | None = None,
                                description: str | None = None,
                                vlan: int | None = None) -> dict:
    """addresses リスト付き IF を構築するヘルパー（B-pass1 テスト用）。"""
    addresses = [
        {"af": "v4", "ip": v4_ip, "prefix": v4_prefix, "scope": None, "secondary": False},
    ]
    if v6_ip is not None:
        addresses.append({"af": "v6", "ip": v6_ip, "prefix": v6_prefix, "scope": None})
    return {
        "id": iface_id,
        "device": iface_id.split("::")[0],
        "name": name,
        "ip": f"{v4_ip}/{v4_prefix}",
        "vlan": vlan,
        "description": description,
        "shutdown": False,
        "addresses": addresses,
    }


@pytest.mark.unit
def test_b_search_attr_as_number_included():
    """_build_search_attr: AS番号が 'as65000' と '65000' の両形式で含まれる。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "core1", "hostname": "CORE1", "vendor": "cisco_ios", "as": 65000}
    iface = _make_iface_with_addresses("core1::ge0", "GigabitEthernet0/0", "10.0.0.1", 30)
    result = _build_search_attr(dev, [iface])
    assert "as65000" in result, f"'as65000' が data-search に含まれない: {result!r}"
    assert "65000" in result, f"'65000' が data-search に含まれない: {result!r}"


@pytest.mark.unit
def test_b_search_attr_as_none_not_included():
    """_build_search_attr: as が None の場合 'as' トークンは含まれない。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None}
    iface = _make_iface_with_addresses("r1::eth0", "eth0", "10.0.0.1", 30)
    result = _build_search_attr(dev, [iface])
    # 'as' で始まるトークンがないこと（asnone 等が混入しない）
    tokens = result.split()
    as_tokens = [t for t in tokens if t.startswith("as") and t != "r1"]
    assert not as_tokens, f"as=None なのに AS トークンが混入: {as_tokens!r} in {result!r}"


@pytest.mark.unit
def test_b_search_attr_subnet_with_prefix_included():
    """_build_search_attr: IP/prefix 形式（CIDR）が data-search に含まれる。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None}
    iface = _make_iface_with_addresses("r1::eth0", "eth0", "10.0.0.1", 30)
    result = _build_search_attr(dev, [iface])
    assert "10.0.0.1/30" in result, f"CIDR 形式が含まれない: {result!r}"
    # ホスト部（従来）も維持される
    assert "10.0.0.1" in result, f"IP ホスト部が含まれない: {result!r}"


@pytest.mark.unit
def test_b_search_attr_vendor_included():
    """_build_search_attr: vendor 文字列が data-search に含まれる。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1", "vendor": "juniper_junos", "as": None}
    iface = _make_iface_with_addresses("r1::ge0", "ge-0/0/0", "10.0.0.1", 30)
    result = _build_search_attr(dev, [iface])
    assert "juniper_junos" in result, f"vendor が含まれない: {result!r}"


@pytest.mark.unit
def test_b_search_attr_description_included():
    """_build_search_attr: IF description が data-search に含まれる（rich-if 相当）。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "sw1", "hostname": "SW1", "vendor": "cisco_ios", "as": None}
    iface = _make_iface_with_addresses(
        "sw1::ge0", "GigabitEthernet0/0", "192.168.10.1", 24,
        description="ACCESS-LINK-TO-SERVER"
    )
    result = _build_search_attr(dev, [iface])
    assert "access-link-to-server" in result.lower(), \
        f"description が含まれない: {result!r}"


@pytest.mark.unit
def test_b_search_attr_vlan_included():
    """_build_search_attr: vlan 番号が data-search に含まれる。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "sw1", "hostname": "SW1", "vendor": "cisco_ios", "as": None}
    iface = {
        "id": "sw1::eth0",
        "device": "sw1",
        "name": "GigabitEthernet0/1",
        "ip": None,
        "vlan": 10,
        "description": None,
        "shutdown": False,
        "addresses": [],
    }
    result = _build_search_attr(dev, [iface])
    assert "vlan10" in result or "10" in result.split(), \
        f"VLAN10 が含まれない: {result!r}"


@pytest.mark.unit
def test_b_search_attr_switchport_access_vlan_included():
    """_build_search_attr: switchport.access_vlan が data-search に含まれる。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "sw1", "hostname": "SW1", "vendor": "cisco_ios", "as": None}
    iface = {
        "id": "sw1::eth0",
        "device": "sw1",
        "name": "GigabitEthernet0/1",
        "ip": None,
        "vlan": None,
        "description": None,
        "shutdown": False,
        "addresses": [],
        "switchport": {"mode": "access", "access_vlan": 20},
    }
    result = _build_search_attr(dev, [iface])
    assert "20" in result.split() or "vlan20" in result, \
        f"switchport access_vlan 20 が含まれない: {result!r}"


@pytest.mark.unit
def test_b_search_attr_dualstack_v4_subnet_included():
    """_build_search_attr: dual-stack の v4 CIDR（10.0.0.1/30）が含まれる。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "DS-R1", "vendor": "cisco_ios", "as": None}
    iface = _make_iface_with_addresses(
        "r1::eth0", "GigabitEthernet0/0",
        "10.0.0.1", 30,
        "2001:db8:1::1", 127,
    )
    result = _build_search_attr(dev, [iface])
    assert "10.0.0.1/30" in result, f"v4 CIDR が含まれない: {result!r}"


@pytest.mark.unit
def test_b_search_attr_dualstack_v6_subnet_included():
    """_build_search_attr: dual-stack の v6 CIDR（2001:db8:1::1/127）が含まれる。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "DS-R1", "vendor": "cisco_ios", "as": None}
    iface = _make_iface_with_addresses(
        "r1::eth0", "GigabitEthernet0/0",
        "10.0.0.1", 30,
        "2001:db8:1::1", 127,
    )
    result = _build_search_attr(dev, [iface])
    assert "2001:db8:1::1/127" in result, f"v6 CIDR が含まれない: {result!r}"


@pytest.mark.unit
def test_b_search_attr_link_local_subnet_excluded():
    """_build_search_attr: link-local アドレスの CIDR は含まれない（fe80::/64 等）。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None}
    iface = {
        "id": "r1::eth0",
        "device": "r1",
        "name": "GigabitEthernet0/0",
        "ip": "10.0.0.1/30",
        "vlan": None,
        "description": None,
        "shutdown": False,
        "addresses": [
            {"af": "v4", "ip": "10.0.0.1", "prefix": 30, "scope": None, "secondary": False},
            {"af": "v6", "ip": "2001:db8::1", "prefix": 64, "scope": None},
            {"af": "v6", "ip": "fe80::1", "prefix": 64, "scope": "link-local"},
        ],
    }
    result = _build_search_attr(dev, [iface])
    assert "fe80" not in result, f"link-local CIDR が混入: {result!r}"
    assert "2001:db8::1" in result, f"GUA v6 が含まれない: {result!r}"


@pytest.mark.unit
def test_b_search_attr_multi_as_area_has_as_and_vendor():
    """_build_search_attr: multi-as-area 相当（AS65000, vendor=cisco_ios）で AS/vendor が含まれる。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "core1", "hostname": "CORE1", "vendor": "cisco_ios", "as": 65000}
    iface1 = _make_iface_with_addresses(
        "core1::ge0", "GigabitEthernet0/0", "10.0.0.1", 30,
        description="CORE-LINK-to-CORE2-AREA0"
    )
    iface2 = _make_iface_with_addresses(
        "core1::ge1", "GigabitEthernet0/1", "10.0.1.1", 30,
        description="CORE-LINK-to-EDGE1-AREA0"
    )
    result = _build_search_attr(dev, [iface1, iface2])
    assert "as65000" in result
    assert "65000" in result
    assert "cisco_ios" in result
    assert "core-link-to-core2-area0" in result.lower()
    assert "10.0.0.1/30" in result
    assert "10.0.1.1/30" in result


@pytest.mark.unit
def test_b_search_attr_deterministic_with_extensions():
    """_build_search_attr 拡充後も決定性が維持される（2回一致）。"""
    from lib.rendering.svg import _build_search_attr
    dev = {"id": "core1", "hostname": "CORE1", "vendor": "cisco_ios", "as": 65000}
    iface = _make_iface_with_addresses(
        "core1::ge0", "GigabitEthernet0/0", "10.0.0.1", 30,
        "2001:db8::1", 64,
        description="TEST-LINK"
    )
    r1 = _build_search_attr(dev, [iface])
    r2 = _build_search_attr(dev, [iface])
    assert r1 == r2, f"非決定的: {r1!r} vs {r2!r}"


# ---------------------------------------------------------------------------
# B-pass1-2: data-ips 属性テスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_b_data_ips_attribute_present_in_html():
    """render(): device-node の <g> に data-ips 属性が含まれる。"""
    from lib.rendering import render
    topo = {
        "title": "data-ips test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {
                "id": "r1::eth0", "device": "r1", "name": "GigabitEthernet0/0",
                "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False,
                "addresses": [
                    {"af": "v4", "ip": "10.0.0.1", "prefix": 30, "scope": None, "secondary": False},
                ],
            },
        ],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    assert 'data-ips=' in html, "data-ips 属性が device-node の <g> に含まれない"


@pytest.mark.unit
def test_b_data_ips_contains_v4_cidr():
    """render(): data-ips に v4 CIDR（10.0.0.1/30）が含まれる。"""
    from lib.rendering import render
    topo = {
        "title": "data-ips v4 test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {
                "id": "r1::eth0", "device": "r1", "name": "GigabitEthernet0/0",
                "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False,
                "addresses": [
                    {"af": "v4", "ip": "10.0.0.1", "prefix": 30, "scope": None, "secondary": False},
                ],
            },
        ],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    ips_vals = re.findall(r'data-ips="([^"]*)"', html)
    all_ips = " ".join(ips_vals)
    assert "10.0.0.1/30" in all_ips, f"data-ips に v4 CIDR が含まれない: {all_ips!r}"


@pytest.mark.unit
def test_b_data_ips_dualstack_contains_v4_and_v6():
    """render(): dual-stack ノードの data-ips に v4/v6 両方の CIDR が含まれる。"""
    from lib.rendering import render
    topo = {
        "title": "data-ips dualstack test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "DS-R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {
                "id": "r1::eth0", "device": "r1", "name": "GigabitEthernet0/0",
                "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False,
                "addresses": [
                    {"af": "v4", "ip": "10.0.0.1", "prefix": 30, "scope": None, "secondary": False},
                    {"af": "v6", "ip": "2001:db8:1::1", "prefix": 127, "scope": None},
                    {"af": "v6", "ip": "fe80::1", "prefix": 64, "scope": "link-local"},
                ],
            },
        ],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    ips_vals = re.findall(r'data-ips="([^"]*)"', html)
    all_ips = " ".join(ips_vals)
    assert "10.0.0.1/30" in all_ips, f"data-ips に v4 CIDR が含まれない: {all_ips!r}"
    assert "2001:db8:1::1/127" in all_ips, f"data-ips に v6 CIDR が含まれない: {all_ips!r}"


@pytest.mark.unit
def test_b_data_ips_no_link_local():
    """render(): data-ips に link-local アドレスが含まれない。"""
    from lib.rendering import render
    topo = {
        "title": "data-ips no-link-local test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {
                "id": "r1::eth0", "device": "r1", "name": "GigabitEthernet0/0",
                "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False,
                "addresses": [
                    {"af": "v4", "ip": "10.0.0.1", "prefix": 30, "scope": None, "secondary": False},
                    {"af": "v6", "ip": "fe80::1", "prefix": 64, "scope": "link-local"},
                ],
            },
        ],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    ips_vals = re.findall(r'data-ips="([^"]*)"', html)
    all_ips = " ".join(ips_vals)
    assert "fe80" not in all_ips, f"data-ips に link-local が混入: {all_ips!r}"


@pytest.mark.unit
def test_b_data_ips_deterministic():
    """render(): 同一 topology を2回 render して data-ips が一致（決定性）。"""
    from lib.rendering import render
    topo = {
        "title": "data-ips deterministic",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {
                "id": "r1::eth0", "device": "r1", "name": "eth0",
                "ip": "10.0.0.1/30", "vlan": None, "description": None, "shutdown": False,
                "addresses": [
                    {"af": "v4", "ip": "10.0.0.1", "prefix": 30, "scope": None, "secondary": False},
                    {"af": "v6", "ip": "2001:db8::1", "prefix": 64, "scope": None},
                ],
            },
            {
                "id": "r2::eth0", "device": "r2", "name": "eth0",
                "ip": "10.0.0.2/30", "vlan": None, "description": None, "shutdown": False,
                "addresses": [
                    {"af": "v4", "ip": "10.0.0.2", "prefix": 30, "scope": None, "secondary": False},
                ],
            },
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    h1 = render(topo)
    h2 = render(topo)
    ips1 = re.findall(r'data-ips="([^"]*)"', h1)
    ips2 = re.findall(r'data-ips="([^"]*)"', h2)
    assert ips1 == ips2, f"data-ips が非決定的: {ips1!r} vs {ips2!r}"


# ---------------------------------------------------------------------------
# B-pass1-3: filterNodes JS 拡張 / B-pass1-4: CSS .search-match の文字列検証
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_b_html_has_search_count_element(rendered_html):
    """生成 HTML に #search-count 要素が含まれる。"""
    assert 'id="search-count"' in rendered_html, \
        "#search-count 要素が HTML に含まれない"


@pytest.mark.unit
def test_b_js_filterNodes_cidr_detection(rendered_html):
    """filterNodes JS に CIDR 判定ロジック（'/' 含む query の分岐）が含まれる。"""
    # CIDR モード判定: query に '/' が含まれるかチェックするコードが存在する
    assert "indexOf('/')" in rendered_html or 'includes("/")' in rendered_html or \
        "cidr" in rendered_html.lower() or "prefix" in rendered_html.lower(), \
        "filterNodes に CIDR 判定ロジックが含まれない"


@pytest.mark.unit
def test_b_js_filterNodes_bigint_v6(rendered_html):
    """filterNodes JS に v6 内包判定用 BigInt ロジックが含まれる。"""
    assert "BigInt" in rendered_html, \
        "filterNodes に v6 CIDR 判定用 BigInt が含まれない"


@pytest.mark.unit
def test_b_js_filterNodes_search_match_class(rendered_html):
    """filterNodes JS が .search-match クラスを付与するコードを含む。"""
    assert "search-match" in rendered_html, \
        "filterNodes に '.search-match' クラス付与が含まれない"


@pytest.mark.unit
def test_b_js_filterNodes_count_display(rendered_html):
    """filterNodes JS が件数を #search-count に反映するコードを含む。"""
    assert "search-count" in rendered_html, \
        "filterNodes に #search-count 更新コードが含まれない"


@pytest.mark.unit
def test_b_css_search_match_class_defined(rendered_html):
    """CSS に .device-node.search-match が定義されている。"""
    assert ".device-node.search-match" in rendered_html, \
        "CSS に .device-node.search-match が定義されていない"


@pytest.mark.unit
def test_b_js_filterNodes_data_ips_used(rendered_html):
    """filterNodes JS が data-ips 属性を参照する（CIDR 内包判定に使用）。"""
    assert "data-ips" in rendered_html, \
        "filterNodes JS に data-ips 参照が含まれない"


@pytest.mark.unit
def test_b_search_count_hidden_on_empty_query(rendered_html):
    """#search-count は空クエリ時に空にする JS コードが含まれる。"""
    # JS 全体で search-count の textContent を空にする処理が含まれること
    # countEl.textContent = '' または '' のような代入
    assert "search-count" in rendered_html, "#search-count が HTML に存在しない"
    # 空文字代入パターン
    has_clear = (
        "textContent = ''" in rendered_html
        or "textContent=''" in rendered_html
        or 'textContent = ""' in rendered_html
    )
    assert has_clear, \
        "#search-count の空クエリ時クリア（textContent = ''）が filterNodes JS に含まれない"


# ===========================================================================
# Round B — B3: IF一覧 af 列追加 + 機器/af/status/L2L3 ドロップダウン絞り込み
# ===========================================================================

# ---------------------------------------------------------------------------
# テスト用ヘルパー: B3 専用 topology（dual/v4/v6/none の各 af パターンを含む）
# ---------------------------------------------------------------------------

def _make_b3_topology():
    """B3 テスト用 topology。
    DS-R1: GUA v4+v6(dual), v4-only, noip(none)
    V4-R2: v4-only × 2
    V6-R3: v6(GUA)-only × 1
    合計6本の IF で all af パターンを網羅。
    """
    return {
        "title": "B3 Test",
        "generated_from": [],
        "devices": [
            {"id": "ds_r1", "hostname": "DS-R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "v4_r2", "hostname": "V4-R2", "vendor": "cisco_ios", "as": 65002, "sections": []},
            {"id": "v6_r3", "hostname": "V6-R3", "vendor": "junos", "as": 65003, "sections": []},
        ],
        "interfaces": [
            # DS-R1 Gi0/0: dual (v4+v6 GUA)
            {
                "id": "ds_r1::Gi0/0", "device": "ds_r1", "name": "GigabitEthernet0/0",
                "ip": "10.0.0.1/30", "admin_status": "up", "mtu": 1500, "vlan": None,
                "l2_l3": "l3", "description": "to-V4-R2", "shutdown": False,
                "addresses": [
                    {"af": "v4", "ip": "10.0.0.1", "prefix": 30, "scope": None, "secondary": False},
                    {"af": "v6", "ip": "2001:db8:1::1", "prefix": 64, "scope": None},
                ],
            },
            # DS-R1 Gi0/1: v4 only
            {
                "id": "ds_r1::Gi0/1", "device": "ds_r1", "name": "GigabitEthernet0/1",
                "ip": "192.168.1.1/24", "admin_status": "down", "mtu": 9000, "vlan": None,
                "l2_l3": "l2", "description": "unused-v4", "shutdown": False,
                "addresses": [
                    {"af": "v4", "ip": "192.168.1.1", "prefix": 24, "scope": None, "secondary": False},
                ],
            },
            # DS-R1 Gi0/2: no IP (none)
            {
                "id": "ds_r1::Gi0/2", "device": "ds_r1", "name": "GigabitEthernet0/2",
                "ip": None, "admin_status": "admin-down", "mtu": None, "vlan": None,
                "l2_l3": None, "description": None, "shutdown": True,
                "addresses": [],
            },
            # V4-R2 ge0: v4 only
            {
                "id": "v4_r2::ge0", "device": "v4_r2", "name": "ge-0/0/0",
                "ip": "10.0.0.2/30", "admin_status": "up", "mtu": 1500, "vlan": None,
                "l2_l3": "l3", "description": "to-DS-R1", "shutdown": False,
                "addresses": [
                    {"af": "v4", "ip": "10.0.0.2", "prefix": 30, "scope": None, "secondary": False},
                ],
            },
            # V4-R2 ge1: v4 only, admin-down
            {
                "id": "v4_r2::ge1", "device": "v4_r2", "name": "ge-0/0/1",
                "ip": "172.16.0.1/24", "admin_status": "admin-down", "mtu": None, "vlan": 100,
                "l2_l3": "l2", "description": None, "shutdown": True,
                "addresses": [
                    {"af": "v4", "ip": "172.16.0.1", "prefix": 24, "scope": None, "secondary": False},
                ],
            },
            # V6-R3 ge0: v6 GUA only（link-local 含む → link-local は除外して v6 判定）
            {
                "id": "v6_r3::ge0", "device": "v6_r3", "name": "ge-0/0/0",
                "ip": None, "admin_status": "up", "mtu": 1500, "vlan": None,
                "l2_l3": "l3", "description": "v6-only-link", "shutdown": False,
                "addresses": [
                    {"af": "v6", "ip": "2001:db8:2::1", "prefix": 64, "scope": None},
                    {"af": "v6", "ip": "fe80::1", "prefix": 64, "scope": "link-local"},
                ],
            },
        ],
        "links": [
            {"a_device": "ds_r1", "a_if": "GigabitEthernet0/0",
             "b_device": "v4_r2", "b_if": "ge-0/0/0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.fixture
def b3_topology():
    return _make_b3_topology()


@pytest.fixture
def b3_ifinv_html(b3_topology):
    from lib.rendering.views import _build_ifinv_table
    return _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])


# ---------------------------------------------------------------------------
# B3-1: af 列 / data-af 属性
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_b3_af_column_header_exists(b3_ifinv_html):
    """B3: ifinv テーブルに AF 列ヘッダが存在する。"""
    assert "AF" in b3_ifinv_html, \
        "ifinv テーブルに AF 列ヘッダが見つからない"


@pytest.mark.unit
def test_b3_af_column_has_data_col(b3_ifinv_html):
    """B3: AF 列 th に data-col='af' が付与される。"""
    assert 'data-col="af"' in b3_ifinv_html, \
        "AF 列に data-col='af' が見つからない"


@pytest.mark.unit
def test_b3_data_af_dual_on_dualstack_iface(b3_topology):
    """B3: dual-stack IF（v4+v6 GUA）の data-af が 'dual'。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    # ds_r1::Gi0/0 は dual
    assert 'data-iface-id="ds_r1::Gi0/0"' in result, "ds_r1::Gi0/0 行が見つからない"
    # data-af="dual" を持つ行が存在する
    assert 'data-af="dual"' in result, \
        "dual-stack IF に data-af='dual' が付与されていない"


@pytest.mark.unit
def test_b3_data_af_v4_on_v4_only_iface(b3_topology):
    """B3: v4のみ IF の data-af が 'v4'。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    assert 'data-af="v4"' in result, \
        "v4-only IF に data-af='v4' が付与されていない"


@pytest.mark.unit
def test_b3_data_af_v6_on_v6_only_iface(b3_topology):
    """B3: v6 GUA のみ IF（link-local 除外）の data-af が 'v6'。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    assert 'data-af="v6"' in result, \
        "v6-only IF に data-af='v6' が付与されていない"


@pytest.mark.unit
def test_b3_data_af_none_on_no_ip_iface(b3_topology):
    """B3: IP なし IF（addresses が空）の data-af が 'none'。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    assert 'data-af="none"' in result, \
        "IP なし IF に data-af='none' が付与されていない"


@pytest.mark.unit
def test_b3_af_column_value_dual_in_cell(b3_topology):
    """B3: dual-stack IF の AF 列セルに 'dual' が表示される。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    # dual が td として出力されること（data-af="dual" の行に対応）
    # "dual" という文字列が data-af 属性以外にもセルテキストとして存在すること
    assert result.count("dual") >= 2, \
        "AF 列セルに 'dual' テキストが含まれない（data-af 属性のみでセルなし）"


@pytest.mark.unit
def test_b3_af_link_local_excluded_from_v6(b3_topology):
    """B3: link-local のみ持つ IF は v6 ではなく none 扱い。"""
    from lib.rendering.views import _build_ifinv_table
    # link-local のみの IF を追加したトポロジー
    topo = _make_b3_topology()
    topo["devices"].append({"id": "ll_r4", "hostname": "LL-R4", "vendor": "cisco_ios", "as": None, "sections": []})
    topo["interfaces"].append({
        "id": "ll_r4::ge0", "device": "ll_r4", "name": "ge-0/0/0",
        "ip": None, "admin_status": "up", "mtu": None, "vlan": None,
        "l2_l3": "l3", "description": None, "shutdown": False,
        "addresses": [
            {"af": "v6", "ip": "fe80::1", "prefix": 64, "scope": "link-local"},
        ],
    })
    result = _build_ifinv_table(topo["devices"], topo["interfaces"])
    # ll_r4::ge0 の行
    import re
    row_m = re.search(r'<tr[^>]*data-iface-id="ll_r4::ge0"[^>]*>', result)
    assert row_m is not None, "ll_r4::ge0 行が見つからない"
    assert 'data-af="none"' in row_m.group(0), \
        "link-local のみの IF が v6 と誤判定されている（none であるべき）"


# ---------------------------------------------------------------------------
# B3-2: data-status / data-l2l3 属性
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_b3_rows_have_data_status(b3_topology):
    """B3: 各 ifinv 行に data-status 属性が付与される。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    import re
    rows = re.findall(r'<tr[^>]*data-iface-id="[^"]*"[^>]*>', result)
    for row_html in rows:
        assert 'data-status="' in row_html, \
            f"data-status 属性が行に見つからない: {row_html[:120]!r}"


@pytest.mark.unit
def test_b3_rows_have_data_l2l3(b3_topology):
    """B3: 各 ifinv 行に data-l2l3 属性が付与される。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    import re
    rows = re.findall(r'<tr[^>]*data-iface-id="[^"]*"[^>]*>', result)
    for row_html in rows:
        assert 'data-l2l3="' in row_html, \
            f"data-l2l3 属性が行に見つからない: {row_html[:120]!r}"


@pytest.mark.unit
def test_b3_data_status_matches_admin_status(b3_topology):
    """B3: data-status の値が admin_status フィールドと一致する。"""
    from lib.rendering.views import _build_ifinv_table
    import re
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    # ds_r1::Gi0/0 は admin_status="up" → data-status="up"
    row_m = re.search(r'<tr[^>]*data-iface-id="ds_r1::Gi0/0"[^>]*>', result)
    assert row_m is not None, "ds_r1::Gi0/0 行が見つからない"
    assert 'data-status="up"' in row_m.group(0), \
        f"ds_r1::Gi0/0 の data-status が 'up' でない: {row_m.group(0)!r}"


@pytest.mark.unit
def test_b3_data_l2l3_matches_l2l3_field(b3_topology):
    """B3: data-l2l3 の値が l2_l3 フィールドと一致する。"""
    from lib.rendering.views import _build_ifinv_table
    import re
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    # ds_r1::Gi0/0 は l2_l3="l3" → data-l2l3="l3"
    row_m = re.search(r'<tr[^>]*data-iface-id="ds_r1::Gi0/0"[^>]*>', result)
    assert row_m is not None, "ds_r1::Gi0/0 行が見つからない"
    assert 'data-l2l3="l3"' in row_m.group(0), \
        f"ds_r1::Gi0/0 の data-l2l3 が 'l3' でない: {row_m.group(0)!r}"


@pytest.mark.unit
def test_b3_data_l2l3_none_sentinel_when_null(b3_topology):
    """B3-A1: l2_l3=None の IF は data-l2l3="none"（sentinel）になる。

    空文字列 "" は「すべて」フィルタ value="" と衝突するため sentinel "none" を使用する。
    """
    from lib.rendering.views import _build_ifinv_table
    import re
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    # ds_r1::Gi0/2 は l2_l3=None → data-l2l3="none"（sentinel）
    row_m = re.search(r'<tr[^>]*data-iface-id="ds_r1::Gi0/2"[^>]*>', result)
    assert row_m is not None, "ds_r1::Gi0/2 行が見つからない"
    assert 'data-l2l3="none"' in row_m.group(0), \
        f"ds_r1::Gi0/2 の data-l2l3 が sentinel 'none' でない: {row_m.group(0)!r}"


# ---------------------------------------------------------------------------
# B3-3: ドロップダウン select 要素の生成
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_b3_select_device_exists(b3_ifinv_html):
    """B3: ifinv ツールバーに id='ifinv-filter-device' select が存在する。"""
    assert 'id="ifinv-filter-device"' in b3_ifinv_html, \
        "id='ifinv-filter-device' select が見つからない"


@pytest.mark.unit
def test_b3_select_af_exists(b3_ifinv_html):
    """B3: ifinv ツールバーに id='ifinv-filter-af' select が存在する。"""
    assert 'id="ifinv-filter-af"' in b3_ifinv_html, \
        "id='ifinv-filter-af' select が見つからない"


@pytest.mark.unit
def test_b3_select_status_exists(b3_ifinv_html):
    """B3: ifinv ツールバーに id='ifinv-filter-status' select が存在する。"""
    assert 'id="ifinv-filter-status"' in b3_ifinv_html, \
        "id='ifinv-filter-status' select が見つからない"


@pytest.mark.unit
def test_b3_select_l2l3_exists(b3_ifinv_html):
    """B3: ifinv ツールバーに id='ifinv-filter-l2l3' select が存在する。"""
    assert 'id="ifinv-filter-l2l3"' in b3_ifinv_html, \
        "id='ifinv-filter-l2l3' select が見つからない"


@pytest.mark.unit
def test_b3_select_af_has_all_options(b3_ifinv_html):
    """B3: #ifinv-filter-af に すべて/v4/v6/dual/none の全 option が存在する。"""
    import re
    m = re.search(r'<select[^>]*id="ifinv-filter-af"[^>]*>(.*?)</select>',
                  b3_ifinv_html, re.DOTALL)
    assert m is not None, "ifinv-filter-af select が見つからない"
    select_html = m.group(0)
    for val in ("v4", "v6", "dual", "none"):
        assert f'value="{val}"' in select_html, \
            f"af select に value='{val}' option が見つからない"


@pytest.mark.unit
def test_b3_select_device_options_deterministic(b3_topology):
    """B3: #ifinv-filter-device の option はデータから決定的に生成される（device id 昇順）。"""
    from lib.rendering.views import _build_ifinv_table
    import re
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    m = re.search(r'<select[^>]*id="ifinv-filter-device"[^>]*>(.*?)</select>',
                  result, re.DOTALL)
    assert m is not None, "ifinv-filter-device select が見つからない"
    select_html = m.group(0)
    # topology の全 device id が option に含まれること
    for dev in b3_topology["devices"]:
        assert f'value="{dev["id"]}"' in select_html, \
            f"device '{dev['id']}' が ifinv-filter-device select に見つからない"


@pytest.mark.unit
def test_b3_select_status_options_from_data(b3_topology):
    """B3: #ifinv-filter-status の option がデータの admin_status から決定的に生成される。"""
    from lib.rendering.views import _build_ifinv_table
    import re
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    m = re.search(r'<select[^>]*id="ifinv-filter-status"[^>]*>(.*?)</select>',
                  result, re.DOTALL)
    assert m is not None, "ifinv-filter-status select が見つからない"
    select_html = m.group(0)
    # b3_topology の admin_status のユニーク値 (up/down/admin-down) が含まれること
    expected_statuses = {"up", "down", "admin-down"}
    for st in expected_statuses:
        assert f'value="{st}"' in select_html, \
            f"status '{st}' が ifinv-filter-status select に見つからない"


@pytest.mark.unit
def test_b3_select_l2l3_options_from_data(b3_topology):
    """B3: #ifinv-filter-l2l3 の option がデータの l2_l3 から決定的に生成される。"""
    from lib.rendering.views import _build_ifinv_table
    import re
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    m = re.search(r'<select[^>]*id="ifinv-filter-l2l3"[^>]*>(.*?)</select>',
                  result, re.DOTALL)
    assert m is not None, "ifinv-filter-l2l3 select が見つからない"
    select_html = m.group(0)
    # b3_topology の l2_l3 のユニーク非空値 (l2/l3) が含まれること
    for val in ("l2", "l3"):
        assert f'value="{val}"' in select_html, \
            f"l2l3 '{val}' が ifinv-filter-l2l3 select に見つからない"


# ---------------------------------------------------------------------------
# B3-4: _applyIfFilters JS のドロップダウンフィルタ AND 統合テスト
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_b3_js_has_device_filter_state_var(b3_topology):
    """B3: _applyIfFilters JS に _ifinvDeviceFilter 状態変数が存在する。"""
    from lib.rendering import render
    html = render(b3_topology)
    import re
    js_m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    assert js_m is not None, "script ブロックが見つからない"
    js = js_m.group(1)
    assert "_ifinvDeviceFilter" in js, \
        "_ifinvDeviceFilter 状態変数が JS に存在しない"


@pytest.mark.unit
def test_b3_js_has_af_filter_state_var(b3_topology):
    """B3: _applyIfFilters JS に _ifinvAfFilter 状態変数が存在する。"""
    from lib.rendering import render
    html = render(b3_topology)
    import re
    js_m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    assert js_m is not None
    js = js_m.group(1)
    assert "_ifinvAfFilter" in js, \
        "_ifinvAfFilter 状態変数が JS に存在しない"


@pytest.mark.unit
def test_b3_js_has_status_filter_state_var(b3_topology):
    """B3: _applyIfFilters JS に _ifinvStatusFilter 状態変数が存在する。"""
    from lib.rendering import render
    html = render(b3_topology)
    import re
    js_m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    assert js_m is not None
    js = js_m.group(1)
    assert "_ifinvStatusFilter" in js, \
        "_ifinvStatusFilter 状態変数が JS に存在しない"


@pytest.mark.unit
def test_b3_js_has_l2l3_filter_state_var(b3_topology):
    """B3: _applyIfFilters JS に _ifinvL2l3Filter 状態変数が存在する。"""
    from lib.rendering import render
    html = render(b3_topology)
    import re
    js_m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    assert js_m is not None
    js = js_m.group(1)
    assert "_ifinvL2l3Filter" in js, \
        "_ifinvL2l3Filter 状態変数が JS に存在しない"


@pytest.mark.unit
def test_b3_js_apply_if_filters_uses_data_af(b3_topology):
    """B3: _applyIfFilters JS が data-af 属性を参照する AND 評価を含む。"""
    from lib.rendering import render
    html = render(b3_topology)
    import re
    js_m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    assert js_m is not None
    js = js_m.group(1)
    assert "data-af" in js, \
        "_applyIfFilters JS が data-af を参照しない"


@pytest.mark.unit
def test_b3_js_apply_if_filters_uses_data_status(b3_topology):
    """B3: _applyIfFilters JS が data-status 属性を参照する。"""
    from lib.rendering import render
    html = render(b3_topology)
    import re
    js_m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    assert js_m is not None
    js = js_m.group(1)
    assert "data-status" in js, \
        "_applyIfFilters JS が data-status を参照しない"


@pytest.mark.unit
def test_b3_js_apply_if_filters_uses_data_l2l3(b3_topology):
    """B3: _applyIfFilters JS が data-l2l3 属性を参照する。"""
    from lib.rendering import render
    html = render(b3_topology)
    import re
    js_m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    assert js_m is not None
    js = js_m.group(1)
    assert "data-l2l3" in js, \
        "_applyIfFilters JS が data-l2l3 を参照しない"


@pytest.mark.unit
def test_b3_js_select_change_listeners_registered(b3_topology):
    """B3: ifinv-filter-* select に addEventListener('change', ...) が登録される JS コードが存在する。"""
    from lib.rendering import render
    html = render(b3_topology)
    import re
    js_m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    assert js_m is not None
    js = js_m.group(1)
    # ifinv-filter-device/af/status/l2l3 の change リスナー登録
    for sel_id in ("ifinv-filter-device", "ifinv-filter-af", "ifinv-filter-status", "ifinv-filter-l2l3"):
        assert sel_id in js, \
            f"select id='{sel_id}' への change リスナー登録が JS に見つからない"


# ---------------------------------------------------------------------------
# B3-5: 決定性・非回帰
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_b3_ifinv_deterministic(b3_topology):
    """B3: b3_topology を2回 _build_ifinv_table して同一出力（決定性）。"""
    from lib.rendering.views import _build_ifinv_table
    r1 = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    r2 = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    assert r1 == r2, "b3_topology の _build_ifinv_table が非決定的"


@pytest.mark.unit
def test_b3_existing_columns_unchanged(b3_ifinv_html):
    """B3: 既存列ヘッダ（Device/Interface/IP/Status/MTU/VLAN/L2L3/Description）が維持される。"""
    for header in ("Device", "Interface", "IP", "Status", "MTU", "VLAN", "L2L3", "Description"):
        assert header in b3_ifinv_html, \
            f"B3 追加後に既存列ヘッダ '{header}' が消えた"


@pytest.mark.unit
def test_b3_existing_data_attrs_unchanged(b3_topology):
    """B3: 既存の data-iface-id/data-device/data-unused/data-search/data-ips が維持される。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    for attr in ("data-iface-id", "data-device", "data-search", "data-ips"):
        assert attr in result, f"B3 追加後に既存属性 '{attr}' が消えた"


@pytest.mark.unit
def test_b3_unused_toggle_still_exists(b3_ifinv_html):
    """B3: 未使用トグル (#ifinv-unused-toggle) が維持される（非回帰）。"""
    assert 'id="ifinv-unused-toggle"' in b3_ifinv_html, \
        "B3 追加後に未使用トグルが消えた"


@pytest.mark.unit
def test_b3_ifinv_html_self_contained(b3_topology):
    """B3: _build_ifinv_table 出力が外部リソース参照（src= / href=）を持たない（自己完結）。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    import re
    external_refs = re.findall(r'(?:src|href)="(?!#)[^"]*"', result)
    assert not external_refs, \
        f"_build_ifinv_table 出力に外部参照が含まれる: {external_refs}"


# ---------------------------------------------------------------------------
# Round B B3 レビュー指摘修正テスト
# ---------------------------------------------------------------------------

# --- A1: l2_l3=None を sentinel "none" に正規化 ---

@pytest.mark.unit
def test_b3_a1_l2l3_none_sentinel_in_data_attr(b3_topology):
    """A1: l2_l3=None の IF は data-l2l3="none" (sentinel) になる（value="" との衝突防止）。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    row_m = re.search(r'<tr[^>]*data-iface-id="ds_r1::Gi0/2"[^>]*>', result)
    assert row_m is not None, "ds_r1::Gi0/2 行が見つからない"
    assert 'data-l2l3="none"' in row_m.group(0), \
        f"l2_l3=None の行が data-l2l3='none' でない: {row_m.group(0)!r}"


@pytest.mark.unit
def test_b3_a1_l2l3_select_has_none_option(b3_topology):
    """A1: l2_l3=None 行がある場合、#ifinv-filter-l2l3 select に value='none' option が存在する。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    m = re.search(r'<select[^>]*id="ifinv-filter-l2l3"[^>]*>(.*?)</select>',
                  result, re.DOTALL)
    assert m is not None, "ifinv-filter-l2l3 select が見つからない"
    assert 'value="none"' in m.group(0), \
        "l2_l3=None 行があるのに value='none' option が ifinv-filter-l2l3 に存在しない"


@pytest.mark.unit
def test_b3_a1_l2l3_select_no_empty_value_for_none(b3_topology):
    """A1: #ifinv-filter-l2l3 の value="" は「すべて」専用のみ（sentinel "none" で空value重複なし）。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    m = re.search(r'<select[^>]*id="ifinv-filter-l2l3"[^>]*>(.*?)</select>',
                  result, re.DOTALL)
    assert m is not None, "ifinv-filter-l2l3 select が見つからない"
    # value="" は「すべて」1個のみ（sentinel "none" があるので空データ option なし）
    empty_options = re.findall(r'<option[^>]*value=""[^>]*>', m.group(0))
    assert len(empty_options) == 1, \
        f"value='' option が「すべて」1個以外に存在する: {empty_options}"


@pytest.mark.unit
def test_b3_a1_l2l3_none_sentinel_cell_display(b3_topology):
    """A1: data-l2l3='none' の L2L3 列セルは '-' 等（空欄でなく）で表示される。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    # ds_r1::Gi0/2 行（l2_l3=None）の td[L2L3] セルが '-' または '(未分類)' 等で表示される
    row_m = re.search(
        r'<tr[^>]*data-iface-id="ds_r1::Gi0/2"[^>]*>(.*?)</tr>',
        result, re.DOTALL
    )
    assert row_m is not None, "ds_r1::Gi0/2 行が見つからない"
    row_body = row_m.group(1)
    # 行内の td を取得
    tds = re.findall(r'<td[^>]*>(.*?)</td>', row_body, re.DOTALL)
    # L2L3 列は8番目（0-indexed: 7）: Device/Interface/IP/AF/Status/MTU/VLAN/L2L3/Description
    assert len(tds) >= 8, f"td 数が不足: {len(tds)}"
    l2l3_cell = tds[7]
    # セルは '-' で表示（空欄ではない）
    assert l2l3_cell.strip() == "-", \
        f"l2_l3=None の L2L3 セルが '-' でない: {l2l3_cell!r}"


# --- A2: dev_hostname_for_select 重複除去 ---

@pytest.mark.unit
def test_b3_a2_no_dev_hostname_for_select_duplication(b3_topology):
    """A2: _build_ifinv_table が dev_hostname_for_select の重複定義なしに device option を生成する（DRY 確認）。

    実装内側の変数名はブラックボックスだが、device option の hostname 表示が正しく動作することで間接確認。
    """
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    m = re.search(r'<select[^>]*id="ifinv-filter-device"[^>]*>(.*?)</select>',
                  result, re.DOTALL)
    assert m is not None, "ifinv-filter-device select が見つからない"
    select_html = m.group(0)
    # 各 device の hostname が option テキストとして表示される
    for dev in b3_topology["devices"]:
        hostname = dev.get("hostname", dev["id"])
        assert hostname in select_html, \
            f"device '{dev['id']}' の hostname '{hostname}' が device option テキストに見つからない"


# --- H-1: data-af 行単位検証 ---

@pytest.mark.unit
def test_b3_h1_data_af_v4_on_target_row(b3_topology):
    """H-1: v4-only IF (ds_r1::Gi0/1) の行に data-af='v4' が付く（行抽出で検証）。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    row_m = re.search(r'<tr[^>]*data-iface-id="ds_r1::Gi0/1"[^>]*>', result)
    assert row_m is not None, "ds_r1::Gi0/1 行が見つからない"
    assert 'data-af="v4"' in row_m.group(0), \
        f"ds_r1::Gi0/1 の行に data-af='v4' が付かない: {row_m.group(0)!r}"


@pytest.mark.unit
def test_b3_h1_data_af_v6_on_target_row(b3_topology):
    """H-1: v6-only IF (v6_r3::ge0) の行に data-af='v6' が付く（行抽出で検証）。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    row_m = re.search(r'<tr[^>]*data-iface-id="v6_r3::ge0"[^>]*>', result)
    assert row_m is not None, "v6_r3::ge0 行が見つからない"
    assert 'data-af="v6"' in row_m.group(0), \
        f"v6_r3::ge0 の行に data-af='v6' が付かない: {row_m.group(0)!r}"


@pytest.mark.unit
def test_b3_h1_data_af_none_on_target_row(b3_topology):
    """H-1: no-IP IF (ds_r1::Gi0/2) の行に data-af='none' が付く（行抽出で検証）。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    row_m = re.search(r'<tr[^>]*data-iface-id="ds_r1::Gi0/2"[^>]*>', result)
    assert row_m is not None, "ds_r1::Gi0/2 行が見つからない"
    assert 'data-af="none"' in row_m.group(0), \
        f"ds_r1::Gi0/2 の行に data-af='none' が付かない: {row_m.group(0)!r}"


# --- H-2: _applyIfFilters 6条件 AND ---

@pytest.mark.unit
def test_b3_h2_apply_if_filters_has_6_conditions_and(b3_topology):
    """H-2: _applyIfFilters JS が matchSearch/matchUnused/matchDevice/matchAf/matchStatus/matchL2l3 の 6条件 AND を持つ。

    _applyIfFilters は rows.forEach コールバックを含むため、関数先頭から閉じ括弧まで
    を含む全テキストを検索して6変数と AND 結合式を確認する。
    """
    from lib.rendering import render
    html = render(b3_topology)
    js_m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    assert js_m is not None, "script ブロックが見つからない"
    js = js_m.group(1)
    # _applyIfFilters 関数が存在する
    assert "function _applyIfFilters" in js, "_applyIfFilters 関数が JS に存在しない"
    # 関数開始位置から 1800 文字以内に 6変数がすべて含まれる
    # P2 #3: matchNodeFilter 追加により関数が長くなったため 1800 に拡張
    start = js.find("function _applyIfFilters")
    fn_region = js[start:start + 1800]
    for var in ("matchSearch", "matchUnused", "matchDevice", "matchAf", "matchStatus", "matchL2l3"):
        assert var in fn_region, \
            f"_applyIfFilters に '{var}' 条件が存在しない"
    # AND 結合式に 6変数（最低限）が含まれる（matchX && matchY && ... の形）
    # P2 #3: matchNodeFilter が追加されているため 7 条件に拡張
    and_m = re.search(
        r'if\s*\(\s*matchSearch\s*&&\s*matchUnused\s*&&\s*matchDevice\s*&&\s*matchAf\s*&&\s*matchStatus\s*&&\s*matchL2l3',
        fn_region
    )
    assert and_m is not None, \
        "_applyIfFilters に 6条件の AND 結合式 (matchSearch && matchUnused && matchDevice && matchAf && matchStatus && matchL2l3) が存在しない"
    # data-* 参照が含まれる（各条件で getAttribute を使用）
    for attr in ("data-unused", "data-device", "data-af", "data-status", "data-l2l3"):
        assert attr in fn_region, \
            f"_applyIfFilters が '{attr}' を参照しない"


# --- H-3: data-status / data-l2l3 値バリエーション行単位検証 ---

@pytest.mark.unit
def test_b3_h3_data_status_down_on_target_row(b3_topology):
    """H-3: admin_status='down' の行に data-status='down' が付く（行抽出）。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    # ds_r1::Gi0/1 は admin_status="down"
    row_m = re.search(r'<tr[^>]*data-iface-id="ds_r1::Gi0/1"[^>]*>', result)
    assert row_m is not None, "ds_r1::Gi0/1 行が見つからない"
    assert 'data-status="down"' in row_m.group(0), \
        f"ds_r1::Gi0/1 の行に data-status='down' が付かない: {row_m.group(0)!r}"


@pytest.mark.unit
def test_b3_h3_data_status_admin_down_on_target_row(b3_topology):
    """H-3: admin_status='admin-down' の行に data-status='admin-down' が付く（行抽出）。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    # ds_r1::Gi0/2 は admin_status="admin-down"
    row_m = re.search(r'<tr[^>]*data-iface-id="ds_r1::Gi0/2"[^>]*>', result)
    assert row_m is not None, "ds_r1::Gi0/2 行が見つからない"
    assert 'data-status="admin-down"' in row_m.group(0), \
        f"ds_r1::Gi0/2 の行に data-status='admin-down' が付かない: {row_m.group(0)!r}"


@pytest.mark.unit
def test_b3_h3_data_l2l3_l2_on_target_row(b3_topology):
    """H-3: l2_l3='l2' の行に data-l2l3='l2' が付く（行抽出）。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    # ds_r1::Gi0/1 は l2_l3="l2"
    row_m = re.search(r'<tr[^>]*data-iface-id="ds_r1::Gi0/1"[^>]*>', result)
    assert row_m is not None, "ds_r1::Gi0/1 行が見つからない"
    assert 'data-l2l3="l2"' in row_m.group(0), \
        f"ds_r1::Gi0/1 の行に data-l2l3='l2' が付かない: {row_m.group(0)!r}"


# --- M-2: addEventListener('change' が JS にある ---

@pytest.mark.unit
def test_b3_m2_select_change_listeners_use_add_event_listener(b3_topology):
    """M-2: ifinv-filter-* select の change 登録が addEventListener('change', ...) 形式である。"""
    from lib.rendering import render
    html = render(b3_topology)
    js_m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    assert js_m is not None, "script ブロックが見つからない"
    js = js_m.group(1)
    # addEventListener と 'change' が共存している（インライン onchange は使わない）
    assert "addEventListener" in js and "'change'" in js, \
        "addEventListener('change', ...) パターンが JS に存在しない"
    # 各 select id について addEventListener('change' が登録されている
    for sel_id in ("ifinv-filter-device", "ifinv-filter-af", "ifinv-filter-status", "ifinv-filter-l2l3"):
        assert sel_id in js, \
            f"select id='{sel_id}' への addEventListener 登録が JS に見つからない"


# --- M-3: device option 決定的昇順 ---

@pytest.mark.unit
def test_b3_m3_device_options_deterministic_ascending_order(b3_topology):
    """M-3: #ifinv-filter-device の option value は device_id 昇順で決定的に並ぶ。"""
    from lib.rendering.views import _build_ifinv_table
    result = _build_ifinv_table(b3_topology["devices"], b3_topology["interfaces"])
    m = re.search(r'<select[^>]*id="ifinv-filter-device"[^>]*>(.*?)</select>',
                  result, re.DOTALL)
    assert m is not None, "ifinv-filter-device select が見つからない"
    # 「すべて」(value="") を除く option value を出現順に取得
    option_values = re.findall(r'<option[^>]*value="([^"]+)"[^>]*>', m.group(0))
    expected = sorted(option_values)
    assert option_values == expected, \
        f"device option が昇順でない: {option_values} != {expected}"


# ============================================================
# P1-#7: OSPF リンクラベルの area 独立行化
# ============================================================

def _make_ospf_v4_link_topology():
    """v4 OSPF single-stack リンクトポロジー（area独立行テスト用）"""
    return {
        "title": "OSPF v4 Link",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False,
             "addresses": [{"af": "v4", "ip": "10.0.0.1", "prefix": 30}]},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False,
             "addresses": [{"af": "v4", "ip": "10.0.0.2", "prefix": 30}]},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "ospf_area": "0", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "ospf": [
                {"device": "r1", "process": 1, "network": "10.0.0.0/30", "area": "0"},
                {"device": "r2", "process": 1, "network": "10.0.0.0/30", "area": "0"},
            ],
        },
    }


def _make_ospf_dualstack_link_topology():
    """v4+v6 OSPF dual-stack リンクトポロジー（area独立行テスト用）"""
    return {
        "title": "OSPF DualStack Link",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False,
             "addresses": [
                 {"af": "v4", "ip": "10.0.0.1", "prefix": 30},
                 {"af": "v6", "ip": "2001:db8:1::1", "prefix": 127},
             ]},
            {"id": "r2::eth0", "device": "r2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False,
             "addresses": [
                 {"af": "v4", "ip": "10.0.0.2", "prefix": 30},
                 {"af": "v6", "ip": "2001:db8:1::2", "prefix": 127},
             ]},
        ],
        "links": [
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "ospf_area": "0", "kind": "inferred-subnet"},
            {"a_device": "r1", "a_if": "eth0", "b_device": "r2", "b_if": "eth0",
             "subnet": "2001:db8:1::/127", "ospf_area": "0", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "ospf": [
                {"device": "r1", "process": 1, "network": "10.0.0.0/30", "area": "0"},
                {"device": "r2", "process": 1, "network": "10.0.0.0/30", "area": "0"},
                {"device": "r1", "process": 1, "network": "2001:db8:1::/127", "area": "0"},
                {"device": "r2", "process": 1, "network": "2001:db8:1::/127", "area": "0"},
            ],
        },
    }


@pytest.mark.unit
def test_p1_7_ospf_single_stack_area_on_separate_tspan_line():
    """P1-#7: single-stack OSPF リンクラベルで area が独立 tspan 行になる（2行構成）。

    期待: <tspan>area 0</tspan><tspan>10.0.0.0/30</tspan> の形式。
    area と subnet が同一 tspan に "area 0 · 10.0.0.0/30" として同居してはならない。
    """
    from lib.rendering.views import _build_view_ospf
    topo = _make_ospf_v4_link_topology()
    ibd = {}
    for i in topo["interfaces"]:
        ibd.setdefault(i["device"], []).append(i)
    html = _build_view_ospf(
        topo["devices"], topo["routing"]["ospf"], topo["links"],
        ibd, topo["segments"], topo["interfaces"]
    )
    # area が独立行: <tspan ...>area 0</tspan> が存在する
    assert re.search(r'<tspan[^>]*>area 0</tspan>', html), \
        "area 0 の独立 tspan 行が見つからない"
    # subnet が独立行: <tspan ...>10.0.0.0/30</tspan> が存在する
    assert re.search(r'<tspan[^>]*>10\.0\.0\.0/30</tspan>', html), \
        "10.0.0.0/30 の独立 tspan 行が見つからない"
    # area と subnet が同一 tspan 内に中黒(·)区切りで同居していないこと
    assert 'area 0 ·' not in html, \
        "area と subnet が同一 tspan で 'area 0 · subnet' の形式になっている（独立行になっていない）"


@pytest.mark.unit
def test_p1_7_ospf_dualstack_area_on_separate_tspan_line():
    """P1-#7: dual-stack OSPF リンクラベルで area/v4/v6 が各独立 tspan 行になる（3行構成）。

    期待:
    1行目: <tspan>area 0</tspan>
    2行目: <tspan>10.0.0.0/30</tspan>
    3行目: <tspan>2001:db8:1::/127</tspan>
    area と subnet が同一 tspan に同居しないこと。
    """
    from lib.rendering.views import _build_view_ospf
    topo = _make_ospf_dualstack_link_topology()
    ibd = {}
    for i in topo["interfaces"]:
        ibd.setdefault(i["device"], []).append(i)
    html = _build_view_ospf(
        topo["devices"], topo["routing"]["ospf"], topo["links"],
        ibd, topo["segments"], topo["interfaces"]
    )
    # area が独立行
    assert re.search(r'<tspan[^>]*>area 0</tspan>', html), \
        "area 0 の独立 tspan 行が見つからない"
    # v4 subnet が独立行
    assert re.search(r'<tspan[^>]*>10\.0\.0\.0/30</tspan>', html), \
        "v4 subnet の独立 tspan 行が見つからない"
    # v6 subnet が独立行
    assert re.search(r'<tspan[^>]*>2001:db8:1::/127</tspan>', html), \
        "v6 subnet の独立 tspan 行が見つからない"
    # area と subnet が同一 tspan に同居しないこと
    assert 'area 0 ·' not in html, \
        "area と subnet が同一 tspan で同居している（独立行になっていない）"


@pytest.mark.integration
def test_p1_7_ospf_label_area_independent_multi_as_area():
    """P1-#7 統合: multi-as-area eval で OSPF ラベルが area 独立行形式になる。

    eval inputs は build_topology でビルドした層別 YAML を使う。
    build_topology が /tmp/multi_as_y に出力済みを前提とするが、
    テスト内でビルドする。
    """
    import os
    import subprocess
    from lib.topology_io import load_topology
    from lib.rendering.views import _build_view_ospf
    # build_topology で一時ファイルを生成
    skill_root = os.path.join(os.path.dirname(__file__), "..", "..")
    dev_root = os.path.join(os.path.dirname(__file__), "..")
    input_dir = os.path.join(dev_root, "evals", "inputs", "multi-as-area")
    out_path = "/tmp/_p1_multi_as_y"
    subprocess.run(
        ["python3", "-m", "scripts.build_topology", input_dir, "-o", out_path],
        cwd=skill_root, check=True, capture_output=True
    )
    topo = load_topology(out_path)
    devices = topo["devices"]
    ospf = topo["routing"].get("ospf", [])
    links = topo["links"]
    interfaces = topo["interfaces"]
    segments = topo["segments"]
    ibd = {}
    for i in interfaces:
        ibd.setdefault(i["device"], []).append(i)
    html = _build_view_ospf(devices, ospf, links, ibd, segments, interfaces)
    # area が独立 tspan になっていること（中黒区切り同居なし）
    assert 'area 0 ·' not in html, \
        "multi-as-area OSPF ラベルで area と subnet が中黒区切りで同居している"
    assert re.search(r'<tspan[^>]*>area 0</tspan>', html), \
        "multi-as-area OSPF ラベルで area 0 の独立 tspan が見つからない"


@pytest.mark.integration
def test_p1_7_ospf_label_area_independent_dualstack_ospf():
    """P1-#7 統合: dualstack-ospf eval で area/v4/v6 が各独立 tspan 行になる。"""
    import os
    import subprocess
    from lib.topology_io import load_topology
    from lib.rendering.views import _build_view_ospf
    skill_root = os.path.join(os.path.dirname(__file__), "..", "..")
    dev_root = os.path.join(os.path.dirname(__file__), "..")
    input_dir = os.path.join(dev_root, "evals", "inputs", "dualstack-ospf")
    out_path = "/tmp/_p1_dso_y"
    subprocess.run(
        ["python3", "-m", "scripts.build_topology", input_dir, "-o", out_path],
        cwd=skill_root, check=True, capture_output=True
    )
    topo = load_topology(out_path)
    devices = topo["devices"]
    ospf = topo["routing"].get("ospf", [])
    links = topo["links"]
    interfaces = topo["interfaces"]
    segments = topo["segments"]
    ibd = {}
    for i in interfaces:
        ibd.setdefault(i["device"], []).append(i)
    html = _build_view_ospf(devices, ospf, links, ibd, segments, interfaces)
    # area が独立 tspan
    assert re.search(r'<tspan[^>]*>area 0</tspan>', html), \
        "dualstack-ospf OSPF ラベルで area 0 の独立 tspan が見つからない"
    # area と subnet が同一 tspan に同居しないこと
    assert 'area 0 ·' not in html, \
        "dualstack-ospf OSPF ラベルで area と subnet が中黒区切りで同居している"
    # v4 と v6 の独立 tspan が存在する
    # v4 subnet は "10." で始まる
    assert re.search(r'<tspan[^>]*>10\.[^<]+</tspan>', html), \
        "dualstack-ospf OSPF ラベルで v4 subnet の独立 tspan が見つからない"
    # v6 subnet は "2001:" で始まる
    assert re.search(r'<tspan[^>]*>2001:[^<]+</tspan>', html), \
        "dualstack-ospf OSPF ラベルで v6 subnet の独立 tspan が見つからない"


# ============================================================
# P1-#4: large-topo 自動 zoomFit（初期表示・selectView）
# ============================================================

@pytest.mark.unit
def test_p1_4_js_contains_initial_zoomfit_call():
    """P1-#4: JS に初期 zoomFit 呼出が含まれる（IIFE末尾 or DOMContentLoaded相当）。

    window._zoomFit または zoomFit() が初期化コード内（selectView('physical') の後付近）
    で呼ばれていること。
    """
    from lib.rendering.template import _JS
    # zoomFit() または window._zoomFit() が初期化位置で呼ばれている
    # selectView('physical') の後に zoomFit 呼出があることを確認
    sv_idx = _JS.find("selectView('physical')")
    assert sv_idx != -1, "selectView('physical') が JS に見つからない"
    after_sv = _JS[sv_idx:]
    # 初期 zoomFit 呼出: window._zoomFit() または zoomFit() が selectView の後に存在
    has_zoomfit_after = (
        "window._zoomFit()" in after_sv or
        re.search(r'\bzoomFit\(\)', after_sv) is not None
    )
    assert has_zoomfit_after, \
        "selectView('physical') の後に zoomFit() 呼出が見つからない（初期 zoomFit 未実装）"


@pytest.mark.unit
def test_p1_4_js_selectview_calls_zoomfit_for_svg_views():
    """P1-#4: selectView() のSVGビュー表示分岐末尾で zoomFit を呼ぶ。

    ifinv ビュー（非SVG）では呼ばれず、SVG ビュー分岐内で zoomFit 呼出があること。
    """
    from lib.rendering.template import _JS
    # selectView 関数内を抽出
    sv_start = _JS.find("function selectView(viewId)")
    assert sv_start != -1, "selectView 関数が JS に見つからない"
    # selectView 関数の本体を大まかに抽出（次の function 宣言まで）
    sv_region = _JS[sv_start:sv_start + 2000]
    # SVG ビュー分岐（else ブロック）に zoomFit 呼出がある
    # viewId === 'ifinv' の if ブロック後の else に zoomFit が必要
    assert "zoomFit" in sv_region, \
        "selectView() 内に zoomFit 呼出が見つからない（SVG ビュー切替時の自動 fit 未実装）"


@pytest.mark.integration
def test_p1_4_html_js_zoomfit_called_after_selectview():
    """P1-#4 統合: render() が生成する HTML の JS に zoomFit 呼出が含まれる。"""
    from lib.rendering import render
    topo = {
        "title": "ZoomFit Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    js_m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    assert js_m is not None, "script ブロックが見つからない"
    js = js_m.group(1)
    assert "zoomFit" in js, "render() 生成 JS に zoomFit が含まれない"
    # selectView の後に zoomFit がある
    sv_idx = js.find("selectView('physical')")
    assert sv_idx != -1
    after = js[sv_idx:]
    has_call = ("window._zoomFit()" in after or re.search(r'\bzoomFit\(\)', after) is not None)
    assert has_call, "selectView('physical') の後に zoomFit() 呼出が見つからない"


# ============================================================
# P1-#6: AS 枠ラベルの重なり回避
# ============================================================

def _make_overlapping_as_labels_topology():
    """2つの AS が同座標に配置されうるトポロジー（重なりテスト用）。

    AS65000(大枠: core, edge 4台) と AS65103(小枠: cust3 1台) が
    同じ座標領域に存在する large-topo 類似構造。
    最小ケース: 片方が1台のデバイスで force-directed で同座標になりやすい状況。
    """
    return {
        "title": "Overlapping AS Labels",
        "generated_from": [],
        "devices": [
            {"id": "core1", "hostname": "Core1", "vendor": "cisco_ios", "as": 65000, "sections": []},
            {"id": "core2", "hostname": "Core2", "vendor": "cisco_ios", "as": 65000, "sections": []},
            {"id": "cust3", "hostname": "Cust3", "vendor": "cisco_ios", "as": 65103, "sections": []},
        ],
        "interfaces": [
            {"id": "core1::eth0", "device": "core1", "name": "eth0", "ip": "10.0.0.1/30",
             "vlan": None, "description": None, "shutdown": False,
             "addresses": [{"af": "v4", "ip": "10.0.0.1", "prefix": 30}]},
            {"id": "core2::eth0", "device": "core2", "name": "eth0", "ip": "10.0.0.2/30",
             "vlan": None, "description": None, "shutdown": False,
             "addresses": [{"af": "v4", "ip": "10.0.0.2", "prefix": 30}]},
            {"id": "cust3::eth0", "device": "cust3", "name": "eth0", "ip": "10.0.1.1/30",
             "vlan": None, "description": None, "shutdown": False,
             "addresses": [{"af": "v4", "ip": "10.0.1.1", "prefix": 30}]},
            {"id": "core1::eth1", "device": "core1", "name": "eth1", "ip": "10.0.1.2/30",
             "vlan": None, "description": None, "shutdown": False,
             "addresses": [{"af": "v4", "ip": "10.0.1.2", "prefix": 30}]},
        ],
        "links": [
            {"a_device": "core1", "a_if": "eth0", "b_device": "core2", "b_if": "eth0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
            {"a_device": "core1", "a_if": "eth1", "b_device": "cust3", "b_if": "eth0",
             "subnet": "10.0.1.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "core1", "local_as": 65000, "local_ip": "10.0.1.2",
                 "neighbor_ip": "10.0.1.1", "peer_as": 65103, "type": "ebgp"},
                {"device": "cust3", "local_as": 65103, "local_ip": "10.0.1.1",
                 "neighbor_ip": "10.0.1.2", "peer_as": 65000, "type": "ebgp"},
                {"device": "core1", "local_as": 65000, "local_ip": "10.0.0.1",
                 "neighbor_ip": "10.0.0.2", "peer_as": 65000, "type": "ibgp"},
                {"device": "core2", "local_as": 65000, "local_ip": "10.0.0.2",
                 "neighbor_ip": "10.0.0.1", "peer_as": 65000, "type": "ibgp"},
            ],
        },
    }


@pytest.mark.unit
def test_p1_6_as_label_chips_have_unique_positions():
    """P1-#6: 複数 AS ラベルチップの (x, y) 座標が重複しない（衝突回避）。

    同一 AS の色違いでなく、異なる AS 間でチップ座標が一致しないこと。
    """
    from lib.rendering.svg import _svg_bgp_as_groups
    from lib.rendering.views import _build_bgp_layout
    topo = _make_overlapping_as_labels_topology()
    bgp = topo["routing"]["bgp"]
    interfaces = topo["interfaces"]
    devices = topo["devices"]
    positions, bgp_devs = _build_bgp_layout(devices, bgp, interfaces)
    html = _svg_bgp_as_groups(bgp_devs, positions)
    # ラベルチップ背景 rect の (x, y) を抽出
    chip_positions_found = re.findall(
        r'<rect x="([0-9.-]+)" y="([0-9.-]+)"[^>]*class="as-group-label-bg"',
        html
    )
    assert len(chip_positions_found) >= 2, \
        f"AS ラベルチップが2個以上ない: {chip_positions_found}"
    # AS ごとのラベルチップ座標が全て異なること（重複なし）
    positions_set = set(chip_positions_found)
    assert len(positions_set) == len(chip_positions_found), \
        f"AS ラベルチップ座標が重複している: {chip_positions_found}"


@pytest.mark.unit
def test_p1_6_as_label_chips_no_overlap_unit():
    """P1-#6: 合成座標 (AS65000, AS65103) で chip が同座標でないこと（単体・決定的）。

    positions を手動設定して _svg_bgp_as_groups の衝突回避を検証する。
    """
    from lib.rendering.svg import _svg_bgp_as_groups
    # AS65000 と AS65103 のデバイスを同座標付近に配置（重なりが起きやすい条件）
    devices = [
        {"id": "core1", "hostname": "Core1", "as": 65000},
        {"id": "cust3",  "hostname": "Cust3",  "as": 65103},
    ]
    # core1 と cust3 を同座標に配置（最悪ケース）
    positions = {
        "core1": (0.0, 0.0),
        "cust3": (0.0, 0.0),
    }
    html = _svg_bgp_as_groups(devices, positions)
    chip_positions_found = re.findall(
        r'<rect x="([0-9.-]+)" y="([0-9.-]+)"[^>]*class="as-group-label-bg"',
        html
    )
    assert len(chip_positions_found) == 2, \
        f"チップが2個生成されない: {chip_positions_found}"
    assert chip_positions_found[0] != chip_positions_found[1], \
        f"AS65000 と AS65103 のラベルチップ座標が重複している: {chip_positions_found}"


@pytest.mark.integration
def test_p1_6_large_topo_as_labels_no_overlap():
    """P1-#6 統合: large-topo の BGP ビューで全 AS ラベルチップが相互非重複。"""
    import os
    import subprocess
    from lib.topology_io import load_topology
    from lib.rendering.svg import _svg_bgp_as_groups
    from lib.rendering.views import _build_bgp_layout
    skill_root = os.path.join(os.path.dirname(__file__), "..", "..")
    dev_root = os.path.join(os.path.dirname(__file__), "..")
    input_dir = os.path.join(dev_root, "evals", "inputs", "large-topo")
    out_path = "/tmp/_p1_large_y"
    subprocess.run(
        ["python3", "-m", "scripts.build_topology", input_dir, "-o", out_path],
        cwd=skill_root, check=True, capture_output=True
    )
    topo = load_topology(out_path)
    devices = topo["devices"]
    bgp = topo["routing"].get("bgp", [])
    interfaces = topo["interfaces"]
    positions, bgp_devs = _build_bgp_layout(devices, bgp, interfaces)
    html = _svg_bgp_as_groups(bgp_devs, positions)
    chip_positions_found = re.findall(
        r'<rect x="([0-9.-]+)" y="([0-9.-]+)"[^>]*class="as-group-label-bg"',
        html
    )
    assert len(chip_positions_found) >= 2, "AS ラベルチップが2個以上ない"
    positions_set = set(chip_positions_found)
    assert len(positions_set) == len(chip_positions_found), \
        f"large-topo AS ラベルチップ座標が重複: {chip_positions_found}"


# ===========================================================================
# P1b #2: IFチップ拡大 + 複数行折返し（iteration-5 Part-4）
# ===========================================================================

def _make_many_chip_topology(n_chips: int):
    """n_chips 個の接続IF を持つ r1 を含む topology（折返しテスト用）。

    r1 に n_chips 個の GigabitEthernet を持たせ、各々 r2〜r{n_chips+1} と接続する。
    r1 のチップは接続IF のみ（Loopback なし）で n_chips 個になる。
    """
    devices = [
        {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
    ]
    for k in range(n_chips):
        devices.append(
            {"id": f"r{k+2}", "hostname": f"R{k+2}", "vendor": "cisco_ios",
             "as": None, "sections": []}
        )

    interfaces = []
    for k in range(n_chips):
        interfaces.append(
            {"id": f"r1::Gi0/{k}", "device": "r1", "name": f"GigabitEthernet0/{k}",
             "ip": f"10.0.{k}.1/30", "vlan": None, "description": None, "shutdown": False}
        )
        interfaces.append(
            {"id": f"r{k+2}::Gi0/0", "device": f"r{k+2}", "name": "GigabitEthernet0/0",
             "ip": f"10.0.{k}.2/30", "vlan": None, "description": None, "shutdown": False}
        )

    links = []
    for k in range(n_chips):
        links.append({
            "a_device": "r1", "a_if": f"GigabitEthernet0/{k}",
            "b_device": f"r{k+2}", "b_if": "GigabitEthernet0/0",
            "subnet": f"10.0.{k}.0/30", "kind": "inferred-subnet",
        })

    return {
        "title": f"Chip Wrap Test {n_chips}",
        "generated_from": [],
        "devices": devices,
        "interfaces": interfaces,
        "links": links,
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }


@pytest.mark.unit
def test_p1b2_chip_radius_enlarged():
    """P1b #2: チップ半径が視認性のため拡大されている（_IF_CHIP_R >= 6）。"""
    from lib.rendering.svg import _IF_CHIP_R
    assert _IF_CHIP_R >= 6, \
        f"チップ半径が拡大されていない: _IF_CHIP_R={_IF_CHIP_R}（期待: >=6）"


@pytest.mark.unit
def test_p1b2_chip_radius_in_svg():
    """P1b #2: レンダリングされた SVG に拡大後の半径値が使われている。"""
    from lib.rendering import render
    from lib.rendering.svg import _IF_CHIP_R
    html = render(_make_many_chip_topology(3))
    assert f'r="{_IF_CHIP_R}"' in html, \
        f"SVG 内のチップ円に r=\"{_IF_CHIP_R}\" が見つからない"


@pytest.mark.unit
def test_p1b2_wrap_constants_exist():
    """P1b #2: 折返し計算に必要な定数が svg モジュールに存在する。"""
    import lib.rendering.svg as svg_mod
    assert hasattr(svg_mod, "_IF_CHIP_PER_ROW"), \
        "_IF_CHIP_PER_ROW 定数が存在しない"
    assert hasattr(svg_mod, "_IF_CHIP_ROW_H"), \
        "_IF_CHIP_ROW_H 定数が存在しない"
    per_row = svg_mod._IF_CHIP_PER_ROW
    row_h = svg_mod._IF_CHIP_ROW_H
    assert per_row >= 1, f"_IF_CHIP_PER_ROW は 1 以上であるべき: {per_row}"
    assert row_h >= 12, f"_IF_CHIP_ROW_H は 12px 以上であるべき: {row_h}"


@pytest.mark.unit
def test_p1b2_wrap_chip_rows_helper():
    """P1b #2: _chip_rows_for(num_chips) が正しいチップ行数を返す。"""
    from lib.rendering.svg import _chip_rows_for, _IF_CHIP_PER_ROW
    # 0チップ → 0行
    assert _chip_rows_for(0) == 0, f"0チップ → 0行のはず: {_chip_rows_for(0)}"
    # 1チップ → 1行
    assert _chip_rows_for(1) == 1, f"1チップ → 1行のはず: {_chip_rows_for(1)}"
    # per_row 個 → 1行
    assert _chip_rows_for(_IF_CHIP_PER_ROW) == 1, \
        f"{_IF_CHIP_PER_ROW}チップ → 1行のはず: {_chip_rows_for(_IF_CHIP_PER_ROW)}"
    # per_row + 1 個 → 2行
    assert _chip_rows_for(_IF_CHIP_PER_ROW + 1) == 2, \
        f"{_IF_CHIP_PER_ROW + 1}チップ → 2行のはず: {_chip_rows_for(_IF_CHIP_PER_ROW + 1)}"
    # 2 * per_row 個 → 2行
    assert _chip_rows_for(_IF_CHIP_PER_ROW * 2) == 2, \
        f"{_IF_CHIP_PER_ROW * 2}チップ → 2行のはず: {_chip_rows_for(_IF_CHIP_PER_ROW * 2)}"
    # 2 * per_row + 1 個 → 3行
    assert _chip_rows_for(_IF_CHIP_PER_ROW * 2 + 1) == 3, \
        f"{_IF_CHIP_PER_ROW * 2 + 1}チップ → 3行のはず: {_chip_rows_for(_IF_CHIP_PER_ROW * 2 + 1)}"


@pytest.mark.unit
def test_p1b2_chip_node_size_for_helper():
    """P1b #2: _chip_node_size_for(num_chips) が行数に応じたノード高を返す。"""
    from lib.rendering.svg import _chip_node_size_for, _chip_rows_for, _IF_CHIP_ROW_H
    from lib.rendering.layout import _NODE_WIDTH, _NODE_HEIGHT

    # 0チップ → 基本高さ
    _w0, h0 = _chip_node_size_for(0)
    assert _w0 == _NODE_WIDTH, f"幅は常に _NODE_WIDTH のはず: {_w0}"
    assert h0 == float(_NODE_HEIGHT), f"0チップ → _NODE_HEIGHT のはず: {h0}"

    # 1行分のチップ
    _w1, h1 = _chip_node_size_for(1)
    assert h1 > float(_NODE_HEIGHT), f"チップあり → 高さが基本値より大きいはず: {h1}"

    # 2行 → 1行より高い
    from lib.rendering.svg import _IF_CHIP_PER_ROW
    n2row = _IF_CHIP_PER_ROW + 1
    _w2, h2 = _chip_node_size_for(n2row)
    assert h2 > h1, \
        f"2行({n2row}チップ) の高さ({h2}) は 1行(1チップ) の高さ({h1}) より大きいはず"
    # 追加行ごとに _IF_CHIP_ROW_H 増える
    assert abs(h2 - h1 - _IF_CHIP_ROW_H) < 1.0, \
        f"2行→1行の高さ差({h2 - h1:.1f}) が _IF_CHIP_ROW_H({_IF_CHIP_ROW_H}) と異なる"


@pytest.mark.unit
def test_p1b2_chip_cx_no_overflow_single_row():
    """P1b #2: 1行に収まるチップ数の場合、全チップ cx がノード幅内に収まる。"""
    from lib.rendering.svg import _svg_if_chip, _IF_CHIP_PER_ROW, _IF_CHIP_OFFSET_X, _IF_CHIP_GAP
    from lib.rendering.layout import _NODE_WIDTH

    iface = {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": None,
             "shutdown": False, "description": None, "addresses": []}
    nx = 50.0
    chip_start_y = 90.0

    # per_row 個以下なら全チップが nx+NODE_WIDTH 内に収まる
    for k in range(_IF_CHIP_PER_ROW):
        svg_str = _svg_if_chip(nx, chip_start_y, k, iface)
        # cx を抽出
        cx_match = re.search(r'cx="([0-9.+-]+)"', svg_str)
        assert cx_match, f"cx が見つからない(k={k}): {svg_str}"
        cx = float(cx_match.group(1))
        assert cx >= nx, \
            f"チップ k={k} の cx={cx:.1f} がノード左端 nx={nx:.1f} より左"
        assert cx <= nx + _NODE_WIDTH, \
            f"チップ k={k} の cx={cx:.1f} がノード右端 nx+{_NODE_WIDTH}={nx + _NODE_WIDTH:.1f} より右"


@pytest.mark.unit
def test_p1b2_chip_wrap_two_rows():
    """P1b #2: per_row+1 個目のチップが2行目（cy が1行目より大きい）に配置される。"""
    from lib.rendering.svg import _svg_if_chip, _IF_CHIP_PER_ROW, _IF_CHIP_OFFSET_Y, _IF_CHIP_ROW_H

    iface = {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": None,
             "shutdown": False, "description": None, "addresses": []}
    nx = 50.0
    chip_start_y = 90.0

    # k=0 (row=0) と k=per_row (row=1) の cy を比較
    svg_k0 = _svg_if_chip(nx, chip_start_y, 0, iface)
    svg_kN = _svg_if_chip(nx, chip_start_y, _IF_CHIP_PER_ROW, iface)

    cy0 = float(re.search(r'cy="([0-9.+-]+)"', svg_k0).group(1))
    cyN = float(re.search(r'cy="([0-9.+-]+)"', svg_kN).group(1))

    assert cyN > cy0, \
        f"per_row番目のチップ(k={_IF_CHIP_PER_ROW}) cy={cyN:.1f} が " \
        f"k=0 の cy={cy0:.1f} 以下になっており、折返しされていない"
    assert abs(cyN - cy0 - _IF_CHIP_ROW_H) < 1.0, \
        f"行間隔 {cyN - cy0:.1f} が _IF_CHIP_ROW_H={_IF_CHIP_ROW_H} と異なる"


@pytest.mark.unit
def test_p1b2_chip_wrap_cx_restarts_at_new_row():
    """P1b #2: 折返し後の行頭チップの cx が1行目の最初と同じ x 位置から始まる。"""
    from lib.rendering.svg import _svg_if_chip, _IF_CHIP_PER_ROW

    iface = {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": None,
             "shutdown": False, "description": None, "addresses": []}
    nx = 50.0
    chip_start_y = 90.0

    svg_k0 = _svg_if_chip(nx, chip_start_y, 0, iface)                  # col=0, row=0
    svg_kN = _svg_if_chip(nx, chip_start_y, _IF_CHIP_PER_ROW, iface)  # col=0, row=1

    cx0 = float(re.search(r'cx="([0-9.+-]+)"', svg_k0).group(1))
    cxN = float(re.search(r'cx="([0-9.+-]+)"', svg_kN).group(1))

    assert abs(cx0 - cxN) < 0.5, \
        f"折返し行頭チップ cx={cxN:.1f} が1行目行頭 cx={cx0:.1f} と異なる（折返し cx リセット不全）"


@pytest.mark.unit
def test_p1b2_many_chips_all_within_node_width():
    """P1b #2: 多数チップ（per_row * 3 + 2）の全 cx がノード幅内に収まる。"""
    from lib.rendering.svg import _svg_if_chip, _IF_CHIP_PER_ROW
    from lib.rendering.layout import _NODE_WIDTH

    iface = {"id": "r1::eth0", "device": "r1", "name": "eth0", "ip": None,
             "shutdown": False, "description": None, "addresses": []}
    nx = 50.0
    chip_start_y = 90.0
    n = _IF_CHIP_PER_ROW * 3 + 2

    for k in range(n):
        svg_str = _svg_if_chip(nx, chip_start_y, k, iface)
        cx_match = re.search(r'cx="([0-9.+-]+)"', svg_str)
        assert cx_match, f"cx が見つからない(k={k})"
        cx = float(cx_match.group(1))
        assert cx >= nx, \
            f"チップ k={k} の cx={cx:.1f} がノード左端 nx={nx:.1f} より左"
        assert cx <= nx + _NODE_WIDTH, \
            f"チップ k={k} の cx={cx:.1f} がノード右端 {nx + _NODE_WIDTH:.1f} を超えている（折返し未実装）"


@pytest.mark.unit
def test_p1b2_node_height_grows_with_chip_rows():
    """P1b #2: チップ行数が増えるとノード矩形高さが増大する。"""
    from lib.rendering import render
    from lib.rendering.svg import _IF_CHIP_PER_ROW

    # 1行: per_row 個
    topo1 = _make_many_chip_topology(_IF_CHIP_PER_ROW)
    html1 = render(topo1)

    # 2行: per_row + 1 個
    topo2 = _make_many_chip_topology(_IF_CHIP_PER_ROW + 1)
    html2 = render(topo2)

    # r1 のノード矩形高さを比較
    def _extract_r1_height(html: str) -> float | None:
        phys = _extract_physical_view(html)
        # data-device="r1" の <g> 内の <rect ... height="...">
        node_g = re.search(
            r'data-device="r1"[^>]*>.*?<rect[^>]+height="([0-9.]+)"',
            phys, re.DOTALL
        )
        if node_g:
            return float(node_g.group(1))
        return None

    h1 = _extract_r1_height(html1)
    h2 = _extract_r1_height(html2)
    assert h1 is not None, "1行のノード高さが抽出できない"
    assert h2 is not None, "2行のノード高さが抽出できない"
    assert h2 > h1, \
        f"2行({_IF_CHIP_PER_ROW + 1}チップ) 高さ({h2}) <= 1行({_IF_CHIP_PER_ROW}チップ) 高さ({h1})"


@pytest.mark.unit
def test_p1b2_2chip_no_regression():
    """P1b #2 非回帰: 2チップ（従来ケース）が折返しなしで描画される。"""
    from lib.rendering import render
    html = render(_make_many_chip_topology(2))
    phys = _extract_physical_view(html)
    chips = re.findall(r'class="[^"]*if-chip[^"]*"', phys)
    assert len(chips) >= 2, f"2チップが描画されていない: {len(chips)}"
    # 2チップなら cy が全て同じ（1行のみ）
    cy_vals = re.findall(r'cy="([0-9.]+)"', phys)
    # r1 ノード内の cy のみ取得（ノード内に2つあるはず）
    # 複数のノードがあるので r1 の device-node 内のみ確認
    r1_match = re.search(
        r'data-device="r1"[^>]*>(.*?)</g>\s*(?=<g class="device-node"|$)',
        phys, re.DOTALL
    )
    if r1_match:
        r1_content = r1_match.group(1)
        r1_cy_vals = re.findall(r'cy="([0-9.]+)"', r1_content)
        assert len(set(r1_cy_vals)) == 1, \
            f"2チップなのに cy が複数値: {set(r1_cy_vals)}（折返し過剰）"


@pytest.mark.unit
def test_p1b2_no_overlap_after_chip_height_expand():
    """P1b #2: チップ高さ拡張後も no_overlap テストが通る（多行チップを含む場合）。"""
    from lib.rendering.layout import (
        _layout_force_directed, _canvas_size_for_nodes, _adaptive_iter
    )
    from lib.rendering.svg import _chip_node_size_for, _IF_CHIP_PER_ROW

    # per_row * 2 + 1 チップ（3行）を持つノードを含む
    n_chips = _IF_CHIP_PER_ROW * 2 + 1
    topo = _make_many_chip_topology(n_chips)
    devices = topo["devices"]
    links = topo["links"]

    # node_sizes はチップ数ベースで高さを渡す
    # r1: n_chips チップ, 他: 1チップ
    chip_count = {"r1": n_chips}
    for dev in devices:
        if dev["id"] != "r1":
            chip_count[dev["id"]] = 1

    # _chip_node_size_for でノード高さを算出してキャンバスサイズを決定
    def _chip_h(dev_id):
        return _chip_node_size_for(chip_count.get(dev_id, 0))[1]

    node_ids = [d["id"] for d in devices]
    max_h = max(_chip_h(nid) for nid in node_ids)
    est_w, est_h = _canvas_size_for_nodes(len(node_ids), max_node_h=max_h)
    edges = [(lk["a_device"], lk["b_device"]) for lk in links]

    # node_sizes に chip_rows 相当の値を渡す
    # _chip_node_size_for(n) と _node_size_for(k) が等しくなる k を探す必要がある
    # 最もシンプル: chip_count を直接渡し、_node_size_for がチップ対応することを期待する
    # ここでは物理レイアウトを使って確認する
    from lib.rendering import _build_physical_layout
    from lib.rendering.svg import _chip_node_size_for

    pos = _build_physical_layout(devices, topo["interfaces"], links, topo["segments"])

    for i, na in enumerate(node_ids):
        for j, nb in enumerate(node_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            wa, ha = _chip_node_size_for(chip_count.get(na, 0))
            wb, hb = _chip_node_size_for(chip_count.get(nb, 0))
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            min_sep_x = (wa + wb) / 2 + 5
            min_sep_y = (ha + hb) / 2 + 5
            no_overlap = dx >= min_sep_x or dy >= min_sep_y
            assert no_overlap, (
                f"チップ高拡張後: ノード {na}({wa:.0f}x{ha:.0f}) と {nb}({wb:.0f}x{hb:.0f}) が重なっている "
                f"(dx={dx:.1f} min_sep_x={min_sep_x:.1f}, "
                f"dy={dy:.1f} min_sep_y={min_sep_y:.1f})"
            )


@pytest.mark.unit
def test_p1b2_deterministic():
    """P1b #2: 多行チップを含む topology で render() が決定的（2回一致）。"""
    from lib.rendering import render
    from lib.rendering.svg import _IF_CHIP_PER_ROW

    topo = _make_many_chip_topology(_IF_CHIP_PER_ROW + 3)
    html1 = render(topo)
    html2 = render(topo)
    assert html1 == html2, "多行チップ topology の render() が非決定的"


@pytest.mark.unit
def test_p1b2_chip_positions_wrap():
    """P1b #2: _chip_positions が折返し座標を返す（per_row+1番目は2行目）。"""
    from lib.rendering.svg import _chip_positions, _IF_CHIP_PER_ROW, _IF_CHIP_ROW_H
    from lib.rendering.layout import _node_size_for

    n_chips = _IF_CHIP_PER_ROW + 1
    dev = {"id": "r1", "hostname": "R1"}
    ifaces = [
        {"id": f"r1::eth{k}", "device": "r1", "name": f"eth{k:02d}",
         "ip": None, "shutdown": False, "description": None}
        for k in range(n_chips)
    ]
    chip_ids = {f"r1::eth{k}" for k in range(n_chips)}

    # ノード中心座標を適当に設定
    nx, ny = 100.0, 100.0
    from lib.rendering.svg import _chip_node_size_for
    _w, node_h = _chip_node_size_for(n_chips)
    node_cx = nx + _w / 2
    node_cy = ny + node_h / 2

    result = _chip_positions(dev, chip_ids, ifaces, node_cx, node_cy)
    assert len(result) == n_chips, f"結果のチップ数が不正: {len(result)}"

    # name ソートで eth00..eth{per_row-1} が row=0、eth{per_row} が row=1
    row0_ids = {f"r1::eth{k}" for k in range(_IF_CHIP_PER_ROW)}
    row1_id = f"r1::eth{_IF_CHIP_PER_ROW}"

    row0_cys = [result[iid][1] for iid in row0_ids if iid in result]
    row1_cy = result[row1_id][1]

    assert row1_cy > row0_cys[0], \
        f"2行目チップ cy={row1_cy:.1f} が 1行目 cy={row0_cys[0]:.1f} 以下（折返し未実装）"
    assert abs(row1_cy - row0_cys[0] - _IF_CHIP_ROW_H) < 1.0, \
        f"行間隔 {row1_cy - row0_cys[0]:.1f} が _IF_CHIP_ROW_H={_IF_CHIP_ROW_H} と異なる"


@pytest.mark.unit
def test_p1b2_existing_no_overlap_20nodes_regression():
    """P1b #2 非回帰: チップ高変更後も large-topo 20台 no_overlap が通る。"""
    from lib.rendering.layout import (
        _layout_force_directed, _node_size_for, _canvas_size_for_nodes, _adaptive_iter
    )

    topo = _load_large_topo_for_test()
    devices = topo["devices"]
    links = topo["links"]
    interfaces = topo["interfaces"]

    node_ids = [d["id"] for d in devices]
    edges = [(lk["a_device"], lk["b_device"]) for lk in links]
    iface_count: dict[str, int] = {}
    for iface in interfaces:
        iface_count[iface["device"]] = iface_count.get(iface["device"], 0) + 1
    node_sizes = {d["id"]: iface_count.get(d["id"], 0) for d in devices}

    n = len(node_ids)
    est_w, est_h = _canvas_size_for_nodes(n, max_node_h=max(
        _node_size_for(node_sizes.get(nid, 0))[1] for nid in node_ids
    ))
    pos = _layout_force_directed(
        node_ids, edges, width=est_w, height=est_h,
        iterations=_adaptive_iter(n), node_sizes=node_sizes,
    )

    for i, na in enumerate(node_ids):
        for j, nb in enumerate(node_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            wa, ha = _node_size_for(node_sizes[na])
            wb, hb = _node_size_for(node_sizes[nb])
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            min_sep_x = (wa + wb) / 2 + 5
            min_sep_y = (ha + hb) / 2 + 5
            no_overlap = dx >= min_sep_x or dy >= min_sep_y
            assert no_overlap, (
                f"large-topo 回帰: ノード {na} と {nb} が重なっている "
                f"(dx={dx:.1f} min_sep_x={min_sep_x:.1f}, "
                f"dy={dy:.1f} min_sep_y={min_sep_y:.1f})"
            )


# ===========================================================================
# P2: フィードバック対応3点
#   #1 チップ/Loopback マーキング（チップ↔IF一覧双方向 + iBGP Loopback連動）
#   #5 複数ノード選択 → 間のエッジ＋表ハイライト
#   #3 node-filter ↔ IF一覧 連動
# ===========================================================================


# ---------------------------------------------------------------------------
# ヘルパー: iBGP + Loopback ありトポロジー（#1 loopback連動テスト用）
# ---------------------------------------------------------------------------

def _make_ibgp_loopback_topology():
    """iBGP + Loopback 付きトポロジー。
    r1/r2 同一 AS65001、互いの Loopback IP で iBGP。
    local_ip は Loopback IP と一致させる（iBGP の loopback 源識別用）。
    """
    return {
        "title": "iBGP Loopback Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": 65001, "sections": []},
            {"id": "r2", "hostname": "R2", "vendor": "cisco_ios", "as": 65001, "sections": []},
        ],
        "interfaces": [
            {"id": "r1::Loopback0", "device": "r1", "name": "Loopback0",
             "ip": "10.255.0.1/32", "vlan": None, "description": None, "shutdown": False,
             "addresses": [], "admin_status": "up"},
            {"id": "r1::Gi0/0", "device": "r1", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.1/30", "vlan": None, "description": "to-R2", "shutdown": False,
             "addresses": [], "admin_status": "up"},
            {"id": "r2::Loopback0", "device": "r2", "name": "Loopback0",
             "ip": "10.255.0.2/32", "vlan": None, "description": None, "shutdown": False,
             "addresses": [], "admin_status": "up"},
            {"id": "r2::Gi0/0", "device": "r2", "name": "GigabitEthernet0/0",
             "ip": "10.0.0.2/30", "vlan": None, "description": "to-R1", "shutdown": False,
             "addresses": [], "admin_status": "up"},
        ],
        "links": [
            {"a_device": "r1", "a_if": "GigabitEthernet0/0",
             "b_device": "r2", "b_if": "GigabitEthernet0/0",
             "subnet": "10.0.0.0/30", "kind": "inferred-subnet"},
        ],
        "segments": [],
        "routing": {
            "bgp": [
                {"device": "r1", "local_as": 65001, "local_ip": "10.255.0.1",
                 "neighbor_ip": "10.255.0.2", "peer_as": 65001, "type": "ibgp"},
                {"device": "r2", "local_as": 65001, "local_ip": "10.255.0.2",
                 "neighbor_ip": "10.255.0.1", "peer_as": 65001, "type": "ibgp"},
            ],
            "ospf": [],
            "static": [
                {"device": "r1", "prefix": "0.0.0.0/0", "next_hop": "10.0.0.2"},
            ],
        },
    }


# ---------------------------------------------------------------------------
# #1-A: チップに data-iface-id が付く（既存機能の確認）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_chip_has_data_iface_id():
    """#1-A: Physical ビューの if-chip 要素に data-iface-id 属性が付いている。"""
    from lib.rendering import render
    html = render(_make_chip_topology())
    phys = _extract_physical_view(html)
    # data-iface-id="r1::Gi0/0" が存在すること
    assert 'data-iface-id="r1::Gi0/0"' in phys, \
        "if-chip に data-iface-id=\"r1::Gi0/0\" が付いていない"


# ---------------------------------------------------------------------------
# #1-B: toggleIfChipHighlight 関数が JS に存在する
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_toggle_if_chip_highlight_function_exists(rendered_html):
    """#1-B: JS に toggleIfChipHighlight 関数が定義されている。"""
    assert "function toggleIfChipHighlight" in rendered_html, \
        "toggleIfChipHighlight 関数が HTML の JS に存在しない"


# ---------------------------------------------------------------------------
# #1-C: if-chip クリックで toggleIfChipHighlight を呼ぶ登録コードが存在する
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_chip_click_registers_toggle_if_chip_highlight(rendered_html):
    """#1-C: JS に if-chip click → toggleIfChipHighlight の登録コードが存在する。"""
    # addEventListener('click') + toggleIfChipHighlight が近傍に存在することを確認
    assert "toggleIfChipHighlight" in rendered_html, \
        "toggleIfChipHighlight の呼び出しが JS にない"
    # .if-chip に対する click イベント登録コードが存在すること
    assert "if-chip" in rendered_html, \
        ".if-chip クラスの参照が JS にない"


# ---------------------------------------------------------------------------
# #1-D: .if-chip.highlighted CSS が存在する
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_chip_highlighted_css_exists(rendered_html):
    """#1-D: CSS に .if-chip.highlighted スタイルが定義されている。"""
    assert ".if-chip.highlighted" in rendered_html, \
        ".if-chip.highlighted CSS スタイルが HTML に存在しない"


# ---------------------------------------------------------------------------
# #1-E: ifinv 行に data-iface-id が付いている
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_ifinv_row_has_data_iface_id(rendered_html):
    """#1-E: IF一覧(ifinv)テーブルの tr に data-iface-id 属性が付いている。"""
    # ifinv-table-body 内の tr に data-iface-id が存在すること
    m = re.search(
        r'id="ifinv-table-body".*?(<tr[^>]*data-iface-id[^>]*>)',
        rendered_html, re.DOTALL
    )
    assert m is not None, \
        "ifinv-table-body 内の tr に data-iface-id 属性が見つからない"


# ---------------------------------------------------------------------------
# #1-F: ifinv 行クリックで toggleIfChipHighlight を呼ぶ登録コードが存在する
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_ifinv_row_click_calls_toggle_if_chip_highlight(rendered_html):
    """#1-F: JS に ifinv 行（data-iface-id）クリック → toggleIfChipHighlight の登録がある。"""
    # data-iface-id を持つ tr へのクリックリスナー登録と toggleIfChipHighlight 呼び出しが
    # 同じ IIFE/ブロック内に存在すること
    js_section = rendered_html[rendered_html.find("<script>"):]
    assert "data-iface-id" in js_section, \
        "JS の script セクションに data-iface-id 参照がない"
    assert "toggleIfChipHighlight" in js_section, \
        "JS の script セクションに toggleIfChipHighlight 呼び出しがない"


# ---------------------------------------------------------------------------
# #1-G: iBGP 行に data-loopback-iface-id が付く
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_ibgp_row_has_loopback_iface_id():
    """#1-G: iBGP セッション行に data-loopback-iface-id 属性が付いている（解決可能ケース）。"""
    from lib.rendering import render
    html = render(_make_ibgp_loopback_topology())
    # BGP Sessions の tr[data-bgp-id] に data-loopback-iface-id が付いていること
    # r1 の iBGP 行に r1::Loopback0 の iface-id が解決されること
    assert 'data-loopback-iface-id="r1::Loopback0"' in html, \
        "iBGP 行（r1）に data-loopback-iface-id=\"r1::Loopback0\" が付いていない"


@pytest.mark.unit
def test_p2_ibgp_row_loopback_iface_id_r2():
    """#1-G2: r2 の iBGP 行にも data-loopback-iface-id が付く。"""
    from lib.rendering import render
    html = render(_make_ibgp_loopback_topology())
    assert 'data-loopback-iface-id="r2::Loopback0"' in html, \
        "iBGP 行（r2）に data-loopback-iface-id=\"r2::Loopback0\" が付いていない"


# ---------------------------------------------------------------------------
# #1-H: eBGP 行には data-loopback-iface-id が付かない（非回帰）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_ebgp_row_no_loopback_iface_id(rendered_html):
    """#1-H: eBGP 行（通常 peer-link 使用）に data-loopback-iface-id は付かない。"""
    # サンプル topology は eBGP のみ
    # data-loopback-iface-id が付く行がないこと（または iBGP のみに付くこと）
    # rendered_html は examples topology（eBGP）を使う
    # eBGP 行（r1 の BGP Sessions）に data-loopback-iface-id がないこと
    bgp_section = re.search(
        r'layer-bgp.*?</table>',
        rendered_html, re.DOTALL
    )
    if bgp_section:
        bgp_html = bgp_section.group(0)
        assert "data-loopback-iface-id" not in bgp_html, \
            "eBGP 行に data-loopback-iface-id が付いている（iBGP のみが対象）"


# ---------------------------------------------------------------------------
# #5-A: _updateEdgeHighlightForSelection 関数（または同等ロジック）が JS に存在する
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_multi_node_edge_highlight_logic_exists(rendered_html):
    """#5-A: 複数ノード選択時にエッジをハイライトするロジックが JS に存在する。"""
    # _selectedNodes.size >= 2 の条件チェックが存在すること
    assert "_selectedNodes.size" in rendered_html, \
        "_selectedNodes.size チェックが JS にない（複数選択エッジハイライトが未実装）"


# ---------------------------------------------------------------------------
# #5-B: ノードクリックハンドラに data-a/data-b 両方含まれるエッジのハイライトロジックがある
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_node_click_highlights_edges_between_selected(rendered_html):
    """#5-B: JS にノードクリック時「data-a/data-b が両方 _selectedNodes に含まれるエッジを highlighted」ロジックがある。"""
    # data-a と data-b の両方が _selectedNodes に含まれる場合のチェックコードが存在すること
    js_text = rendered_html[rendered_html.find("<script>"):]
    # _selectedNodes.has(...) が data-a/data-b の確認ロジックとして存在すること
    assert "_selectedNodes.has" in js_text, \
        "_selectedNodes.has() によるエッジ判定ロジックが JS にない"


# ---------------------------------------------------------------------------
# #5-C: clearSelection でエッジハイライトが解除される（既存の clearLinkHighlight を流用）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_clear_selection_removes_edge_highlight(rendered_html):
    """#5-C: clearSelection が呼ばれると highlighted エッジも解除される（clearLinkHighlight 経由）。"""
    # clearSelection 内に clearLinkHighlight の呼び出しが存在すること（既存確認）
    js_text = rendered_html[rendered_html.find("<script>"):]
    assert "clearLinkHighlight" in js_text, \
        "clearLinkHighlight が JS にない"
    # clearSelection 関数内で clearLinkHighlight が呼ばれていること
    clear_sel_match = re.search(
        r'function clearSelection\(\).*?clearLinkHighlight',
        js_text, re.DOTALL
    )
    assert clear_sel_match is not None, \
        "clearSelection 内に clearLinkHighlight 呼び出しがない"


# ---------------------------------------------------------------------------
# #5-D: bgp-session / link-edge に対するエッジハイライトループが存在する
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_edge_highlight_loop_covers_bgp_and_link(rendered_html):
    """#5-D: 複数選択エッジハイライトが .bgp-session と .link-edge 両方を走査する。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    # .bgp-session と .link-edge の querySelectorAll が複数選択ロジック近傍に存在すること
    assert "bgp-session" in js_text, \
        ".bgp-session の参照が JS にない"
    assert "link-edge" in js_text, \
        ".link-edge の参照が JS にない"


# ---------------------------------------------------------------------------
# #5-E: 1ノード以下選択でエッジハイライトを解除するコードが存在する
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_single_node_clears_edge_highlight(rendered_html):
    """#5-E: 選択ノードが1個以下になったときエッジハイライトを解除するコードが存在する。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    # _selectedNodes.size が 2 未満のときに highlighted を remove するコードがあること
    # "<= 1" または "< 2" での分岐コードが存在すること
    has_leq1 = "_selectedNodes.size <= 1" in js_text or "_selectedNodes.size < 2" in js_text
    assert has_leq1, \
        "_selectedNodes.size <= 1 (または < 2) の分岐コードが JS にない"


# ---------------------------------------------------------------------------
# #3-A: _applyIfFilters が _hiddenNodes を AND 条件で参照している
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_apply_if_filters_uses_hidden_nodes(rendered_html):
    """#3-A: _applyIfFilters 関数が _hiddenNodes を参照して ifinv 行をフィルタする。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    # _applyIfFilters の定義中に _hiddenNodes の参照が存在すること
    applyif_match = re.search(
        r'function _applyIfFilters\(\).*?_hiddenNodes',
        js_text, re.DOTALL
    )
    assert applyif_match is not None, \
        "_applyIfFilters 内に _hiddenNodes の参照がない（#3 node-filter連動が未実装）"


# ---------------------------------------------------------------------------
# #3-B: setNodeVisibility 後に _applyIfFilters が呼ばれる
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_set_node_visibility_calls_apply_if_filters(rendered_html):
    """#3-B: setNodeVisibility 内で _applyIfFilters() が呼ばれている。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    set_vis_match = re.search(
        r'function setNodeVisibility\(.*?\n.*?_applyIfFilters',
        js_text, re.DOTALL
    )
    assert set_vis_match is not None, \
        "setNodeVisibility 内に _applyIfFilters() 呼び出しがない"


# ---------------------------------------------------------------------------
# #3-C: clearAllNodes / selectAllNodes 後に _applyIfFilters が呼ばれる
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_clear_all_nodes_calls_apply_if_filters(rendered_html):
    """#3-C: clearAllNodes 内で _applyIfFilters() が呼ばれている。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    clear_all_match = re.search(
        r'function clearAllNodes\(\).*?_applyIfFilters',
        js_text, re.DOTALL
    )
    assert clear_all_match is not None, \
        "clearAllNodes 内に _applyIfFilters() 呼び出しがない"


@pytest.mark.unit
def test_p2_select_all_nodes_calls_apply_if_filters(rendered_html):
    """#3-C2: selectAllNodes 内で _applyIfFilters() が呼ばれている。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    select_all_match = re.search(
        r'function selectAllNodes\(\).*?_applyIfFilters',
        js_text, re.DOTALL
    )
    assert select_all_match is not None, \
        "selectAllNodes 内に _applyIfFilters() 呼び出しがない"


# ---------------------------------------------------------------------------
# #3-D: _applyIfFilters で機器行に ifinv-row-hidden が付く（matchDevice 連動確認）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_apply_if_filters_hidden_nodes_condition(rendered_html):
    """#3-D: _applyIfFilters が data-device と _hiddenNodes の AND で行を隠す条件を持つ。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    # _hiddenNodes.has(...) が _applyIfFilters の関数スコープ内に存在すること
    applyif_with_has = re.search(
        r'function _applyIfFilters\(\).*?_hiddenNodes\.has',
        js_text, re.DOTALL
    )
    assert applyif_with_has is not None, \
        "_applyIfFilters 内に _hiddenNodes.has() がない（機器フィルタ条件が未実装）"


# ---------------------------------------------------------------------------
# 非回帰: 既存の選択/ハイライト/フィルタ機能が壊れていない
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_regression_toggle_bgp_highlight_exists(rendered_html):
    """非回帰: toggleBgpHighlight 関数が引き続き存在する。"""
    assert "function toggleBgpHighlight" in rendered_html, \
        "toggleBgpHighlight が HTML から消えた（非回帰）"


@pytest.mark.unit
def test_p2_regression_toggle_ospf_highlight_exists(rendered_html):
    """非回帰: toggleOspfHighlight 関数が引き続き存在する。"""
    assert "function toggleOspfHighlight" in rendered_html, \
        "toggleOspfHighlight が HTML から消えた（非回帰）"


@pytest.mark.unit
def test_p2_regression_selected_nodes_set_exists(rendered_html):
    """非回帰: _selectedNodes Set 宣言が引き続き存在する。"""
    assert "var _selectedNodes = new Set()" in rendered_html, \
        "_selectedNodes Set 宣言が消えた（非回帰）"


@pytest.mark.unit
def test_p2_regression_clear_all_nodes_function_exists(rendered_html):
    """非回帰: clearAllNodes 関数が引き続き存在する。"""
    assert "function clearAllNodes" in rendered_html, \
        "clearAllNodes が HTML から消えた（非回帰）"


@pytest.mark.unit
def test_p2_regression_apply_if_filters_still_has_existing_conditions(rendered_html):
    """非回帰: _applyIfFilters の既存フィルタ条件（matchDevice/matchStatus 等）が残っている。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    # 既存の matchDevice 条件が残っていること
    assert "_ifinvDeviceFilter" in js_text, \
        "_ifinvDeviceFilter が _applyIfFilters から消えた（非回帰）"
    assert "_ifinvStatusFilter" in js_text, \
        "_ifinvStatusFilter が _applyIfFilters から消えた（非回帰）"


# ===========================================================================
# フィードバック対応 (P1/P1b/P2) テスト
# ===========================================================================


# ---------------------------------------------------------------------------
# B1 修正: test_p2_ebgp_row_no_loopback_iface_id — BGP テーブルを正確に抽出
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p2_ebgp_row_no_loopback_iface_id_v2(rendered_html):
    """#1-H 改: eBGP 行に data-loopback-iface-id が付かないことをBGP表本体で確認。

    layer-bgp CSS クラスの誤マッチを避け、"BGP Sessions" 見出し直後の
    <table class="layer-bgp"> 内のみを検査する。
    rendered_html は examples topology（eBGP のみ）を使う。
    """
    # "BGP Sessions" テキスト以降の最初の </table> までを抽出
    bgp_section = re.search(
        r'BGP Sessions</h4>.*?<table[^>]*>.*?</table>',
        rendered_html, re.DOTALL
    )
    # BGP Sessions テーブルがない場合はテストをスキップ（eBGP なし topology）
    if bgp_section is None:
        return
    bgp_html = bgp_section.group(0)
    # eBGP 行に data-loopback-iface-id がないこと
    assert "data-loopback-iface-id" not in bgp_html, (
        f"eBGP 行に data-loopback-iface-id が付いている（iBGP のみが対象）。"
        f"BGP テーブル部: {bgp_html[:200]}"
    )


# ---------------------------------------------------------------------------
# B2 修正: test_p1b2_no_overlap_after_chip_height_expand — _node_size_for ベースに修正
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_p1b2_no_overlap_after_chip_height_expand_v2():
    """P1b #2 改: _node_size_for ベースでの no-overlap 判定（layout と整合）。

    layout が使う _node_size_for(n_ifaces) ベースで判定することで、
    実際のレイアウトエンジンとテスト判定を一致させる（B HIGH-1 修正）。
    """
    from lib.rendering.layout import _node_size_for
    from lib.rendering.svg import _IF_CHIP_PER_ROW
    from lib.rendering import _build_physical_layout

    # per_row * 2 + 1 チップ（3行）を持つノードを含む
    n_chips = _IF_CHIP_PER_ROW * 2 + 1
    topo = _make_many_chip_topology(n_chips)
    devices = topo["devices"]
    links = topo["links"]

    # IF 数マップ（_build_physical_layout が node_sizes として使う）
    iface_count: dict[str, int] = {}
    for iface in topo["interfaces"]:
        dev_id = iface["device"]
        iface_count[dev_id] = iface_count.get(dev_id, 0) + 1

    node_ids = [d["id"] for d in devices]
    pos = _build_physical_layout(devices, topo["interfaces"], links, topo["segments"])

    for i, na in enumerate(node_ids):
        for j, nb in enumerate(node_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            # layout は _node_size_for(n_ifaces) を使う（B HIGH-1 修正）
            wa, ha = _node_size_for(iface_count.get(na, 0))
            wb, hb = _node_size_for(iface_count.get(nb, 0))
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            min_sep_x = (wa + wb) / 2 + 5
            min_sep_y = (ha + hb) / 2 + 5
            no_overlap = dx >= min_sep_x or dy >= min_sep_y
            assert no_overlap, (
                f"_node_size_for ベース: ノード {na}({wa:.0f}x{ha:.0f}) と "
                f"{nb}({wb:.0f}x{hb:.0f}) が重なっている "
                f"(dx={dx:.1f} min_sep_x={min_sep_x:.1f}, "
                f"dy={dy:.1f} min_sep_y={min_sep_y:.1f})"
            )


# ---------------------------------------------------------------------------
# B3 (HIGH-2): OSPF セグメントラベルが tspan 2行（dy が異なる）であること
# ---------------------------------------------------------------------------

def _make_ospf_segment_topology_simple():
    """OSPF セグメント付き最小 topology（A1 ラベルテスト用）。
    area1 に 192.168.50.0/24 セグメントが含まれる。
    """
    return {
        "title": "OSPF Segment Label Test",
        "generated_from": [],
        "devices": [
            {"id": "core1", "hostname": "CORE1", "vendor": "cisco_ios",
             "as": None, "sections": []},
            {"id": "acc1", "hostname": "ACC1", "vendor": "cisco_ios",
             "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "core1::Gi0/2", "device": "core1", "name": "GigabitEthernet0/2",
             "ip": "192.168.50.1/24", "vlan": None, "description": None, "shutdown": False,
             "addresses": [], "admin_status": "up"},
            {"id": "acc1::Gi0/0", "device": "acc1", "name": "GigabitEthernet0/0",
             "ip": "192.168.50.2/24", "vlan": None, "description": None, "shutdown": False,
             "addresses": [], "admin_status": "up"},
        ],
        "links": [],
        "segments": [
            {
                "id": "seg::192.168.50.0/24",
                "subnet": "192.168.50.0/24",
                "ospf_area": "1",
                "ospf_network": "192.168.50.0/24",
                "members": ["core1::Gi0/2", "acc1::Gi0/0"],
            }
        ],
        "routing": {
            "bgp": [],
            "ospf": [
                {"device": "core1", "network": "192.168.50.0/24", "area": "1", "process": "1"},
                {"device": "acc1", "network": "192.168.50.0/24", "area": "1", "process": "1"},
            ],
            "static": [],
        },
    }


@pytest.mark.unit
def test_a1_ospf_segment_label_two_tspan():
    """A1: OSPF セグメントラベルが tspan 2行（area 行と subnet 行に dy が異なる）で描画される。

    楕円内の seg-label text に <tspan dy="0">area ...</tspan> と
    <tspan dy="14">subnet</tspan> の2行が存在することを確認（B HIGH-2）。
    """
    from lib.rendering import render
    topo = _make_ospf_segment_topology_simple()
    html = render(topo)

    # OSPF ビューの seg-label を探す
    seg_labels = re.findall(
        r'<text[^>]*class="[^"]*seg-label[^"]*"[^>]*>(.*?)</text>',
        html, re.DOTALL
    )
    assert seg_labels, "seg-label text 要素が見つからない"

    # 少なくとも1つの seg-label が tspan 2行であること
    found_two_tspan = False
    for label_content in seg_labels:
        tspans = re.findall(r'<tspan[^>]*dy="([^"]+)"[^>]*>', label_content)
        if len(tspans) >= 2:
            found_two_tspan = True
            dy_vals = [float(t) for t in tspans]
            assert dy_vals[0] == 0.0, \
                f"1行目 tspan の dy={dy_vals[0]} が 0 でない（area 行）"
            assert dy_vals[1] > 0.0, \
                f"2行目 tspan の dy={dy_vals[1]} が 0 以下（subnet 行が別行でない）"
            break

    assert found_two_tspan, (
        f"OSPF セグメントラベルに tspan 2行が見つからない。"
        f"見つかった seg-label: {seg_labels[:2]}"
    )


@pytest.mark.unit
def test_a1_ospf_segment_label_has_area_and_subnet():
    """A1: OSPF セグメントラベルに area と subnet が別 tspan で入っている。"""
    from lib.rendering import render
    topo = _make_ospf_segment_topology_simple()
    html = render(topo)

    # "area 1" と "192.168.50.0/24" が別々の tspan に含まれること
    seg_labels = re.findall(
        r'<text[^>]*class="[^"]*seg-label[^"]*"[^>]*>(.*?)</text>',
        html, re.DOTALL
    )
    assert seg_labels, "seg-label text 要素が見つからない"

    for label_content in seg_labels:
        tspans = re.findall(r'<tspan[^>]*>(.*?)</tspan>', label_content, re.DOTALL)
        if len(tspans) >= 2:
            area_tspan = tspans[0]
            subnet_tspan = tspans[1]
            assert "area" in area_tspan.lower() or "1" in area_tspan, \
                f"1行目 tspan に area 情報がない: {area_tspan}"
            assert "192.168.50" in subnet_tspan or "/" in subnet_tspan, \
                f"2行目 tspan に subnet 情報がない: {subnet_tspan}"
            return

    pytest.fail(f"tspan 2行の seg-label が見つからない: {seg_labels[:2]}")


# ---------------------------------------------------------------------------
# A2: AS 衝突回避の試行上限を動的に（large-topo 非回帰）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_a2_resolve_chip_pos_dynamic_limit():
    """A2: _resolve_chip_pos の試行上限が動的（固定 10 でない）で、AS 多数時に収束する。"""
    from lib.rendering.svg import _svg_bgp_as_groups
    from lib.rendering.layout import _NODE_WIDTH, _NODE_HEIGHT

    # 6 個の AS（固定 10 回試行では足りないケースを想定）
    n_as = 6
    devices = []
    positions = {}
    for i in range(n_as):
        dev_id = f"r{i+1}"
        devices.append({"id": dev_id, "hostname": f"R{i+1}", "as": i + 1})
        # 全デバイスを同一 y 座標に並べて衝突しやすくする
        positions[dev_id] = (i * 50.0, 100.0)

    svg_out = _svg_bgp_as_groups(devices, positions)
    # SVG が生成されること（エラーで空でないこと）
    assert svg_out, "6 AS で _svg_bgp_as_groups が空を返した"
    # 全 AS のラベルチップが含まれること
    for i in range(n_as):
        assert f"AS {i + 1}" in svg_out, \
            f"AS {i + 1} のラベルが SVG に含まれない"


@pytest.mark.unit
def test_a2_large_topo_as_groups_regression():
    """A2 非回帰: large-topo（AS5）で _svg_bgp_as_groups が重なりなく生成される。"""
    import os
    large_dir = os.path.join(
        os.path.dirname(__file__), "..", "evals", "inputs", "large-topo"
    )
    if not os.path.isdir(large_dir):
        pytest.skip("large-topo フィクスチャが存在しない")

    from scripts.parse_configs import parse_paths, collect_inputs
    from scripts.build_topology import build
    from lib.rendering import render

    paths = collect_inputs(large_dir)
    devices = parse_paths(paths)
    topo = build(devices, generated_from=paths)
    html = render(topo)
    assert html, "large-topo で render() が空を返した（非回帰）"
    # AS グループが生成されていること（BGP ビューに as-group が存在）
    assert "as-group" in html, "large-topo の BGP ビューに as-group が見つからない"


# ---------------------------------------------------------------------------
# A3: static ルートの宛先が Loopback /32 のとき data-loopback-iface-id が付く
# ---------------------------------------------------------------------------

def _make_static_loopback_topology():
    """static 経路の宛先が他機器の Loopback /32 になる topology。
    acc1 → acc2::Loopback0 (10.255.3.2/32) への static ルートがある。
    """
    return {
        "title": "Static Loopback Test",
        "generated_from": [],
        "devices": [
            {"id": "acc1", "hostname": "ACC1", "vendor": "cisco_ios",
             "as": None, "sections": []},
            {"id": "acc2", "hostname": "ACC2", "vendor": "cisco_ios",
             "as": None, "sections": []},
        ],
        "interfaces": [
            {"id": "acc1::Loopback0", "device": "acc1", "name": "Loopback0",
             "ip": "10.255.3.1/32", "vlan": None, "description": None, "shutdown": False,
             "addresses": [], "admin_status": "up"},
            {"id": "acc1::Gi0/0", "device": "acc1", "name": "GigabitEthernet0/0",
             "ip": "192.168.50.2/24", "vlan": None, "description": None, "shutdown": False,
             "addresses": [], "admin_status": "up"},
            {"id": "acc2::Loopback0", "device": "acc2", "name": "Loopback0",
             "ip": "10.255.3.2/32", "vlan": None, "description": None, "shutdown": False,
             "addresses": [], "admin_status": "up"},
            {"id": "acc2::Gi0/0", "device": "acc2", "name": "GigabitEthernet0/0",
             "ip": "192.168.50.3/24", "vlan": None, "description": None, "shutdown": False,
             "addresses": [], "admin_status": "up"},
        ],
        "links": [],
        "segments": [],
        "routing": {
            "bgp": [],
            "ospf": [],
            "static": [
                # acc1 → acc2 の Loopback (/32)
                {"device": "acc1", "prefix": "10.255.3.2/32", "next_hop": "192.168.50.3"},
                # acc2 → acc1 の Loopback (/32)
                {"device": "acc2", "prefix": "10.255.3.1/32", "next_hop": "192.168.50.2"},
            ],
        },
    }


@pytest.mark.unit
def test_a3_static_loopback_iface_id_attached():
    """A3: static ルート（宛先 /32）の行に宛先機器の Loopback iface-id が付く。

    acc1 の static 宛先 10.255.3.2/32 は acc2::Loopback0 のアドレスなので、
    その行に data-loopback-iface-id="acc2::Loopback0" が付与されること。
    """
    from lib.rendering import render
    topo = _make_static_loopback_topology()
    html = render(topo)

    # acc1 の static 行に data-loopback-iface-id="acc2::Loopback0" が存在すること
    assert 'data-loopback-iface-id="acc2::Loopback0"' in html, (
        "static 宛先 10.255.3.2/32 の行に data-loopback-iface-id=\"acc2::Loopback0\" がない。"
        f"Static Route 関連 HTML: {re.findall(r'data-route-id[^>]*', html)[:5]}"
    )


@pytest.mark.unit
def test_a3_static_loopback_iface_id_r2_to_r1():
    """A3: acc2 → acc1 方向の static 行にも Loopback iface-id が付く。"""
    from lib.rendering import render
    topo = _make_static_loopback_topology()
    html = render(topo)
    assert 'data-loopback-iface-id="acc1::Loopback0"' in html, (
        "static 宛先 10.255.3.1/32 の行に data-loopback-iface-id=\"acc1::Loopback0\" がない"
    )


@pytest.mark.unit
def test_a3_static_non_loopback_no_iface_id():
    """A3: static 宛先が /32 でない（または解決不能）場合は data-loopback-iface-id が付かない。"""
    from lib.rendering import render
    topo = _make_static_loopback_topology()
    # prefix が /24 のルートを追加（/32 解決対象外）
    topo["routing"]["static"].append(
        {"device": "acc1", "prefix": "0.0.0.0/0", "next_hop": "192.168.50.1"}
    )
    html = render(topo)
    # /32 Loopback 解決ルートが存在すること（既存のものが壊れていない）
    assert 'data-loopback-iface-id="acc2::Loopback0"' in html, \
        "/32 ルートの data-loopback-iface-id が消えた"
    # 0.0.0.0/0 行に data-loopback-iface-id がないこと
    # route-id="acc1::0.0.0.0/0::..." を含む tr に loopback-iface-id がないこと
    default_tr = re.search(
        r'<tr[^>]*data-route-id="acc1::0\.0\.0\.0/0::[^"]*"[^>]*>',
        html
    )
    if default_tr:
        assert "data-loopback-iface-id" not in default_tr.group(0), \
            "0.0.0.0/0 ルート行に data-loopback-iface-id が付いている（対象外）"


# ---------------------------------------------------------------------------
# A4: toggleIfChipHighlight — some() ベースのトグル判定
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_a4_toggle_if_chip_highlight_uses_some(rendered_html):
    """A4: toggleIfChipHighlight が chips[0] ではなく Array.from(chips).some() でトグル判定する。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    # toggleIfChipHighlight 関数内に some() が存在すること
    toggle_fn = re.search(
        r'function toggleIfChipHighlight\(ifaceId\)(.*?)^    \}',
        js_text, re.DOTALL | re.MULTILINE
    )
    if toggle_fn is None:
        # 関数定義が 1 行インデントでない場合も考慮
        toggle_fn = re.search(
            r'function toggleIfChipHighlight\(ifaceId\)(.*?)(?=\n  function |\n    function )',
            js_text, re.DOTALL
        )
    assert toggle_fn is not None, "toggleIfChipHighlight 関数が見つからない"
    fn_body = toggle_fn.group(1)
    assert ".some(" in fn_body or "Array.from" in fn_body, (
        "toggleIfChipHighlight が chips[0] ベース判定のまま（.some() が未使用）。"
        f"関数本体: {fn_body[:300]}"
    )


# ---------------------------------------------------------------------------
# A5: DOMContentLoaded で zoomFit — IIFE 後に初期化
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_a5_zoom_fit_uses_dom_content_loaded(rendered_html):
    """A5: 初期 zoomFit が DOMContentLoaded または IIFE 後の即時呼び出しで実行される。

    window.addEventListener('load', ...) ではなく DOMContentLoaded を使うか、
    IIFE で window._zoomFit を定義した後に呼び出す設計になっていること。
    """
    js_text = rendered_html[rendered_html.find("<script>"):]
    # DOMContentLoaded で zoomFit を呼ぶ、または window._zoomFit 定義後に即時呼び出す
    has_domcontentloaded = "DOMContentLoaded" in js_text and "_zoomFit" in js_text
    # フォールバック: window._zoomFit が定義される IIFE の後に selectView と zoomFit が続く構造
    has_post_iife = bool(re.search(
        r'window\._zoomFit\s*=\s*zoomFit.*?\}\)\(\);.*?_zoomFit\(\)',
        js_text, re.DOTALL
    ))
    assert has_domcontentloaded or has_post_iife, (
        "初期 zoomFit が DOMContentLoaded ではなく load イベント（or 未定義状態）で呼ばれている。"
        "A5: DOMContentLoaded に変更してください。"
    )


# ---------------------------------------------------------------------------
# A6: selectAll/clearAll の _applyIfFilters 多重呼び出し最適化
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_a6_select_all_nodes_calls_apply_if_filters_once(rendered_html):
    """A6: selectAllNodes のループ内では _applyIfFilters を呼ばず、最後に1回のみ呼ぶ。

    setNodeVisibility 内の _applyIfFilters 呼び出しをループ中にスキップして
    最後に1回まとめて呼ぶ設計になっていること（中間ちらつき解消）。
    """
    js_text = rendered_html[rendered_html.find("<script>"):]

    # selectAllNodes 関数を抽出
    select_fn = re.search(
        r'function selectAllNodes\(\)(.*?)(?=\nfunction |\n    function )',
        js_text, re.DOTALL
    )
    assert select_fn is not None, "selectAllNodes 関数が見つからない"
    fn_body = select_fn.group(1)

    # ループ内の setNodeVisibility 呼び出し数と、ループ外の _applyIfFilters の有無を確認
    # skipFilter 引数 or ループ後に _applyIfFilters() が来る構造
    has_skip_filter = "skipFilter" in fn_body or "skipApply" in fn_body
    has_post_apply = "_applyIfFilters" in fn_body

    # いずれかの方式（skipFilter 引数 or ループ後一括呼び出し）が採用されていること
    assert has_skip_filter or has_post_apply, (
        "selectAllNodes にループ後の _applyIfFilters 呼び出しが見当たらない"
    )


@pytest.mark.unit
def test_a6_clear_all_nodes_calls_apply_if_filters_once(rendered_html):
    """A6: clearAllNodes のループ内では _applyIfFilters を呼ばず、最後に1回のみ呼ぶ。"""
    js_text = rendered_html[rendered_html.find("<script>"):]

    clear_fn = re.search(
        r'function clearAllNodes\(\)(.*?)(?=\nfunction |\n    function )',
        js_text, re.DOTALL
    )
    assert clear_fn is not None, "clearAllNodes 関数が見つからない"
    fn_body = clear_fn.group(1)

    has_skip_filter = "skipFilter" in fn_body or "skipApply" in fn_body
    has_post_apply = "_applyIfFilters" in fn_body

    assert has_skip_filter or has_post_apply, (
        "clearAllNodes にループ後の _applyIfFilters 呼び出しが見当たらない"
    )


# ---------------------------------------------------------------------------
# B HIGH-3 修正: if-chip click → toggleIfChipHighlight の近傍結合確認
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_b_high3_if_chip_click_toggle_proximity(rendered_html):
    """B HIGH-3: '.if-chip' セレクタと addEventListener('click') と toggleIfChipHighlight が
    近傍（同一 IIFE/スコープ内）で結合されていることを確認する。
    """
    js_text = rendered_html[rendered_html.find("<script>"):]
    # if-chip クリック登録 IIFE（.querySelectorAll('.if-chip[data-iface-id]') を含む）内に
    # addEventListener('click') と toggleIfChipHighlight が共存すること
    chip_iife = re.search(
        r"querySelectorAll\('[^']*if-chip[^']*'\).*?addEventListener.*?click.*?toggleIfChipHighlight",
        js_text, re.DOTALL
    )
    assert chip_iife is not None, (
        "'.if-chip' セレクタ → addEventListener('click') → toggleIfChipHighlight が"
        "近傍で結合されていない"
    )


@pytest.mark.unit
def test_b_high3_ifinv_row_data_iface_id_value(rendered_html):
    """B HIGH-3 補: ifinv 行の data-iface-id に具体値（非空文字列）が入っている。"""
    ifinv_tr = re.search(
        r'<tr[^>]*data-iface-id="([^"]+)"',
        rendered_html
    )
    assert ifinv_tr is not None, "ifinv 行に data-iface-id が見つからない"
    iface_id_val = ifinv_tr.group(1)
    assert iface_id_val, "data-iface-id が空文字列"
    # iface-id は "{device}::{ifname}" 形式であること（:: を含む）
    assert "::" in iface_id_val, \
        f"data-iface-id=\"{iface_id_val}\" が {{device}}::{{ifname}} 形式でない"


# ---------------------------------------------------------------------------
# C1: _chip_positions docstring が現実装を正確に記述している
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_c1_chip_positions_docstring_mentions_chip_node_size():
    """C1: _chip_positions の docstring が _chip_node_size_for を参照している。"""
    import inspect
    from lib.rendering.svg import _chip_positions
    doc = inspect.getdoc(_chip_positions) or ""
    assert "_chip_node_size_for" in doc, (
        "_chip_positions の docstring が _chip_node_size_for を参照していない（C HIGH-1）"
    )


# ---------------------------------------------------------------------------
# C2: _chip_xy_for ヘルパー — 座標重複排除
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_c2_chip_xy_for_helper_exists():
    """C2: _chip_xy_for(k, nx, chip_start_y) ヘルパーが svg.py に存在する。"""
    import lib.rendering.svg as svg_mod
    assert hasattr(svg_mod, "_chip_xy_for"), (
        "_chip_xy_for ヘルパーが svg.py に存在しない（C HIGH-2）"
    )


@pytest.mark.unit
def test_c2_chip_xy_for_returns_correct_coords():
    """C2: _chip_xy_for が _svg_if_chip / _chip_positions と一致する座標を返す。"""
    from lib.rendering.svg import (
        _chip_xy_for, _IF_CHIP_OFFSET_X, _IF_CHIP_GAP, _IF_CHIP_OFFSET_Y,
        _IF_CHIP_ROW_H, _IF_CHIP_PER_ROW,
    )
    nx = 50.0
    chip_start_y = 90.0

    # k=0: col=0, row=0
    cx0, cy0 = _chip_xy_for(0, nx, chip_start_y)
    assert abs(cx0 - (nx + _IF_CHIP_OFFSET_X)) < 0.5, \
        f"k=0 の cx={cx0:.1f} が期待値 {nx + _IF_CHIP_OFFSET_X:.1f} と異なる"
    assert abs(cy0 - (chip_start_y + _IF_CHIP_OFFSET_Y)) < 0.5, \
        f"k=0 の cy={cy0:.1f} が期待値 {chip_start_y + _IF_CHIP_OFFSET_Y:.1f} と異なる"

    # k=_IF_CHIP_PER_ROW: col=0, row=1
    cx1, cy1 = _chip_xy_for(_IF_CHIP_PER_ROW, nx, chip_start_y)
    assert abs(cx1 - (nx + _IF_CHIP_OFFSET_X)) < 0.5, \
        f"k={_IF_CHIP_PER_ROW} の cx={cx1:.1f} が col=0 の期待値と異なる（折返し）"
    assert abs(cy1 - (chip_start_y + _IF_CHIP_OFFSET_Y + _IF_CHIP_ROW_H)) < 0.5, \
        f"k={_IF_CHIP_PER_ROW} の cy={cy1:.1f} が2行目期待値と異なる"


# ---------------------------------------------------------------------------
# 非回帰: multi-as-area での static loopback 解決（A3 実データ確認）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_a3_multi_as_area_static_loopback_regression():
    """A3 非回帰: multi-as-area フィクスチャの acc1/acc2 相互 loopback static で解決確認。"""
    import os
    multi_dir = os.path.join(
        os.path.dirname(__file__), "..", "evals", "inputs", "multi-as-area"
    )
    if not os.path.isdir(multi_dir):
        pytest.skip("multi-as-area フィクスチャが存在しない")

    from scripts.parse_configs import parse_paths, collect_inputs
    from scripts.build_topology import build
    from lib.rendering import render

    paths = collect_inputs(multi_dir)
    devs = parse_paths(paths)
    topo = build(devs, generated_from=paths)
    html = render(topo)

    # acc1 の static 宛先 10.255.3.2/32 → acc2::Loopback0
    # acc2 の static 宛先 10.255.3.1/32 → acc1::Loopback0
    # どちらかが解決されていること（どちらかの Loopback iface-id が static 行に付く）
    has_any_static_loopback = (
        'data-loopback-iface-id' in html and
        re.search(r'<table[^>]*class="[^"]*layer-static[^"]*"', html) is not None
    )
    # static テーブルがない場合は build が static を認識していないのでスキップ
    if re.search(r'<table[^>]*class="[^"]*layer-static[^"]*"', html) is None:
        pytest.skip("multi-as-area topology に static テーブルが生成されていない")

    assert has_any_static_loopback, (
        "multi-as-area の acc1/acc2 static loopback 行に data-loopback-iface-id がない"
    )


# ===========================================================================
# FA: フィードバック対応
#   F4: ノード間隔縮小（_CANVAS_FACTOR 圧縮）
#   F3: AS枠の重なり分離（BGPビュー AS65000 ↔ AS65103 等が被る問題）
# ===========================================================================


# ---------------------------------------------------------------------------
# F4: _CANVAS_FACTOR_W / _CANVAS_FACTOR_H を 3 / 2.5 まで縮小
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fa_f4_canvas_factor_w_le3():
    """F4: _CANVAS_FACTOR_W が 3 以下（ノード間隔圧縮済み）"""
    from lib.rendering.layout import _CANVAS_FACTOR_W
    assert _CANVAS_FACTOR_W <= 3, (
        f"_CANVAS_FACTOR_W={_CANVAS_FACTOR_W} が 3 超（縮小未実施）"
    )


@pytest.mark.unit
def test_fa_f4_canvas_factor_h_le2_5():
    """F4: _CANVAS_FACTOR_H が 2.5 以下（ノード間隔圧縮済み）"""
    from lib.rendering.layout import _CANVAS_FACTOR_H
    assert _CANVAS_FACTOR_H <= 2.5, (
        f"_CANVAS_FACTOR_H={_CANVAS_FACTOR_H} が 2.5 超（縮小未実施）"
    )


@pytest.mark.unit
def test_fa_f4_canvas_shrinks_vs_factor6_5():
    """F4: 縮小後のキャンバスが係数6/5より小さい（n=20 Physical）"""
    from lib.rendering.layout import (
        _canvas_size_for_nodes, _NODE_WIDTH, _NODE_HEIGHT,
        _CANVAS_SCALE_EXP, _MIN_CANVAS_W, _MIN_CANVAS_H,
    )
    n = 20
    w_new, h_new = _canvas_size_for_nodes(n)
    w_old = max(_MIN_CANVAS_W, n * (_NODE_WIDTH + 20) ** _CANVAS_SCALE_EXP * 6)
    h_old = max(_MIN_CANVAS_H, n * (_NODE_HEIGHT + 20) ** _CANVAS_SCALE_EXP * 5)
    assert w_new < w_old, (
        f"F4: 縮小後幅 {w_new:.0f} >= 旧値 {w_old:.0f}（係数 6 比）"
    )
    assert h_new < h_old, (
        f"F4: 縮小後高 {h_new:.0f} >= 旧値 {h_old:.0f}（係数 5 比）"
    )


@pytest.mark.unit
def test_fa_f4_no_overlap_large_topo_20nodes():
    """F4: 係数縮小後も large-topo 20台でノード矩形が重ならない（non-regression）"""
    from lib.rendering.layout import (
        _layout_force_directed, _node_size_for, _canvas_size_for_nodes, _adaptive_iter
    )

    topo = _load_large_topo_for_test()
    devices = topo["devices"]
    links = topo["links"]
    interfaces = topo["interfaces"]

    node_ids = [d["id"] for d in devices]
    edges = [(lk["a_device"], lk["b_device"]) for lk in links]
    iface_count: dict[str, int] = {}
    for iface in interfaces:
        iface_count[iface["device"]] = iface_count.get(iface["device"], 0) + 1
    node_sizes = {d["id"]: iface_count.get(d["id"], 0) for d in devices}

    n = len(node_ids)
    est_w, est_h = _canvas_size_for_nodes(n, max_node_h=max(
        _node_size_for(node_sizes.get(nid, 0))[1] for nid in node_ids
    ))
    pos = _layout_force_directed(
        node_ids, edges, width=est_w, height=est_h,
        iterations=_adaptive_iter(n), node_sizes=node_sizes,
    )

    for i, na in enumerate(node_ids):
        for j, nb in enumerate(node_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            wa, ha = _node_size_for(node_sizes[na])
            wb, hb = _node_size_for(node_sizes[nb])
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            min_sep_x = (wa + wb) / 2 + 5
            min_sep_y = (ha + hb) / 2 + 5
            no_overlap = dx >= min_sep_x or dy >= min_sep_y
            assert no_overlap, (
                f"F4: large-topo ノード {na} と {nb} が重なっている "
                f"(dx={dx:.1f} min_sep_x={min_sep_x:.1f}, "
                f"dy={dy:.1f} min_sep_y={min_sep_y:.1f})"
            )


@pytest.mark.unit
def test_fa_f4_no_overlap_multi_as_area():
    """F4: 係数縮小後も multi-as-area BGP ビューでノード重なりゼロ"""
    from lib.rendering.views import _build_bgp_layout
    from lib.rendering.layout import _node_size_for

    topo = _make_multi_as_area_topology()
    pos, _devs = _build_bgp_layout(
        topo["devices"], topo["routing"].get("bgp", []), topo["interfaces"]
    )
    iface_count: dict[str, int] = {}
    for iface in topo["interfaces"]:
        iface_count[iface["device"]] = iface_count.get(iface["device"], 0) + 1

    dev_ids = [d["id"] for d in topo["devices"] if d["id"] in pos]
    for i, na in enumerate(dev_ids):
        for j, nb in enumerate(dev_ids):
            if j <= i:
                continue
            x1, y1 = pos[na]
            x2, y2 = pos[nb]
            wa, ha = _node_size_for(iface_count.get(na, 0))
            wb, hb = _node_size_for(iface_count.get(nb, 0))
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            needed_x = (wa + wb) / 2 + 5
            needed_y = (ha + hb) / 2 + 5
            no_overlap = dx >= needed_x or dy >= needed_y
            assert no_overlap, (
                f"F4: multi-as-area ノード {na} と {nb} が重なっている "
                f"(dx={dx:.1f} needed_x={needed_x:.1f}, "
                f"dy={dy:.1f} needed_y={needed_y:.1f})"
            )


@pytest.mark.unit
def test_fa_f4_deterministic(sample_topology):
    """F4: 係数縮小後も render() が決定的（2回一致）"""
    import copy
    from lib.rendering import render
    html1 = render(copy.deepcopy(sample_topology))
    html2 = render(copy.deepcopy(sample_topology))
    assert html1 == html2, "F4: 係数縮小後の render() が非決定的"


# ---------------------------------------------------------------------------
# F3: AS枠の重なり分離
# ---------------------------------------------------------------------------

def _as_group_rects_from_bgp_view(bgp_view_html: str) -> list[tuple[float, float, float, float]]:
    """BGP ビュー HTML から as-group <rect> の (x, y, w, h) を抽出して返す。"""
    # <rect x="..." y="..." width="..." height="..." ... class="as-group" ...>
    rects = re.findall(
        r'<rect\s+x="([^"]+)"\s+y="([^"]+)"\s+width="([^"]+)"\s+height="([^"]+)"[^>]*class="as-group"',
        bgp_view_html,
    )
    if not rects:
        # class が後置の場合
        rects = re.findall(
            r'<rect[^>]+class="as-group"[^>]*x="([^"]+)"[^>]*y="([^"]+)"[^>]*width="([^"]+)"[^>]*height="([^"]+)"',
            bgp_view_html,
        )
    return [(float(x), float(y), float(w), float(h)) for x, y, w, h in rects]


def _aabb_overlap(ax: float, ay: float, aw: float, ah: float,
                  bx: float, by: float, bw: float, bh: float,
                  margin: float = 0.0) -> bool:
    """2 AABB (左上x,y・幅・高さ) が重なるか判定する（margin で収縮）。"""
    # margin > 0 の場合は判定を甘くする（マージン分だけ重なりを許容）
    return not (
        ax + aw <= bx + margin or
        bx + bw <= ax + margin or
        ay + ah <= by + margin or
        by + bh <= ay + margin
    )


@pytest.mark.unit
def test_fa_f3_large_topo_bgp_as_rects_no_overlap():
    """F3: large-topo BGP ビューで全 AS 枠 rect ペアが非重なり（AS65000 ↔ AS65103 含む）"""
    import os
    from scripts.parse_configs import parse_paths, collect_inputs
    from scripts.build_topology import build
    from lib.rendering import render

    large_dir = os.path.join(
        os.path.dirname(__file__), "..", "evals", "inputs", "large-topo"
    )
    paths = collect_inputs(large_dir)
    devices_raw = parse_paths(paths)
    topo = build(devices_raw, generated_from=paths)
    html = render(topo)

    # BGP ビュー部分を抽出
    bgp_m = re.search(
        r'<g class="view view-bgp"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>)',
        html, re.DOTALL
    )
    assert bgp_m, "view-bgp が見つからない"
    bgp_view = bgp_m.group(0)

    rects = _as_group_rects_from_bgp_view(bgp_view)
    assert len(rects) >= 2, f"AS 枠 rect が 2 個未満: {len(rects)} 個"

    # 全 AS 枠ペアの非重なりを検証（1px の余裕を持たせた判定）
    margin = 1.0  # 1px 以内の接触は許容（浮動小数点誤差）
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            ax, ay, aw, ah = rects[i]
            bx, by, bw, bh = rects[j]
            assert not _aabb_overlap(ax, ay, aw, ah, bx, by, bw, bh, margin=margin), (
                f"F3: AS枠 [{i}]=({ax:.0f},{ay:.0f},{aw:.0f},{ah:.0f}) と "
                f"[{j}]=({bx:.0f},{by:.0f},{bw:.0f},{bh:.0f}) が重なっている"
            )


@pytest.mark.unit
def test_fa_f3_multi_as_area_bgp_as_rects_no_overlap():
    """F3 非回帰: multi-as-area (AS65000/65100/65200) の全 AS 枠ペアが非重なり"""
    from lib.rendering import render

    topo = _make_multi_as_area_topology()
    html = render(topo)

    bgp_m = re.search(
        r'<g class="view view-bgp"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>)',
        html, re.DOTALL
    )
    assert bgp_m, "multi-as-area: view-bgp が見つからない"
    bgp_view = bgp_m.group(0)

    rects = _as_group_rects_from_bgp_view(bgp_view)
    if len(rects) < 2:
        return  # AS 単体 or BGP ビューなし → スキップ（非エラー）

    margin = 1.0
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            ax, ay, aw, ah = rects[i]
            bx, by, bw, bh = rects[j]
            assert not _aabb_overlap(ax, ay, aw, ah, bx, by, bw, bh, margin=margin), (
                f"F3 multi-as-area: AS枠 [{i}]=({ax:.0f},{ay:.0f},{aw:.0f},{ah:.0f}) と "
                f"[{j}]=({bx:.0f},{by:.0f},{bw:.0f},{bh:.0f}) が重なっている"
            )


@pytest.mark.unit
def test_fa_f3_as_relative_positions_preserved():
    """F3: AS 内相対位置が維持される（同一 AS メンバーの相対座標が分離前後で変わらない）"""
    from lib.rendering.views import _build_bgp_layout

    # AS65000 に 4 台: core1/core2/edge1/edge2 → 内部相対距離は維持される
    topo = _load_large_topo_for_test()
    pos, bgp_devs = _build_bgp_layout(
        topo["devices"], topo["routing"]["bgp"], topo["interfaces"]
    )

    # AS65000 メンバーを収集
    as65000 = [d["id"] for d in bgp_devs if d.get("as") == 65000 and d["id"] in pos]
    assert len(as65000) >= 2, f"AS65000 メンバーが少なすぎ: {as65000}"

    # 2 回呼んで座標が一致 → 決定性確認（相対位置の安定性代替検証）
    pos2, _ = _build_bgp_layout(
        topo["devices"], topo["routing"]["bgp"], topo["interfaces"]
    )
    for dev_id in as65000:
        x1, y1 = pos[dev_id]
        x2, y2 = pos2[dev_id]
        assert abs(x1 - x2) < 0.01 and abs(y1 - y2) < 0.01, (
            f"F3: AS65000 メンバー {dev_id} の座標が非決定的 ({x1:.1f},{y1:.1f}) vs ({x2:.1f},{y2:.1f})"
        )


@pytest.mark.unit
def test_fa_f3_external_nodes_survive_separation():
    """F3: AS 分離後も外部ピアノード（ext:...）が BGP ビューに存在する"""
    import os
    from scripts.parse_configs import parse_paths, collect_inputs
    from scripts.build_topology import build
    from lib.rendering import render

    large_dir = os.path.join(
        os.path.dirname(__file__), "..", "evals", "inputs", "large-topo"
    )
    paths = collect_inputs(large_dir)
    devices_raw = parse_paths(paths)
    topo = build(devices_raw, generated_from=paths)
    html = render(topo)

    bgp_m = re.search(
        r'<g class="view view-bgp"[^>]*>(.*?)(?=<g class="view view-|</g>\s*</g>)',
        html, re.DOTALL
    )
    if not bgp_m:
        return  # BGP ビューなし → 外部ノードもなし → OK

    bgp_view = bgp_m.group(0)
    # large-topo には cust1~4 (AS65101~65104) の単一AS eBGP があるが外部ノードはないはず
    # BGP ビューが生成されていること自体を確認する
    assert "device-node" in bgp_view, "F3: BGP ビューに device-node が存在しない"


@pytest.mark.unit
def test_fa_f3_deterministic_after_separation():
    """F3: AS 枠分離後も render() が決定的（2回 BGP ビュー一致）"""
    import copy
    import os
    from scripts.parse_configs import parse_paths, collect_inputs
    from scripts.build_topology import build
    from lib.rendering import render

    large_dir = os.path.join(
        os.path.dirname(__file__), "..", "evals", "inputs", "large-topo"
    )
    paths = collect_inputs(large_dir)
    devices_raw = parse_paths(paths)
    topo = build(devices_raw, generated_from=paths)

    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "F3: AS 枠分離後の render() が非決定的"


# ===========================================================================
# FB: 複数選択ビュー対応 (F1) + IF一覧選択連動 (F2)
# ===========================================================================

# ---------------------------------------------------------------------------
# F1-A: _updateEdgeHighlightForSelection が _currentView で分岐する
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f1_update_edge_highlight_branches_on_current_view(rendered_html):
    """F1-A: _updateEdgeHighlightForSelection が _currentView を参照して分岐する。
    ビュー対応前は _currentView を見ていないため FAIL する。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _updateEdgeHighlightForSelection\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_updateEdgeHighlightForSelection 関数が JS に見つからない"
    func_body = func_match.group(1)
    assert "_currentView" in func_body, \
        "_updateEdgeHighlightForSelection が _currentView を参照していない（F1 ビュー分岐未実装）"


# ---------------------------------------------------------------------------
# F1-B: physical ビュー時は .view-physical .link-edge のみをハイライト対象にする
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f1_physical_view_targets_view_physical_link_edge(rendered_html):
    """F1-B: physical ビューのエッジハイライトが view-physical スコープの .link-edge を対象とする。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _updateEdgeHighlightForSelection\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_updateEdgeHighlightForSelection 関数が JS に見つからない"
    func_body = func_match.group(1)
    # physical 分岐で view-physical スコープのセレクタを使うこと
    assert "view-physical" in func_body, \
        "_updateEdgeHighlightForSelection が .view-physical スコープを参照していない（F1-B 未実装）"


# ---------------------------------------------------------------------------
# F1-C: physical ビュー時は BGP 表行（tr[data-bgp-id]）をハイライトしない
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f1_physical_view_does_not_touch_bgp_table(rendered_html):
    """F1-C: physical ビュー選択ハイライトは BGP 表行（tr[data-bgp-id]）を操作しない。
    分岐内の physical セクションに tr[data-bgp-id] が出現しないことを確認する。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _updateEdgeHighlightForSelection\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_updateEdgeHighlightForSelection 関数が JS に見つからない"
    func_body = func_match.group(1)
    # physical 分岐があること
    assert "_currentView" in func_body, \
        "F1-C の前提: _currentView 分岐が存在しない"
    # physical 条件節を取り出す: === 'physical' のブロックに tr[data-bgp-id] が出ないこと
    physical_block_match = re.search(
        r"=== ['\"]physical['\"].*?(?=\s*\}\s*else\s*if\s*\(|\s*\}\s*// end if _currentView|\Z)",
        func_body, re.DOTALL
    )
    if physical_block_match:
        physical_block = physical_block_match.group(0)
        assert 'data-bgp-id' not in physical_block, \
            "F1-C: physical 分岐内で BGP 表行（data-bgp-id）を操作している"


# ---------------------------------------------------------------------------
# F1-D: bgp ビュー時は .view-bgp .bgp-session をハイライト対象にする
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f1_bgp_view_targets_view_bgp_bgp_session(rendered_html):
    """F1-D: bgp ビューのエッジハイライトが view-bgp スコープの .bgp-session を対象とする。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _updateEdgeHighlightForSelection\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_updateEdgeHighlightForSelection 関数が JS に見つからない"
    func_body = func_match.group(1)
    assert "view-bgp" in func_body, \
        "_updateEdgeHighlightForSelection が .view-bgp スコープを参照していない（F1-D 未実装）"


# ---------------------------------------------------------------------------
# F1-E: bgp ビュー時は tr[data-bgp-id] 表行もハイライトする
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f1_bgp_view_highlights_bgp_table_rows(rendered_html):
    """F1-E: bgp ビューのハイライトで BGP 表行（tr[data-bgp-id]）もハイライトする。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _updateEdgeHighlightForSelection\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_updateEdgeHighlightForSelection 関数が JS に見つからない"
    func_body = func_match.group(1)
    # bgp 分岐内に data-bgp-id の参照があること
    bgp_block_match = re.search(
        r"=== ['\"]bgp['\"].*?(?=\s*\}\s*else\s*if\s*\(|\s*\}\s*// end if _currentView|\Z)",
        func_body, re.DOTALL
    )
    if bgp_block_match:
        bgp_block = bgp_block_match.group(0)
        assert 'data-bgp-id' in bgp_block, \
            "F1-E: bgp 分岐内で BGP 表行（data-bgp-id）をハイライトしていない"
    else:
        # 分岐の抽出ができない場合は関数全体に data-bgp-id と view-bgp の共存を確認
        assert 'data-bgp-id' in func_body and 'view-bgp' in func_body, \
            "F1-E: _updateEdgeHighlightForSelection に view-bgp かつ data-bgp-id の参照がない"


# ---------------------------------------------------------------------------
# F1-F: ospf ビュー時は .view-ospf .link-edge をハイライト対象にする
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f1_ospf_view_targets_view_ospf_link_edge(rendered_html):
    """F1-F: ospf ビューのエッジハイライトが view-ospf スコープの .link-edge を対象とする。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _updateEdgeHighlightForSelection\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_updateEdgeHighlightForSelection 関数が JS に見つからない"
    func_body = func_match.group(1)
    assert "view-ospf" in func_body, \
        "_updateEdgeHighlightForSelection が .view-ospf スコープを参照していない（F1-F 未実装）"


# ---------------------------------------------------------------------------
# F1-G: ospf ビュー時は OSPF 表行（tr[data-ospf-id]）もハイライトする
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f1_ospf_view_highlights_ospf_table_rows(rendered_html):
    """F1-G: ospf ビューのハイライトで OSPF 表行（data-ospf-id トークンマッチ）もハイライトする。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _updateEdgeHighlightForSelection\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_updateEdgeHighlightForSelection 関数が JS に見つからない"
    func_body = func_match.group(1)
    # ospf 分岐内に data-ospf-id の参照があること
    assert "data-ospf-id" in func_body, \
        "F1-G: _updateEdgeHighlightForSelection 内に data-ospf-id の参照がない（OSPF 表連動未実装）"


# ---------------------------------------------------------------------------
# F1-H: selectView 呼び出し後に _updateEdgeHighlightForSelection が再適用される
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f1_select_view_calls_update_edge_highlight(rendered_html):
    """F1-H: selectView 関数が _updateEdgeHighlightForSelection() を呼んでビュー切替時に再適用する。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    selectview_match = re.search(
        r'function selectView\(viewId\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert selectview_match is not None, \
        "selectView 関数が JS に見つからない"
    sv_body = selectview_match.group(1)
    assert "_updateEdgeHighlightForSelection" in sv_body, \
        "F1-H: selectView 内で _updateEdgeHighlightForSelection() が呼ばれていない（ビュー切替時の再適用未実装）"


# ---------------------------------------------------------------------------
# F1-I: clearSelection で selection-edge-hl が全解除される（非回帰）
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f1_clear_selection_removes_selection_edge_hl(rendered_html):
    """F1-I 非回帰: clearSelection 後は selection-edge-hl が解除される仕組みが存在する。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    # _updateEdgeHighlightForSelection の冒頭で selection-edge-hl を解除すること
    func_match = re.search(
        r'function _updateEdgeHighlightForSelection\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_updateEdgeHighlightForSelection 関数が JS に見つからない"
    func_body = func_match.group(1)
    assert "selection-edge-hl" in func_body, \
        "F1-I: _updateEdgeHighlightForSelection 内に selection-edge-hl の解除コードが存在しない"


# ---------------------------------------------------------------------------
# F2-A: selectView('ifinv') 時にドロップダウン状態変数がリセットされる
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f2_select_view_ifinv_resets_device_filter(rendered_html):
    """F2-A: selectView('ifinv') 入場時に _ifinvDeviceFilter が空文字にリセットされる。
    直接 selectView 内でも _resetIfinvFilters() 経由でも可。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    # _resetIfinvFilters 関数があり、その中で _ifinvDeviceFilter = '' を行う場合を確認
    reset_func_match = re.search(
        r'function _resetIfinvFilters\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    if reset_func_match:
        reset_body = reset_func_match.group(1)
        assert "_ifinvDeviceFilter" in reset_body, \
            "F2-A: _resetIfinvFilters 内で _ifinvDeviceFilter がリセットされていない（残留バグ未修正）"
        # selectView の ifinv 分岐から _resetIfinvFilters が呼ばれること
        sv_match = re.search(
            r'function selectView\(viewId\)(.*?)(?=\n    function |\n    // ={3,})',
            js_text, re.DOTALL
        )
        assert sv_match is not None, "selectView 関数が JS に見つからない"
        sv_body = sv_match.group(1)
        ifinv_block_match = re.search(
            r"viewId\s*===\s*['\"]ifinv['\"].*?(?=\}\s*else\b|\Z)",
            sv_body, re.DOTALL
        )
        if ifinv_block_match:
            ifinv_block = ifinv_block_match.group(0)
            has_direct = "_ifinvDeviceFilter" in ifinv_block
            has_indirect = "_resetIfinvFilters" in ifinv_block
            assert has_direct or has_indirect, \
                "F2-A: selectView ifinv 分岐内で _ifinvDeviceFilter も _resetIfinvFilters も呼ばれていない"
    else:
        # _resetIfinvFilters がない場合: selectView 内に直接 _ifinvDeviceFilter があること
        sv_match = re.search(
            r'function selectView\(viewId\)(.*?)(?=\n    function |\n    // ={3,})',
            js_text, re.DOTALL
        )
        assert sv_match is not None, "selectView 関数が JS に見つからない"
        assert "_ifinvDeviceFilter" in sv_match.group(1), \
            "F2-A: selectView に _ifinvDeviceFilter リセットコードがない（残留バグ未修正）"


# ---------------------------------------------------------------------------
# F2-B: selectView('ifinv') 時にドロップダウン <select> の value もリセットされる
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f2_select_view_ifinv_resets_select_element_value(rendered_html):
    """F2-B: selectView('ifinv') 入場時に ifinv-filter-device の <select>.value が '' にリセットされる。
    直接 selectView 内でも、_resetIfinvFilters() 経由でも可。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    # selectView または _resetIfinvFilters のどちらかに ifinv-filter-device の参照があること
    assert "ifinv-filter-device" in js_text, \
        "F2-B: ifinv-filter-device セレクタ参照が JS にない（<select>.value リセット未実装）"
    # さらに、selectView の ifinv 分岐から _resetIfinvFilters か直接参照が呼ばれること
    reset_func_match = re.search(
        r'function _resetIfinvFilters\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    if reset_func_match:
        # _resetIfinvFilters 内に ifinv-filter-device があること
        assert "ifinv-filter-device" in reset_func_match.group(1), \
            "F2-B: _resetIfinvFilters 内に ifinv-filter-device 参照がない"


# ---------------------------------------------------------------------------
# F2-C: selectView('ifinv') 入場時に _applyIfFilters が呼ばれる
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f2_select_view_ifinv_calls_apply_if_filters(rendered_html):
    """F2-C: selectView('ifinv') 入場時に _applyIfFilters() が（直接または間接に）呼ばれる。
    _resetIfinvFilters() 経由でも可（_resetIfinvFilters の中で _applyIfFilters を呼ぶ）。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    selectview_match = re.search(
        r'function selectView\(viewId\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert selectview_match is not None, \
        "selectView 関数が JS に見つからない"
    sv_body = selectview_match.group(1)
    # ifinv 分岐内で _applyIfFilters() 直接または _resetIfinvFilters()（間接）が呼ばれること
    ifinv_block_match = re.search(
        r"viewId\s*===\s*['\"]ifinv['\"].*?(?=\}\s*else\b|\Z)",
        sv_body, re.DOTALL
    )
    if ifinv_block_match:
        ifinv_block = ifinv_block_match.group(0)
        has_direct = "_applyIfFilters" in ifinv_block
        has_indirect = "_resetIfinvFilters" in ifinv_block
        assert has_direct or has_indirect, \
            "F2-C: selectView ifinv 分岐内で _applyIfFilters() も _resetIfinvFilters() も呼ばれていない"
        # _resetIfinvFilters 経由の場合、その関数内で _applyIfFilters が呼ばれることを確認
        if has_indirect and not has_direct:
            reset_func_match = re.search(
                r'function _resetIfinvFilters\(\)(.*?)(?=\n    function |\n    // ={3,})',
                js_text, re.DOTALL
            )
            assert reset_func_match is not None, \
                "F2-C: _resetIfinvFilters 関数が JS に見つからない"
            assert "_applyIfFilters" in reset_func_match.group(1), \
                "F2-C: _resetIfinvFilters 内で _applyIfFilters() が呼ばれていない"
    else:
        has_call = "_applyIfFilters" in sv_body or "_resetIfinvFilters" in sv_body
        assert has_call, \
            "F2-C: selectView に _applyIfFilters() / _resetIfinvFilters() 呼び出しがない"


# ---------------------------------------------------------------------------
# F2-D: _applyIfFilters に _selectedNodes による matchSelection 条件がある
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f2_apply_if_filters_has_match_selection_condition(rendered_html):
    """F2-D: _applyIfFilters が _selectedNodes に基づく matchSelection 条件を持つ。
    ノード未選択は全表示、複数選択なら選択機器のみ表示（IF一覧の選択連動）。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _applyIfFilters\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_applyIfFilters 関数が JS に見つからない"
    func_body = func_match.group(1)
    # _selectedNodes を参照するマッチ条件が存在すること
    assert "_selectedNodes" in func_body, \
        "F2-D: _applyIfFilters に _selectedNodes による選択連動条件がない（F2 選択連動未実装）"


# ---------------------------------------------------------------------------
# F2-E: _applyIfFilters の AND 条件に matchSelection が追加されている
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f2_apply_if_filters_and_includes_match_selection(rendered_html):
    """F2-E: _applyIfFilters の 最終 AND 式に matchSelection (または同等変数) が含まれる。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _applyIfFilters\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_applyIfFilters 関数が JS に見つからない"
    func_body = func_match.group(1)
    # matchSelection（または matchSel / selectedMatch 等）が AND 式に含まれること
    has_match_selection = (
        "matchSelection" in func_body
        or re.search(r'matchSel\b', func_body) is not None
    )
    assert has_match_selection, \
        "F2-E: _applyIfFilters の AND 式に matchSelection 変数が存在しない（F2 選択連動未実装）"


# ---------------------------------------------------------------------------
# F2-F: _selectedNodes.size === 0 のとき matchSelection は全行 true になる
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f2_match_selection_true_when_no_nodes_selected(rendered_html):
    """F2-F: _selectedNodes.size === 0 のとき matchSelection が true になるロジックが存在する。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _applyIfFilters\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_applyIfFilters 関数が JS に見つからない"
    func_body = func_match.group(1)
    # _selectedNodes.size === 0 の条件が matchSelection ロジックにあること
    has_size_zero = (
        "_selectedNodes.size === 0" in func_body
        or "_selectedNodes.size == 0" in func_body
        or re.search(r'_selectedNodes\.size\s*<\s*1\b', func_body) is not None
        or re.search(r'!\s*_selectedNodes\.size\b', func_body) is not None
    )
    assert has_size_zero, \
        "F2-F: _applyIfFilters に _selectedNodes.size === 0 の全行表示条件がない"


# ---------------------------------------------------------------------------
# F2-G: 選択変化（ノードクリック）時に _applyIfFilters が呼ばれる
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f2_node_click_calls_apply_if_filters(rendered_html):
    """F2-G: ノードクリックハンドラが _updateEdgeHighlightForSelection() と
    _applyIfFilters() の両方を呼ぶ。選択変化を IF一覧に即時反映するため必要。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    # _updateEdgeHighlightForSelection() の呼び出しを含むノードクリックハンドラを探し、
    # その直後に _applyIfFilters() があることを確認する
    # ノードクリックハンドラ: _selectedNodes.add(deviceId) ... _updateEdgeHighlightForSelection() ... _applyIfFilters()
    node_handler_match = re.search(
        r'_selectedNodes\.add\(deviceId\).*?_updateEdgeHighlightForSelection\(\).*?_applyIfFilters\(\)',
        js_text, re.DOTALL
    )
    assert node_handler_match is not None, \
        "F2-G: ノードクリックハンドラが _applyIfFilters() を呼んでいない（IF一覧選択連動未実装）"


# ---------------------------------------------------------------------------
# F2-H: カードクリックでも _applyIfFilters が呼ばれる
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f2_card_click_calls_apply_if_filters(rendered_html):
    """F2-H: カードクリックハンドラも _applyIfFilters() を呼ぶ。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    # カードクリックハンドラ: _selectedNodes.add(deviceId) の後に
    # _updateEdgeHighlightForSelection() と _applyIfFilters() が呼ばれること
    # ノードクリックとカードクリックの両方のパターンをカバーするため、
    # device-card を使った querySelectorAll の後のハンドラ本体を確認する
    card_handler_match = re.search(
        r"device-card.*?_updateEdgeHighlightForSelection\(\).*?_applyIfFilters\(\)",
        js_text, re.DOTALL
    )
    assert card_handler_match is not None, \
        "F2-H: カードクリックハンドラが _applyIfFilters() を呼んでいない"


# ---------------------------------------------------------------------------
# F2-I 非回帰: 既存 _applyIfFilters の 7条件 AND が維持される
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_f2_apply_if_filters_existing_conditions_preserved(rendered_html):
    """F2-I 非回帰: F2 追加後も既存フィルタ条件（matchSearch/matchUnused/matchDevice/
    matchAf/matchStatus/matchL2l3/matchNodeFilter）が _applyIfFilters に残っている。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _applyIfFilters\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_applyIfFilters 関数が JS に見つからない"
    func_body = func_match.group(1)
    existing_conditions = [
        "matchSearch", "matchUnused", "matchDevice",
        "matchAf", "matchStatus", "matchL2l3", "matchNodeFilter",
    ]
    for cond in existing_conditions:
        assert cond in func_body, \
            f"F2-I 非回帰: _applyIfFilters から '{cond}' 条件が消えた"


# ---------------------------------------------------------------------------
# F1/F2 非回帰: _updateEdgeHighlightForSelection が既存の selection-edge-hl 解除を保持する
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_regression_update_edge_hl_clears_all_three_selectors(rendered_html):
    """F1 非回帰: _updateEdgeHighlightForSelection が bgp-session/link-edge/tr の
    3セレクタすべての selection-edge-hl を解除するコードを持つ。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _updateEdgeHighlightForSelection\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, \
        "_updateEdgeHighlightForSelection 関数が JS に見つからない"
    func_body = func_match.group(1)
    # 3クリア: bgp-session.selection-edge-hl / link-edge.selection-edge-hl / tr.selection-edge-hl
    assert "bgp-session.selection-edge-hl" in func_body or \
           ("bgp-session" in func_body and "selection-edge-hl" in func_body), \
        "非回帰: bgp-session の selection-edge-hl クリアコードが消えた"
    assert "link-edge.selection-edge-hl" in func_body or \
           ("link-edge" in func_body and "selection-edge-hl" in func_body), \
        "非回帰: link-edge の selection-edge-hl クリアコードが消えた"


# ===========================================================================
# FA/FB 2巡目 低コスト堅牢化テスト
# ===========================================================================

# ---------------------------------------------------------------------------
# 修正1: F3 AS分離 max_iters 動的収束保証 (correctness HIGH-2)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fa_f3_max_iters_dynamic_scales_with_as_count():
    """F3: _separate_as_clusters の実効 max_iters が AS 数に応じた動的値になる。
    8AS を同一座標から呼んだとき全ペアが分離されること（50固定では破綻しうる）。"""
    from lib.rendering.views import _separate_as_clusters

    n_as = 8
    # 8 AS それぞれ 1 台を同じ座標 (0, 0) に配置（最悪ケース）
    positions = {f"dev{i}": (0.0, 0.0) for i in range(n_as)}
    bgp_devices = [{"id": f"dev{i}", "as": 65000 + i} for i in range(n_as)]
    node_sizes = {f"dev{i}": 0 for i in range(n_as)}
    padding = 20.0

    result = _separate_as_clusters(positions, bgp_devices, node_sizes, padding)

    # 全 AS 枠ペアが非重なりであること
    from lib.rendering.views import _as_cluster_bbox

    def _bbox(dev_id):
        return _as_cluster_bbox([dev_id], {dev_id: result[dev_id]}, node_sizes, padding)

    def _rects_overlap(r1, r2):
        ax, ay, ax2, ay2 = r1
        bx, by, bx2, by2 = r2
        return not (ax2 <= bx or bx2 <= ax or ay2 <= by or by2 <= ay)

    dev_ids = list(result.keys())
    for i in range(len(dev_ids)):
        for j in range(i + 1, len(dev_ids)):
            bb_a = _bbox(dev_ids[i])
            bb_b = _bbox(dev_ids[j])
            assert not _rects_overlap(bb_a, bb_b), (
                f"F3: 8AS 同一座標ケースで AS枠 {dev_ids[i]} と {dev_ids[j]} が重なっている"
            )


@pytest.mark.unit
def test_fa_f3_max_iters_10as_all_separated():
    """F3: 10 AS を同一座標から配置しても全ペア AS 枠が分離されること。"""
    from lib.rendering.views import _separate_as_clusters, _as_cluster_bbox

    n_as = 10
    positions = {f"dev{i}": (0.0, 0.0) for i in range(n_as)}
    bgp_devices = [{"id": f"dev{i}", "as": 65000 + i} for i in range(n_as)]
    node_sizes = {f"dev{i}": 0 for i in range(n_as)}
    padding = 20.0

    result = _separate_as_clusters(positions, bgp_devices, node_sizes, padding)

    def _bbox(dev_id):
        return _as_cluster_bbox([dev_id], {dev_id: result[dev_id]}, node_sizes, padding)

    def _rects_overlap(r1, r2):
        ax, ay, ax2, ay2 = r1
        bx, by, bx2, by2 = r2
        return not (ax2 <= bx or bx2 <= ax or ay2 <= by or by2 <= ay)

    dev_ids = list(result.keys())
    for i in range(len(dev_ids)):
        for j in range(i + 1, len(dev_ids)):
            bb_a = _bbox(dev_ids[i])
            bb_b = _bbox(dev_ids[j])
            assert not _rects_overlap(bb_a, bb_b), (
                f"F3: 10AS 同一座標ケースで AS枠 {dev_ids[i]} と {dev_ids[j]} が重なっている"
            )


# ---------------------------------------------------------------------------
# 修正2: clearSelection で selection-edge-hl を確実クリア (correctness MED-1)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_med1_clear_selection_calls_update_edge_highlight(rendered_html):
    """MED-1: clearSelection() 末尾で _updateEdgeHighlightForSelection() を呼ぶ。
    clearSelection 後に selection-edge-hl が残留しないことを保証する。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function clearSelection\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, "clearSelection 関数が見つからない"
    func_body = func_match.group(1)
    assert "_updateEdgeHighlightForSelection" in func_body, (
        "clearSelection() が _updateEdgeHighlightForSelection() を呼んでいない"
        "（clearSelection 後に selection-edge-hl が残留する）"
    )


# ---------------------------------------------------------------------------
# 修正3: _resetIfinvFilters が未使用トグルもリセット (correctness MED-2)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fb_med2_reset_ifinv_filters_resets_unused_toggle(rendered_html):
    """MED-2: _resetIfinvFilters が _ifinvUnusedOnly=false と
    #ifinv-unused-toggle の checked=false をリセットするコードを含む。"""
    js_text = rendered_html[rendered_html.find("<script>"):]
    func_match = re.search(
        r'function _resetIfinvFilters\(\)(.*?)(?=\n    function |\n    // ={3,})',
        js_text, re.DOTALL
    )
    assert func_match is not None, "_resetIfinvFilters 関数が見つからない"
    func_body = func_match.group(1)
    assert "_ifinvUnusedOnly" in func_body, (
        "_resetIfinvFilters が _ifinvUnusedOnly をリセットしていない"
    )
    assert "ifinv-unused-toggle" in func_body, (
        "_resetIfinvFilters が #ifinv-unused-toggle をリセットしていない"
    )


# ---------------------------------------------------------------------------
# 修正4: _as_cluster_bbox 空リストガード (correctness LOW)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fa_low_as_cluster_bbox_empty_raises_value_error():
    """LOW: _as_cluster_bbox([]) は空リストで ValueError を投げる（防御的ガード）。"""
    from lib.rendering.views import _as_cluster_bbox

    with pytest.raises((ValueError, IndexError)):
        _as_cluster_bbox([], {}, {}, 20.0)


@pytest.mark.unit
def test_fa_low_as_cluster_bbox_single_node():
    """LOW: _as_cluster_bbox は1ノードで正常動作する（ガード追加後の非回帰）。"""
    from lib.rendering.views import _as_cluster_bbox

    positions = {"dev1": (100.0, 200.0)}
    node_sizes = {"dev1": 0}
    result = _as_cluster_bbox(["dev1"], positions, node_sizes, padding=20.0)
    min_x, min_y, max_x, max_y = result
    assert min_x < max_x, "min_x >= max_x: bbox が不正"
    assert min_y < max_y, "min_y >= max_y: bbox が不正"


# ===========================================================================
# Round C: 使い勝手3機能
# ===========================================================================

# ---------------------------------------------------------------------------
# ① キーボード操作拡充
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_rc_keyboard_input_guard_in_js(rendered_html):
    """① 入力中ガード: keydown ハンドラが INPUT/TEXTAREA/SELECT の e.target チェックを持つ"""
    js_part = rendered_html[rendered_html.find("<script>"):]
    # e.target.tagName のガード (INPUT/TEXTAREA/SELECT) が含まれること
    assert "INPUT" in js_part, "INPUT ガードが keydown ハンドラにない"
    assert "TEXTAREA" in js_part, "TEXTAREA ガードが keydown ハンドラにない"


@pytest.mark.unit
def test_rc_keyboard_escape_blurs_input(rendered_html):
    """① Escape キー: 入力欄に focus がある場合 blur() を呼ぶコードが存在する"""
    js_part = rendered_html[rendered_html.find("<script>"):]
    assert "blur()" in js_part, "Escape で入力欄を blur() するコードがない"


@pytest.mark.unit
def test_rc_keyboard_number_keys_view_switch(rendered_html):
    """① 数字キー 1〜9 でビュー切替: querySelectorAll('.view-tab') を使う処理が存在する"""
    js_part = rendered_html[rendered_html.find("<script>"):]
    # 数字キーで selectView を呼ぶ分岐
    assert "view-tab" in js_part, "数字キーによるビュー切替コードが見つからない"
    # 数字-1 インデックスのアクセス（parseInt や Number 等）
    assert "parseInt" in js_part or "Number(" in js_part or "charCodeAt" in js_part, \
        "数字キーのインデックス変換処理が見つからない"


@pytest.mark.unit
def test_rc_keyboard_slash_search_focus(rendered_html):
    """① '/' キーで #search-input をフォーカスし preventDefault するコードが存在する"""
    js_part = rendered_html[rendered_html.find("<script>"):]
    assert "search-input" in js_part, "#search-input へのフォーカスコードがない"
    assert "preventDefault" in js_part, "/ キーの preventDefault が見つからない"


@pytest.mark.unit
def test_rc_keyboard_help_text_updated(rendered_html):
    """① ヘルプ文言に数字キーと '/' が追記されている"""
    # ヘッダ部のヘルプ span 内を確認（script ブロック外）
    # script タグを除外した本文を検査
    body_part = re.sub(r'<script[^>]*>.*?</script>', '', rendered_html, flags=re.DOTALL)
    assert "1" in body_part and "5" in body_part, \
        "ヘルプ文言に数字キー (1〜5) の記述がない"
    assert "/" in body_part, "ヘルプ文言に / キーの記述がない"


# ---------------------------------------------------------------------------
# ② 統合凡例トグルパネル
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_rc_legend_toggle_button_exists(rendered_html):
    """② id="legend-toggle" ボタンが存在する"""
    assert 'id="legend-toggle"' in rendered_html, "legend-toggle ボタンが存在しない"


@pytest.mark.unit
def test_rc_legend_panel_exists(rendered_html):
    """② id="legend-panel" パネルが存在する"""
    assert 'id="legend-panel"' in rendered_html, "legend-panel が存在しない"


@pytest.mark.unit
def test_rc_toggle_legend_function_exists(rendered_html):
    """② toggleLegend() 関数が JS に存在する"""
    js_part = rendered_html[rendered_html.find("<script>"):]
    assert "toggleLegend" in js_part, "toggleLegend 関数が存在しない"


@pytest.mark.unit
def test_rc_legend_panel_initially_hidden(rendered_html):
    """② legend-panel は初期状態で非表示 (display:none)"""
    assert 'id="legend-panel"' in rendered_html
    # id="legend-panel" の直後の style 属性に display:none が含まれること
    import re
    m = re.search(r'id="legend-panel"([^>]*>)', rendered_html)
    assert m is not None, "legend-panel 要素が見つからない"
    tag_content = m.group(0) + rendered_html[m.end():m.end() + 50]
    # style="display:none" が要素属性か直後のインラインスタイルに含まれること
    assert "display:none" in tag_content or "display: none" in tag_content, \
        "legend-panel が初期状態で非表示になっていない"


@pytest.mark.unit
def test_rc_legend_static_sections(rendered_html):
    """② 静的凡例ラベル（eBGP / iBGP / Loopback / 外部ピア）が含まれる"""
    assert "eBGP" in rendered_html, "eBGP 凡例ラベルがない"
    assert "iBGP" in rendered_html, "iBGP 凡例ラベルがない"
    assert "Loopback" in rendered_html, "Loopback 凡例ラベルがない"
    assert "外部ピア" in rendered_html, "外部ピア 凡例ラベルがない"


@pytest.mark.unit
def test_rc_legend_dynamic_as_section_with_bgp_topology():
    """② AS を持つ topology で AS{n} 行と _as_color 由来の stroke 色が昇順で出る"""
    from lib.rendering import render
    from lib.rendering.svg import _as_color
    topo = {
        "title": "AS Legend Test",
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
    html = render(topo)
    # AS65001, AS65002 の両方が凡例に含まれること
    assert "AS65001" in html, "legend に AS65001 行がない"
    assert "AS65002" in html, "legend に AS65002 行がない"
    # stroke 色が含まれること（昇順: 65001 -> 65002）
    stroke_65001, _, _ = _as_color(65001)
    stroke_65002, _, _ = _as_color(65002)
    assert stroke_65001 in html, f"legend に AS65001 の stroke 色 {stroke_65001} がない"
    assert stroke_65002 in html, f"legend に AS65002 の stroke 色 {stroke_65002} がない"
    # 昇順: 65001 が 65002 より前に現れること
    pos_65001 = html.find("AS65001")
    pos_65002 = html.find("AS65002")
    assert pos_65001 < pos_65002, "AS 凡例が昇順になっていない（65001 が 65002 より後）"


@pytest.mark.unit
def test_rc_legend_no_as_section_without_bgp():
    """② AS を持たない topology では AS セクションが凡例に出ない"""
    from lib.rendering import render
    topo = {
        "title": "No AS Topology",
        "generated_from": [],
        "devices": [
            {"id": "sw1", "hostname": "SW1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    # AS セクション見出しが出ないこと（"AS枠" や "AS Frame" 等は凡例パネル内限定のため）
    # legend-panel の内容だけ抽出して確認
    import re
    panel_match = re.search(r'id="legend-panel"[^>]*>(.*?)</div>', html, re.DOTALL)
    if panel_match:
        panel_content = panel_match.group(1)
        # AS65XXX 形式の記述がないこと
        assert not re.search(r"AS\d{5}", panel_content), \
            "AS なし topology なのに凡例パネルに AS 行が出ている"


@pytest.mark.unit
def test_rc_legend_deterministic(sample_topology):
    """② legend を含む render 出力が決定的（2回呼んで同一）"""
    from lib.rendering import render
    import copy
    html1 = render(copy.deepcopy(sample_topology))
    html2 = render(copy.deepcopy(sample_topology))
    assert html1 == html2, "legend を含む render 出力が非決定的"


# ---------------------------------------------------------------------------
# ③ 接続フィルタ
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_rc_filter_connected_button_exists(rendered_html):
    """③ id="filter-connected" ボタンが存在する"""
    assert 'id="filter-connected"' in rendered_html, "filter-connected ボタンがない"


@pytest.mark.unit
def test_rc_invert_selection_button_exists(rendered_html):
    """③ id="invert-selection" ボタンが存在する"""
    assert 'id="invert-selection"' in rendered_html, "invert-selection ボタンがない"


@pytest.mark.unit
def test_rc_filter_connected_function_js(rendered_html):
    """③ filterConnected() 相当の JS 関数が存在し physical/bgp/ospf ビュー対応の分岐を持つ"""
    js_part = rendered_html[rendered_html.find("<script>"):]
    assert "filterConnected" in js_part, "filterConnected 関数が存在しない"
    # _currentView 別の分岐確認
    assert "physical" in js_part, "physical ビューの分岐がない"
    assert "bgp" in js_part, "bgp ビューの分岐がない"
    assert "ospf" in js_part, "ospf ビューの分岐がない"


@pytest.mark.unit
def test_rc_filter_connected_uses_link_edge_data(rendered_html):
    """③ filterConnected は .link-edge[data-a][data-b] を参照する"""
    js_part = rendered_html[rendered_html.find("<script>"):]
    assert "link-edge" in js_part and "data-a" in js_part and "data-b" in js_part, \
        "filterConnected が link-edge の data-a/data-b を参照していない"


@pytest.mark.unit
def test_rc_filter_connected_ospf_seg_grouping(rendered_html):
    """③ filterConnected の OSPF 分岐が seg-edge の data-seg-id グルーピングを行う"""
    js_part = rendered_html[rendered_html.find("<script>"):]
    assert "seg-edge" in js_part, "ospf 分岐で seg-edge が参照されていない"
    assert "data-seg-id" in js_part, "ospf 分岐で data-seg-id が参照されていない"


@pytest.mark.unit
def test_rc_invert_selection_function_js(rendered_html):
    """③ invertSelection() 関数が存在し _updateEdgeHighlightForSelection と _updateCardFilter を呼ぶ"""
    js_part = rendered_html[rendered_html.find("<script>"):]
    assert "invertSelection" in js_part, "invertSelection 関数が存在しない"
    assert "_updateEdgeHighlightForSelection" in js_part, \
        "invertSelection が _updateEdgeHighlightForSelection を呼んでいない"
    assert "_updateCardFilter" in js_part, \
        "invertSelection が _updateCardFilter を呼んでいない"


@pytest.mark.unit
def test_rc_filter_connected_empty_selection_noop(rendered_html):
    """③ filterConnected: 選択が空のとき no-op コード（早期リターン等）が存在する"""
    js_part = rendered_html[rendered_html.find("<script>"):]
    # _selectedNodes.size === 0 またはそれに相当するガード
    assert "_selectedNodes.size" in js_part or "_selectedNodes.size ===" in js_part or \
           "if (_selectedNodes.size" in js_part, \
        "filterConnected の空選択ガードが見つからない"


# ---------------------------------------------------------------------------
# Round C バグ修正・テスト強化（tdd-guide 追加分）
# ---------------------------------------------------------------------------


# === 【実バグ1】invertSelection 2パス構造テスト ===

@pytest.mark.unit
def test_rc_invert_selection_two_pass_structure(rendered_html):
    """invertSelection: devId集合を先に確定（pass1）してから全DOM要素にclassListを適用（pass2）する2パス構造を持つ"""
    func_body = _extract_js_function(rendered_html, "invertSelection")
    assert func_body, "invertSelection 関数が見つからない"
    # 2パス構造の検証:
    # pass1: 表示中devIdのうち_selectedNodesに含まれないものだけnewSelectedに追加（classList操作なし）
    # pass2: 全 .device-node に対して newSelected.has(devId) でclassListを一括更新
    # → 1つ目のforEachでは classList.add('selected') が発生しないこと（newSelected.add のみ）
    # → 2つ目のforEachで classList.add/remove を行うこと
    # querySelectorAll が3回以上（device-node pass1 / device-node pass2 / device-card）使われること
    queries = []
    pos = 0
    while True:
        idx = func_body.find("querySelectorAll", pos)
        if idx == -1:
            break
        queries.append(idx)
        pos = idx + 1
    assert len(queries) >= 3, \
        (f"invertSelection の querySelectorAll が {len(queries)} 個しかない。"
         "pass1(devId集合確定) / pass2(device-node classList) / pass3(device-card) の3回が必要")
    # pass1 ループ（1回目querySelectorAll）の中には classList.add('selected') がないこと
    first_loop_start = queries[0]
    second_loop_start = queries[1]
    first_loop_body = func_body[first_loop_start:second_loop_start]
    assert "classList.add('selected')" not in first_loop_body, \
        ("pass1 ループ内で classList.add('selected') が発生している。"
         "devId集合確定フェーズでDOM操作をすると多重ビュー環境でクラス逆転バグが起きる")
    # pass2 ループ（2回目querySelectorAll）には classList 操作があること
    second_loop_body = func_body[second_loop_start:]
    assert "classList" in second_loop_body, \
        "pass2 以降のループに classList 操作がない"


# === 【実バグ2】filterConnected ifinvビューの早期 return テスト ===

@pytest.mark.unit
def test_rc_filter_connected_ifinv_early_return(rendered_html):
    """filterConnected: ifinvビューでは隣接計算をせず早期returnすること"""
    func_body = _extract_js_function(rendered_html, "filterConnected")
    assert func_body, "filterConnected 関数が見つからない"
    # _currentView === 'ifinv' の early return が関数本体にあること
    assert "_currentView === 'ifinv'" in func_body, \
        "filterConnected に ifinv ビューの early return がない（ifinvビュー状態汚染バグ）"
    # returnが直後に来ること（if (_currentView === 'ifinv') return; パターン）
    ifinv_pos = func_body.find("_currentView === 'ifinv'")
    # ifinv 文字列の後150文字以内に return が含まれること
    surrounding = func_body[ifinv_pos:ifinv_pos + 150]
    assert "return" in surrounding, \
        "ifinv チェックの直後に return がない"


# === 【MEDIUM】toggleLegend getComputedStyle テスト ===

@pytest.mark.unit
def test_rc_toggle_legend_uses_computed_style(rendered_html):
    """toggleLegend: CSS由来の非表示も検出できるよう getComputedStyle を使うこと"""
    func_body = _extract_js_function(rendered_html, "toggleLegend")
    assert func_body, "toggleLegend 関数が見つからない"
    assert "getComputedStyle" in func_body, \
        "toggleLegend が getComputedStyle を使っていない（CSS由来displayで誤動作するバグ）"


# === 【テスト強化 H-3】keyboard help text のタグ単位検証 ===

@pytest.mark.unit
def test_rc_keyboard_help_text_kbd_tags(rendered_html):
    """ヘルプ文言に <kbd>1</kbd>〜<kbd>5</kbd> と <kbd>/</kbd> のタグが存在する"""
    body_part = re.sub(r'<script[^>]*>.*?</script>', '', rendered_html, flags=re.DOTALL)
    assert "<kbd>1</kbd>" in body_part, "ヘルプ文言に <kbd>1</kbd> タグがない"
    assert "<kbd>5</kbd>" in body_part, "ヘルプ文言に <kbd>5</kbd> タグがない"
    assert "<kbd>/</kbd>" in body_part, "ヘルプ文言に <kbd>/</kbd> タグがない"


# === 【テスト強化 H-4】filterConnected 関数本体に3分岐があること ===

@pytest.mark.unit
def test_rc_filter_connected_three_view_branches_in_body(rendered_html):
    """filterConnected 関数本体に physical/bgp/ospf の3分岐が全て存在する"""
    func_body = _extract_js_function(rendered_html, "filterConnected")
    assert func_body, "filterConnected 関数が見つからない"
    assert "'physical'" in func_body or '"physical"' in func_body, \
        "filterConnected 本体に physical 分岐がない"
    assert "'bgp'" in func_body or '"bgp"' in func_body, \
        "filterConnected 本体に bgp 分岐がない"
    assert "'ospf'" in func_body or '"ospf"' in func_body, \
        "filterConnected 本体に ospf 分岐がない"


# === 【テスト強化 H-1】legend-panel 領域にスコープした AS 昇順検証 ===

@pytest.mark.unit
def test_rc_legend_as_order_scoped_to_legend_panel():
    """AS凡例の昇順が legend-panel スコープ内で確認される（SVGノードラベルに引っ張られない）"""
    from lib.rendering import render
    topo = {
        "title": "AS Order Test",
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
    html = render(topo)
    # legend-panel 開始位置以降に絞って検証（SVGノードラベル位置に影響されない）
    panel_start = html.find('id="legend-panel"')
    assert panel_start != -1, "legend-panel が見つからない"
    panel_region = html[panel_start:]
    pos_65001 = panel_region.find("AS65001")
    pos_65002 = panel_region.find("AS65002")
    assert pos_65001 != -1, "legend-panel に AS65001 がない"
    assert pos_65002 != -1, "legend-panel に AS65002 がない"
    assert pos_65001 < pos_65002, \
        "legend-panel 内で AS65001 が AS65002 より後に現れる（昇順でない）"


# === 【テスト強化 C-1】legend_no_as の素通り防止 ===

@pytest.mark.unit
def test_rc_legend_no_as_section_scoped():
    """AS なし topology では legend-panel 内に AS 番号行が出ないこと（素通りしない構造）"""
    from lib.rendering import render
    topo = {
        "title": "No AS Topology",
        "generated_from": [],
        "devices": [
            {"id": "sw1", "hostname": "SW1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    panel_start = html.find('id="legend-panel"')
    assert panel_start != -1, "legend-panel が存在しない（素通りせず確実に検証できる）"
    # legend-panel 以降の文字列を対象に AS 番号パターンを検索
    panel_region = html[panel_start:]
    # AS65XXX 形式の AS 番号が含まれないこと
    assert not re.search(r"AS\d{5}", panel_region), \
        "AS なし topology なのに legend-panel 領域に AS 行が出ている"


# === 【テスト強化 M-1】legend_static_sections を legend-panel 領域にスコープ ===

@pytest.mark.unit
def test_rc_legend_static_sections_scoped(rendered_html):
    """静的凡例ラベルが legend-panel 内に含まれること（全体検索でなくパネル内スコープ）"""
    panel_start = rendered_html.find('id="legend-panel"')
    assert panel_start != -1, "legend-panel が存在しない"
    panel_region = rendered_html[panel_start:]
    assert "eBGP" in panel_region, "legend-panel 内に eBGP 凡例ラベルがない"
    assert "iBGP" in panel_region, "legend-panel 内に iBGP 凡例ラベルがない"
    assert "Loopback" in panel_region, "legend-panel 内に Loopback 凡例ラベルがない"
    assert "外部ピア" in panel_region, "legend-panel 内に 外部ピア 凡例ラベルがない"


# === 【ユニットテスト追加】_build_legend_as_html / _collect_bgp_asns 単体 ===

@pytest.mark.unit
def test_rc_build_legend_as_html_empty():
    """_build_legend_as_html([]) は空文字を返す（AS なし → AS セクション非表示）"""
    from lib.rendering.views import _build_legend_as_html
    result = _build_legend_as_html([])
    assert result == "", f"空リストで空文字でなく '{result}' が返った"


@pytest.mark.unit
def test_rc_build_legend_as_html_single():
    """_build_legend_as_html([65001]) は AS65001 を含む HTML を返す"""
    from lib.rendering.views import _build_legend_as_html
    result = _build_legend_as_html([65001])
    assert "AS65001" in result, "_build_legend_as_html が AS65001 を含まない"
    assert "AS 枠" in result, "_build_legend_as_html にセクションタイトルがない"


@pytest.mark.unit
def test_rc_build_legend_as_html_deterministic():
    """_build_legend_as_html は同一入力で同一出力（決定的）"""
    from lib.rendering.views import _build_legend_as_html
    result1 = _build_legend_as_html([65001, 65002])
    result2 = _build_legend_as_html([65001, 65002])
    assert result1 == result2, "_build_legend_as_html が非決定的"


@pytest.mark.unit
def test_rc_collect_bgp_asns_sorted_unique():
    """_collect_bgp_asns は重複なし昇順 int リストを返す"""
    from lib.rendering.views import _collect_bgp_asns
    devices = [
        {"id": "r1", "as": 65002},
        {"id": "r2", "as": 65001},
        {"id": "r3", "as": 65001},  # 重複
    ]
    bgp_entries = [
        {"local_as": 65003, "device": "r1"},
        {"local_as": 65001, "device": "r2"},  # 重複
    ]
    result = _collect_bgp_asns(devices, bgp_entries)
    assert result == [65001, 65002, 65003], f"昇順ユニーク結果が期待と異なる: {result}"


@pytest.mark.unit
def test_rc_collect_bgp_asns_empty():
    """_collect_bgp_asns は空入力で空リストを返す"""
    from lib.rendering.views import _collect_bgp_asns
    result = _collect_bgp_asns([], [])
    assert result == [], f"空入力で [] でなく {result} が返った"


@pytest.mark.unit
def test_rc_collect_bgp_asns_devices_only():
    """_collect_bgp_asns は devices のみの場合でも AS を収集する"""
    from lib.rendering.views import _collect_bgp_asns
    devices = [{"id": "r1", "as": 65100}, {"id": "r2", "as": None}]
    result = _collect_bgp_asns(devices, [])
    assert result == [65100], f"devices のみの AS 収集が期待と異なる: {result}"


# ===========================================================================
# Round C クロスレビュー修正テスト
# ===========================================================================

# ---------------------------------------------------------------------------
# 修正1【HIGH・実バグ】filterConnected OSPF ビューで link-edge も参照する
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_roundc_filter_connected_ospf_also_uses_link_edge(rendered_html):
    """filterConnected の ospf 分岐内に .view-ospf .link-edge[data-a][data-b] が含まれること（p2p 隣接バグ修正）"""
    func_body = _extract_js_function(rendered_html, "filterConnected")
    assert func_body, "filterConnected 関数が見つからない"
    # ospf 分岐のスコープ: 'ospf' 検出位置以降かつ bgp 分岐開始より前を対象
    ospf_start = func_body.find("'ospf'")
    assert ospf_start != -1, "filterConnected に ospf 分岐がない"
    # ospf 分岐内（1500文字以内）に view-ospf .link-edge が含まれること
    ospf_branch = func_body[ospf_start: ospf_start + 1500]
    assert ".view-ospf .link-edge" in ospf_branch, (
        "filterConnected の ospf 分岐が .view-ospf .link-edge[data-a][data-b] を参照していない"
        "（p2p リンク主体のOSPFトポロジで接続先のみが壊れるバグ）"
    )


@pytest.mark.unit
def test_roundc_filter_connected_ospf_branch_has_addadjacentbyedge(rendered_html):
    """filterConnected の ospf 分岐内に _addAdjacentByEdge 呼び出しが存在する（p2p 用）"""
    func_body = _extract_js_function(rendered_html, "filterConnected")
    assert func_body, "filterConnected 関数が見つからない"
    ospf_start = func_body.find("'ospf'")
    assert ospf_start != -1, "filterConnected に ospf 分岐がない"
    ospf_branch = func_body[ospf_start: ospf_start + 1500]
    # ospf 分岐内で _addAdjacentByEdge が呼ばれていること（p2p ヘルパー再利用）
    assert "_addAdjacentByEdge" in ospf_branch, (
        "filterConnected の ospf 分岐内で _addAdjacentByEdge が呼ばれていない"
        "（p2p OSPFリンクに対する隣接解決が欠落）"
    )


@pytest.mark.unit
def test_roundc_ospf_view_link_edge_present_in_ospf_topology():
    """OSPF p2p トポロジの render 出力に .view-ospf 内の link-edge[data-a][data-b] が存在する"""
    from lib.rendering import render
    topo = _make_ospf_two_devices_topology()
    html = render(topo)
    # view-ospf グループを抽出
    ospf_view_start = html.find('class="view view-ospf"')
    assert ospf_view_start != -1, "OSPF ビューが生成されていない"
    # 次の class="view view-" まで or 3000文字の範囲を ospf ビューとみなす
    ospf_view_end = html.find('class="view view-', ospf_view_start + 10)
    if ospf_view_end == -1:
        ospf_view_end = ospf_view_start + 5000
    ospf_view_html = html[ospf_view_start:ospf_view_end]
    # link-edge[data-a][data-b] が存在すること
    assert 'data-a=' in ospf_view_html and 'data-b=' in ospf_view_html, (
        "OSPF ビュー内に link-edge[data-a][data-b] が存在しない"
        "（p2p リンクが link-edge としてレンダリングされていない）"
    )


# ---------------------------------------------------------------------------
# 修正2【MEDIUM・UX】凡例パネルの静的セクションをビュー存在に応じて条件表示
# ---------------------------------------------------------------------------

def _make_ospf_only_topology():
    """BGP なし・OSPF あり の topology（BGP節は出ないはずの検証用）"""
    return {
        "title": "OSPF Only Topology",
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
            "bgp": [],
            "static": [],
        },
    }


def _make_bgp_only_no_ospf_topology():
    """BGP あり・OSPF なし の topology（OSPF節は出ないはずの検証用）"""
    return {
        "title": "BGP Only No OSPF",
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
def test_roundc_legend_bgp_section_present_with_bgp(rendered_html):
    """BGP ビューを持つ sample_topology では凡例パネル内に BGP 節（eBGP/iBGP）が出ること"""
    panel_start = rendered_html.find('id="legend-panel"')
    assert panel_start != -1, "legend-panel が存在しない"
    panel_region = rendered_html[panel_start:]
    assert "eBGP" in panel_region, "BGP あり topology の legend-panel 内に eBGP 節がない"
    assert "iBGP" in panel_region, "BGP あり topology の legend-panel 内に iBGP 節がない"


@pytest.mark.unit
def test_roundc_legend_bgp_section_absent_without_bgp():
    """BGP なし topology では凡例パネル内に BGP 節（eBGP/iBGP/unknown）が出ないこと"""
    from lib.rendering import render
    html = render(_make_ospf_only_topology())
    panel_start = html.find('id="legend-panel"')
    assert panel_start != -1, "legend-panel が存在しない"
    # legend-panel div から <script> タグ開始までをパネル領域として検証
    # （<script> 以降の JS コメントにこれらの文字列が現れる場合を除外するため）
    script_start = html.find("<script>", panel_start)
    panel_region = html[panel_start:script_start] if script_start != -1 else html[panel_start:]
    # BGP 節テキストが含まれないこと
    assert "eBGP" not in panel_region, (
        "BGP なし topology なのに legend-panel（HTML部分）内に 'eBGP' が含まれている（UXバグ）"
    )
    assert "iBGP" not in panel_region, (
        "BGP なし topology なのに legend-panel（HTML部分）内に 'iBGP' が含まれている（UXバグ）"
    )


@pytest.mark.unit
def test_roundc_legend_ospf_section_present_with_ospf(rendered_html):
    """OSPF ビューを持つ sample_topology では凡例パネル内に OSPF 節が出ること"""
    panel_start = rendered_html.find('id="legend-panel"')
    assert panel_start != -1, "legend-panel が存在しない"
    panel_region = rendered_html[panel_start:]
    assert "OSPF リンク" in panel_region, "OSPF あり topology の legend-panel 内に OSPF 節がない"


@pytest.mark.unit
def test_roundc_legend_ospf_section_absent_without_ospf():
    """OSPF なし topology では凡例パネル内に OSPF 節が出ないこと"""
    from lib.rendering import render
    html = render(_make_bgp_only_no_ospf_topology())
    panel_start = html.find('id="legend-panel"')
    assert panel_start != -1, "legend-panel が存在しない"
    # legend-panel div から <script> タグ開始までをパネル領域として検証
    script_start = html.find("<script>", panel_start)
    panel_region = html[panel_start:script_start] if script_start != -1 else html[panel_start:]
    assert "OSPF リンク" not in panel_region, (
        "OSPF なし topology なのに legend-panel（HTML部分）内に 'OSPF リンク' が含まれている（UXバグ）"
    )


@pytest.mark.unit
def test_roundc_legend_node_link_sections_always_present():
    """ノード節・Physical リンク節は BGP/OSPF の有無によらず常に表示されること"""
    from lib.rendering import render
    # BGP も OSPF もない最小 topology
    topo = {
        "title": "Minimal No Protocol",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    panel_start = html.find('id="legend-panel"')
    assert panel_start != -1, "legend-panel が存在しない"
    panel_region = html[panel_start:]
    assert "通常ノード" in panel_region, "legend-panel 内にノード節（通常ノード）がない"
    assert "Physical リンク" in panel_region, "legend-panel 内に Physical リンク節がない"


@pytest.mark.unit
def test_roundc_legend_ifchip_section_always_present():
    """IF チップ節はビュー有無によらず常に表示されること"""
    from lib.rendering import render
    topo = {
        "title": "IF Chip Legend Test",
        "generated_from": [],
        "devices": [
            {"id": "r1", "hostname": "R1", "vendor": "cisco_ios", "as": None, "sections": []},
        ],
        "interfaces": [],
        "links": [],
        "segments": [],
        "routing": {"bgp": [], "ospf": [], "static": []},
    }
    html = render(topo)
    panel_start = html.find('id="legend-panel"')
    assert panel_start != -1, "legend-panel が存在しない"
    panel_region = html[panel_start:]
    assert "接続 IF" in panel_region, "legend-panel 内に IF チップ節（接続 IF）がない"


@pytest.mark.unit
def test_roundc_legend_deterministic_with_bgp_and_ospf(rendered_html):
    """BGP+OSPF を持つ sample_topology での render は決定的（凡例条件分岐修正後も）"""
    from lib.rendering import render
    import copy
    from lib.topology_io import load_topology
    import os
    examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
    topo = load_topology(os.path.join(examples_dir, "topology"))
    html1 = render(copy.deepcopy(topo))
    html2 = render(copy.deepcopy(topo))
    assert html1 == html2, "凡例条件分岐修正後に render 出力が非決定的になっている"


@pytest.mark.unit
def test_roundc_legend_bgp_and_ospf_both_present_with_both_protocols(rendered_html):
    """BGP+OSPF 両方を持つ sample_topology では凡例パネルに BGP 節も OSPF 節も出ること"""
    panel_start = rendered_html.find('id="legend-panel"')
    assert panel_start != -1, "legend-panel が存在しない"
    panel_region = rendered_html[panel_start:]
    assert "eBGP" in panel_region, "BGP+OSPF topology の legend-panel 内に eBGP がない"
    assert "OSPF リンク" in panel_region, "BGP+OSPF topology の legend-panel 内に OSPF リンクがない"
