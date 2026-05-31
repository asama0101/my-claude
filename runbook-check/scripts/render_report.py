#!/usr/bin/env python3
"""
作業手順書レビュー結果を自己完結HTMLに変換する。
結果は「シート別チェック結果」で構成する（手順書はSTEPごとにシートが分かれるケースが多いため）。

使い方:
    python render_report.py findings.json -o report.html

findings.json のスキーマは SKILL.md を参照。依存ライブラリなし・オフライン動作・印刷対応。
"""
import argparse
import html
import json
import sys
from datetime import datetime

SEVERITY = {
    "blocker":     {"label": "Blocker", "mark": "🔴", "rank": 0, "color": "#c0392b", "bg": "#fdecea"},
    "important":   {"label": "重要",     "mark": "🟠", "rank": 1, "color": "#d35400", "bg": "#fef0e6"},
    "recommended": {"label": "推奨",     "mark": "🟡", "rank": 2, "color": "#b7950b", "bg": "#fdf6e3"},
    "minor":       {"label": "軽微",     "mark": "🔵", "rank": 3, "color": "#2471a3", "bg": "#eaf2f8"},
}
VERDICT_STYLE = {"実施非推奨": "#c0392b", "修正後可": "#d35400", "実施可": "#1e8449"}
OTHER_GROUP = "全体・横断"


def esc(s):
    return html.escape(str(s if s is not None else ""))


def severity_of(f):
    return SEVERITY.get(f.get("severity", "minor"), SEVERITY["minor"])


def sheet_of_finding(f):
    """findingの所属シートを決める。明示の sheet → location の '!' 前 → 全体。"""
    if f.get("sheet"):
        return f["sheet"]
    loc = str(f.get("location", ""))
    if "!" in loc:
        return loc.split("!", 1)[0].strip().strip("'")
    return OTHER_GROUP


def badges_html(counts, small=False):
    cls = "badge small" if small else "badge"
    out = []
    for k, s in SEVERITY.items():
        if small and not counts.get(k):
            continue
        out.append(f'<span class="{cls}" style="background:{s["bg"]};color:{s["color"]};border-color:{s["color"]}">'
                   f'{s["mark"]} {s["label"]} {counts.get(k,0)}</span>')
    return "".join(out) or '<span class="badge small ok">指摘なし</span>'


def render_finding(f):
    s = severity_of(f)
    revs = "".join(f'<span class="rev">{esc(r)}</span>' for r in f.get("reviewers", []))
    loc = str(f.get("location", "")).strip()
    loc_badge = f'<span class="loc-badge">📍 {esc(loc)}</span>' if loc else ""
    return f"""
    <div class="finding" style="border-left-color:{s['color']}">
      <div class="finding-head">
        <span class="sev" style="background:{s['color']}">{s['mark']} {s['label']}</span>
        {loc_badge}
        <span class="dim">{esc(f.get('dimension',''))}</span>
      </div>
      <div class="problem"><b>問題:</b> {esc(f.get('problem',''))}</div>
      <div class="suggestion"><b>改善案:</b> {esc(f.get('suggestion',''))}</div>
      <div class="revs">検出: {revs or '<span class="rev">-</span>'}</div>
    </div>"""


