---
name: pptx-creator
description: MDファイル・Excel・テキストなどのインプットからPowerPoint（.pptx）を生成するスキル。「資料を作って」「スライドを作成して」「PPTXにして」「プレゼン資料を作って」などのキーワードが含まれる場合に必ず使用すること。ユーザーがMarkdown・Excel・テキストを渡してPPTX出力を求めている場合、テンプレートの有無にかかわらず積極的に使用する。JupyterHub環境でのHTMLプレビュー確認→PPTX生成という2ステップワークフローに対応。
---

# PPTX作成スキル

インプットファイル（MD/Excel/テキスト等）を読み込み、JupyterHubブラウザでHTMLプレビューを確認してからPPTXを生成する。

---

## ワークフロー概要

```
Step 1: インプット収集
Step 2: スライド構成をユーザーと相談・合意
Step 3: HTMLプレビュー生成 → JupyterHubで確認
Step 4: ユーザーOK → PPTX生成（Cアプローチ）
```

---

## Step 1: インプット収集

以下を確認する。

| 確認項目 | 内容 |
|---|---|
| インプットファイル | MD / Excel / テキスト / CSV 等のパスを取得して読み込む |
| PPTXテンプレート | `templates/` 配下の `.pptx` ファイルを探す。なければ「なし」 |
| 出力先 | デフォルトは `output/<ファイル名>.pptx` |
| 仮想環境 | プロジェクトルートの `.venv/` を使用。`python-pptx` / `openpyxl` が入っているか確認 |

テンプレートがある場合は、スライドレイアウト一覧を自動取得してユーザーに提示する：

```python
from pptx import Presentation
prs = Presentation("templates/template.pptx")
for i, layout in enumerate(prs.slide_layouts):
    print(f"  [{i}] {layout.name}")
```

---

## Step 2: スライド構成の相談

インプットを読み込んだ後、以下の形式でユーザーに確認する。作業を進める前に**必ず合意を得る**。

```
スライド構成案：
1. タイトルスライド         → レイアウト: "Title Slide"（またはテンプレート[0]）
2. 目次                     → レイアウト: "Title and Content"
3. ○○の概要                → レイアウト: "Title and Content"
4. ○○の比較               → レイアウト: "Two Content"（2カラム）
5. まとめ                   → レイアウト: "Title Only"

テンプレート: templates/xxx.pptx を使用
全 5 スライド。よろしければ「OK」とお知らせください。
修正があればスライド番号と内容を教えてください。
```

ユーザーから修正が来た場合は構成を更新して再提示する。

---

## Step 3: HTMLプレビュー生成

合意が取れたら、スライド1枚ごとを16:9比率で表示するHTMLを生成して `output/<name>_preview.html` に保存する。

