"""report_html.py — レビュー結果JSON から自己完結型HTMLレポートを生成する。

stdlib のみ使用。ユーザー入力はすべて html.escape でサニタイズ。
"""
import argparse
import html
import json

# 重大度の降順ソートキー
_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

_SEVERITY_COLOR = {
    "CRITICAL": "#c0392b",
    "HIGH":     "#e67e22",
    "MEDIUM":   "#f1c40f",
    "LOW":      "#27ae60",
}

_VERDICT_COLOR = {
    "blocked":  "#c0392b",
    "warning":  "#e67e22",
    "approved": "#27ae60",
}

_CSS = """
body { font-family: sans-serif; margin: 2em; color: #222; }
h1 { border-bottom: 2px solid #888; padding-bottom: 0.3em; }
.meta { color: #555; font-size: 0.9em; margin-bottom: 1.5em; }
.overall { font-size: 1.4em; font-weight: bold; margin: 1em 0; }
table { border-collapse: collapse; width: 100%; margin-bottom: 2em; }
th, td { border: 1px solid #ccc; padding: 0.4em 0.7em; text-align: center; }
th { background: #f0f0f0; }
td.name { text-align: left; }
.badge { display: inline-block; padding: 0.15em 0.5em; border-radius: 3px;
         color: #fff; font-size: 0.85em; font-weight: bold; }
.finding { border: 1px solid #ddd; border-left: 4px solid #888;
           margin-bottom: 1em; padding: 0.5em 1em; }
.finding .loc { color: #777; font-size: 0.85em; }
.finding .detail, .finding .fix { margin-top: 0.4em; font-size: 0.9em; }
"""


def overall_verdict(data: dict) -> str:
    """全レビュアーのfindingsを見てoverall verdictを返す。

    CRITICAL があれば "blocked"、HIGH があれば "warning"、それ以外は "approved"。
    """
    severities = {
        f["severity"]
        for r in data.get("reviewers", [])
        for f in r.get("findings", [])
    }
    if "CRITICAL" in severities:
        return "blocked"
    if "HIGH" in severities:
        return "warning"
    return "approved"


def _badge(severity: str) -> str:
    color = _SEVERITY_COLOR.get(severity, "#888")
    return f'<span class="badge" style="background:{color}">{html.escape(severity)}</span>'


def _verdict_span(verdict: str) -> str:
    color = _VERDICT_COLOR.get(verdict, "#888")
    return f'<span style="color:{color};font-weight:bold">{html.escape(verdict)}</span>'


def _count_by_severity(findings: list) -> dict:
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        sev = f.get("severity", "LOW")
        if sev in counts:
            counts[sev] += 1
    return counts


def render_report(data: dict) -> str:
    """findings JSON から自己完結型HTML文字列を返す。"""
    target = html.escape(data.get("target", ""))
    generated_at = html.escape(data.get("generated_at", ""))
    verdict = overall_verdict(data)
    verdict_color = _VERDICT_COLOR.get(verdict, "#888")

    # --- サマリーテーブル ---
    table_rows = []
    for r in data.get("reviewers", []):
        name = html.escape(r.get("name", ""))
        rv = r.get("verdict", "")  # _verdict_span 内で escape するため raw のまま渡す
        counts = _count_by_severity(r.get("findings", []))
        table_rows.append(
            f"<tr>"
            f'<td class="name">{name}</td>'
            f"<td>{counts['CRITICAL']}</td>"
            f"<td>{counts['HIGH']}</td>"
            f"<td>{counts['MEDIUM']}</td>"
            f"<td>{counts['LOW']}</td>"
            f"<td>{_verdict_span(rv)}</td>"
            f"</tr>"
        )
    table_html = (
        "<table>"
        "<tr><th>Reviewer</th><th>CRITICAL</th><th>HIGH</th><th>MEDIUM</th><th>LOW</th><th>Verdict</th></tr>"
        + "".join(table_rows)
        + "</table>"
    )

    # --- findings を重大度降順でまとめる ---
    all_findings = []
    for r in data.get("reviewers", []):
        for f in r.get("findings", []):
            all_findings.append(f)

    all_findings.sort(key=lambda f: _SEVERITY_ORDER.get(f.get("severity", "LOW"), 99))

    finding_blocks = []
    for f in all_findings:
        sev = f.get("severity", "LOW")
        border_color = _SEVERITY_COLOR.get(sev, "#888")
        summary = html.escape(f.get("summary", ""))
        location = html.escape(f.get("location", ""))
        detail = html.escape(f.get("detail", ""))
        fix = html.escape(f.get("fix", ""))
        finding_blocks.append(
            f'<div class="finding" style="border-left-color:{border_color}">'
            f"{_badge(sev)} <strong>{summary}</strong>"
            f'<div class="loc">{location}</div>'
            f'<div class="detail">Detail: {detail}</div>'
            f'<div class="fix">Fix: {fix}</div>'
            f"</div>"
        )

    findings_html = "".join(finding_blocks)

    return f"""\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>OpsReviewer Report - {target}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>OpsReviewer Report</h1>
<div class="meta">
  <div>Target: <strong>{target}</strong></div>
  <div>Generated: {generated_at}</div>
</div>
<div class="overall">
  Overall Verdict: <span style="color:{verdict_color}">{html.escape(verdict)}</span>
</div>
{table_html}
<h2>Findings</h2>
{findings_html}
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="レビュー結果をHTMLレポートに変換する")
    parser.add_argument("--input", required=True, help="findings JSON ファイルのパス")
    parser.add_argument("--output", required=True, help="出力 HTML ファイルのパス")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    html_str = render_report(data)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_str)


if __name__ == "__main__":
    main()
