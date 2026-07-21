#!/usr/bin/env python3
"""Markdown中間生成物を report_template.html に差し込んでHTMLレポートを組み立てる。

標準ライブラリのみに依存する（外部の markdown パッケージを前提にしない）。
対応するMarkdown記法: 見出し(#-######、末尾に`{#id}`で明示的アンカーIDを指定可)、
GFMテーブル、番号なし/番号付きリスト、チェックリスト(- [ ]/- [x])、フェンス付き
コードブロック(`callgraph`は関数見出しへの自動スクロール/`.html`ノードへのページ
遷移に対応、`line-notes`はコード+解説+例の3列レンダリング、`glossary`は用語+要約+
詳細説明の用語集エントリを定義する)、引用(>)、水平線(---)、インライン code/bold/
italic/link。本文中の`[[term]]`(表示テキストを変えるなら`[[term|表示テキスト]]`)は
`glossary`フェンスで定義した用語への軽量リンクとして解決される(同一ページ内の定義を
優先し、`--glossary-in`で読み込んだ他ページの定義があればそちらへリンクする)。想定外の
記法は素の段落として出力する。

使い方:
    python3 build_report.py --input report.md --output report.html \
        --title "shaper-db transform/ レビュー地図" --target "src/shaper_db/transform/"
"""
from __future__ import annotations

import argparse
import html
import io
import json
import keyword
import re
import tokenize
from datetime import datetime, timezone
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "report_template.html"
CALLGRAPH_JS_PATH = Path(__file__).resolve().parent.parent / "assets" / "callgraph.js"

# シンタックスハイライト用トークン分類(assets/report_template.html の --tok-* CSS変数と
# 1対1対応させる。この6種類以外は無色のまま=html.escapeされた素のテキストになる)。
PY_KEYWORDS = frozenset(keyword.kwlist) | frozenset(keyword.softkwlist)
# tokenizeモジュールは Python 3.12 以降 f-string を FSTRING_START/MIDDLE/END に分割する。
# 無い環境(3.11以前)では f-string 全体が1つの STRING トークンになるため、両対応にする。
_FSTRING_TOKEN_TYPES = tuple(
    t
    for t in (
        getattr(tokenize, "FSTRING_START", None),
        getattr(tokenize, "FSTRING_MIDDLE", None),
        getattr(tokenize, "FSTRING_END", None),
    )
    if t is not None
)
_STRING_TOKEN_TYPES = (tokenize.STRING,) + _FSTRING_TOKEN_TYPES
_SKIP_LOOKAHEAD_TYPES = (tokenize.NL, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT)

# tokenize が構文的に不完全な断片(複数行呼び出しの継続行・開き括弧のみの行等)で失敗した
# ときのフォールバック用の簡易トークナイザ。優先順位はコメント→文字列(未閉じも許容)→
# デコレータ→数値→識別子。
FALLBACK_TOKEN_RE = re.compile(
    r"""
    (?P<comment>\#.*) |
    (?P<string>[rRbBfFuU]{0,2}(?:'''.*?'''|\"\"\".*?\"\"\"
        |'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"
        |'(?:\\.|[^'\\])*|"(?:\\.|[^"\\])*)) |
    (?P<decorator>@[A-Za-z_][\w.]*) |
    (?P<number>\b\d[\d_]*\.?[\d_]*(?:[eE][+-]?\d+)?[jJ]?\b) |
    (?P<name>\b[A-Za-z_]\w*\b)
    """,
    re.VERBOSE,
)

INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
# 用語集参照(wikiリンク風)。`[[term]]` または表示テキストを変える `[[term|表示テキスト]]`。
TERM_REF_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# 見出し末尾の明示的アンカーID指定(references/flow-map-format.md「見出しへの明示的
# アンカー」節を正典とする)。例: "### `foo()` — file:line {#fn-foo}"。表示テキストからは
# `{#...}` を取り除き、id属性にはこちらを使う(自動slugifyより優先)。
HEADER_ID_OVERRIDE_RE = re.compile(r"^(.*?)\s*\{#([\w-]+)\}\s*$")
CHECKBOX_RE = re.compile(r"^(\s*)-\s\[([ xX])\]\s+(.*)$")
UL_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
OL_RE = re.compile(r"^(\s*)\d+\.\s+(.*)$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
HR_RE = re.compile(r"^\s*-{3,}\s*$")

# references/flow-map-format.md 4節・8節の固定書式
# (<details>/<details open>/<summary>.../</summary>/</details>)専用。
# この4パターン以外の生HTMLは一般にパススルーしない(許可タグを最小限に限定するため)。
DETAILS_SUMMARY_RE = re.compile(r"^<summary>.*</summary>$")

# callgraph フェンスブロックの文法(references/flow-map-format.md 6節を正典とする)。
# `<左ノード> -> <右ノード>[: <エッジラベル>]`。ノードは `id[ref]`(通常ノード)か
# `id`(終端ノード、file:line を持たない)のいずれか。ノード id は `[` `]` `->` を含まない。
CALLGRAPH_NODE_BRACKET_RE = re.compile(r"^(.*?)\[([^\[\]]*)\]\s*(?::\s*(.*))?$")
CALLGRAPH_REF_LINE_RE = re.compile(r"^(.*):(\d+)$")
# ref が `file:line` ではなく別ページ(+アンカー)への直接リンクであることを示す形式。
# 例: "sync_rules.html", "config.html#fn-load_config"。マッチした場合はクリックで
# そのページへ遷移するナビゲーションリンクとして扱う(references/flow-map-format.md
# 「1. インデックスページ」を正典とする)。
CALLGRAPH_HTML_REF_RE = re.compile(r"^\S+\.html(#[\w-]+)?$")

# line-notes フェンスブロックの行区切り(references/flow-map-format.md 7節を正典とする)。
# `<コード1行> ::: <解説>[ ::: <例>]`。コード側の先頭の空白(インデント)は保持し、
# 解説・例側だけ inline() でMarkdown処理する。区切りが無い行は解説・例なし(コードだけ)
# として扱う。
LINE_NOTES_SEP = " ::: "


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


def _line_start_offsets(code: str) -> list[int]:
    """1始まりのtokenize行番号→`code`内の絶対文字オフセットの対応表を作る。

    `starts[row]` が行`row`(1始まり)の先頭オフセット。末尾に余分な1件を足しておき、
    ENDMARKER等が実際の行数を超える行番号を指しても安全にフォールバックできるようにする。
    """
    starts = [0]
    pos = 0
    for line in code.splitlines(keepends=True):
        starts.append(pos)
        pos += len(line)
    starts.append(pos)
    return starts


def _tokenize_spans(code: str) -> list[tuple[int, int, str]] | None:
    """`code`(1行〜複数行のPython断片)を`tokenize`で解析し、`(開始offset, 終了offset,
    css種別)`のリストを返す。構文的に不完全(継続行の断片・未閉じの括弧等)でtokenizeが
    失敗した場合はNoneを返し、呼び出し側に`_fallback_spans`へ切り替えさせる。

    tokenizeの失敗モードは環境(Pythonバージョン)によって送出される例外が微妙に異なる
    (TokenizeError/IndentationError等)ため、ここでは意図的に例外種別を絞らず全て捕捉する
    — このハイライトはベストエフォートの付加価値機能であり、失敗時は常に安全な
    フォールバック(素のエスケープ表示)に落とせるので、想定外の例外で処理全体を止める
    必要が無い。
    """
    starts = _line_start_offsets(code)

    def offset(row: int, col: int) -> int:
        row = max(1, min(row, len(starts) - 1))
        return min(starts[row] + col, len(code))

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except Exception:
        return None

    spans: list[tuple[int, int, str]] = []
    at_line_start = True
    n = len(tokens)
    idx = 0
    try:
        while idx < n:
            tok = tokens[idx]
            ttype, tstr, start, end = tok.type, tok.string, tok.start, tok.end
            if ttype in (tokenize.NEWLINE, tokenize.NL):
                at_line_start = True
                idx += 1
                continue
            if ttype in (tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER):
                idx += 1
                continue
            if ttype == tokenize.COMMENT:
                spans.append((offset(*start), offset(*end), "comment"))
                at_line_start = False
                idx += 1
                continue
            if ttype == tokenize.OP and tstr == "@" and at_line_start:
                # デコレータ: 行頭の "@" から続く dotted name 連鎖(a.b.c 等)までを1span にする。
                # 直後の呼び出し括弧 "(...)" 自体は装飾しない(引数は通常のトークンとして扱う)。
                deco_end = end
                j = idx + 1
                while j < n and (
                    tokens[j].type == tokenize.NAME
                    or (tokens[j].type == tokenize.OP and tokens[j].string == ".")
                ):
                    deco_end = tokens[j].end
                    j += 1
                spans.append((offset(*start), offset(*deco_end), "deco"))
                idx = j
                at_line_start = False
                continue
            at_line_start = False
            if ttype in _STRING_TOKEN_TYPES:
                spans.append((offset(*start), offset(*end), "str"))
            elif ttype == tokenize.NUMBER:
                spans.append((offset(*start), offset(*end), "num"))
            elif ttype == tokenize.NAME:
                if tstr in PY_KEYWORDS:
                    spans.append((offset(*start), offset(*end), "kw"))
                else:
                    k = idx + 1
                    while k < n and tokens[k].type in _SKIP_LOOKAHEAD_TYPES:
                        k += 1
                    if k < n and tokens[k].type == tokenize.OP and tokens[k].string == "(":
                        spans.append((offset(*start), offset(*end), "fn"))
            idx += 1
    except Exception:
        return None

    spans.sort(key=lambda s: s[0])
    return spans


def _fallback_spans(code: str) -> list[tuple[int, int, str]]:
    """`tokenize`が使えない行(継続行の断片等)向けの正規表現ベースの簡易トークナイズ。"""
    spans: list[tuple[int, int, str]] = []
    for m in FALLBACK_TOKEN_RE.finditer(code):
        kind = m.lastgroup
        start, end = m.start(), m.end()
        if kind == "comment":
            spans.append((start, end, "comment"))
        elif kind == "string":
            spans.append((start, end, "str"))
        elif kind == "decorator":
            spans.append((start, end, "deco"))
        elif kind == "number":
            spans.append((start, end, "num"))
        elif kind == "name":
            word = m.group()
            if word in PY_KEYWORDS:
                spans.append((start, end, "kw"))
            else:
                j = end
                while j < len(code) and code[j] in " \t":
                    j += 1
                if j < len(code) and code[j] == "(":
                    spans.append((start, end, "fn"))
    return spans


def _render_spans(code: str, spans: list[tuple[int, int, str]]) -> str:
    """spansで示された区間だけ`<span class="tok-{cls}">`で囲み、それ以外はhtml.escapeする
    共通レンダラ。spansは開始位置でソート済みを前提とする。"""
    out: list[str] = []
    pos = 0
    for start, end, cls in spans:
        if start < pos:
            continue
        if start > pos:
            out.append(html.escape(code[pos:start]))
        out.append(f'<span class="tok-{cls}">{html.escape(code[start:end])}</span>')
        pos = end
    if pos < len(code):
        out.append(html.escape(code[pos:]))
    return "".join(out)


def render_highlighted_code(code: str) -> str:
    """1行のPythonコード文字列(line-notesのコード列)をハイライト済みHTMLにする
    (html.escape済み、そのまま`<pre><code>`に差し込んでよい)。"""
    spans = _tokenize_spans(code)
    if spans is None:
        spans = _fallback_spans(code)
    return _render_spans(code, spans)


def highlight_python_block(code: str) -> str:
    """複数行の ```python``` フェンス全体をハイライトする(html.escape済み)。

    まずブロック全体をtokenizeし、成功すればそのまま使う(この方が複数行にまたがる
    文字列等も正しく扱える)。失敗したら1行ずつ`render_highlighted_code`にフォール
    バックして結合する。
    """
    spans = _tokenize_spans(code)
    if spans is not None:
        return _render_spans(code, spans)
    return "\n".join(render_highlighted_code(line) for line in code.split("\n"))


def inline(text: str, glossary: dict | None = None) -> str:
    text = html.escape(text, quote=False)
    text = INLINE_CODE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", text)
    text = BOLD_RE.sub(lambda m: f"<strong>{m.group(1)}</strong>", text)
    text = ITALIC_RE.sub(lambda m: f"<em>{m.group(1)}</em>", text)

    def _term_ref(m: re.Match) -> str:
        term = m.group(1).strip()
        alias = (m.group(2) or term).strip()
        entry = glossary.get(term) if glossary else None
        if entry is None:
            return f"{alias}<!-- glossary term not found: {html.escape(term, quote=False)} -->"
        title_attr = html.escape(entry["summary"], quote=True)
        return f'<a class="term-ref" href="{entry["href"]}" title="{title_attr}">{alias}</a>'

    text = TERM_REF_RE.sub(_term_ref, text)
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


def split_table_row(row: str) -> list[str]:
    """テーブル行をセル区切りの`|`で分割する。`\\|`はセル内の文字`|`として扱い区切らない
    (GFM準拠)。分割後、各セルの`\\|`は`|`に戻す。"""
    stripped = row.strip().strip("|")
    raw_cells = re.split(r"(?<!\\)\|", stripped)
    return [c.strip().replace("\\|", "|") for c in raw_cells]


def render_table(rows: list[str], glossary: dict | None = None) -> str:
    header_cells = split_table_row(rows[0])
    body_rows = rows[2:]
    out = ["<table>", "<thead><tr>"]
    out += [f"<th>{inline(c, glossary)}</th>" for c in header_cells]
    out.append("</tr></thead><tbody>")
    for row in body_rows:
        cells = split_table_row(row)
        out.append("<tr>" + "".join(f"<td>{inline(c, glossary)}</td>" for c in cells) + "</tr>")
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
        def parse_ref(ref_value: str) -> tuple[str | None, int | None, str | None]:
            """ref文字列を (file, line, href) に分解する。

            `.html`/`.html#anchor` 形式ならクリック時の遷移先(href)として扱い、
            file/lineはNoneのままにする。それ以外は従来通り`file:line`形式の
            ツールチップ用参照として解釈する。
            """
            if CALLGRAPH_HTML_REF_RE.match(ref_value):
                return None, None, ref_value
            m = CALLGRAPH_REF_LINE_RE.match(ref_value)
            if m:
                try:
                    return m.group(1), int(m.group(2)), None
                except ValueError:
                    return m.group(1), None, None
            return ref_value, None, None

        # 同じidが複数回出てきたら同一ノードとして統合する。refは「最初に出現した
        # 非nullのref」を採用する — 終端(refなし)として先に出現しても、後続の出現に
        # refがあればそれで補う(終端ノードが先に出ると情報が失われる問題を防ぐ)。
        if node_id in nodes:
            if nodes[node_id]["ref"] is None and ref:
                file_, line_no, href = parse_ref(ref)
                nodes[node_id]["ref"] = ref
                nodes[node_id]["file"] = file_
                nodes[node_id]["line"] = line_no
                nodes[node_id]["href"] = href
            return
        file_ = None
        line_no = None
        href = None
        if ref:
            file_, line_no, href = parse_ref(ref)
        nodes[node_id] = {
            "id": node_id,
            "ref": ref,
            "file": file_,
            "line": line_no,
            "href": href,
        }

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


def render_line_notes_block(code_lines: list[str], glossary: dict | None = None) -> str:
    """line-notes ブロック1つ分(コード1行+解説+例を並べた行の集まり)のHTMLを組み立てる。

    1行は `<コード> ::: <解説>[ ::: <例>]` の形式。区切りが無い/1個だけの行は
    解説・例のうち無い側を空欄として扱う(比例原則で省いた行、または区切り文字が
    コード側にしか無い稀なケースへのフォールバック)。
    """
    out = ['<div class="line-notes">']
    out.append(
        '<div class="line-notes-row line-notes-header">'
        '<div class="line-notes-header-cell">コード</div>'
        '<div class="line-notes-header-cell">解説</div>'
        '<div class="line-notes-header-cell">例</div>'
        "</div>"
    )
    for raw_line in code_lines:
        parts = raw_line.split(LINE_NOTES_SEP, 2)
        code_part = parts[0]
        note_part = parts[1] if len(parts) > 1 else ""
        example_part = parts[2] if len(parts) > 2 else ""
        code_html = render_highlighted_code(code_part) if code_part else "&nbsp;"
        note_html = inline(note_part.strip(), glossary) if note_part.strip() else "&nbsp;"
        example_html = (
            inline(example_part.strip(), glossary) if example_part.strip() else "&nbsp;"
        )
        out.append(
            '<div class="line-notes-row">'
            f'<pre class="line-notes-code"><code>{code_html}</code></pre>'
            f'<div class="line-notes-note">{note_html}</div>'
            f'<div class="line-notes-example">{example_html}</div>'
            "</div>"
        )
    out.append("</div>")
    return "\n".join(out)


def parse_glossary_block(code_lines: list[str]) -> dict[str, dict]:
    """glossary ブロック1つ分の各行をパースし、`{用語: {summary, detail, anchor}}` を返す。

    1行は `<用語> ::: <要約>[ ::: <詳しい説明>]` の形式。要約(2列目)は必須、詳しい説明
    (3列目)は任意。区切りが無い/1列しかない行は書式ミスとして黙ってスキップする
    (line-notes/callgraphと同様、1行の不備でブロック全体の生成を止めない)。

    Args:
        code_lines: フェンス内の各行(先頭・末尾のフェンス行を除く)。

    Returns:
        用語をキーとするエントリ辞書(挿入順=出現順)。
    """
    glossary_slugs: dict = {}
    entries: dict[str, dict] = {}
    for raw_line in code_lines:
        if not raw_line.strip():
            continue
        parts = raw_line.split(LINE_NOTES_SEP, 2)
        if len(parts) < 2:
            continue
        term = parts[0].strip()
        summary = parts[1].strip()
        detail = parts[2].strip() if len(parts) > 2 else ""
        if not term:
            continue
        entries[term] = {
            "summary": summary,
            "detail": detail,
            "anchor": f"term-{slugify(term, glossary_slugs)}",
        }
    return entries


def extract_glossary(md_text: str) -> dict[str, dict]:
    """`md_text`中の全`glossary`フェンスブロックを見つけ、マージした用語辞書を返す。

    同じ用語が複数回定義された場合は後勝ち(エラーにしない)。

    Args:
        md_text: パース対象のMarkdown全文。

    Returns:
        用語をキーとするエントリ辞書(`parse_glossary_block`の戻り値と同形)。
    """
    lines = md_text.splitlines()
    n = len(lines)
    glossary: dict[str, dict] = {}
    i = 0
    while i < n:
        line = lines[i]
        if line.strip().startswith("```"):
            fence = line.strip()[:3]
            lang = line.strip().lstrip("`").strip()
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith(fence):
                code_lines.append(lines[i])
                i += 1
            i += 1
            if lang == "glossary":
                glossary.update(parse_glossary_block(code_lines))
            continue
        i += 1
    return glossary


def render_glossary_block(entries: dict[str, dict]) -> str:
    """glossary ブロック1つ分(用語+要約+詳細を並べた一覧)のHTMLを組み立てる。

    Args:
        entries: `parse_glossary_block`の戻り値と同形の用語エントリ辞書。

    Returns:
        用語の登場順(辞書の挿入順)に並べた`<div class="glossary-list">`のHTML文字列。
    """
    out = ['<div class="glossary-list">']
    for term, entry in entries.items():
        out.append(f'<div class="glossary-entry" id="{entry["anchor"]}">')
        out.append(f'<p class="glossary-term">{inline(term)}</p>')
        out.append(f'<p class="glossary-summary">{inline(entry["summary"])}</p>')
        if entry["detail"]:
            out.append(f'<p class="glossary-detail">{inline(entry["detail"])}</p>')
        out.append("</div>")
    out.append("</div>")
    return "\n".join(out)


def markdown_to_html(md_text: str, incoming_glossary: dict | None = None) -> tuple[str, str, bool, dict]:
    """(本文HTML, TOC HTML, callgraphブロックを1つ以上含むか, このページのglossary辞書) を返す。"""
    local_glossary = extract_glossary(md_text)
    resolved: dict[str, dict] = {}
    for term, entry in local_glossary.items():
        resolved[term] = {**entry, "href": f"#{entry['anchor']}"}
    if incoming_glossary:
        for term, entry in incoming_glossary.get("terms", {}).items():
            if term not in resolved:
                resolved[term] = {**entry, "href": f"{incoming_glossary['page']}#{entry['anchor']}"}

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
            body.append(f"<p>{inline(''.join(para_buf), resolved)}</p>")
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
            elif lang == "line-notes":
                body.append(render_line_notes_block(code_lines, resolved))
            elif lang == "glossary":
                body.append(render_glossary_block(parse_glossary_block(code_lines)))
            else:
                block_text = "\n".join(code_lines)
                if lang in ("python", "py"):
                    code_escaped = highlight_python_block(block_text)
                else:
                    code_escaped = html.escape(block_text)
                lang_cls = f' class="language-{lang}"' if lang else ""
                body.append(f"<pre><code{lang_cls}>{code_escaped}</code></pre>")
            continue

        stripped = line.strip()
        if (
            stripped in ("<details>", "<details open>", "</details>")
            or DETAILS_SUMMARY_RE.match(stripped)
        ):
            # references/flow-map-format.md 4節・8節の固定書式専用のパススルー。
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
            id_override = HEADER_ID_OVERRIDE_RE.match(text)
            if id_override:
                text = id_override.group(1).strip()
                slug = id_override.group(2)
            else:
                slug = slugify(text, slugs)
            body.append(f'<h{level} id="{slug}">{inline(text, resolved)}</h{level}>')
            if level in (2, 3):
                # 左レール(路線図)の「駅」1つ分。rail-marker が路線上の点、rail-label が
                # 見出しテキスト(scroll-spy JSがこのテキストをヘッダーの現在地ラベルに
                # そのまま反映するため、リンク内で独立したspanにしておく)。
                toc.append(
                    f'<li class="rail-station rail-h{level}">'
                    f'<a href="#{slug}">'
                    '<span class="rail-marker" aria-hidden="true"></span>'
                    f'<span class="rail-label">{html.escape(text)}</span>'
                    "</a></li>"
                )
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
            body.append(render_table(table_rows, resolved))
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
                list_builder.add_item(
                    indent, "ul-checklist", f"{mark} {inline(cm.group(3), resolved)}"
                )
            elif um:
                indent = len(um.group(1))
                list_builder.add_item(indent, "ul", inline(um.group(2), resolved))
            else:
                indent = len(om.group(1))
                list_builder.add_item(indent, "ol", inline(om.group(2), resolved))
            i += 1
            continue

        if line.strip().startswith(">"):
            flush_para()
            flush_list()
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            body.append(f"<blockquote>{inline(' '.join(quote_lines), resolved)}</blockquote>")
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
    return "\n".join(body), "\n".join(toc), has_callgraph, local_glossary


def build_report(
    input_path: Path,
    output_path: Path,
    title: str,
    target: str,
    glossary_in: Path | None = None,
    glossary_out: Path | None = None,
) -> None:
    md_text = input_path.read_text(encoding="utf-8")
    incoming = None
    if glossary_in is not None:
        try:
            incoming = json.loads(glossary_in.read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(f"警告: 用語集JSONが見つかりません: {glossary_in}")
            incoming = None
    body_html, toc_html, has_callgraph, local_glossary = markdown_to_html(md_text, incoming)
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
        .replace("__TOC_HTML__", toc_html or '<li class="rail-empty"><em>(見出しなし)</em></li>')
        .replace("__BODY_HTML__", body_html)
        .replace("__CALLGRAPH_ASSETS__", callgraph_assets)
    )
    output_path.write_text(html_out, encoding="utf-8")
    if glossary_out is not None and local_glossary:
        glossary_out.write_text(
            json.dumps(
                {"page": output_path.name, "terms": local_glossary}, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Markdown中間生成物のパス")
    parser.add_argument("--output", required=True, type=Path, help="出力HTMLファイルのパス")
    parser.add_argument("--title", required=True, help="レポートタイトル")
    parser.add_argument("--target", required=True, help="対象範囲の説明（例: src/shaper_db/transform/）")
    parser.add_argument(
        "--glossary-in",
        type=Path,
        default=None,
        help="他ページの用語集JSON(--glossary-outで書き出したもの)を読み込み、"
        "[[term]]をそのページへのリンクとして解決する",
    )
    parser.add_argument(
        "--glossary-out",
        type=Path,
        default=None,
        help="このファイル中のglossaryフェンスをJSONとして書き出す(index.mdをビルドする際に指定する)",
    )
    args = parser.parse_args()
    build_report(
        args.input, args.output, args.title, args.target, args.glossary_in, args.glossary_out
    )
    print(f"HTMLレポートを生成しました: {args.output}")


if __name__ == "__main__":
    main()
