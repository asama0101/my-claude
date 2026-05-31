#!/usr/bin/env python3
"""
topology.json（構造化ネットワークモデル）から、**インタラクティブな構成図HTML**を生成する。
外部ライブラリ無し（素SVG＋バニラJS）・オフライン・`file://` 直開き対応。

特徴:
  - 物理（機器・IF・FDF=光配線盤・TIE=局間タイ回線）と論理（IP・AS・BGP・static）を1枚に重ねて描く。
    フロー（物理経路/eBGP/static）を選ぶと、左サイドバーにステップが展開し、図と表が連動マークされる。
  - **IPはIFに帰属**（IFノードがIPを表示）、**BGPピアは neighbor_ip→対向IF** に解決してアンカーする。
  - **作業で追加となる要素（status:"added"）を緑・太線**で強調（既存=muted、フォーカス=ゴールド）。
  - フロー（物理経路・eBGP往復・static）を選ぶと該当エッジを **5層フォーカス演出**で強調。
  - **1エッジ=1バッジ**＋衝突回避（他バッジ＋Node bbox回避＋escape）、**往復エッジは lane offset** で分離。
  - ホイールズーム / ドラッグパン / 数字キーでフロー選択 / 注釈クリックでフォーカス。
  - データは `topology.flows.json`（サイドカー）に書き出し、HTMLは `fetch` → 失敗時は埋め込みJSONにフォールバック。

使い方:
    python render_topology.py review-work/topology.json -o review-work/topology.html
    # 同ディレクトリに topology.flows.json も出力される
"""
import argparse
import json
import os
import sys


