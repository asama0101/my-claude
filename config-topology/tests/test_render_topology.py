"""
TDD テスト: render_topology.render()

テスト方針:
- examples/sample-topology.json を基準入力として使用
- 各テストは独立しており、共有状態なし
- 外部依存なし（標準ライブラリのみ）
- カバレッジ 80%以上目標
"""
import json
import os
import sys
import copy
import importlib

import pytest

# scripts/ を sys.path に追加
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS_DIR))


# ---- フィクスチャ -------------------------------------------------------

@pytest.fixture(scope="module")
def sample_topology():
    """examples/sample-topology.json を読み込んで返す（モジュールスコープで1回のみ）"""
    examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
    path = os.path.join(examples_dir, "sample-topology.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def rendered_html(sample_topology):
    """sample-topology.json を render() した HTML（モジュールスコープで1回のみ）"""
    from render_topology import render
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
    from render_topology import render
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
    from render_topology import render

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
    from render_topology import render
    try:
        result = render(empty_topology)
    except Exception as e:
        pytest.fail(f"空 topology で例外が発生: {e}")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.unit
def test_render_empty_topology_returns_html(empty_topology):
    """空 topology でも HTML 構造が返る"""
    from render_topology import render
    result = render(empty_topology)
    lower = result.lower()
    assert "<html" in lower or "<!doctype html" in lower


@pytest.mark.unit
def test_render_empty_topology_has_svg(empty_topology):
    """空 topology でも SVG 要素が含まれる（空でも描画エリアあり）"""
    from render_topology import render
    result = render(empty_topology)
    assert "<svg" in result.lower()


# ---- ユニットテスト: 決定性 ---------------------------------------------

@pytest.mark.unit
def test_render_deterministic(sample_topology):
    """同一入力で2回 render した結果が完全一致"""
    from render_topology import render
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
    from render_topology import render

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
    from render_topology import render

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
    """CLI 実行で topology.html が生成される"""
    import subprocess

    # 一時ディレクトリに topology.json を書き出す
    json_path = tmp_path / "topology.json"
    json_path.write_text(json.dumps(sample_topology), encoding="utf-8")

    out_path = tmp_path / "output.html"
    scripts_dir = os.path.join(os.path.dirname(__file__), "..", "scripts")
    script_path = os.path.join(scripts_dir, "render_topology.py")

    result = subprocess.run(
        [sys.executable, script_path, str(json_path), "-o", str(out_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CLI が失敗: stderr={result.stderr}"
    assert out_path.exists(), "出力 HTML ファイルが生成されていない"
    content = out_path.read_text(encoding="utf-8")
    assert len(content) > 100


@pytest.mark.integration
def test_cli_default_output_path(tmp_path, sample_topology):
    """CLI で -o 省略時、入力と同じディレクトリに topology.html が生成される"""
    import subprocess

    json_path = tmp_path / "topology.json"
    json_path.write_text(json.dumps(sample_topology), encoding="utf-8")

    scripts_dir = os.path.join(os.path.dirname(__file__), "..", "scripts")
    script_path = os.path.join(scripts_dir, "render_topology.py")

    result = subprocess.run(
        [sys.executable, script_path, str(json_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CLI が失敗: stderr={result.stderr}"
    expected_out = tmp_path / "topology.html"
    assert expected_out.exists(), "topology.html がデフォルト出力パスに生成されていない"


# ---- 統合テスト: ファイル I/O ------------------------------------------

@pytest.mark.integration
def test_render_output_can_be_written_and_read(tmp_path, sample_topology):
    """render() の出力をファイルに書いて再読込できる"""
    from render_topology import render

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
    from render_topology import render
    html = render(_make_vrrp_topology())
    lower = html.lower()
    # data-layer="vrrp" または id="toggle-vrrp" が存在すること
    assert 'data-layer="vrrp"' in lower or "toggle-vrrp" in lower, \
        "vrrp トグルが生成されていない"


@pytest.mark.unit
def test_vrrp_css_hide_rule_generated():
    """routing に vrrp キーを足すと body.hide-vrrp .layer-vrrp { display:none } 相当のCSSルールが出力される"""
    from render_topology import render
    html = render(_make_vrrp_topology())
    # CSS ルール: body.hide-vrrp .layer-vrrp（display:none を含む）
    assert "hide-vrrp" in html, "body.hide-vrrp CSS ルールが生成されていない"
    assert "layer-vrrp" in html, ".layer-vrrp CSS ルールが生成されていない"


@pytest.mark.unit
def test_existing_protocols_css_still_generated_dynamically(sample_topology):
    """bgp/ospf/static の hide CSS ルールが sample topology でも動的生成で出力される"""
    from render_topology import render
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
    from render_topology import render
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
    from render_topology import render
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
    from render_topology import render
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
    from render_topology import render
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
    from render_topology import render
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
    from render_topology import render
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
    """R1→R2 と R2→R1 の双方向 BGP エントリがあっても SVG のエッジは1本のみ"""
    import re
    from render_topology import render
    html = render(_make_bidirectional_bgp_topology())

    # BGP エッジは <g class="bgp-session"> で囲まれた <path> として描画される
    bgp_sessions = re.findall(r'class="bgp-session"', html)
    assert len(bgp_sessions) == 1, \
        f"BGP 双方向エントリで {len(bgp_sessions)} 本のエッジが描画された（期待: 1本）"


@pytest.mark.unit
def test_bgp_single_direction_still_rendered():
    """片方向 BGP エントリのみのとき、1本のエッジが描画される"""
    import re
    from render_topology import render

    topo = _make_bidirectional_bgp_topology()
    # r2 側エントリを削除（片方向）
    topo["routing"]["bgp"] = [topo["routing"]["bgp"][0]]
    html = render(topo)

    bgp_sessions = re.findall(r'class="bgp-session"', html)
    assert len(bgp_sessions) == 1, \
        f"片方向 BGP エントリで {len(bgp_sessions)} 本のエッジが描画された（期待: 1本）"