def render_params(parameters):
    if not parameters:
        return ""
    rows = []
    for p in parameters:
        valid = p.get("valid")
        if valid is False:
            cls, status = "invalid", f'⚠ {esc(p.get("note"))}'
        elif valid is True:
            cls, status = "", "OK"
        else:
            cls, status = "unfilled", "（未入力）"
        val = esc(p.get("value")) if p.get("filled") else "（未入力）"
        rows.append(
            f'<tr class="{cls}"><td>{esc(p.get("name"))}</td><td class="mono">{esc(p.get("cell"))}</td>'
            f'<td class="mono">{val}</td><td>{esc(p.get("type") or "")}</td>'
            f'<td class="mono">{esc(p.get("constraint") or "")}</td><td>{status}</td>'
            f'<td class="basis">{esc(p.get("basis") or "")}</td></tr>'
        )
    return f"""
  <h2>パラメータ（入力値の検証結果）</h2>
  <p class="note">※ 「検証根拠」は<b>インプット情報（IP一覧/設計値ファイル）との照合</b>結果。<b>照合元が無い／不一致は NG</b>（設計値を保証できない）。
     あわせて 形式（型の妥当性）・宣言された許容範囲・相互整合（IP×マスク）も機械検証する。</p>
  <table class="ptab">
    <thead><tr><th>パラメータ名</th><th>セル</th><th>値</th><th>型</th><th>許容範囲</th><th>状態</th><th>検証根拠（何を参照したか）</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>"""


APPROVER_FIELDS = [
    ("what", "作業内容"),
    ("purpose", "目的・背景"),
    ("targets", "対象機器・範囲"),
    ("impact", "影響（断時間・対象通信）"),
    ("rollback", "切り戻し"),
]


def render_work_types(types):
    if not types:
        return ""
    chips = "".join(f'<span class="wtype">{esc(t)}</span>' for t in types)
    return f'<div class="wtypes"><span class="wtypes-label">作業タイプ:</span>{chips}</div>'


def render_approver_summary(summary):
    if not summary:
        return ""
    rows = "".join(
        f'<div class="appr-row"><span class="appr-k">{esc(jp)}</span>'
        f'<span class="appr-v">{esc(summary[key])}</span></div>'
        for key, jp in APPROVER_FIELDS if summary.get(key)
    )
    if not rows:
        return ""
    return f"""
  <section class="approver">
    <h2>作業承認者向け説明</h2>
    <div class="appr-grid">{rows}</div>
  </section>"""


CHECK_DIMENSIONS = [
    ("1", "目的・前提・事前準備"),
    ("2", "手順の粒度・順序"),
    ("3", "正常性確認"),
    ("4", "切り戻し・ロールバック"),
    ("5", "危険手順・影響範囲"),
    ("6", "コマンド正確性・ベンダー差"),
    ("7", "並行作業・競合制御"),
    ("8", "認証・セキュリティ"),
    ("9", "エスカレーション・連絡体制"),
    ("10", "体裁・一貫性"),
    ("11", "関数・パラメータ整合"),
    ("12", "投入Config整合"),
    ("13", "改版履歴"),
    ("14", "現行Config整合（バックアップ照合）"),
]


def _leading_num(s):
    s = str(s).lstrip()
    i = 0
    while i < len(s) and s[i].isdigit():
        i += 1
    return s[:i] if i else None


def render_check_dimensions(data):
    """作業承認者向け説明の直下に、本レビューで確認した観点と指摘件数を一覧表示する。
    レビューの網羅性が一目で伝わるようにする。"""
    findings = data.get("findings", [])
    counts = {}
    for f in findings:
        dim = str(f.get("dimension", ""))
        num = _leading_num(dim)
        if num:
            counts[num] = counts.get(num, 0) + 1
        elif "関数" in dim:
            # 「関数チェック」(番号なし)は観点11『関数・パラメータ整合』に集約する
            counts["11"] = counts.get("11", 0) + 1
    backup_done = bool(data.get("backup_compared") or counts.get("14"))

    chips = []
    for num, label in CHECK_DIMENSIONS:
        if num == "14" and not backup_done:
            continue  # バックアップ未照合なら観点14は出さない
        chips.append((f"{num}. {label}", counts.get(num, 0)))

    cells = []
    for label, n in chips:
        if n > 0:
            cells.append(f'<span class="ck ck-hit">{esc(label)}<b>指摘{n}</b></span>')
        else:
            cells.append(f'<span class="ck">{esc(label)}<span class="ck-ok">指摘なし</span></span>')
    return f"""
  <section class="checks">
    <h2>チェック観点（本レビューで確認した項目）</h2>
    <div class="ck-grid">{"".join(cells)}</div>
  </section>"""