# ───────────────────────── データ変換（network モデル → 描画データ） ─────────────────────────
def build_render_data(topo):
    devices = topo.get("devices", []) or []
    interfaces = topo.get("interfaces", []) or []
    facilities = topo.get("facilities", []) or []
    phys = topo.get("phys_links", []) or []
    bgp = topo.get("bgp", []) or []
    statics = topo.get("static_routes", []) or []

    fac_by_id = {f.get("id"): f for f in facilities}
    dev_by_id = {d.get("id"): d for d in devices}
    if_by_dev = {}
    for itf in interfaces:
        if_by_dev.setdefault(itf.get("device"), []).append(itf)

    def ip_key(v):
        return str(v or "").split("/")[0].strip()

    ip2if = {}
    for itf in interfaces:
        k = ip_key(itf.get("ip"))
        if k:
            ip2if[k] = itf

    # --- 列順序（物理チェーン → 残りの機器）---
    order, seen_dev, seen_fac = [], set(), set()

    def add_col(kind, id_):
        if id_ is None:
            return
        s = seen_dev if kind == "device" else seen_fac
        if id_ in s:
            return
        s.add(id_)
        order.append((kind, id_))

    for pl in phys:
        add_col("device", pl.get("a_device"))
        for v in pl.get("via", []) or []:
            add_col("facility", v)
        add_col("device", pl.get("b_device"))
    for d in devices:
        add_col("device", d.get("id"))
    if not order:
        order = [("device", d.get("id")) for d in devices]

    COLW, DEVW, DEVH, IFW, IFH, FACW, FACH = 300, 188, 56, 170, 46, 132, 46
    n_cols = max(len(order), 1)

    columns, nodes = [], []
    center = {}  # id -> (cx, cy)

    def place(node, cx, cy, w, h):
        node["x"] = round(cx - w / 2, 1)
        node["y"] = round(cy - h / 2, 1)
        node["w"] = w
        node["h"] = h
        nodes.append(node)
        center[node["id"]] = (cx, cy)

    for ci, (kind, id_) in enumerate(order):
        cx = 130 + COLW * ci + COLW / 2
        divider = 130 + COLW * ci
        if kind == "device":
            dev = dev_by_id.get(id_, {"id": id_, "hostname": id_})
            columns.append({"id": "col-" + str(id_), "label": dev.get("hostname", id_),
                            "x": round(cx, 1), "divider": round(divider, 1)})
            place({"id": id_, "title": dev.get("hostname", id_),
                   "subtitle": ("AS" + str(dev["as"])) if dev.get("as") else "",
                   "type": "device", "layer": "physical", "status": dev.get("status", "existing")},
                  cx, 150, DEVW, DEVH)
            iy = 150 + 92
            for itf in if_by_dev.get(id_, []):
                ipv = itf.get("ip", "")
                vl = ("VLAN " + str(itf["vlan"])) if itf.get("vlan") else ""
                sub = " · ".join([s for s in [ipv, vl] if s]) or itf.get("description", "")
                place({"id": itf.get("id"), "title": itf.get("name", itf.get("id")),
                       "subtitle": sub, "desc": itf.get("description", ""), "ip": ipv,
                       "type": "iface", "layer": "logical" if ipv else "physical",
                       "status": itf.get("status", "existing"), "device": id_},
                      cx, iy, IFW, IFH)
                iy += 66
        else:
            f = fac_by_id.get(id_, {"id": id_, "label": id_, "type": ""})
            columns.append({"id": "col-" + str(id_), "label": "物理設備",
                            "x": round(cx, 1), "divider": round(divider, 1)})
            ftype = (f.get("type") or "").upper()
            place({"id": id_, "title": ftype or "設備", "subtitle": f.get("label", ""),
                   "type": "facility", "layer": "physical", "status": f.get("status", "existing")},
                  cx, 150, FACW, FACH)

    # --- 解決できない端点（外部ピア / next-hop）の追加列 ---
    ext_x = 130 + COLW * n_cols + COLW / 2
    ext_y = [150]

    def ext_node(nid, title, subtitle, status, ntype="peer", layer="logical"):
        if nid in center:
            return nid
        place({"id": nid, "title": title, "subtitle": subtitle, "type": ntype,
               "layer": layer, "status": status}, ext_x, ext_y[0], IFW, IFH)
        ext_y[0] += 70
        return nid

    def if_node_of(dev_id, ifname):
        for itf in if_by_dev.get(dev_id, []):
            if ifname and itf.get("name") == ifname:
                return itf.get("id")
        return dev_id

    def _net3(ip):  # 先頭3オクテット（/24〜/30 のP2P対向判定の簡易キー）
        parts = ip_key(ip).split(".")
        return ".".join(parts[:3]) if len(parts) == 4 else None

    def local_if_of(g):
        dev = g.get("device")
        cand = [i for i in if_by_dev.get(dev, []) if ip_key(i.get("ip"))]
        # 1) local_ip が明示されていれば最優先（IPはIFに帰属）
        lip = ip_key(g.get("local_ip"))
        if lip:
            for i in cand:
                if ip_key(i.get("ip")) == lip:
                    return i.get("id")
        # 2) neighbor_ip と同一サブネット（先頭3オクテット一致）の自IFを選ぶ
        nnet = _net3(g.get("neighbor_ip"))
        if nnet:
            same = [i for i in cand if _net3(i.get("ip")) == nnet]
            if len(same) == 1:
                return same[0].get("id")
        # 3) 自IFが1本だけならそれ
        if len(cand) == 1:
            return cand[0].get("id")
        return dev

    # --- flows（実体の“流れ”を抽出） ---
    flows = []

    def num():
        return len(flows) + 1

    for i, pl in enumerate(phys):
        a = if_node_of(pl.get("a_device"), pl.get("a_if"))
        b = if_node_of(pl.get("b_device"), pl.get("b_if"))
        chain = [a] + list(pl.get("via", []) or []) + [b]
        steps = []
        for k in range(len(chain) - 1):
            passes = "物理結線"
            if k == 0 and pl.get("a_if"):
                passes = pl["a_if"]
            elif k == len(chain) - 2 and pl.get("b_if"):
                passes = pl["b_if"]
            steps.append({"from": chain[k], "to": chain[k + 1], "passes": passes, "note": pl.get("label", "")})
        flows.append({"id": "phys%d" % i, "icon": "🔌", "name": "%d. 物理経路 %s" % (num(), pl.get("label", "")),
                      "sub": "FDF/TIE 経由の結線", "layer": "physical",
                      "status": pl.get("status", "existing"), "steps": steps})

    for i, g in enumerate(bgp):
        local = local_if_of(g)
        nip = ip_key(g.get("neighbor_ip"))
        remote = ip2if[nip].get("id") if nip in ip2if else ext_node(
            "peer-" + (nip or str(i)), "外部ピア", g.get("neighbor_ip", ""), g.get("status", "existing"))
        la, pa = g.get("local_as", "?"), g.get("peer_as", "?")
        steps = [
            {"from": local, "to": remote, "passes": "経路広告 AS%s→AS%s" % (la, pa),
             "note": "neighbor %s" % g.get("neighbor_ip", "")},
            {"from": remote, "to": local, "passes": "経路広告 AS%s→AS%s" % (pa, la),
             "note": "eBGPは双方向セッション"},
        ]
        flows.append({"id": "bgp%d" % i, "icon": "🔁", "name": "%d. eBGP AS%s⇄AS%s" % (num(), la, pa),
                      "sub": g.get("neighbor_ip", ""), "layer": "logical",
                      "status": g.get("status", "existing"), "steps": steps})

    for i, s in enumerate(statics):
        src = s.get("device")
        nh = ip_key(s.get("next_hop"))
        dst = ip2if[nh].get("id") if nh in ip2if else ext_node(
            "nh-" + (nh or str(i)), "next-hop", s.get("next_hop", ""), s.get("status", "existing"))
        steps = [{"from": src, "to": dst, "passes": "static %s" % s.get("prefix", ""),
                  "note": "next-hop %s" % s.get("next_hop", "")}]
        flows.append({"id": "st%d" % i, "icon": "🧭", "name": "%d. static %s" % (num(), s.get("prefix", "")),
                      "sub": "→ %s" % s.get("next_hop", ""), "layer": "logical",
                      "status": s.get("status", "existing"), "steps": steps})

    # flow の from/to が nodes に無いものは除外（堅牢性）
    ids = {n["id"] for n in nodes}
    for fl in flows:
        fl["steps"] = [st for st in fl["steps"] if st["from"] in ids and st["to"] in ids]
    flows = [fl for fl in flows if fl["steps"]]

    # 統合表（機器ごと1カード・カード内に複数 section）
    # 各カード: {"title", "node", "status", "sections": [{"category","columns","rows":[...]}, ...]}
    # 各 row:  {"cells", "node", "flow", "status"}
    # id を持たない不正 device は機器集合に入れない（None と device 欠落の BGP/static を取り違えないため）。
    dev_ids = {d.get("id") for d in devices if d.get("id") is not None}
    valid_flow_ids = {fl["id"] for fl in flows}  # 上の堅牢性フィルタで生き残ったフローだけ表行を連動させる

    def _linked_flow(fid):
        # フローが除外済み（端点ノード不在等）なら表行をクリック不可にする（無反応クリック防止）。
        return fid if fid in valid_flow_ids else None

    def _bgp_row(i, g, *, with_device):
        nip = ip_key(g.get("neighbor_ip"))
        node = ip2if[nip].get("id") if nip in ip2if else None
        head = [g.get("device", "")] if with_device else []
        return {"cells": head + [g.get("local_ip", ""), g.get("neighbor_ip", ""),
                                 f"{g.get('local_as', '?')}→{g.get('peer_as', '?')}"],
                "node": node, "flow": _linked_flow("bgp%d" % i), "status": g.get("status", "existing")}

    def _st_row(i, s, *, with_device):
        nh = ip_key(s.get("next_hop"))
        node = ip2if[nh].get("id") if nh in ip2if else None
        head = [s.get("device", "")] if with_device else []
        return {"cells": head + [s.get("prefix", ""), s.get("next_hop", "")],
                "node": node, "flow": _linked_flow("st%d" % i), "status": s.get("status", "existing")}

    tables = []
    for d in devices:
        did = d.get("id")
        # IF section（IF が無くても見出しは出す＝その機器にIF未定義であることを可視化する）
        if_rows = [{"cells": [itf.get("name", ""), itf.get("ip", ""), itf.get("vlan", ""), itf.get("description", "")],
                    "node": itf.get("id"), "flow": None, "status": itf.get("status", "existing")}
                   for itf in if_by_dev.get(did, [])]
        sections = [{"category": "IF", "columns": ["IF", "IP", "VLAN", "description"], "rows": if_rows}]

        # BGP / static section（当該機器分のみ・元配列インデックス i を維持）。did=None の不正 device には紐づけない。
        bgp_rows = [_bgp_row(i, g, with_device=False) for i, g in enumerate(bgp)
                    if did is not None and g.get("device") == did]
        if bgp_rows:
            sections.append({"category": "BGP", "columns": ["local", "neighbor", "AS"], "rows": bgp_rows})
        st_rows = [_st_row(i, s, with_device=False) for i, s in enumerate(statics)
                   if did is not None and s.get("device") == did]
        if st_rows:
            sections.append({"category": "static", "columns": ["prefix", "next-hop"], "rows": st_rows})

        # 拡張 sections（device.sections）を正規化して append
        for sec in (d.get("sections") or []):
            ext_rows = [{"cells": r.get("cells", []) or [], "node": r.get("node"),
                         "flow": _linked_flow(r.get("flow")), "status": r.get("status", "existing")}
                        for r in (sec.get("rows") or [])]
            sections.append({"category": sec.get("category", ""),
                             "columns": sec.get("columns", []) or [], "rows": ext_rows})

        title = (d.get("hostname", did) or "") + (" / AS" + str(d["as"]) if d.get("as") else "")
        tables.append({"title": title, "node": did, "status": d.get("status", "existing"), "sections": sections})

    # orphan（device 未割当）BGP/static を末尾1カードにまとめる（"機器" 列を残す）
    orphan_bgp_rows = [_bgp_row(i, g, with_device=True) for i, g in enumerate(bgp)
                       if g.get("device") not in dev_ids]
    orphan_st_rows = [_st_row(i, s, with_device=True) for i, s in enumerate(statics)
                      if s.get("device") not in dev_ids]
    if orphan_bgp_rows or orphan_st_rows:
        orphan_sections = []
        if orphan_bgp_rows:
            orphan_sections.append({"category": "BGP", "columns": ["機器", "local", "neighbor", "AS"], "rows": orphan_bgp_rows})
        if orphan_st_rows:
            orphan_sections.append({"category": "static", "columns": ["機器", "prefix", "next-hop"], "rows": orphan_st_rows})
        tables.append({"title": "その他（機器未割当）", "node": None, "status": "existing", "sections": orphan_sections})

    W = max(960, int(ext_x + COLW / 2) if ext_y[0] > 150 else 130 + COLW * n_cols)
    max_y = max([n["y"] + n["h"] for n in nodes], default=400)
    H = max(560, int(max_y + 80))

    groups = [
        {"id": "existing", "label": "既存", "stroke": "#5b6b7d", "fill": "#161d27", "sub": "#8a94a3"},
        {"id": "added", "label": "追加（本作業）", "stroke": "#37d67a", "fill": "#10261b", "sub": "#7be0a6"},
    ]
    for n in nodes:
        n["group"] = n.get("status", "existing")

    # 統合表（機器・IF一覧 / BGP / static）用の元データ。IF行は interfaces[].id で node と連動させる。
    model = {
        "devices": devices,
        "interfaces": interfaces,
        "facilities": facilities,
        "bgp": bgp,
        "static_routes": statics,
    }
    return {"title": topo.get("title", "network topology"),
            "viewBox": {"w": W, "h": H}, "columns": columns, "groups": groups,
            "nodes": nodes, "flows": flows, "model": model, "tables": tables}


