#!/usr/bin/env python3
"""Markdown中間生成物を report_template.html に差し込んでHTMLレポートを組み立てる。

標準ライブラリのみに依存する（外部の markdown パッケージを前提にしない）。
対応するMarkdown記法: 見出し(#-######)、GFMテーブル、番号なし/番号付きリスト、
チェックリスト(- [ ]/- [x])、フェンス付きコードブロック、引用(>)、水平線(---)、
インライン code/bold/italic/link。想定外の記法は素の段落として出力する。

使い方:
    python3 build_report.py --input report.md --output report.html \
        --title "shaper-db transform/ レビュー地図" --target "src/shaper_db/transform/"
"""
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "report_template.html"
CALLGRAPH_JS_PATH = Path(__file__).resolve().parent.parent / "assets" / "callgraph.js"

INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")
CHECKBOX_RE = re.compile(r"^(\s*)-\s\[([ xX])\]\s+(.*)$")
UL_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
OL_RE = re.compile(r"^(\s*)\d+\.\s+(.*)$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
HR_RE = re.compile(r"^\s*-{3,}\s*$")

# references/module-map-format.md 6節・7節の固定書式
# (<details>/<details open>/<summary>.../</summary>/</details>)専用。
# この4パターン以外の生HTMLは一般にパススルーしない(許可タグを最小限に限定するため)。
DETAILS_SUMMARY_RE = re.compile(r"^<summary>.*</summary>$")

# callgraph フェンスブロックの文法(references/module-map-format.md 6節を正典とする)。
# `<左ノード> -> <右ノード>[: <エッジラベル>]`。ノードは `id[ref]`(通常ノード)か
# `id`(終端ノード、file:line を持たない)のいずれか。ノード id は `[` `]` `->` を含まない。
CALLGRAPH_NODE_BRACKET_RE = re.compile(r"^(.*?)\[([^\[\]]*)\]\s*(?::\s*(.*))?$")
CALLGRAPH_REF_LINE_RE = re.compile(r"^(.*):(\d+)$")


def slugify(text: str, seen: dict) -> str:
    plain = re.sub(r"`([^`]+)`", r"\1", text)
    plain = re.sub(r"[^\w\s\-一-龥ぁ-んァ-ヶー]", "", plain, flags=re.UNICODE)
    slug = plain.strip().lower().replace(" ", "-") or "section"
    if slug in seen:
        seen[slug] += 1
        slug = f"{slug}-{seen[slug]}"
    else:
        seen[slug] = 0
    return slug


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = INLINE_CODE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", text)
    text = BOLD_RE.sub(lambda m: f"<strong>{m.group(1)}</strong>", text)
    text = ITALIC_RE.sub(lambda m: f"<em>{m.group(1)}</em>", text)
    text = LINK_RE.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    return text


class ListBuilder:
    """インデント量でネストを判定するシンプルなリストスタック。"""

    def __init__(self) -> None:
        self.stack: list[tuple[int, str]] = []  # (indent, tag)
        self.out: list[str] = []

    def _open(self, indent: int, tag: str) -> None:
        self.stack.append((indent, tag))
        cls = ' class="checklist"' if tag == "ul-checklist" else ""
        real_tag = "ul" if tag.startswith("ul") else "ol"
        self.out.append(f"<{real_tag}{cls}>")

    def _close_to(self, indent: int) -> None:
        while self.stack and self.stack[-1][0] > indent:
            real_tag = "ul" if self.stack[-1][1].startswith("ul") else "ol"
            self.out.append(f"</{real_tag}>")
            self.stack.pop()

    def add_item(self, indent: int, tag: str, body_html: str) -> None:
        if self.stack and self.stack[-1][0] > indent:
            self._close_to(indent)
        if not self.stack or self.stack[-1][0] < indent:
            self._open(indent, tag)
        elif self.stack[-1][1] != tag:
            real_tag = "ul" if self.stack[-1][1].startswith("ul") else "ol"
            self.out.append(f"</{real_tag}>")
            self.stack.pop()
            self._open(indent, tag)
        self.out.append(f"<li>{body_html}</li>")

    def close_all(self) -> None:
        self._close_to(-1)

    def render(self) -> str:
        return "\n".join(self.out)


def render_table(rows: list[str]) -> str:
    header_cells = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    body_rows = rows[2:]
    out = ["<table>", "<thead><tr>"]
    out += [f"<th>{inline(c)}</th>" for c in header_cells]
    out.append("</tr></thead><tbody>")
    for row in body_rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def parse_callgraph_node(text: str, allow_label: bool) -> tuple[str, str | None, str | None]:
    """ノード片(+右辺のみ許すエッジラベル)をパースする。(id, ref, label) を返す。

    ref がある場合(`id[ref]`)はそれを返し、無ければ終端ノードとして ref=None を返す。
    allow_label=True のときだけラベル分離を試みる(左ノードにはラベルは付かない仕様)。
    """
    text = text.strip()
    m = CALLGRAPH_NODE_BRACKET_RE.match(text)
    if m:
        node_id = m.group(1).strip()
        ref = m.group(2).strip() or None
        label = m.group(3).strip() if (allow_label and m.group(3) is not None) else None
        return node_id, ref, label
    if allow_label and ":" in text:
        node_id, _, label = text.partition(":")
        return node_id.strip(), None, label.strip()
    return text, None, None


def parse_callgraph_line(line: str) -> dict | None:
    """1行をパースし {"left": (id, ref), "right": (id, ref), "label": str|None} を返す。

    空行は None を返す。矢印(`->`)が無い、または片方のノード id が空の場合は ValueError。
    """
    raw = line.strip()
    if not raw:
        return None
    if "->" not in raw:
        raise ValueError("矢印(->)が見つかりません")
    left_text, right_text = raw.split("->", 1)
    left_id, left_ref, _ = parse_callgraph_node(left_text, allow_label=False)
    right_id, right_ref, label = parse_callgraph_node(right_text, allow_label=True)
    if not left_id or not right_id:
        raise ValueError("ノードidが空です")
    return {"left": (left_id, left_ref), "right": (right_id, right_ref), "label": label}


def build_callgraph_data(code_lines: list[str]) -> tuple[dict, list[str]]:
    """callgraph ブロックの各行から (ノード/エッジデータ, パースエラー一覧) を組み立てる。"""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    errors: list[str] = []

    def ensure_node(node_id: str, ref: str | None) -> None:
        def parse_ref(ref_value: str) -> tuple[str, int | None]:
            m = CALLGRAPH_REF_LINE_RE.match(ref_value)
            if m:
                try:
                    return m.group(1), int(m.group(2))
                except ValueError:
                    return m.group(1), None
            return ref_value, None

        # 同じidが複数回出てきたら同一ノードとして統合する。refは「最初に出現した
        # 非nullのref」を採用する — 終端(refなし)として先に出現しても、後続の出現に
        # refがあればそれで補う(終端ノードが先に出ると情報が失われる問題を防ぐ)。
        if node_id in nodes:
            if nodes[node_id]["ref"] is None and ref:
                file_, line_no = parse_ref(ref)
                nodes[node_id]["ref"] = ref
                nodes[node_id]["file"] = file_
                nodes[node_id]["line"] = line_no
            return
        file_ = None
        line_no = None
        if ref:
            file_, line_no = parse_ref(ref)
        nodes[node_id] = {"id": node_id, "ref": ref, "file": file_, "line": line_no}

    for raw_line in code_lines:
        if not raw_line.strip():
            continue
        try:
            parsed = parse_callgraph_line(raw_line)
        except ValueError as exc:
            errors.append(f"{raw_line.strip()} ({exc})")
            continue
        if parsed is None:
            continue
        left_id, left_ref = parsed["left"]
        right_id, right_ref = parsed["right"]
        ensure_node(left_id, left_ref)
        ensure_node(right_id, right_ref)
        edges.append({"from": left_id, "to": right_id, "label": parsed["label"]})

    return {"nodes": list(nodes.values()), "edges": edges}, errors


def render_callgraph_block(code_lines: list[str], graph_id: str) -> str:
    """callgraph ブロック1つ分のコンテナ要素+データJSONのHTMLを組み立てる。"""
    data, errors = build_callgraph_data(code_lines)
    out: list[str] = []
    for err in errors:
        # 1行の書式ミスでレポート全体の生成を止めない。コメントとして残し処理を続行する。
        out.append(f"<!-- callgraph parse error: {html.escape(err)} -->")
    json_payload = json.dumps(data, ensure_ascii=False)
    # <script type="application/json"> 内に安全に埋め込むため、HTMLパーサが </script として
    # 誤認する箇所を無害化する(JSON文字列中の "\/" は仕様上有効なエスケープ)。
    json_payload = json_payload.replace("</", "<\\/")
    out.append('<div class="callgraph-wrap">')
    out.append(
        '<div class="callgraph-toolbar">'
        f'<input type="text" class="callgraph-filter" placeholder="ノードを絞り込み..." '
        f'aria-label="ノード名で絞り込み" data-graph="{graph_id}">'
        f'<button type="button" class="callgraph-zoom-in" data-graph="{graph_id}" '
        f'aria-label="拡大">+</button>'
        f'<button type="button" class="callgraph-zoom-out" data-graph="{graph_id}" '
        f'aria-label="縮小">-</button>'
        f'<button type="button" class="callgraph-zoom-reset" data-graph="{graph_id}" '
        f'aria-label="表示をリセット">reset</button>'
        "</div>"
    )
    out.append(f'<div class="callgraph" id="{graph_id}" role="img" aria-label="呼び出しグラフ"></div>')
    out.append("</div>")
    out.append(f'<script type="application/json" id="{graph_id}-data">{json_payload}</script>')
    return "\n".join(out)


def markdown_to_html(md_text: str) -> tuple[str, str, bool]:
    """(本文HTML, TOC HTML, callgraphブロックを1つ以上含むか) を返す。"""
    lines = md_text.splitlines()
    body: list[str] = []
    toc: list[str] = []
    slugs: dict = {}
    i = 0
    list_builder: ListBuilder | None = None
    para_buf: list[str] = []
    graph_count = 0
    has_callgraph = False

    def flush_para() -> None:
        # 日本語の文章は行送りに半角スペースを要らないため、連結時に空白を挟まない。
        if para_buf:
            body.append(f"<p>{inline(''.join(para_buf))}</p>")
            para_buf.clear()

    def flush_list() -> None:
        nonlocal list_builder
        if list_builder is not None:
            list_builder.close_all()
            body.append(list_builder.render())
            list_builder = None

    n = len(lines)
    while i < n:
        line = lines[i]

        if line.strip().startswith("```"):
            flush_para()
            flush_list()
            fence = line.strip()[:3]
            lang = line.strip().lstrip("`").strip()
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith(fence):
                code_lines.append(lines[i])
                i += 1
            i += 1
            if lang == "callgraph":
                graph_count += 1
                has_callgraph = True
                body.append(render_callgraph_block(code_lines, f"graph-{graph_count}"))
            else:
                code_escaped = html.escape("\n".join(code_lines))
                lang_cls = f' class="language-{lang}"' if lang else ""
                body.append(f"<pre><code{lang_cls}>{code_escaped}</code></pre>")
            continue

        stripped = line.strip()
        if (
            stripped in ("<details>", "<details open>", "</details>")
            or DETAILS_SUMMARY_RE.match(stripped)
        ):
            # references/module-map-format.md 6節・7節の固定書式専用のパススルー。
            # この4パターン以外の生HTMLは一般に許可しない(セキュリティ上、許可タグを最小限に限定)。
            flush_para()
            flush_list()
            body.append(stripped)
            i += 1
            continue

        m = HEADER_RE.match(line)
        if m:
            flush_para()
            flush_list()
            level = len(m.group(1))
            text = m.group(2).strip()
            slug = slugify(text, slugs)
            body.append(f'<h{level} id="{slug}">{inline(text)}</h{level}>')
            if level in (2, 3):
                toc.append(f'<a class="toc-h{level}" href="#{slug}">{html.escape(text)}</a>')
            i += 1
            continue

        if TABLE_ROW_RE.match(line) and i + 1 < n and TABLE_SEP_RE.match(lines[i + 1]):
            flush_para()
            flush_list()
            table_rows = [line, lines[i + 1]]
            i += 2
            while i < n and TABLE_ROW_RE.match(lines[i]):
                table_rows.append(lines[i])
                i += 1
            body.append(render_table(table_rows))
            continue

        if HR_RE.match(line) and not line.strip().startswith("-  "):
            flush_para()
            flush_list()
            body.append("<hr>")
            i += 1
            continue

        cm = CHECKBOX_RE.match(line)
        um = UL_RE.match(line) if not cm else None
        om = OL_RE.match(line) if not cm and not um else None
        if cm or um or om:
            flush_para()
            if list_builder is None:
                list_builder = ListBuilder()
            if cm:
                indent = len(cm.group(1))
                checked = cm.group(2).lower() == "x"
                mark = "&#9745;" if checked else "&#9744;"
                list_builder.add_item(indent, "ul-checklist", f"{mark} {inline(cm.group(3))}")
            elif um:
                indent = len(um.group(1))
                list_builder.add_item(indent, "ul", inline(um.group(2)))
            else:
                indent = len(om.group(1))
                list_builder.add_item(indent, "ol", inline(om.group(2)))
            i += 1
            continue

        if line.strip().startswith(">"):
            flush_para()
            flush_list()
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            body.append(f"<blockquote>{inline(' '.join(quote_lines))}</blockquote>")
            continue

        if not line.strip():
            flush_para()
            flush_list()
            i += 1
            continue

        flush_list()
        para_buf.append(line.strip())
        i += 1

    flush_para()
    flush_list()
    return "\n".join(body), "\n".join(toc), has_callgraph


def build_report(input_path: Path, output_path: Path, title: str, target: str) -> None:
    md_text = input_path.read_text(encoding="utf-8")
    body_html, toc_html, has_callgraph = markdown_to_html(md_text)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z")
    if has_callgraph:
        callgraph_js = CALLGRAPH_JS_PATH.read_text(encoding="utf-8")
        callgraph_assets = f"<script>\n{callgraph_js}\n</script>"
    else:
        callgraph_assets = ""
    html_out = (
        template.replace("__TITLE__", html.escape(title))
        .replace("__TARGET__", html.escape(target))
        .replace("__GENERATED_AT__", generated_at)
        .replace("__TOC_HTML__", toc_html or "<em>(見出しなし)</em>")
        .replace("__BODY_HTML__", body_html)
        .replace("__CALLGRAPH_ASSETS__", callgraph_assets)
    )
    output_path.write_text(html_out, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Markdown中間生成物のパス")
    parser.add_argument("--output", required=True, type=Path, help="出力HTMLファイルのパス")
    parser.add_argument("--title", required=True, help="レポートタイトル")
    parser.add_argument("--target", required=True, help="対象範囲の説明（例: src/shaper_db/transform/）")
    args = parser.parse_args()
    build_report(args.input, args.output, args.title, args.target)
    print(f"HTMLレポートを生成しました: {args.output}")


if __name__ == "__main__":
    main()