# 実機の「設定」を構成するコマンドの先頭語（ベンダー横断・小文字判定）。
# commit/save/write/show/login 等の運用・確認・接続操作や地の文は投入Configに含めない。
CONFIG_VERBS = ("set ", "delete ", "deactivate ", "activate ", "rename ", "insert ",
                "annotate ", "no ", "interface ", "ip ", "ipv6 ", "vlan ", "router ",
                "hostname ", "snmp-server ", "ntp ", "aaa ", "line ", "access-list ",
                "route ", "spanning-tree ", "switchport ", "channel-group ")


def is_config_command(cmd):
    """投入Configに載せるべき『設定コマンド』か。commit/save/show/接続手順/地の文は除外。"""
    c = str(cmd or "").strip().lower()
    return any(c.startswith(v) for v in CONFIG_VERBS)


def render_injected_config(config_preview):
    """全STEPの解決後コマンドのうち**実機の設定コマンドのみ**を統合した『作業の投入Config』。
    これは作業で機器へ投入される設定そのもので、現行Config照合（妥当性チェック）の対象。
    commit/save・show による確認・接続/ログイン手順・地の文は設定ではないため除外する。"""
    lines = []
    skipped = 0
    for blk in config_preview:
        sheet = blk.get("sheet", "")
        for ln in blk.get("lines", []):
            raw = ln.get("command")
            if not is_config_command(raw):
                skipped += 1
                continue
            cmd = esc(raw)
            tag = f'<span class="ec-src">{esc(sheet)}!{esc(str(ln.get("location","")).split("!")[-1])}</span>'
            lines.append(f'<div class="ec-line">{tag}<code>{cmd}</code></div>')
    if not lines:
        return ""
    note = ("作業で機器へ投入される設定コマンドのみを順に統合したもの（＝投入される設定そのもの）。"
            "作成時バックアップ（現行Config）との照合で妥当性を確認する対象。"
            "commit/保存・確認(show)・接続/ログイン手順などの非設定操作は除外している。")
    return f"""
  <h3>作業の投入Config（全STEP統合・関数解決後）</h3>
  <p class="note">{note}</p>
  <div class="exp-config">{"".join(lines)}</div>"""


def render_unused_params(unused):
    """記入されているのに、どの関数からも参照されていないパラメータセル。参考情報。"""
    if not unused:
        return ""
    rows = "".join(
        f'<tr><td>{esc(u.get("name"))}</td><td class="mono">{esc(u.get("cell"))}</td>'
        f'<td class="mono">{esc(u.get("value"))}</td></tr>'
        for u in unused
    )
    return f"""
  <h3>参照されていない記入済みパラメータ</h3>
  <p class="note">値が入力されているが、どの関数（コマンド生成）からも参照されていないセル。本来使うはずのコマンドの参照漏れ、不要な記入、別用途のいずれか。要確認。</p>
  <table class="ptab">
    <thead><tr><th>パラメータ名</th><th>セル</th><th>記入値</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>"""


def render_pre_summary(open_questions):
    """『確認が必要な事項』を作業前サマリとして冒頭に出す。当番が最優先で押さえる要点。"""
    if not open_questions:
        return ""
    items = "".join(f"<li>{esc(q)}</li>" for q in open_questions)
    return f"""
  <section class="presum">
    <h2>確認が必要な事項（作業前に押さえる要点）</h2>
    <ul class="presum-list">{items}</ul>
  </section>"""


def render_topology_link(data):
    """構成図は別ファイル topology.html。レポートからはリンクで案内する。"""
    href = data.get("topology_html") or ("topology.html" if data.get("topology") else "")
    if not href:
        return ""
    return (f'<h3>構成図</h3>'
            f'<p class="note">物理（機器・IF・FDF・TIE）と論理（IP・AS・BGP・スタティックルート）を1枚に重ねた'
            f'構成図は別ファイル <a href="{esc(href)}">{esc(href)}</a> を参照（作業で追加される要素は色分け表示）。</p>')