# ───────────────────────── HTML テンプレート（CSS＋バニラJSエンジン） ─────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>構成図 - __TITLE__</title>
<style>
:root{
  --bg:#0c1117; --bg-2:#11171f; --panel:#161d27; --line:#2a3340;
  --text:#d6dde6; --muted:#8a94a3;
  --edge:#2c3441; --edge-active:#ffd166; --edge-active-glow:rgba(255,209,102,0.55);
  --added:#37d67a; --added-glow:rgba(55,214,122,0.45);
  --tbl-h:240px;
}
*{box-sizing:border-box;}
html,body{margin:0;height:100%;}
body{background:var(--bg);color:var(--text);
  font-family:-apple-system,"Segoe UI","Hiragino Sans","Yu Gothic UI",sans-serif;overflow:hidden;}
.app{display:grid;grid-template-columns:320px 1fr;
  grid-template-rows:auto 1fr 6px var(--tbl-h);
  grid-template-areas:"header header" "sidebar canvas" "sidebar resizer" "sidebar table";
  height:100vh;}
header{grid-area:header;background:var(--bg-2);border-bottom:1px solid var(--line);
  padding:10px 18px;display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;}
header h1{font-size:15px;margin:0;}
header .path{color:var(--muted);font-size:12px;font-family:ui-monospace,Menlo,monospace;}
header .hint{color:var(--muted);font-size:11px;margin-left:auto;}
.sidebar{grid-area:sidebar;background:var(--panel);border-right:1px solid var(--line);
  overflow-y:auto;padding:12px;}
.sec-t{font-size:11px;letter-spacing:.08em;color:var(--muted);margin:12px 4px 6px;text-transform:uppercase;}
.flow-btn{display:flex;gap:8px;align-items:center;width:100%;text-align:left;background:var(--bg-2);
  color:var(--text);border:1px solid var(--line);border-radius:8px;padding:7px 9px;margin:4px 0;cursor:pointer;font-size:12px;}