### HTMLの基本構造

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>スライドプレビュー</title>
<style>
  body { font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif; background: #e8eaf0; margin: 0; padding: 24px; }
  .slide-wrapper { margin-bottom: 32px; }
  .slide-label { font-size: 13px; color: #555; margin-bottom: 8px; font-weight: 600; }
  .slide {
    width: 960px; height: 540px;  /* 16:9 固定 */
    background: white;
    box-shadow: 0 4px 16px rgba(0,0,0,0.15);
    position: relative;
    overflow: hidden;
  }
</style>
</head>
<body>
  <div class="slide-wrapper">
    <div class="slide-label">スライド 1 / 5 — タイトルスライド</div>
    <div class="slide" id="slide-1">
      <!-- スライド内容 -->
    </div>
  </div>
</body>
</html>
```

### デザイン哲学：落ち着いた・プロフェッショナルなスタイルを優先する

派手さより読みやすさ。ユーザーは過剰な強調や大きすぎる数値表示より、清潔で整理されたデザインを好む。

- **主色**: `#1565C0`（ブルー）を使うが、全面塗りより「ヘッダーバー」「左ボーダー」程度の使い方にとどめる
- **背景**: ほぼ白か薄いグレー（`#F0F4F8`）。強い色の大きな背景ブロックは避ける
- **テキスト強調**: 太字・下線で十分。アクセントカラーの大見出し数字は必要な場合のみ
- **カード**: `border-left: 4px solid #1565C0` のような左ボーダーカードが読みやすい
- **表**: 青ヘッダー＋交互行の薄い色が標準

**良い例（落ち着き）:**
```css
.card { background: #EEF2FF; border-left: 4px solid #1565C0; padding: 12px 16px; }
.header-bar { background: #1565C0; height: 70px; }
.kpi-value { font-size: 30px; font-weight: 700; color: #1565C0; }
```

**避けるべき例（派手すぎ）:**
```css
/* 全面青背景のKPIカードが3枚並んで数字が黄色で40px以上 → やりすぎ */
.kpi { background: #1565C0; }
.kpi-num { font-size: 40px; color: #FFD54F; }
```

### フロー図はSVGで描く（divではなく）

フロー図・接続図をHTMLで表現するとき、`div` + CSSフレックスボックスは矢印が貧弱になりレイアウトが崩れやすい。`<svg>` で正確に描く。

**矢印マーカー付きSVGフロー図の例（縦型）：**

```html
<svg width="370" height="390" xmlns="http://www.w3.org/2000/svg"
     style="font-family:'Hiragino Sans','Yu Gothic',sans-serif;">
  <defs>
    <marker id="arr" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0,10 3.5,0 7" fill="#1565c0"/>
    </marker>
  </defs>
  <!-- ノード1 -->
  <rect x="34" y="0" width="300" height="64" rx="8" fill="#dbeafe" stroke="#3b82f6" stroke-width="2"/>
  <text x="184" y="28" text-anchor="middle" font-size="15" font-weight="bold" fill="#1e40af">エンドユーザー</text>
  <text x="184" y="50" text-anchor="middle" font-size="12" fill="#3b82f6">（家庭・法人）</text>
  <!-- 矢印（tailEndマーカー付き） -->
  <line x1="184" y1="64" x2="184" y2="94" stroke="#1565c0" stroke-width="2.5" marker-end="url(#arr)"/>
  <!-- ラベルバッジ -->
  <rect x="196" y="69" width="116" height="19" rx="4" fill="#fef3c7" stroke="#f59e0b" stroke-width="1"/>
  <text x="254" y="83" text-anchor="middle" font-size="9" font-weight="bold" fill="#92400e">月額料金を支払う</text>
  <!-- ノード2 以降同様 -->
</svg>
```

**横型フロー（4ノード）の例：**

```html
<svg width="912" height="108" xmlns="http://www.w3.org/2000/svg"
     style="font-family:'Hiragino Sans','Yu Gothic',sans-serif;">
  <defs>
    <marker id="arrh" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0,10 3.5,0 7" fill="#1565c0"/>
    </marker>
  </defs>
  <rect x="0" y="14" width="188" height="88" rx="8" fill="#dbeafe" stroke="#3b82f6" stroke-width="2"/>
  <text x="94" y="52" text-anchor="middle" font-size="13" font-weight="bold" fill="#1e40af">① ONU / HGW</text>
  <text x="94" y="72" text-anchor="middle" font-size="11" fill="#3b82f6">宅内光終端装置</text>
  <line x1="188" y1="58" x2="224" y2="58" stroke="#1565c0" stroke-width="2.5" marker-end="url(#arrh)"/>
  <text x="206" y="46" text-anchor="middle" font-size="10" fill="#718096">光信号</text>
  <!-- 残りのノードも同様 -->
</svg>
```

HTMLプレビューを生成したら、パスをユーザーに伝える：

```
HTMLプレビューを生成しました: output/xxx_preview.html
JupyterHubのファイルブラウザから開いて確認してください。
修正があれば教えてください。問題なければ「OK」とお知らせください。
```

---

## Step 4: PPTX生成（ハイブリッドCアプローチ）

ユーザーから「OK」が来たらPPTXを生成する。

### ⚠️ 最重要: EMUフロートバグを防ぐ

**Pythonの `/` 演算子は整数同士でも `float` を返す。**  
`Inches(5.6) / 2 → 3200400.0`（float）となり、OOXMLに書き込まれると PowerPoint がファイルを破損と判定して開けなくなる。

**必ずスクリプト冒頭に以下を定義し、全ての計算座標に使うこと：**

```python
def E(v) -> int:
    """EMU値を整数に変換する。/演算はfloatを返すため破損の原因になる。"""
    return int(round(v))
```

**使用箇所:**
```python
# NG: float になる
cx = CARD_X + CARD_W / 2          # → float!
fill_w = TRK_W * ratio             # → float!
cw = (SLIDE_W - MRG * 2) / 3      # → float!
th = height * 0.48                 # → float!

# OK: 常にE()でラップ
cx = E(CARD_X + CARD_W / 2)
fill_w = E(TRK_W * ratio)
cw = E((SLIDE_W - MRG * 2) / 3)
th = E(height * 0.48)
```

また、`add_rect` / `add_textbox` / `add_table` の内部でも全引数を `E()` でラップすると安全：

```python
def add_rect(slide, left, top, width, height, fill=None, line=None, line_pt=1.0):
    sh = slide.shapes.add_shape(1, E(left), E(top), E(width), E(height))
    ...
```

### テンプレートあり（推奨パターン）

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

prs = Presentation("templates/template.pptx")

def get_layout(prs, name: str):
    for layout in prs.slide_layouts:
        if layout.name == name:
            return layout
    return prs.slide_layouts[6]  # fallback: blank

layout = get_layout(prs, "Title Slide")
slide = prs.slides.add_slide(layout)

for ph in slide.placeholders:
    if ph.placeholder_format.idx == 0:
        ph.text = "タイトルテキスト"
    elif ph.placeholder_format.idx == 1:
        ph.text = "サブタイトル"
```

### テンプレートなし（フルカスタムパターン）

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)

def E(v) -> int:
    return int(round(v))

def new_prs():
    prs = Presentation()
    prs.slide_width  = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs

def blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])

def add_rect(slide, left, top, width, height, fill=None, line=None, line_pt=1.0):
    sh = slide.shapes.add_shape(1, E(left), E(top), E(width), E(height))
    sh.line.fill.background()
    if fill:
        sh.fill.solid(); sh.fill.fore_color.rgb = fill
    else:
        sh.fill.background()
    if line:
        sh.line.color.rgb = line; sh.line.width = Pt(line_pt)
    else:
        sh.line.fill.background()
    return sh

def add_textbox(slide, left, top, width, height, text,
                size=Pt(11), bold=False, color=None,
                align=PP_ALIGN.LEFT, wrap=True):
    if color is None: color = RGBColor(0x1A, 0x20, 0x2C)
    tb = slide.shapes.add_textbox(E(left), E(top), E(width), E(height))
    tf = tb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = size; r.font.bold = bold; r.font.color.rgb = color
    return tb
```

### フロー図の矢印コネクタ（OOXML XML注入）

python-pptx の `add_connector` に矢印ヘッドを付けるには XML を直接操作する：

```python
from pptx.enum.shapes import MSO_CONNECTOR
from pptx.oxml import parse_xml
from pptx.oxml.ns import qn

def add_arrow(slide, x1, y1, x2, y2, color=None, w_pt=2.5):
    """矢印ヘッド付きコネクタ（tailEnd=triangle）を追加する。"""
    if color is None:
        color = RGBColor(0x15, 0x65, 0xC0)
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                      E(x1), E(y1), E(x2), E(y2))
    sp   = conn._element
    spPr = sp.find(qn('p:spPr'))
    for old in spPr.findall(qn('a:ln')):
        spPr.remove(old)
    ns = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
    r, g, b = color[0], color[1], color[2]
    w_emu = int(w_pt * 12700)
    ln_xml = (
        f'<a:ln {ns} w="{w_emu}">'
        f'<a:solidFill><a:srgbClr val="{r:02X}{g:02X}{b:02X}"/></a:solidFill>'
        f'<a:tailEnd type="triangle" w="med" len="med"/>'
        f'</a:ln>'
    )
    spPr.append(parse_xml(ln_xml))
    return conn
```

### PPTX破損チェック（生成後に必ず実行）

生成後、保存前に float 座標が混入していないか確認する：

```python
import zipfile, re

def verify_no_float_coords(pptx_path: str) -> bool:
    with zipfile.ZipFile(pptx_path) as z:
        total = 0
        for name in z.namelist():
            if name.startswith('ppt/slides/slide') and '.rels' not in name:
                floats = re.findall(r'(?:x|y|cx|cy)="\\d+\\.\\d+"',
                                    z.read(name).decode())
                total += len(floats)
        if total > 0:
            print(f"⚠ float座標が {total} 件残っています。E()の適用を確認してください。")
            return False
        print(f"✓ float座標なし")
        return True

verify_no_float_coords("output/xxx.pptx")
```

### 生成コードの配置

- 生成したスクリプトは `src/create_<name>.py` に保存する
- `output/<name>.pptx` に出力する
- 実行コマンドをユーザーに伝える：

```
スクリプトを生成しました: src/create_xxx.py
以下で実行してください:
  source .venv/bin/activate && python src/create_xxx.py
出力先: output/xxx.pptx
```

---

## スライドレイアウトの選び方

| 用途 | テンプレートレイアウト名（一般的） | フォールバック |
|---|---|---|
| 表紙・タイトル | "Title Slide" | blank + 全カスタム |
| セクション区切り | "Section Header" | blank + 背景色 + 大テキスト |
| 本文（1カラム） | "Title and Content" | blank + セクションヘッダー + テキストボックス |
| 2カラム比較 | "Two Content" / "Comparison" | blank + 左右分割の add_textbox |
| タイトルのみ | "Title Only" | blank + add_textbox |
| 白紙（フル自由） | "Blank" / slide_layouts[6] | そのまま使用 |

---

## よくある要素パターン

### ヘッダーバー（全スライド共通・落ち着いたスタイル）

```python
HDR_H = Inches(0.97)   # 70px / 540 * 7.5
MRG   = Inches(0.67)   # 48px / 960 * 13.33

def add_header(slide, title: str, num: str = None):
    add_rect(slide, 0, 0, SLIDE_W, HDR_H, fill=RGBColor(0x15,0x65,0xC0))
    if num:
        bs = Inches(0.38)
        bx = MRG
        by = E((HDR_H - bs) / 2)   # E()必須
        add_rect(slide, bx, by, bs, bs, fill=RGBColor(0xFF,0xFF,0xFF))
        add_textbox(slide, bx, by, bs, bs, num, Pt(13), True,
                    RGBColor(0x15,0x65,0xC0), PP_ALIGN.CENTER)
        tx = bx + bs + Inches(0.14)
    else:
        tx = MRG
    add_textbox(slide, tx, E((HDR_H - Inches(0.38)) / 2),   # E()必須
                SLIDE_W - tx - MRG, Inches(0.38),
                title, Pt(20), True, RGBColor(0xFF,0xFF,0xFF))
```

### 左ボーダーカード（落ち着いた強調）

```python
def add_border_card(slide, left, top, width, height,
                    title, body, bg=None, border_color=None):
    if bg is None: bg = RGBColor(0xEE,0xF2,0xFF)
    if border_color is None: border_color = RGBColor(0x15,0x65,0xC0)
    add_rect(slide, left, top, width, height, fill=bg)
    add_rect(slide, left, top, Inches(0.06), height, fill=border_color)
    add_textbox(slide, left+Inches(0.14), top+Inches(0.1),
                width-Inches(0.2), Inches(0.28),
                title, Pt(13), True, border_color)
    add_textbox(slide, left+Inches(0.14), top+Inches(0.42),
                width-Inches(0.2), height-Inches(0.52),
                body, Pt(12), False, RGBColor(0x4A,0x55,0x68))
```

### テーブル（標準スタイル）

```python
def add_tbl(slide, left, top, width, row_h, headers, data, col_widths,
            hdr_colors=None):
    n_r = 1 + len(data)
    n_c = len(headers)
    tbl = slide.shapes.add_table(
        n_r, n_c, E(left), E(top), E(width), E(row_h * n_r)
    ).table
    for i, cw in enumerate(col_widths):
        tbl.columns[i].width = E(cw)
    for ci, h in enumerate(headers):
        cell = tbl.cell(0, ci)
        hc = hdr_colors[ci] if hdr_colors else RGBColor(0x15,0x65,0xC0)
        cell.fill.solid(); cell.fill.fore_color.rgb = hc
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        r = p.add_run(); r.text = h
        r.font.size = Pt(12); r.font.bold = True
        r.font.color.rgb = RGBColor(0xFF,0xFF,0xFF)
    for ri, row in enumerate(data):
        for ci, text in enumerate(row):
            cell = tbl.cell(ri + 1, ci)
            if ri % 2 == 1:
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(0xF7,0xFA,0xFC)
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            r = p.add_run(); r.text = text
            r.font.size = Pt(12)
            r.font.color.rgb = RGBColor(0x1A,0x20,0x2C)
    return tbl
```

### KPIカード（控えめスタイル）

```python
# 控えめ（推奨）: 白背景、上部カラーバーのみ
add_rect(slide, kx, ky, kw, kh, fill=RGBColor(0xFF,0xFF,0xFF),
         line=RGBColor(0xE2,0xE8,0xF0))
add_rect(slide, kx, ky, kw, Inches(0.05), fill=RGBColor(0x15,0x65,0xC0))
add_textbox(slide, kx, ky+Inches(0.15), kw, Inches(0.5),
            "1,648万", Pt(28), True, RGBColor(0x15,0x65,0xC0), PP_ALIGN.CENTER)
add_textbox(slide, kx, ky+Inches(0.62), kw, Inches(0.28),
            "IPoE接続契約数（2024年3月末）", Pt(10), False,
            RGBColor(0x71,0x80,0x96), PP_ALIGN.CENTER)

# ピクセル換算メモ: 1px ≈ Inches(0.01389) ≈ Inches(x/960*13.33) = Inches(y/540*7.5)
```