def render_reference(data):
    body = (render_injected_config(data.get("config_preview", []))
            + render_unused_params(data.get("unused_params", []))
            + render_topology_link(data))
    if not body.strip():
        return ""
    return f"""
  <h2>参考情報</h2>{body}"""


def render(data):
    target = data.get("target", "(対象未指定)")
    overall = data.get("overall", "")
    verdict = data.get("verdict", "")
    findings = list(data.get("findings", []))
    parameters = data.get("parameters", [])
    config_preview = data.get("config_preview", [])
    good_points = data.get("good_points", [])
    open_questions = data.get("open_questions", [])
    sheets_order = data.get("sheets_order", [])
    work_types = data.get("work_types", [])
    approver_summary = data.get("approver_summary", {})

    # 集計
    total_counts = {k: 0 for k in SEVERITY}
    for f in findings:
        total_counts[f.get("severity", "minor")] = total_counts.get(f.get("severity", "minor"), 0) + 1

    # シート別にfindingsとconfigをまとめる
    by_sheet_find = {}
    for f in findings:
        by_sheet_find.setdefault(sheet_of_finding(f), []).append(f)
    by_sheet_cfg = {blk.get("sheet", ""): blk.get("lines", []) for blk in config_preview}

    # シートの並び順: sheets_order優先 → 出現順 → 全体は最後
    seen = []
    for name in sheets_order:
        if name in by_sheet_find or name in by_sheet_cfg:
            seen.append(name)
    for name in list(by_sheet_cfg) + list(by_sheet_find):
        if name and name != OTHER_GROUP and name not in seen:
            seen.append(name)
    if OTHER_GROUP in by_sheet_find:
        seen.append(OTHER_GROUP)

    sections = []
    for name in seen:
        fs = sorted(by_sheet_find.get(name, []),
                    key=lambda f: (severity_of(f)["rank"], str(f.get("dimension", ""))))
        counts = {k: 0 for k in SEVERITY}
        for f in fs:
            counts[f.get("severity", "minor")] = counts.get(f.get("severity", "minor"), 0) + 1
        find_html = "".join(render_finding(f) for f in fs) or '<p class="empty">指摘なし。</p>'
        sections.append(f"""
  <div class="sheet-block">
    <h3>シート: {esc(name)} <span class="sheet-badges">{badges_html(counts, small=True)}</span></h3>
    {find_html}
  </div>""")
    sheets_html = "\n".join(sections) if sections else '<p class="empty">対象シートなし。</p>'

    good_html = "".join(f"<li>{esc(g)}</li>" for g in good_points) or "<li>-</li>"
    verdict_color = VERDICT_STYLE.get(verdict, "#555")
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>作業手順書レビュー結果 - {esc(target)}</title>
<style>
  :root {{ --fg:#1a1a1a; --muted:#666; --line:#e2e2e2; --card:#fff; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,"Segoe UI","Hiragino Kaku Gothic ProN","Noto Sans JP",sans-serif;
         color:var(--fg); margin:0; background:#f5f6f8; line-height:1.7; }}
  .wrap {{ max-width:920px; margin:0 auto; padding:32px 20px 80px; }}
  header {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:24px 28px; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  .target {{ color:var(--muted); font-size:14px; margin-bottom:16px; }}
  .verdict {{ display:inline-block; font-weight:700; font-size:15px; color:#fff;
             padding:6px 14px; border-radius:6px; background:{verdict_color}; margin-bottom:14px; }}
  .overall {{ margin:8px 0 18px; }}
  .badges {{ display:flex; gap:10px; flex-wrap:wrap; }}
  .badge {{ font-size:13px; font-weight:600; padding:5px 11px; border-radius:20px; border:1px solid; }}
  .badge.small {{ font-size:11px; padding:2px 8px; }}
  .badge.ok {{ background:#eaf7ee; color:#1e8449; border-color:#1e8449; }}
  .wtypes {{ margin:8px 0 14px; display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}
  .wtypes-label {{ font-size:12px; color:var(--muted); }}
  .wtype {{ font-size:12px; font-weight:600; background:#eef3ff; color:#2f5fbf; border:1px solid #bcd0f5; border-radius:14px; padding:3px 11px; }}
  .approver {{ background:#fff; border:1px solid var(--line); border-left:5px solid #2f5fbf; border-radius:10px; padding:18px 22px; margin-top:18px; }}
  .approver h2 {{ margin:0 0 12px; border:none; padding:0; font-size:16px; }}
  .appr-grid {{ display:flex; flex-direction:column; gap:8px; }}
  .appr-row {{ display:flex; gap:12px; align-items:baseline; }}
  .appr-k {{ flex:0 0 150px; font-weight:600; font-size:13px; color:#445; }}
  .appr-v {{ flex:1; font-size:14px; }}
  .checks {{ background:#fff; border:1px solid var(--line); border-radius:10px; padding:14px 20px 18px; margin-top:18px; }}
  .checks h2 {{ margin:0 0 12px; border:none; padding:0; font-size:15px; }}
  .ck-grid {{ display:flex; flex-wrap:wrap; gap:7px; }}
  .ck {{ display:inline-flex; align-items:center; gap:7px; font-size:12px; background:#f2f4f7; color:#445;
        border:1px solid var(--line); border-radius:6px; padding:4px 9px; }}
  .ck-ok {{ color:#9aa4b2; font-size:11px; }}
  .ck-hit {{ background:#fef0e6; color:#b34700; border-color:#e8b98f; }}
  .ck-hit b {{ font-size:11px; background:#d35400; color:#fff; border-radius:9px; padding:0 7px; font-weight:700; }}
  h2 {{ font-size:16px; margin:34px 0 14px; padding-bottom:8px; border-bottom:2px solid var(--line); }}
  .sheet-block {{ background:#fafbfc; border:1px solid var(--line); border-radius:10px;
                 padding:14px 18px; margin-bottom:18px; }}
  .sheet-block h3 {{ font-size:15px; margin:4px 0 12px; display:flex; align-items:center;
                    gap:10px; flex-wrap:wrap; }}
  .sheet-badges {{ display:inline-flex; gap:6px; flex-wrap:wrap; }}
  .sheet-block h4 {{ font-size:13px; color:var(--muted); margin:14px 0 8px; }}
  .finding {{ background:var(--card); border:1px solid var(--line); border-left:5px solid;
             border-radius:8px; padding:14px 16px; margin-bottom:12px; }}
  .finding-head {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:9px; }}
  .sev {{ color:#fff; font-weight:700; font-size:12px; padding:3px 9px; border-radius:5px; }}
  .dim {{ font-weight:600; font-size:14px; }}
  .loc {{ color:var(--muted); font-size:13px; font-family:ui-monospace,Menlo,Consolas,monospace; }}
  .loc-badge {{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:12px; font-weight:700;
               color:#1b3a5b; background:#e7effb; border:1px solid #b9cdf0; border-radius:5px; padding:2px 8px; }}
  .problem, .suggestion {{ font-size:14px; margin:6px 0; }}
  .suggestion {{ background:#f7fbf7; border-radius:6px; padding:8px 10px; }}
  .revs {{ font-size:12px; color:var(--muted); margin-top:8px; }}
  .rev {{ display:inline-block; background:#eef1f5; color:#445; border-radius:4px; padding:1px 7px; margin-left:5px; font-size:11px; }}
  .cfg-line {{ background:#1e2127; border:1px solid #2c313a; border-left:4px solid #3fa45b;
              border-radius:6px; padding:8px 12px; margin-bottom:8px; }}
  .cfg-line.cfg-hard {{ border-left-color:#d35400; }}
  .cfg-meta {{ font-size:12px; color:#9aa4b2; margin-bottom:4px; display:flex; justify-content:space-between; gap:10px; }}
  .cfg-step {{ display:inline-block; background:#3a3f4b; color:#cdd3dc; border-radius:4px; padding:0 7px; margin-right:6px; }}
  .cfg-loc {{ font-family:ui-monospace,Menlo,Consolas,monospace; }}
  .cfg-line code {{ color:#e6edf3; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13px; white-space:pre-wrap; word-break:break-all; }}
  .cfg-refs {{ font-size:11px; color:#9aa4b2; margin-top:6px; }}
  .ref {{ display:inline-block; background:#2c313a; color:#aeb6c2; border-radius:4px; padding:1px 7px; margin:0 4px 2px 0; font-family:ui-monospace,Menlo,Consolas,monospace; }}
  .ref.cross {{ background:#4a3a22; color:#e2b97f; }}
  .mono {{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13px; }}
  .ptab {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:8px; overflow:hidden; font-size:14px; }}
  .ptab th, .ptab td {{ text-align:left; padding:8px 12px; border-bottom:1px solid var(--line); }}
  .ptab th {{ background:#f0f2f5; font-size:13px; }}
  .ptab td.basis {{ font-size:12px; color:#566; }}
  .ptab tr.unfilled td {{ background:#fef0e6; color:#d35400; }}
  .ptab tr.invalid td {{ background:#fdecea; color:#c0392b; }}
  ul {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:14px 18px 14px 36px; }}
  .empty {{ color:var(--muted); }}
  .exp-config {{ background:#1e2127; border:1px solid #2c313a; border-radius:8px; padding:12px 14px; }}
  .ec-line {{ display:flex; gap:10px; align-items:baseline; padding:2px 0; }}
  .ec-src {{ flex:0 0 auto; min-width:110px; color:#9aa4b2; font-size:11px; font-family:ui-monospace,Menlo,Consolas,monospace; }}
  .ec-line code {{ color:#e6edf3; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13px; white-space:pre-wrap; word-break:break-all; }}
  .presum {{ background:#fffaf0; border:1px solid #f0d9a8; border-left:5px solid #d39e00; border-radius:10px; padding:14px 22px 16px; margin-top:18px; }}
  .presum h2 {{ margin:0 0 10px; border:none; padding:0; font-size:15px; color:#8a6d00; }}
  .presum-list {{ background:transparent; border:none; border-radius:0; padding:0 0 0 20px; margin:0; }}
  .presum-list li {{ font-size:14px; margin:4px 0; }}
  footer {{ color:var(--muted); font-size:12px; margin-top:40px; text-align:center; }}
  @media print {{ body {{ background:#fff; }} .finding, header, ul, .sheet-block {{ break-inside:avoid; }} }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>作業手順書レビュー結果</h1>
    <div class="target">対象: {esc(target)}</div>
    {render_work_types(work_types)}
    {f'<div class="verdict">{esc(verdict)}</div>' if verdict else ''}
    <div class="overall">{esc(overall)}</div>
    <div class="badges">{badges_html(total_counts)}</div>
  </header>
  {render_approver_summary(approver_summary)}
  {render_check_dimensions(data)}
  {render_pre_summary(open_questions)}

  <h2>シート別チェック結果</h2>
  {sheets_html}
  {render_params(parameters)}

  <h2>良い点</h2>
  <ul>{good_html}</ul>
  {render_reference(data)}

  <footer>generated {generated} / runbook-check</footer>
</div>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("findings")
    ap.add_argument("-o", "--output", default="report.html")
    args = ap.parse_args()
    try:
        with open(args.findings, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError) as e:
        print(f"findings.json の読み込みに失敗: {e}", file=sys.stderr)
        sys.exit(1)
    with open(args.output, "w", encoding="utf-8") as fp:
        fp.write(render(data))
    print(f"HTMLレポートを出力しました: {args.output}")


if __name__ == "__main__":
    main()