.flow-btn:hover{border-color:#3c5063;}
.flow-btn.active{border-color:var(--edge-active);background:#1c2330;box-shadow:0 0 0 1px var(--edge-active) inset;}
.flow-btn .ic{font-size:14px;}
.flow-btn .nm{flex:1;line-height:1.25;}
.flow-btn .nm small{display:block;color:var(--muted);font-size:10.5px;}
.flow-btn .badge-add{font-size:9px;font-weight:700;color:#06210f;background:var(--added);border-radius:8px;padding:0 6px;}
.legend{font-size:11.5px;color:var(--muted);margin:4px 2px;}
.legend .row{display:flex;align-items:center;gap:7px;margin:4px 0;}
.legend .sw{width:24px;height:0;border-top:3px solid;} .legend .bx{width:14px;height:12px;border:2px solid;border-radius:3px;}
.reset{width:100%;margin-top:10px;background:#1b2330;color:var(--text);border:1px solid var(--line);
  border-radius:8px;padding:7px;font-size:12px;cursor:pointer;}
.canvas{grid-area:canvas;position:relative;overflow:hidden;background:
  radial-gradient(circle at 30% 20%, #121a24 0, var(--bg) 60%);}
svg#stage{width:100%;height:100%;cursor:grab;} svg#stage.grabbing{cursor:grabbing;}
.resizer{grid-area:resizer;background:var(--line);cursor:row-resize;}
.resizer:hover{background:#3c5063;}
/* フロー直下に展開されるステップ（アコーディオン・既定は畳む） */
.flow-steps{list-style:none;counter-reset:step;padding:4px 0 6px 6px;margin:2px 0 6px;display:none;}
.flow-item.active .flow-steps{display:block;}
.flow-steps li{counter-increment:step;position:relative;padding:6px 8px 6px 30px;margin:4px 0;
  background:var(--bg-2);border:1px solid var(--line);border-radius:7px;cursor:pointer;font-size:11.5px;}
.flow-steps li::before{content:counter(step);position:absolute;left:6px;top:6px;width:18px;height:18px;
  background:#222c39;border-radius:50%;font-size:10px;display:flex;align-items:center;justify-content:center;color:var(--muted);}
.flow-steps li .ft{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;}
.flow-steps li .ar{color:var(--edge-active);}
.flow-steps li .passes{font-size:11.5px;background:#10161e;border-left:2px solid var(--edge-active);
  padding:2px 7px;margin:3px 0 1px;border-radius:3px;}
.flow-steps li .note{color:var(--muted);font-size:11px;}
.flow-steps li.focused{border-color:var(--edge-active);}
.flow-steps li.focused::before{background:var(--edge-active);color:#1a1100;}
.empty{color:var(--muted);font-size:12px;padding:8px;}
/* CANVAS の下の統合表エリア */
.tablearea{grid-area:table;background:var(--panel);border-top:1px solid var(--line);overflow-y:auto;padding:8px 16px;}
.tablearea h2{font-size:12px;color:var(--muted);margin:0 0 8px;letter-spacing:.05em;position:sticky;top:0;background:var(--panel);padding:2px 0;}
.tables-wrap{display:block;}
.node-card{border:1px solid var(--line);border-radius:8px;background:var(--bg-2);padding:8px 12px;margin:0 0 14px;}
.node-card.added{border-color:var(--added);}
.card-h{font-size:13px;font-weight:700;margin:0 0 6px;display:flex;align-items:center;gap:8px;}
.sec-cap{font-size:11px;color:var(--muted);letter-spacing:.05em;margin:8px 2px 3px;text-transform:uppercase;}
.tbl{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:12px;}
.tbl th,.tbl td{text-align:left;padding:4px 8px;border-bottom:1px solid var(--line);white-space:nowrap;}
.tbl th{background:#10161e;color:var(--muted);font-size:11px;position:sticky;top:0;}
.tbl td.mono,.tbl td .mono{font-family:ui-monospace,Menlo,monospace;}
.tbl tr[data-node]{cursor:pointer;}
.tbl tr.added td:first-child::after{content:"追加";font-size:9px;font-weight:700;color:#06210f;background:var(--added);border-radius:7px;padding:0 5px;margin-left:6px;}
.tbl tr.added td{color:#9ff0c2;}
.tbl tr.mark{background:#2a2410;box-shadow:inset 3px 0 0 var(--edge-active);}
.tbl tr.mark td{color:#ffe9a8;}
/* nodes / edges / badges */
.node rect{filter:drop-shadow(0 2px 4px rgba(0,0,0,.5));}
.node .t{font-size:12px;font-weight:700;} .node .s{font-size:10.2px;}
.node.dim{opacity:.18;} .node.endpoint rect{stroke-width:3px;}
.edge{fill:none;stroke:var(--edge);stroke-width:1.6px;}
.edge.added{stroke:var(--added);} .edge.dim{opacity:.12;}
.edge.active{stroke:var(--edge-active);filter:drop-shadow(0 0 4px var(--edge-active-glow));}
.edge.focused-edge{stroke-width:3.4px;}
.col-label{fill:var(--muted);font-size:11px;letter-spacing:.14em;text-anchor:middle;}
.col-div{stroke:#1c2531;stroke-dasharray:3,5;}
.edge-step-pill{fill:#1b2330;stroke:#3a4858;stroke-width:1.2px;}
.edge-step-pill.added{stroke:var(--added);}
.edge-step-badge text{font-size:11px;font-weight:700;fill:var(--text);pointer-events:none;}
.edge-step-badge.active .edge-step-pill{fill:var(--edge-active);stroke:#fff8d6;}
.edge-step-badge.active text{fill:#1a1100;}
.edge-step-halo{fill:none;stroke:var(--edge-active);stroke-width:2px;opacity:0;}
.tether{stroke:#3a4858;stroke-dasharray:2,3;stroke-width:1px;}
#tooltip{position:fixed;z-index:50;max-width:340px;display:none;background:rgba(14,20,28,.97);
  border:1px solid var(--edge-active);border-radius:8px;padding:9px 11px;font-size:12px;
  box-shadow:0 6px 24px rgba(0,0,0,.5);backdrop-filter:blur(4px);pointer-events:none;}
#tooltip .h{font-weight:700;margin-bottom:4px;} #tooltip .chip{font-family:ui-monospace,Menlo,monospace;color:var(--edge-active);}
#tooltip code{display:block;background:#0c1219;border-left:2px solid var(--edge-active);padding:3px 7px;margin:4px 0;border-radius:3px;white-space:pre-wrap;}
#tooltip .nt{color:var(--muted);} #tooltip hr{border:none;border-top:1px solid var(--line);margin:6px 0;}
@keyframes pulse{0%,100%{transform:scale(1);}50%{transform:scale(1.42);
  filter:drop-shadow(0 0 2px #fff) drop-shadow(0 0 6px var(--edge-active)) drop-shadow(0 0 12px var(--edge-active-glow));}}
@keyframes halo-burst{0%{transform:scale(.55);opacity:.85;}100%{transform:scale(3);opacity:0;}}
@keyframes edge-pulse{0%,100%{stroke-width:2.8px;stroke:var(--edge-active);}50%{stroke-width:4.2px;stroke:#fff;filter:drop-shadow(0 0 6px var(--edge-active-glow));}}
@keyframes node-glow{0%,100%{filter:drop-shadow(0 0 3px var(--edge-active-glow));}50%{filter:drop-shadow(0 0 9px #fff);}}
@keyframes anno-flash{0%{background:#5a4a10;}100%{background:var(--bg-2);}}
.edge-step-scale.pulsing{animation:pulse .9s ease-in-out infinite;transform-origin:center;transform-box:fill-box;}
.edge-step-halo.bursting{animation:halo-burst 1.3s ease-out infinite;transform-origin:center;transform-box:fill-box;}
.edge.focused-edge.zap{animation:edge-pulse 1.1s ease-in-out infinite;}
.node.endpoint.zap rect{animation:node-glow 1.1s ease-in-out infinite;transform-box:fill-box;transform-origin:center;}
.flow-steps li.focused.flash{animation:anno-flash 1.2s ease-out;}
</style>
</head>
<body>
<div class="app">
  <header>
    <h1>構成図（インタラクティブ）</h1>
    <span class="path">__SUBTITLE__</span>
    <span class="hint">ホイール=ズーム / ドラッグ=パン / 数字=フロー選択 / F=全体 / Esc=解除</span>
  </header>
  <aside class="sidebar">
    <div class="sec-t">フロー（番号は図のバッジ番号と連動）</div>
    <div id="flows"></div>
    <div class="sec-t">凡例</div>
    <div class="legend">
      <div class="row"><span class="bx" style="border-color:#5b6b7d"></span>既存</div>
      <div class="row"><span class="bx" style="border-color:#37d67a"></span><span style="color:#7be0a6">追加（本作業）</span></div>
      <div class="row"><span class="sw" style="border-color:#ffd166"></span>選択中フロー（フォーカス）</div>
    </div>
    <button class="reset" id="reset">全体表示にリセット (F)</button>
  </aside>
  <div class="canvas"><svg id="stage" xmlns="http://www.w3.org/2000/svg"></svg></div>
  <div class="resizer" id="resizer"></div>
  <div class="tablearea">
    <h2>機器ごとの一覧（IF / BGP / static / 拡張。図のフォーカスと連動。行クリックで図へ移動）</h2>
    <div id="tables" class="tables-wrap"></div>
  </div>
</div>
<div id="tooltip"></div>

<script type="application/json" id="workflow-data">__DATA__</script>
<script>
"use strict";
const SVGNS="http://www.w3.org/2000/svg";
let DATA=null;
async function loadData(){
  try{ const r=await fetch('./topology.flows.json'); if(r.ok) return await r.json(); }catch(e){}
  return JSON.parse(document.getElementById('workflow-data').textContent);
}
const el=(t,a,txt)=>{const e=document.createElementNS(SVGNS,t);for(const k in a)e.setAttribute(k,a[k]);if(txt!=null)e.textContent=txt;return e;};
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

const ST={vb:null, base:null, activeFlow:null, focus:null};
const NODE={}; let EDGES=[]; let STAGE,LY={};

function init(data){
  DATA=data;
  STAGE=document.getElementById('stage');
  const vb=data.viewBox;
  ST.base={x:0,y:0,w:vb.w,h:vb.h}; ST.vb={...ST.base};
  data.nodes.forEach(n=>NODE[n.id]=n);
  buildEdges();
  draw();
  buildSidebar();
  buildTables();
  applyView(); fitAll(false);
  wireEvents();
}

// 1エッジ=1バッジ: 有向 (from,to) でユニーク化。各エッジに乗る (flowId,stepIdx) を集約。
function buildEdges(){
  const map=new Map();
  DATA.flows.forEach(fl=>fl.steps.forEach((st,si)=>{
    const key=st.from+''+st.to;
    if(!map.has(key)) map.set(key,{from:st.from,to:st.to,steps:[],id:'e'+map.size});
    map.get(key).steps.push({flow:fl,si,step:st});
  }));
  EDGES=[...map.values()];
  // 往復ペア検出 → lane offset 割当（決定的 lex）
  const set=new Set(EDGES.map(e=>e.from+''+e.to));
  EDGES.forEach(e=>{
    const rev=e.to+''+e.from;
    if(set.has(rev)) e.lane=(e.from<e.to)?1:-1; else e.lane=0;
    // layer: 物理/論理の区別。将来のレイヤートグルUI用に算出・保持。現バージョンでは描画フィルタに未使用。
    e.layer=e.steps.some(s=>s.flow.layer==='logical')?'logical':'physical';
    e.added=e.steps.some(s=>(s.step.statusGuess||s.flow.status)==='added');
  });
}

function nodeCenter(id){const n=NODE[id];return n?{x:n.x+n.w/2,y:n.y+n.h/2}:null;}

// エッジ bezier。同カラム(x近)=上下、別カラム=左右。lane offset を制御点へ。
function edgeGeom(e){
  const a=NODE[e.from],b=NODE[e.to]; if(!a||!b)return null;
  const ac={x:a.x+a.w/2,y:a.y+a.h/2}, bc={x:b.x+b.w/2,y:b.y+b.h/2};
  const dx=bc.x-ac.x, dy=bc.y-ac.y;
  const horiz=Math.abs(dx)>=Math.abs(dy);
  const lane=(e.lane||0)*38;
  let p0,p1,c1,c2;
  if(horiz){
    const s=dx>=0?1:-1;
    p0={x:ac.x+s*a.w/2,y:ac.y}; p1={x:bc.x-s*b.w/2,y:bc.y};
    const mx=(p0.x+p1.x)/2;
    c1={x:mx,y:p0.y+lane}; c2={x:mx,y:p1.y+lane};
  }else{
    const s=dy>=0?1:-1;
    p0={x:ac.x,y:ac.y+s*a.h/2}; p1={x:bc.x,y:bc.y-s*b.h/2};
    const my=(p0.y+p1.y)/2;
    c1={x:p0.x+lane,y:my}; c2={x:p1.x+lane,y:my};
  }
  return {d:`M ${p0.x} ${p0.y} C ${c1.x} ${c1.y} ${c2.x} ${c2.y} ${p1.x} ${p1.y}`,p0,p1};
}

function draw(){
  STAGE.innerHTML='';
  const defs=el('defs');
  defs.appendChild(marker('arrow','#2c3441'));
  defs.appendChild(marker('arrow-active','#ffd166'));
  STAGE.appendChild(defs);
  LY.col=el('g',{class:'col-layer'});
  LY.edge=el('g',{class:'edge-layer'});
  LY.node=el('g',{class:'node-layer'});
  LY.badge=el('g',{class:'badge-layer'});
  // 厳守: defs → col → edge → node → badge（badge最前面）
  STAGE.appendChild(LY.col); STAGE.appendChild(LY.edge); STAGE.appendChild(LY.node); STAGE.appendChild(LY.badge);

  (DATA.columns||[]).forEach(c=>{
    LY.col.appendChild(el('line',{class:'col-div',x1:c.divider,y1:30,x2:c.divider,y2:DATA.viewBox.h-20}));
    LY.col.appendChild(el('text',{class:'col-label',x:c.x,y:50},c.label));
  });

  EDGES.forEach(e=>{
    const g=edgeGeom(e); if(!g)return; e.geom=g;
    const p=el('path',{class:'edge'+(e.added?' added':''),d:g.d,'marker-end':'url(#arrow)','data-edge':e.id});
    e.dom=p; LY.edge.appendChild(p);
  });

  (DATA.nodes||[]).forEach(n=>{
    const grp=(DATA.groups||[]).find(g=>g.id===n.group)||{stroke:'#5b6b7d',fill:'#161d27',sub:'#8a94a3'};
    const g=el('g',{class:'node','data-node':n.id});
    g.appendChild(el('rect',{x:n.x,y:n.y,width:n.w,height:n.h,rx:8,
      fill:grp.fill,stroke:n.status==='added'?'var(--added)':grp.stroke,
      'stroke-width':n.status==='added'?2.4:1.5}));
    g.appendChild(el('text',{class:'t',x:n.x+10,y:n.y+(n.subtitle?20:n.h/2+4),
      fill:n.status==='added'?'#9ff0c2':'var(--text)'},n.title));
    if(n.subtitle) g.appendChild(el('text',{class:'s',x:n.x+10,y:n.y+36,fill:grp.sub},n.subtitle));
    n.dom=g; LY.node.appendChild(g);
    g.addEventListener('mouseover',ev=>{ if(ST.activeFlow) return; showNodeTip(n,ev); });
    g.addEventListener('mouseout',()=>hideTip());
  });

  placeBadges();
}
function marker(id,color){
  const m=el('marker',{id,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'});
  m.appendChild(el('path',{d:'M0 0 L10 5 L0 10 z',fill:color})); return m;
}

// ── バッジ配置（衝突回避: 他バッジ楕円距離 + Node bbox回避 + escape） ──
const OFFS=[0.50,0.44,0.56,0.38,0.62,0.32,0.68,0.26,0.74,0.20,0.80,0.15,0.85,0.10,0.90];
function placeBadges(){
  const placed=[]; // {x,y,w,h}
  const nodeRects=(DATA.nodes||[]).map(n=>({x:n.x,y:n.y,w:n.w,h:n.h}));
  // マルチステップ→短いパス優先で midpoint 確保
  const ordered=[...EDGES].filter(e=>e.geom).sort((a,b)=>b.steps.length-a.steps.length || pathLen(a)-pathLen(b));
  ordered.forEach(e=>{
    const path=e.dom, L=path.getTotalLength();
    const label=badgeLabel(e);
    const approxW=Math.max(20,label.length*7+14), approxH=18;
    let best=null,bestScore=-1e9;
    for(const t of OFFS){
      const pt=path.getPointAtLength(L*t);
      const r={x:pt.x-approxW/2,y:pt.y-approxH/2,w:approxW,h:approxH};
      let score=0;
      for(const q of placed){const d=ellipseDist(r,q); if(d<1.05) score-=(1.05-d)*3;}
      for(const nr of nodeRects){ if(overlap(r,nr,4)) score-=3.5; }
      score+=1-Math.abs(t-0.5);
      if(score>bestScore){bestScore=score;best={pt,t,r};}
    }
    // escape: Node bbox から脱出
    let {pt,t,r}=best;
    if(nodeRects.some(nr=>overlap(r,nr,4))){
      for(let d=0.02;d<=0.4;d+=0.02){
        for(const tt of [t+d,t-d]){ if(tt<=0.05||tt>=0.95)continue;
          const p2=path.getPointAtLength(L*tt), r2={x:p2.x-approxW/2,y:p2.y-approxH/2,w:approxW,h:approxH};
          if(!nodeRects.some(nr=>overlap(r2,nr,4))){pt=p2;t=tt;r=r2;break;}
        }
        if(!nodeRects.some(nr=>overlap(r,nr,4)))break;
      }
    }
    placed.push(r);
    e.badgePos=pt; e.badgeMid=path.getPointAtLength(L*0.5);
    buildBadge(e,label);
  });
}
function pathLen(e){return e.dom?e.dom.getTotalLength():0;}
function badgeLabel(e){
  const nums=e.steps.map(s=>s.si+1).sort((a,b)=>a-b);
  if(nums.length===1)return String(nums[0]);
  if(nums.length<=5)return nums.join(' · ');
  return nums[0]+'–'+nums[nums.length-1]+' ('+nums.length+')';
}
function ellipseDist(a,b){const dx=(a.x+a.w/2)-(b.x+b.w/2),dy=(a.y+a.h/2)-(b.y+b.h/2);
  return Math.sqrt((dx/((a.w+b.w)/2))**2+(dy/((a.h+b.h)/2))**2);}
function overlap(a,b,m){m=m||0;return !(a.x+a.w+m<b.x||b.x+b.w+m<a.x||a.y+a.h+m<b.y||b.y+b.h+m<a.y);}

function buildBadge(e,label){
  const pos=e.badgePos;
  // midpoint から離れていたら破線テザー
  if(Math.hypot(pos.x-e.badgeMid.x,pos.y-e.badgeMid.y)>26){
    LY.badge.appendChild(el('line',{class:'tether',x1:e.badgeMid.x,y1:e.badgeMid.y,x2:pos.x,y2:pos.y}));
  }
  const outer=el('g',{class:'edge-step-badge','data-edge':e.id,transform:`translate(${pos.x},${pos.y})`});
  outer.appendChild(el('ellipse',{class:'edge-step-halo',rx:18,ry:13}));
  const hit=el('rect',{class:'edge-step-hit',x:-24,y:-16,width:48,height:32,rx:10,
    fill:'rgba(0,0,0,0.001)','pointer-events':'all'});
  outer.appendChild(hit);
  const scale=el('g',{class:'edge-step-scale'});
  const w=Math.max(20,label.length*7+14);
  scale.appendChild(el('rect',{class:'edge-step-pill'+(e.added?' added':''),x:-w/2,y:-9,width:w,height:18,rx:9}));
  scale.appendChild(el('text',{x:0,y:4,'text-anchor':'middle'},label));
  outer.appendChild(scale);
  e.badge=outer; LY.badge.appendChild(outer);
  outer.addEventListener('mouseover',ev=>showEdgeTip(e,ev));
  outer.addEventListener('mouseout',ev=>{ if(!outer.contains(ev.relatedTarget)) hideTip(); });
  outer.addEventListener('click',()=>cycleFocus(e));
}

// ── サイドバー ──
function buildSidebar(){
  const box=document.getElementById('flows'); box.innerHTML='';
  DATA.flows.forEach((fl,i)=>{
    const item=document.createElement('div'); item.className='flow-item'; item.dataset.flow=fl.id;
    const b=document.createElement('button');
    b.className='flow-btn'; b.dataset.flow=fl.id;
    b.innerHTML=`<span class="ic">${fl.icon||'•'}</span><span class="nm">${esc(fl.name)}<small>${esc(fl.sub||'')}</small></span>`+
      (fl.status==='added'?'<span class="badge-add">追加</span>':'');
    b.addEventListener('click',()=>selectFlow(fl.id));
    const ol=document.createElement('ol'); ol.className='flow-steps'; ol.dataset.flow=fl.id;
    item.appendChild(b); item.appendChild(ol); box.appendChild(item);
  });
  document.getElementById('reset').addEventListener('click',()=>{ST.activeFlow=null;ST.focus=null;refreshActive();fitAll(true);});
}

// ── 統合表（機器ごとカード。行は data-node / data-flow で図と双方向連動） ──
const monoish=v=>/[0-9]/.test(String(v))&&/[./]/.test(String(v));
function buildTables(){
  const root=document.getElementById('tables'); if(!root)return;
  let html='';
  (DATA.tables||[]).forEach(t=>{
    const cardAdded=t.status==='added';
    const nodeAttr=t.node?` data-node="${esc(t.node)}"`:''
    html+=`<div class="node-card${cardAdded?' added':''}"${nodeAttr}>`;
    html+=`<div class="card-h">${esc(t.title)}${cardAdded?'<span class="badge-add">追加</span>':''}</div>`;
    (t.sections||[]).forEach(sec=>{
      html+=`<div class="sec-cap">${esc(sec.category)}</div>`;
      html+=`<table class="tbl"><thead><tr>`+
        (sec.columns||[]).map(c=>`<th>${esc(c)}</th>`).join('')+`</tr></thead><tbody>`;
      (sec.rows||[]).forEach(r=>{
        const attrs=(r.node?` data-node="${esc(r.node)}"`:'')+(r.flow?` data-flow="${esc(r.flow)}"`:'');
        html+=`<tr${attrs} class="${r.status==='added'?'added':''}">`+
          (r.cells||[]).map((c,i)=>`<td class="${(i===0||monoish(c))?'mono':''}">${esc(c)}</td>`).join('')+`</tr>`;
      });
      if(!(sec.rows||[]).length) html+=`<tr><td colspan="${(sec.columns||[]).length||1}" class="empty">なし</td></tr>`;
      html+='</tbody></table>';
    });
    html+='</div>';
  });
  root.innerHTML=html||'<p class="empty">機器情報がありません。</p>';
  root.querySelectorAll('tr[data-node],tr[data-flow]').forEach(tr=>{
    tr.style.cursor='pointer';
    tr.addEventListener('click',()=>{
      const fid=tr.getAttribute('data-flow'), nid=tr.getAttribute('data-node');
      if(fid && DATA.flows.some(f=>f.id===fid) && ST.activeFlow!==fid){ selectFlow(fid); }
      if(nid){ const n=NODE[nid]; if(n){ if(n.dom)n.dom.classList.add('endpoint'); const c=nodeCenter(nid); if(c)panTo(c.x,c.y); } }
      markTableRows(nid?[nid]:[], fid);
    });
  });
}
function markTableRows(ids, flowId){
  const root=document.getElementById('tables'); if(!root)return;
  root.querySelectorAll('tr.mark').forEach(tr=>tr.classList.remove('mark'));
  // node 連動は「フロー行(data-flow)でない＝IF行」だけに限定（BGP/static 行が他フローの端点nodeで誤点灯するのを防ぐ）
  (ids||[]).forEach(id=>root.querySelectorAll(`tr[data-node="${cssEsc(id)}"]:not([data-flow])`).forEach(tr=>tr.classList.add('mark')));
  // BGP/static 行は対応フロー選択時のみマーク
  if(flowId) root.querySelectorAll(`tr[data-flow="${cssEsc(flowId)}"]`).forEach(tr=>tr.classList.add('mark'));
}
function cssEsc(s){return String(s).replace(/["\\]/g,'\\$&');}

// ── フロー選択 / フォーカス ──
function selectFlow(id){ ST.activeFlow=(ST.activeFlow===id)?null:id; ST.focus=null; refreshActive(); if(ST.activeFlow) fitFlow(id); }
function refreshActive(){
  document.querySelectorAll('.flow-btn').forEach(b=>b.classList.toggle('active',b.dataset.flow===ST.activeFlow));
  const fl=DATA.flows.find(f=>f.id===ST.activeFlow);
  const onIds=new Set(); if(fl) fl.steps.forEach(s=>{onIds.add(s.from);onIds.add(s.to);});
  const edgeOn=new Set(); if(fl) EDGES.forEach(e=>{ if(e.steps.some(s=>s.flow.id===fl.id)) edgeOn.add(e.id); });
  (DATA.nodes||[]).forEach(n=>{ if(!n.dom)return; n.dom.classList.toggle('dim',!!fl&&!onIds.has(n.id)); n.dom.classList.remove('endpoint','zap'); });
  EDGES.forEach(e=>{ if(!e.dom)return;
    const on=!fl||edgeOn.has(e.id);
    e.dom.classList.toggle('active',!!fl&&edgeOn.has(e.id));
    e.dom.classList.toggle('dim',!!fl&&!edgeOn.has(e.id));
    e.dom.setAttribute('marker-end', (!!fl&&edgeOn.has(e.id))?'url(#arrow-active)':'url(#arrow)');
    e.dom.classList.remove('focused-edge','zap');
    if(e.badge){ e.badge.style.opacity=on?1:0.15; e.badge.classList.remove('active'); relabelBadge(e,fl); }
  });
  clearFocusAnim();
  markTableRows(fl?[...onIds]:[], fl?fl.id:null);
  renderAnnotations(fl);
}
// バッジの番号を「選択中フローのステップ番号」に合わせる（フロー番号⇔図のバッジ番号を連動）
function badgeLabelFor(e,fl){
  if(fl){ const nums=e.steps.filter(s=>s.flow.id===fl.id).map(s=>s.si+1).sort((a,b)=>a-b);
    if(nums.length){ if(nums.length===1)return String(nums[0]); if(nums.length<=5)return nums.join('·'); return nums[0]+'–'+nums[nums.length-1]; } }
  return badgeLabel(e);
}
function relabelBadge(e,fl){
  if(!e.badge)return; const txt=e.badge.querySelector('.edge-step-scale text'); if(!txt)return;
  const label=badgeLabelFor(e,fl); txt.textContent=label;
  const pill=e.badge.querySelector('.edge-step-pill'); if(pill){const w=Math.max(20,label.length*7+14);pill.setAttribute('x',-w/2);pill.setAttribute('width',w);}
}
function cycleFocus(e){
  // バッジクリック: 単体ならフォーカス、マルチは循環。
  // 対象エッジが現在のフローに属さない場合は、そのエッジ自身のフローへ切り替える（空配列クラッシュ防止）。
  if(!e.steps.length)return;
  const fid=(ST.activeFlow && e.steps.some(s=>s.flow.id===ST.activeFlow))?ST.activeFlow:e.steps[0].flow.id;
  if(ST.activeFlow!==fid) selectFlow(fid);
  const stepsOnEdge=e.steps.filter(s=>s.flow.id===fid);
  if(!stepsOnEdge.length)return;
  let idx=0;
  if(ST.focus&&ST.focus.edge===e.id&&ST.focus.flow===fid){ idx=(ST.focus.k+1)%stepsOnEdge.length; }
  ST.focus={edge:e.id,k:idx,flow:fid,si:stepsOnEdge[idx].si};
  applyFocus();
}
function focusStep(flowId,si){
  if(ST.activeFlow!==flowId) selectFlow(flowId);
  const e=EDGES.find(x=>x.steps.some(s=>s.flow.id===flowId&&s.si===si));
  ST.focus={edge:e?e.id:null,flow:flowId,si};
  applyFocus();
}
function clearFocusAnim(){
  document.querySelectorAll('.edge-step-scale.pulsing').forEach(x=>x.classList.remove('pulsing'));
  document.querySelectorAll('.edge-step-halo.bursting').forEach(x=>x.classList.remove('bursting'));
  document.querySelectorAll('.edge.zap').forEach(x=>x.classList.remove('zap','focused-edge'));
  document.querySelectorAll('.node.endpoint').forEach(x=>x.classList.remove('endpoint','zap'));
  document.querySelectorAll('.edge-step-badge.active').forEach(b=>{ if(!ST.activeFlow)b.classList.remove('active'); });
}
function applyFocus(){
  clearFocusAnim();
  const f=ST.focus; if(!f)return;
  const fl=DATA.flows.find(x=>x.id===f.flow); const st=fl&&fl.steps[f.si]; if(!st)return;
  const e=EDGES.find(x=>x.id===f.edge);
  // 1 バッジ pulse + 反転, 2 halo, 3 edge pulse, 4 endpoints, 5 anno flash
  if(e&&e.badge){ e.badge.classList.add('active'); e.badge.querySelector('.edge-step-scale').classList.add('pulsing');
    e.badge.querySelector('.edge-step-halo').classList.add('bursting'); }
  if(e&&e.dom){ e.dom.classList.add('focused-edge','zap','active'); e.dom.setAttribute('marker-end','url(#arrow-active)'); }
  [st.from,st.to].forEach(id=>{const n=NODE[id]; if(n&&n.dom){n.dom.classList.add('endpoint','zap'); n.dom.classList.remove('dim');}});
  markTableRows([st.from,st.to], f.flow);
  // pan to step midpoint
  if(e&&e.geom){ const m=e.dom.getPointAtLength(e.dom.getTotalLength()*0.5); panTo(m.x,m.y); }
  flashAnno(f.si);
}

// ── 注釈（サイドバーの選択フロー直下にアコーディオン展開） ──
function renderAnnotations(fl){
  document.querySelectorAll('.flow-item').forEach(it=>it.classList.toggle('active',!!fl&&it.dataset.flow===fl.id));
  if(!fl) return;
  const ol=document.querySelector(`.flow-steps[data-flow="${cssEsc(fl.id)}"]`); if(!ol) return;
  ol.innerHTML='';
  fl.steps.forEach((st,si)=>{
    const li=document.createElement('li'); li.dataset.si=si;
    const fn=NODE[st.from]?(NODE[st.from].title):st.from, tn=NODE[st.to]?(NODE[st.to].title):st.to;
    li.innerHTML=`<div class="ft">${esc(fn)} <span class="ar">→</span> ${esc(tn)}</div>`+
      (st.passes?`<div class="passes">${esc(st.passes)}</div>`:'')+(st.note?`<div class="note">${esc(st.note)}</div>`:'');
    li.addEventListener('click',()=>{ focusStep(fl.id,si); li.scrollIntoView({block:'nearest',behavior:'smooth'}); });
    ol.appendChild(li);
  });
}
function flashAnno(si){
  if(!ST.activeFlow)return;
  const ol=document.querySelector(`.flow-steps[data-flow="${cssEsc(ST.activeFlow)}"]`); if(!ol)return;
  ol.querySelectorAll('li').forEach(li=>li.classList.remove('focused','flash'));
  const li=ol.querySelector(`li[data-si="${si}"]`); if(!li)return;
  li.classList.add('focused'); void li.offsetWidth; li.classList.add('flash');
  li.scrollIntoView({block:'nearest',behavior:'smooth'});
}

// ── ツールチップ ──
function showEdgeTip(e,ev){
  const tip=document.getElementById('tooltip');
  let html='';
  e.steps.forEach((s,i)=>{ if(i)html+='<hr>';
    const fn=NODE[s.step.from]?NODE[s.step.from].title:s.step.from, tn=NODE[s.step.to]?NODE[s.step.to].title:s.step.to;
    html+=`<div class="h">${esc(s.flow.name)} · step ${s.si+1}</div>`+
      `<div><span class="chip">${esc(fn)} → ${esc(tn)}</span></div>`+
      (s.step.passes?`<code>${esc(s.step.passes)}</code>`:'')+(s.step.note?`<div class="nt">${esc(s.step.note)}</div>`:'');
  });
  tip.innerHTML=html; posTip(ev);
}
function showNodeTip(n,ev){
  const tip=document.getElementById('tooltip');
  let html=`<div class="h">${esc(n.title)}</div>`;
  if(n.subtitle)html+=`<div class="chip">${esc(n.subtitle)}</div>`;
  if(n.desc)html+=`<div class="nt">${esc(n.desc)}</div>`;
  html+=`<div class="nt">${n.status==='added'?'★ 本作業で追加':'既存'} / ${n.type}</div>`;
  tip.innerHTML=html; posTip(ev);
}
function posTip(ev){const tip=document.getElementById('tooltip');tip.style.display='block';
  let x=ev.clientX+16,y=ev.clientY+16;const r=tip.getBoundingClientRect();
  if(x+r.width>innerWidth)x=ev.clientX-r.width-16; if(y+r.height>innerHeight)y=ev.clientY-r.height-16;
  tip.style.left=x+'px';tip.style.top=y+'px';}
function hideTip(){document.getElementById('tooltip').style.display='none';}

// ── ズーム / パン / フィット ──
function applyView(){STAGE.setAttribute('viewBox',`${ST.vb.x} ${ST.vb.y} ${ST.vb.w} ${ST.vb.h}`);}
function fitAll(anim){ fitBox({x:0,y:0,w:ST.base.w,h:ST.base.h},anim); }
function fitFlow(id){ const fl=DATA.flows.find(f=>f.id===id); if(!fl)return;
  const ids=new Set(); fl.steps.forEach(s=>{ids.add(s.from);ids.add(s.to);});
  let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
  ids.forEach(i=>{const n=NODE[i]; if(!n)return; x0=Math.min(x0,n.x);y0=Math.min(y0,n.y);x1=Math.max(x1,n.x+n.w);y1=Math.max(y1,n.y+n.h);});
  if(x0>x1)return; fitBox({x:x0-60,y:y0-60,w:(x1-x0)+120,h:(y1-y0)+120},true);
}
function fitBox(b,anim){
  const r=STAGE.getBoundingClientRect(), ar=r.width/r.height;
  let w=b.w,h=b.h; if(w/h>ar)h=w/ar; else w=h*ar;
  const target={x:b.x-(w-b.w)/2,y:b.y-(h-b.h)/2,w,h};
  if(anim) animateView(target); else {ST.vb=target;applyView();}
}
function animateView(target){const from={...ST.vb},t0=performance.now(),D=320;
  function step(now){let k=Math.min(1,(now-t0)/D);k=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2;
    ST.vb={x:from.x+(target.x-from.x)*k,y:from.y+(target.y-from.y)*k,w:from.w+(target.w-from.w)*k,h:from.h+(target.h-from.h)*k};
    applyView(); if(k<1)requestAnimationFrame(step);} requestAnimationFrame(step);}
function panTo(cx,cy){ const t={x:cx-ST.vb.w/2,y:cy-ST.vb.h/2,w:ST.vb.w,h:ST.vb.h}; animateView(t); }

function wireEvents(){
  STAGE.addEventListener('wheel',ev=>{ev.preventDefault();
    const r=STAGE.getBoundingClientRect();
    const mx=ST.vb.x+(ev.clientX-r.left)/r.width*ST.vb.w, my=ST.vb.y+(ev.clientY-r.top)/r.height*ST.vb.h;
    const f=ev.deltaY<0?0.88:1.14; const nw=Math.max(120,Math.min(ST.base.w*3,ST.vb.w*f)),nh=nw*(ST.vb.h/ST.vb.w);
    ST.vb={x:mx-(mx-ST.vb.x)*(nw/ST.vb.w),y:my-(my-ST.vb.y)*(nh/ST.vb.h),w:nw,h:nh}; applyView();
  },{passive:false});
  let pan=null;
  STAGE.addEventListener('mousedown',ev=>{ if(ev.target.closest('.edge-step-badge'))return; pan={x:ev.clientX,y:ev.clientY,vx:ST.vb.x,vy:ST.vb.y}; STAGE.classList.add('grabbing');});
  window.addEventListener('mousemove',ev=>{ if(!pan)return; const r=STAGE.getBoundingClientRect();
    ST.vb.x=pan.vx-(ev.clientX-pan.x)/r.width*ST.vb.w; ST.vb.y=pan.vy-(ev.clientY-pan.y)/r.height*ST.vb.h; applyView();});
  window.addEventListener('mouseup',()=>{pan=null;STAGE.classList.remove('grabbing');});
  window.addEventListener('keydown',ev=>{
    if(ev.key>='1'&&ev.key<='9'){const i=+ev.key-1; if(DATA.flows[i])selectFlow(DATA.flows[i].id);}
    else if(ev.key==='0'){if(DATA.flows[9])selectFlow(DATA.flows[9].id);}
    else if(ev.key==='f'||ev.key==='F'){fitAll(true);}
    else if(ev.key==='+'||ev.key==='='){ST.vb.w*=0.85;ST.vb.h*=0.85;applyView();}
    else if(ev.key==='-'){ST.vb.w/=0.85;ST.vb.h/=0.85;applyView();}
    else if(ev.key==='Escape'){ if(ST.focus){ST.focus=null;refreshActive();} else if(ST.activeFlow){ST.activeFlow=null;refreshActive();fitAll(true);} }
  });
  // resizer
  const rz=document.getElementById('resizer'); let rs=null;
  const saved=localStorage.getItem('rbc-tbl-h'); if(saved)document.documentElement.style.setProperty('--tbl-h',saved);
  rz.addEventListener('mousedown',ev=>{rs={y:ev.clientY,h:parseInt(getComputedStyle(document.documentElement).getPropertyValue('--tbl-h'))||240};ev.preventDefault();});
  window.addEventListener('mousemove',ev=>{ if(!rs)return; let h=Math.max(120,Math.min(600,rs.h-(ev.clientY-rs.y)));
    document.documentElement.style.setProperty('--tbl-h',h+'px');});
  window.addEventListener('mouseup',()=>{ if(rs){localStorage.setItem('rbc-tbl-h',getComputedStyle(document.documentElement).getPropertyValue('--tbl-h').trim());rs=null;}});
}

loadData().then(d=>{
  if(!d||!d.nodes||!d.nodes.length){const t=document.getElementById('tables');if(t)t.innerHTML='<p class="empty">構成データがありません。</p>';return;}
  init(d);
});
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topology")
    ap.add_argument("-o", "--output", default="topology.html")
    args = ap.parse_args()
    try:
        with open(args.topology, encoding="utf-8") as fp:
            topo = json.load(fp)
    except (OSError, json.JSONDecodeError) as e:
        print(f"topology.json の読み込みに失敗: {e}", file=sys.stderr)
        sys.exit(1)

    data = build_render_data(topo)
    sidecar = os.path.join(os.path.dirname(os.path.abspath(args.output)), "topology.flows.json")
    with open(sidecar, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)

    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = str(data.get("title", "network topology"))
    subtitle = f"{len(data['nodes'])} nodes / {len(data['flows'])} flows"
    html = (HTML_TEMPLATE
            .replace("__TITLE__", title.replace("<", "&lt;"))
            .replace("__SUBTITLE__", subtitle)
            .replace("__DATA__", embedded))
    with open(args.output, "w", encoding="utf-8") as fp:
        fp.write(html)

    n_add = sum(1 for n in data["nodes"] if n.get("status") == "added")
    print(f"構成図HTMLを出力しました: {args.output}（nodes {len(data['nodes'])} / flows {len(data['flows'])} / 追加node {n_add}）")
    print(f"  サイドカー: {sidecar}")


if __name__ == "__main__":
    main()
