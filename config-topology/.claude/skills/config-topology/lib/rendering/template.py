"""
rendering/template.py — HTML テンプレート（静的 CSS/JS 定数 + build_html）
"""
from __future__ import annotations

from lib.rendering.svg import _esc

# ---------------------------------------------------------------------------
# 静的 CSS 定数（f-string 内では {{ }} でエスケープされていた箇所を { } に戻す）
# ---------------------------------------------------------------------------

_CSS = """\
    /* CSS 変数によるカラースキーム（拡張用） */
    :root {
      --color-node-fill: #dbeafe;
      --color-node-stroke: #3b82f6;
      --color-node-text: #1e3a5f;
      --color-seg-fill: #fef3c7;
      --color-seg-stroke: #d97706;
      --color-link: #6b7280;
      --color-bgp-ebgp: #2563eb;
      --color-bgp-ibgp: #d97706;
      --color-bgp-highlight: #dc2626;  /* BGPセッション選択時の共通ハイライト色（赤系）: iBGPアンバー・eBGP青と判別可能 */
      --color-bgp-unknown: #9ca3af;
      --color-highlight: #f59e0b;
      --color-selected: #ef4444;
      --color-card-bg: #f9fafb;
      --color-card-border: #e5e7eb;
      --color-ospf: #059669;  /* OSPFラベル・テーマ色（緑系）*/
      --font-main: 'Segoe UI', Arial, sans-serif;
      --font-mono: 'Consolas', 'Courier New', monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    html, body {
      height: 100%;
    }

    body {
      font-family: var(--font-main);
      background: #f3f4f6;
      color: #111827;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }

    header {
      background: #1e3a5f;
      color: #fff;
      padding: 12px 20px;
      display: flex;
      align-items: center;
      gap: 16px;
    }

    header h1 {
      font-size: 1.1rem;
      font-weight: 600;
    }

    /* ビュー切替タブ */
    .view-tabs {
      background: #fff;
      border-bottom: 2px solid var(--color-card-border);
      padding: 0 20px;
      display: flex;
      gap: 0;
    }

    .view-tab {
      padding: 8px 16px;
      font-size: 0.85rem;
      font-weight: 600;
      border: none;
      background: transparent;
      color: #6b7280;
      cursor: pointer;
      border-bottom: 3px solid transparent;
      margin-bottom: -2px;
      transition: color 0.15s, border-color 0.15s;
    }

    .view-tab:hover {
      color: #1e3a5f;
    }

    .view-tab.active {
      color: #1e3a5f;
      border-bottom-color: #3b82f6;
    }

    .controls {
      background: #fff;
      border-bottom: 1px solid var(--color-card-border);
      padding: 8px 20px;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
    }

    .controls-label {
      font-size: 0.8rem;
      font-weight: 600;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .layer-toggle {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 0.85rem;
      cursor: pointer;
      padding: 3px 8px;
      border-radius: 4px;
      border: 1px solid var(--color-card-border);
      background: var(--color-card-bg);
      user-select: none;
    }

    .layer-toggle:hover {
      background: #e5e7eb;
    }

    /* 検索ボックス */
    #search-input {
      padding: 4px 10px;
      font-size: 0.85rem;
      border: 1px solid var(--color-card-border);
      border-radius: 4px;
      min-width: 200px;
    }

    kbd {
      font-family: var(--font-mono);
      background: #e5e7eb;
      border: 1px solid #9ca3af;
      border-radius: 3px;
      padding: 1px 5px;
      font-size: 0.75rem;
    }

    /* 上下スプリットペインコンテナ（ヘッダ等固定UI の下に残り高さを分割） */
    #split-pane-container {
      display: flex;
      flex-direction: column;
      flex: 1;
      min-height: 0;
    }

    #svg-container {
      overflow: auto;
      flex: 1;
      min-height: 120px;
      background: #fff;
      cursor: grab;
      position: relative;
    }

    /* 上下ペイン境界バー（ドラッグで高さ可変） */
    #split-divider {
      height: 6px;
      background: #e5e7eb;
      border-top: 1px solid #d1d5db;
      border-bottom: 1px solid #d1d5db;
      cursor: row-resize;
      flex-shrink: 0;
      user-select: none;
    }

    #split-divider:hover {
      background: #93c5fd;
    }

    #svg-container:active {
      cursor: grabbing;
    }

    #topology-svg {
      display: block;
    }

    /* ノード */
    .node-rect {
      fill: var(--color-node-fill);
      stroke: var(--color-node-stroke);
      stroke-width: 2;
      transition: fill 0.15s, stroke-width 0.15s;
    }

    .device-node:hover .node-rect,
    .device-node.highlighted .node-rect {
      fill: #bfdbfe;
      stroke-width: 3;
    }

    .device-node.selected .node-rect {
      fill: #fef08a;
      stroke: var(--color-selected);
      stroke-width: 3;
    }

    .device-node.dimmed .node-rect {
      fill: #f3f4f6;
      stroke: #d1d5db;
      opacity: 0.4;
    }

    .device-node.dimmed text {
      opacity: 0.4;
    }

    .device-node.search-match .node-rect {
      stroke: #f59e0b;
      stroke-width: 3;
    }

    .node-label {
      font-size: 13px;
      font-weight: 700;
      fill: var(--color-node-text);
      pointer-events: none;
    }

    .node-sublabel {
      font-size: 10px;
      fill: #6b7280;
      pointer-events: none;
    }

    /* セグメントノード */
    .seg-ellipse {
      fill: var(--color-seg-fill);
      stroke: var(--color-seg-stroke);
      stroke-width: 2;
    }

    .seg-label {
      font-size: 10px;
      fill: #92400e;
      pointer-events: none;
    }

    .seg-edge {
      stroke: var(--color-seg-stroke);
      stroke-width: 1.5;
      stroke-dasharray: 6 3;
    }

    .seg-edge.highlighted {
      stroke: var(--color-highlight);
      stroke-width: 3.5;
      stroke-dasharray: none;
    }

    .segment-node.highlighted .seg-ellipse {
      stroke: var(--color-highlight);
      stroke-width: 3.5;
    }

    /* リンク */
    .link-line {
      stroke: var(--color-link);
      stroke-width: 2;
      transition: stroke 0.15s, stroke-width 0.15s;
    }

    .link-edge:hover .link-line,
    .link-edge.highlighted .link-line {
      stroke: var(--color-highlight);
      stroke-width: 4;
    }

    /* BGP エッジ */
    .bgp-edge {
      stroke-width: 2;
      stroke-dasharray: 8 4;
      opacity: 0.8;
    }

    .bgp-ebgp { stroke: var(--color-bgp-ebgp); }
    .bgp-ibgp { stroke: var(--color-bgp-ibgp); }
    .bgp-unknown { stroke: var(--color-bgp-unknown); }

    .bgp-badge {
      font-size: 10px;
      fill: var(--color-bgp-ebgp);
      pointer-events: none;
      font-family: var(--font-mono);
    }

    /* OSPF リンクラベル（A2/A3: bgp-badge と同一フォントサイズ・OSPFテーマ色） */
    .link-label {
      font-size: 10px;
      fill: var(--color-ospf);
      pointer-events: none;
      font-family: var(--font-mono);
    }

    /* カード */
    #cards-section {
      padding: 20px;
      overflow: auto;
      min-height: 80px;
    }

    #cards-section h2 {
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 12px;
      color: #374151;
    }

    .cards-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 16px;
    }

    .device-card {
      background: var(--color-card-bg);
      border: 1px solid var(--color-card-border);
      border-radius: 8px;
      padding: 16px;
    }

    .device-card h3 {
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 10px;
      display: flex;
      gap: 6px;
      align-items: center;
      flex-wrap: wrap;
    }

    .device-card h4 {
      font-size: 0.8rem;
      font-weight: 600;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin: 10px 0 4px;
    }

    .badge-vendor {
      font-size: 0.7rem;
      background: #e0e7ff;
      color: #3730a3;
      padding: 2px 6px;
      border-radius: 10px;
      font-weight: 500;
    }

    .badge-as {
      font-size: 0.7rem;
      background: #d1fae5;
      color: #065f46;
      padding: 2px 6px;
      border-radius: 10px;
      font-weight: 500;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.8rem;
    }

    th {
      text-align: left;
      padding: 3px 6px;
      background: #f3f4f6;
      color: #6b7280;
      font-weight: 600;
    }

    td {
      padding: 3px 6px;
      border-bottom: 1px solid #f3f4f6;
      font-family: var(--font-mono);
      word-break: break-all;
    }

    tr:last-child td { border-bottom: none; }

    .section-table { margin-top: 4px; }

    /* カード選択スタイル */
    .device-card.selected {
      border: 2px solid var(--color-selected);
      box-shadow: 0 0 6px rgba(239,68,68,0.4);
    }

    tr.selected td {
      background: #fef08a;
    }

    tr.highlighted td {
      background: #fef3c7;
      font-weight: 600;
    }

    /* ノードフィルタ（非表示クラス: display:none 強制） */
    .node-filtered {
      display: none !important;
    }

    /* ノードフィルタ UI パネル */
    .node-filter-panel {
      background: #fff;
      border-bottom: 1px solid var(--color-card-border);
      padding: 6px 20px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }

    .node-filter-label {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 0.82rem;
      cursor: pointer;
      padding: 2px 6px;
      border-radius: 4px;
      border: 1px solid var(--color-card-border);
      background: var(--color-card-bg);
      user-select: none;
    }

    .node-filter-label:hover {
      background: #e5e7eb;
    }

    .node-filter-btn {
      padding: 3px 10px;
      font-size: 0.82rem;
      border: 1px solid var(--color-card-border);
      border-radius: 4px;
      background: #e0e7ff;
      color: #3730a3;
      cursor: pointer;
      font-weight: 600;
    }

    .node-filter-btn:hover {
      background: #c7d2fe;
    }

    /* IF チップ（Physical ビュー ノード内の接続IF/Loopback 表示、iteration-3 #2） */
    .if-chip circle {
      fill: #bfdbfe;
      stroke: #3b82f6;
      stroke-width: 1.5;
      transition: fill 0.1s;
    }

    .if-chip:hover circle {
      fill: #93c5fd;
    }

    .if-chip-shutdown circle {
      fill: #f3f4f6;
      stroke: #d1d5db;
      opacity: 0.5;
    }

    /* #7: Loopback チップ識別（緑系: 通常チップの青と区別）*/
    .if-chip-loopback circle {
      fill: #bbf7d0;
      stroke: #16a34a;
      stroke-width: 1.5;
    }

    .if-chip-loopback:hover circle {
      fill: #86efac;
    }

    /* #7: Loopback かつ shutdown の複合状態（緑系薄表示） */
    .if-chip-loopback.if-chip-shutdown circle {
      fill: #d1fae5;
      stroke: #6b7280;
      opacity: 0.5;
    }

    /* #7: IF チップ凡例（左下固定オーバーレイ）。全ビュー常時表示。
       チップが無いビューでも表示されるが意図的（凡例は常に視認できる）。 */
    #chip-legend {
      position: absolute;
      bottom: 8px;
      left: 8px;
      display: flex;
      gap: 10px;
      align-items: center;
      background: rgba(255,255,255,0.88);
      border: 1px solid #e5e7eb;
      border-radius: 6px;
      padding: 4px 10px;
      font-size: 0.75rem;
      font-family: var(--font-mono);
      color: #374151;
      pointer-events: none;
    }

    /* HC2: static 経路 next-hop ノードのハイライト（手動選択 .selected と独立） */
    .device-node.route-target .node-rect {
      fill: #d1fae5;
      stroke: #059669;
      stroke-width: 3;
    }

    .device-card.route-target {
      border: 2px solid #059669;
      box-shadow: 0 0 6px rgba(5,150,105,0.4);
    }

    /* ズーム操作ボタン群（図ペイン右上に重ねる） */
    #zoom-controls {
      position: absolute;
      top: 8px;
      right: 8px;
      display: flex;
      gap: 4px;
      z-index: 10;
    }

    .zoom-btn {
      padding: 4px 8px;
      font-size: 0.8rem;
      font-weight: 600;
      border: 1px solid var(--color-card-border);
      border-radius: 4px;
      background: rgba(255, 255, 255, 0.92);
      color: #374151;
      cursor: pointer;
      line-height: 1;
    }

    .zoom-btn:hover {
      background: #e0e7ff;
      border-color: #6366f1;
      color: #3730a3;
    }

    /* BGP ビュー AS グルーピング枠（iteration-3 Batch2 #4: 視認性改善）
       色（fill/stroke）は svg のインライン style で AS 別に付与するためここでは省略 */
    .as-group {
      stroke-width: 2;
      stroke-dasharray: none;
    }

    .as-group-label {
      font-size: 15px;
      font-weight: 700;
      pointer-events: none;
      font-family: var(--font-mono);
    }

    .as-group-label-bg {
      opacity: 0.85;
    }

    /* #3: Static 行クリック時の行マーキング */
    tr.route-row-selected td {
      background: #d1fae5;
      outline: 2px solid #059669;
      outline-offset: -2px;
      font-weight: 600;
    }

    /* #5: BGP セッションハイライト（iBGP/eBGP 共通: 既定アンバー・eBGP青と判別可能な赤系） */
    .bgp-session.highlighted .bgp-edge {
      stroke: var(--color-bgp-highlight);  /* 共通変数で赤系を使用: eBGP青・iBGPアンバーと明確に判別 */
      stroke-width: 5;  /* 基本線幅(2)より太くして視認性を確保（#4 レビュー指摘対応）*/
      opacity: 1;
    }

    /* 多ノードC: カード絞り込み（選択外カードを非表示） */
    .card-unselected {
      display: none;
    }

    /* ============================================================
     * Phase2E: IF 一覧/棚卸しビュー
     * ============================================================ */

    /* IF一覧コンテナ（#svg-container と同じ上ペイン内に存在） */
    .ifinv-container {
      overflow: auto;
      flex: 1;
      min-height: 120px;
      background: #fff;
      padding: 12px 20px;
      box-sizing: border-box;
    }

    /* status 集計バー */
    .ifinv-summary {
      display: flex;
      gap: 10px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }

    .ifinv-badge {
      font-size: 0.8rem;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 12px;
      font-family: var(--font-mono);
    }

    .ifinv-badge-up { background: #d1fae5; color: #065f46; }
    .ifinv-badge-down { background: #fee2e2; color: #991b1b; }
    .ifinv-badge-admindown { background: #f3f4f6; color: #6b7280; border: 1px solid #d1d5db; }

    /* ツールバー（検索・フィルタ） */
    .ifinv-toolbar {
      display: flex;
      gap: 12px;
      align-items: center;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }

    #ifinv-search {
      padding: 4px 10px;
      font-size: 0.85rem;
      border: 1px solid var(--color-card-border);
      border-radius: 4px;
      min-width: 260px;
    }

    .ifinv-filter-label {
      font-size: 0.83rem;
      cursor: pointer;
    }

    /* IF 一覧テーブル */
    .ifinv-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.8rem;
    }

    .ifinv-th {
      text-align: left;
      padding: 4px 8px;
      background: #f3f4f6;
      color: #6b7280;
      font-weight: 600;
      white-space: nowrap;
      user-select: none;
    }

    .ifinv-th:hover { background: #e5e7eb; }

    .ifinv-table td {
      padding: 3px 8px;
      border-bottom: 1px solid #f3f4f6;
      font-family: var(--font-mono);
      word-break: break-all;
    }

    .ifinv-table tr:last-child td { border-bottom: none; }

    /* 未使用候補行のハイライト */
    .ifinv-table tr[data-unused="1"] td {
      background: #fff7ed;
      color: #92400e;
    }

    /* 検索/フィルタ非表示（_applyIfFilters により ifinv-row-hidden に一本化） */
    .ifinv-row-hidden {
      display: none !important;
    }

    /* B-pass1b: グローバル検索フォーカスノード（「次へ」で巡回中の対象） */
    .device-node.search-focus .node-rect {
      stroke: #dc2626;
      stroke-width: 4;
      filter: drop-shadow(0 0 6px rgba(220,38,38,0.6));
    }

    /* B-pass1b: ifinv ヒット行強調（グローバル検索マッチ） */
    tr.search-match td {
      background: #fef3c7;
    }\
"""

# ---------------------------------------------------------------------------
# 静的 JS 定数
# ---------------------------------------------------------------------------

_JS = """\
    // ============================================================
    // ビュー切替
    // ============================================================
    var _currentView = 'physical';

    function selectView(viewId) {
      _currentView = viewId;

      var ifinvTable = document.getElementById('view-ifinv-table');
      var svgContainer = document.getElementById('svg-container');
      var zoomControls = document.getElementById('zoom-controls');
      var chipLegend = document.getElementById('chip-legend');

      if (viewId === 'ifinv') {
        // ifinv ビュー: SVG コンテナを隠し、IF 一覧テーブルを表示
        // 図系 UI（ズームボタン・チップ凡例）は ifinv に無関係なので非表示
        // 非SVGビュー追加時はここに同様の分岐を追加するか、
        // 各ビューコンテナに data-view-type="table" 等を付与してデータ駆動化する
        if (svgContainer) svgContainer.style.display = 'none';
        if (zoomControls) zoomControls.style.display = 'none';
        if (chipLegend) chipLegend.style.display = 'none';
        if (ifinvTable) ifinvTable.style.display = '';
      } else {
        // SVG ビュー（physical/bgp/ospf 等）: IF 一覧テーブルを隠し、SVG コンテナを表示
        if (ifinvTable) ifinvTable.style.display = 'none';
        if (svgContainer) svgContainer.style.display = '';
        if (zoomControls) zoomControls.style.display = '';
        if (chipLegend) chipLegend.style.display = '';

        // ビュー <g> の表示切替
        var views = document.querySelectorAll('.view');
        views.forEach(function(v) {
          if (v.classList.contains('view-' + viewId)) {
            v.style.display = '';
          } else {
            v.style.display = 'none';
          }
        });

        // viewBox を選択ビューの data-bbox にセット（SVG はコンテナ 100% 固定）
        var activeView = document.querySelector('.view-' + viewId);
        if (activeView) {
          var bbox = activeView.getAttribute('data-bbox');
          if (bbox) {
            var svg = document.getElementById('topology-svg');
            svg.setAttribute('viewBox', bbox);
          }
        }
      }

      // タブのアクティブ状態更新
      var tabs = document.querySelectorAll('.view-tab');
      tabs.forEach(function(tab) {
        if (tab.dataset.view === viewId) {
          tab.classList.add('active');
        } else {
          tab.classList.remove('active');
        }
      });

      // 検索状態をリセット（SVG ビューのみ）
      if (viewId !== 'ifinv') {
        var searchInput = document.getElementById('search-input');
        if (searchInput && searchInput.value) {
          filterNodes(searchInput.value);
        }
      }
    }

    // 初期ビューを設定
    selectView('physical');

    // ============================================================
    // 検索 / フィルタ
    // ============================================================

    // ---- CIDR ユーティリティ ----
    function _parseCidrV4(cidr) {
      // "10.0.0.0/24" → {netInt, prefix} or null
      var slash = cidr.indexOf('/');
      if (slash === -1) return null;
      var ipPart = cidr.slice(0, slash);
      var prefixStr = cidr.slice(slash + 1);
      var prefix = parseInt(prefixStr, 10);
      if (isNaN(prefix) || prefix < 0 || prefix > 32) return null;
      var octets = ipPart.split('.');
      if (octets.length !== 4) return null;
      var netInt = 0;
      for (var i = 0; i < 4; i++) {
        var o = parseInt(octets[i], 10);
        if (isNaN(o) || o < 0 || o > 255) return null;
        netInt = (netInt * 256 + o) >>> 0;
      }
      return {netInt: netInt, prefix: prefix};
    }

    function _ipv4ToInt(ip) {
      var octets = ip.split('.');
      if (octets.length !== 4) return null;
      var val = 0;
      for (var i = 0; i < 4; i++) {
        var o = parseInt(octets[i], 10);
        if (isNaN(o) || o < 0 || o > 255) return null;
        val = (val * 256 + o) >>> 0;
      }
      return val;
    }

    function _inCidrV4(ipCidr, networkCidr) {
      // ipCidr: "10.0.0.1/30" (address部のみ使用), networkCidr: {netInt, prefix}
      var slash = ipCidr.indexOf('/');
      var ip = slash !== -1 ? ipCidr.slice(0, slash) : ipCidr;
      var ipInt = _ipv4ToInt(ip);
      if (ipInt === null) return false;
      if (networkCidr.prefix === 0) return true;
      var mask = (~((1 << (32 - networkCidr.prefix)) - 1)) >>> 0;
      return ((ipInt & mask) >>> 0) === ((networkCidr.netInt & mask) >>> 0);
    }

    function _expandV6(ip) {
      // IPv6 短縮形を展開して 8グループの数値配列を返す。失敗時 null
      ip = ip.toLowerCase();
      // :: を展開
      var dcolon = ip.indexOf('::');
      var left, right;
      if (dcolon !== -1) {
        left = ip.slice(0, dcolon).split(':').filter(function(s) { return s !== ''; });
        right = ip.slice(dcolon + 2).split(':').filter(function(s) { return s !== ''; });
        var fill = 8 - left.length - right.length;
        if (fill < 0) return null;
        var mid = [];
        for (var i = 0; i < fill; i++) mid.push('0');
        var groups = left.concat(mid).concat(right);
      } else {
        var groups = ip.split(':');
      }
      if (groups.length !== 8) return null;
      var nums = [];
      for (var j = 0; j < 8; j++) {
        var v = parseInt(groups[j], 16);
        if (isNaN(v)) return null;
        nums.push(v);
      }
      return nums;
    }

    function _v6ToBigInt(nums) {
      var val = BigInt(0);
      for (var i = 0; i < 8; i++) {
        val = (val << BigInt(16)) | BigInt(nums[i]);
      }
      return val;
    }

    function _parseCidrV6(cidr) {
      // "2001:db8::/32" → {netBig, prefix} or null
      var slash = cidr.indexOf('/');
      if (slash === -1) return null;
      var ipPart = cidr.slice(0, slash);
      var prefix = parseInt(cidr.slice(slash + 1), 10);
      if (isNaN(prefix) || prefix < 0 || prefix > 128) return null;
      var nums = _expandV6(ipPart);
      if (!nums) return null;
      return {netBig: _v6ToBigInt(nums), prefix: prefix};
    }

    function _inCidrV6(ipCidr, networkCidr) {
      // ipCidr: "2001:db8::1/64" のアドレス部
      var slash = ipCidr.indexOf('/');
      var ip = slash !== -1 ? ipCidr.slice(0, slash) : ipCidr;
      var nums = _expandV6(ip);
      if (!nums) return false;
      var ipBig = _v6ToBigInt(nums);
      if (networkCidr.prefix === 0) return true;
      var shift = BigInt(128 - networkCidr.prefix);
      var mask = ((BigInt(1) << BigInt(networkCidr.prefix)) - BigInt(1)) << shift;
      return (ipBig & mask) === (networkCidr.netBig & mask);
    }

    function _isV4Cidr(s) {
      return /^(\\d{1,3}\\.){3}\\d{1,3}\\/\\d+$/.test(s);
    }

    function _isV6Cidr(s) {
      return s.indexOf('/') !== -1 && (s.indexOf(':') !== -1);
    }

    // 共通ヘルパー: ips 配列（空白区切り文字列 or 配列）が cidrQuery に内包される IP を持つか
    // _nodeMatchesCidr / _applyIfFilters 両方から再利用する（v4/v6 ループを DRY 化）。
    function _ipsMatchCidr(ipsAttr, cidrQuery) {
      var ipsStr = (ipsAttr || '').trim();
      if (!ipsStr) return false;
      var ips = ipsStr.split(/\\s+/);
      if (_isV4Cidr(cidrQuery)) {
        var net4 = _parseCidrV4(cidrQuery);
        if (!net4) return false;
        for (var i = 0; i < ips.length; i++) {
          if (ips[i].indexOf(':') === -1 && _inCidrV4(ips[i], net4)) return true;
        }
        return false;
      } else {
        var net6 = _parseCidrV6(cidrQuery);
        if (!net6) return false;
        for (var i = 0; i < ips.length; i++) {
          if (ips[i].indexOf(':') !== -1 && _inCidrV6(ips[i], net6)) return true;
        }
        return false;
      }
    }

    function _nodeMatchesCidr(node, cidrQuery) {
      var ipsAttr = node.getAttribute('data-ips') || '';
      return _ipsMatchCidr(ipsAttr, cidrQuery);
    }

    // 検索ナビゲーション状態（全ビュー横断・タブ自動切替用）
    var _searchMatches = [];     // マッチした機器ID の決定的リスト（id 昇順）
    var _searchFocusIndex = -1;  // 現在フォーカス中のインデックス（-1=未選択）
    var _isNavigating = false;   // navigateSearchNext 実行中フラグ（filterNodes のインデックスリセットをガード）

    function filterNodes(query) {
      var q = (query || '').toLowerCase().trim();

      // CIDR モード判定: '/' を含み v4/v6 CIDR として解釈できる場合
      var isCidrMode = q.indexOf('/') !== -1 && (_isV4Cidr(q) || _isV6Cidr(q));

      // 全グラフビュー（physical/bgp/ospf）を横断してノードにマッチ適用
      var allGraphViews = document.querySelectorAll('.view');
      // マッチした機器IDを収集（ビュー間重複除去）
      var matchedDevices = new Set();

      allGraphViews.forEach(function(viewEl) {
        var nodes = viewEl.querySelectorAll('.device-node');
        nodes.forEach(function(node) {
          if (!q) {
            node.classList.remove('dimmed');
            node.classList.remove('search-match');
            node.classList.remove('search-focus');
          } else {
            var matched;
            if (isCidrMode) {
              matched = _nodeMatchesCidr(node, q);
            } else {
              var searchVal = (node.getAttribute('data-search') || '').toLowerCase();
              matched = searchVal.indexOf(q) !== -1;
            }
            if (matched) {
              node.classList.remove('dimmed');
              node.classList.add('search-match');
              var devId = node.getAttribute('data-device');
              if (devId) matchedDevices.add(devId);
            } else {
              node.classList.add('dimmed');
              node.classList.remove('search-match');
              node.classList.remove('search-focus');
            }
          }
        });

        // エッジも淡色化（両端が dimmed のとき）
        var links = viewEl.querySelectorAll('.link-edge');
        links.forEach(function(link) {
          if (!q) {
            link.style.opacity = '';
            return;
          }
          var aNode = viewEl.querySelector('.device-node[data-device="' + CSS.escape(link.dataset.a) + '"]');
          var bNode = viewEl.querySelector('.device-node[data-device="' + CSS.escape(link.dataset.b) + '"]');
          var aDimmed = aNode && aNode.classList.contains('dimmed');
          var bDimmed = bNode && bNode.classList.contains('dimmed');
          link.style.opacity = (aDimmed && bDimmed) ? '0.15' : '';
        });
      });

      // ifinv 行もグローバルクエリで駆動（CIDR 内包 or テキスト部分一致）
      _ifinvSearchQuery = q;
      _applyIfFilters();

      // ifinv マッチ行の機器も matchedDevices に追加（件数カウントに含む）
      if (q) {
        var ifinvRows = document.querySelectorAll('#ifinv-table-body tr');
        ifinvRows.forEach(function(row) {
          if (!row.classList.contains('ifinv-row-hidden')) {
            var devId = row.getAttribute('data-device');
            if (devId) matchedDevices.add(devId);
          }
        });
      }

      // マッチ機器リストを id 昇順の決定的リストに変換（ナビゲーション用）
      _searchMatches = Array.from(matchedDevices).sort();
      // _isNavigating 中（navigateSearchNext から selectView 経由で再呼び出しの場合）は
      // インデックスをリセットしない（クロスタブ「次へ」で i/N 表示が維持される）
      if (!_isNavigating) {
        _searchFocusIndex = -1;
        // フォーカスクラス解除（ユーザー入力起動のときのみリセット）
        document.querySelectorAll('.device-node.search-focus').forEach(function(n) {
          n.classList.remove('search-focus');
        });
      }

      // 件数表示（未ナビゲーション時は件数のみ）
      _updateSearchCount();
    }

    // 件数表示更新ヘルパー
    function _updateSearchCount() {
      var countEl = document.getElementById('search-count');
      if (!countEl) return;
      var searchInput = document.getElementById('search-input');
      var q = searchInput ? searchInput.value.trim() : '';
      if (!q) {
        countEl.textContent = '';
        return;
      }
      var total = _searchMatches.length;
      if (total === 0) {
        countEl.textContent = '0件';
        return;
      }
      if (_searchFocusIndex >= 0) {
        countEl.textContent = (_searchFocusIndex + 1) + '/' + total + '件';
      } else {
        countEl.textContent = total + '件';
      }
    }

    // 「次へ」ナビゲーション — マッチ機器を id 昇順で巡回
    // 各ステップで対象機器をグラフビューに表示（タブ自動切替）し中央寄せ
    function navigateSearchNext() {
      if (_searchMatches.length === 0) return;

      // 旧フォーカス解除
      document.querySelectorAll('.device-node.search-focus').forEach(function(n) {
        n.classList.remove('search-focus');
      });

      // 次のインデックスへ進む（巡回）
      _searchFocusIndex = (_searchFocusIndex + 1) % _searchMatches.length;
      var targetDevId = _searchMatches[_searchFocusIndex];

      // 対象ノードをグラフビューに表示（現ビューがグラフビューかつノードを含むならそのまま）
      var targetInCurrentView = false;
      if (_currentView !== 'ifinv') {
        var currentViewEl = document.querySelector('.view-' + _currentView);
        if (currentViewEl) {
          var nodeInCurrent = currentViewEl.querySelector(
            '.device-node[data-device="' + CSS.escape(targetDevId) + '"]'
          );
          if (nodeInCurrent) targetInCurrentView = true;
        }
      }
      // 現ビューにない or ifinv ビュー → Physical タブへ自動切替
      // _isNavigating フラグで filterNodes 内の _searchFocusIndex リセットを抑止する
      if (!targetInCurrentView) {
        _isNavigating = true;
        selectView('physical');
        _isNavigating = false;
      }

      // フォーカスノードに .search-focus クラスを付与（全ビュー）
      document.querySelectorAll(
        '.device-node[data-device="' + CSS.escape(targetDevId) + '"]'
      ).forEach(function(n) {
        n.classList.add('search-focus');
      });

      // 中央寄せ: 現ビューのノード座標を使い、viewport の translateX/Y を更新
      _centerOnDevice(targetDevId);

      // 件数表示を i/N件 に更新
      _updateSearchCount();
    }

    // ノード中央寄せヘルパー（ズーム closure の _zoomState 共有オブジェクト経由で更新）
    function _centerOnDevice(deviceId) {
      var currentViewEl = document.querySelector('.view-' + _currentView);
      if (!currentViewEl) return;
      var node = currentViewEl.querySelector(
        '.device-node[data-device="' + CSS.escape(deviceId) + '"]'
      );
      if (!node) return;
      // 実座標は子 .node-rect の x/y/width/height 属性から取得する
      // g の transform="translate(0,0)" は常に原点のため使用しない
      var rect = node.querySelector('.node-rect');
      if (!rect) return;  // セグメント等 .node-rect を持たない要素は安全に return
      var rx = parseFloat(rect.getAttribute('x') || '0');
      var ry = parseFloat(rect.getAttribute('y') || '0');
      var rw = parseFloat(rect.getAttribute('width') || '0');
      var rh = parseFloat(rect.getAttribute('height') || '0');
      // ノード中心座標（rect の中心）
      var nx = rx + rw / 2;
      var ny = ry + rh / 2;
      var container = document.getElementById('svg-container');
      if (!container) return;
      var cw = container.clientWidth || 800;
      var ch = container.clientHeight || 600;
      // _zoomState 共有オブジェクトで closure の scale を読み、translateX/Y を更新する。
      // _applyTransform() を呼ぶことで closure 側の状態と viewport transform が同期する。
      if (window._zoomState && window._applyTransform) {
        var currentScale = window._zoomState.scale;
        window._zoomState.translateX = cw / 2 - nx * currentScale;
        window._zoomState.translateY = ch / 2 - ny * currentScale;
        window._applyTransform();
      }
    }

    // search-next ボタン・Enter キーのイベント登録
    (function() {
      var nextBtn = document.getElementById('search-next');
      if (nextBtn) {
        nextBtn.addEventListener('click', function(e) {
          e.stopPropagation();
          navigateSearchNext();
        });
      }
      var searchInput = document.getElementById('search-input');
      if (searchInput) {
        searchInput.addEventListener('keydown', function(e) {
          if (e.key === 'Enter') {
            e.preventDefault();
            navigateSearchNext();
          }
        });
      }
    })();

    // ============================================================
    // ズーム / パン
    // ============================================================
    (function() {
      const container = document.getElementById('svg-container');
      const svg = document.getElementById('topology-svg');
      const vp = document.getElementById('viewport');

      // ズーム定数（重複排除: wheel/ボタン/zoomFit のクランプをここで一元管理）
      var ZOOM_STEP = 1.2;
      var ZOOM_MIN = 0.2;
      var ZOOM_MAX = 5.0;

      let scale = 1.0;
      let translateX = 0;
      let translateY = 0;
      let isDragging = false;
      let dragStart = { x: 0, y: 0 };
      let translateStart = { x: 0, y: 0 };

      function applyTransform() {
        vp.setAttribute('transform',
          'translate(' + translateX + ',' + translateY + ') scale(' + scale + ')');
      }

      // ズーム（マウスホイール）
      container.addEventListener('wheel', function(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? (1 / ZOOM_STEP) : ZOOM_STEP;
        scale = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, scale * delta));
        applyTransform();
      }, { passive: false });

      // パン（マウスドラッグ）
      container.addEventListener('mousedown', function(e) {
        // ノード/リンク/ズームボタン上のクリックは pan を発火させない
        if (e.target.closest('.device-node') || e.target.closest('.link-edge')) return;
        if (e.target.closest('#zoom-controls')) return;
        isDragging = true;
        dragStart = { x: e.clientX, y: e.clientY };
        translateStart = { x: translateX, y: translateY };
        e.preventDefault();
      });

      document.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        translateX = translateStart.x + (e.clientX - dragStart.x);
        translateY = translateStart.y + (e.clientY - dragStart.y);
        applyTransform();
      });

      document.addEventListener('mouseup', function() {
        isDragging = false;
      });

      // ズームボタン群のクリックハンドラ
      var zoomFitBtn = document.getElementById('zoom-fit');
      var zoomInBtn = document.getElementById('zoom-in');
      var zoomOutBtn = document.getElementById('zoom-out');
      var zoomResetBtn = document.getElementById('zoom-reset');

      function zoomFit() {
        // コンテナ寸法0ガード: レイアウト前やテスト環境では 0 になる場合がある
        var cw = container.clientWidth;
        var ch = container.clientHeight;
        if (cw === 0 || ch === 0) {
          scale = 1.0; translateX = 0; translateY = 0;
          applyTransform();
          return;
        }
        // viewBox の全4要素（minX minY W H）を parse して centering を補正
        var vb = svg.getAttribute('viewBox');
        if (vb) {
          var parts = vb.split(' ');
          if (parts.length === 4) {
            var vbX = parseFloat(parts[0]);  // min-x（0 以外になりうる）
            var vbY = parseFloat(parts[1]);  // min-y（0 以外になりうる）
            var vbW = parseFloat(parts[2]);
            var vbH = parseFloat(parts[3]);
            if (vbW > 0 && vbH > 0) {
              var fitScale = Math.min(cw / vbW, ch / vbH, ZOOM_MAX);
              scale = Math.max(ZOOM_MIN, fitScale);
              // vbX/vbY を考慮した centering（min-x/min-y が 0 でも安全）
              translateX = (cw - vbW * scale) / 2 - vbX * scale;
              translateY = (ch - vbH * scale) / 2 - vbY * scale;
              applyTransform();
              return;
            }
          }
        }
        // フォールバック: リセット
        scale = 1.0; translateX = 0; translateY = 0;
        applyTransform();
      }

      // キーボード
      document.addEventListener('keydown', function(e) {
        if (e.key === 'f' || e.key === 'F') {
          // F = 全体表示（zoomFit）: HTML ヘルプ表記と実挙動を一致させる
          zoomFit();
        } else if (e.key === 'Escape') {
          // Esc = 選択/ハイライト解除 + 等倍リセット
          clearSelection();
          scale = 1.0;
          translateX = 0;
          translateY = 0;
          applyTransform();
        }
      });

      applyTransform();

      if (zoomFitBtn) zoomFitBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        zoomFit();
      });
      if (zoomInBtn) zoomInBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        scale = Math.min(ZOOM_MAX, scale * ZOOM_STEP);
        applyTransform();
      });
      if (zoomOutBtn) zoomOutBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        scale = Math.max(ZOOM_MIN, scale / ZOOM_STEP);
        applyTransform();
      });
      if (zoomResetBtn) zoomResetBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        scale = 1.0; translateX = 0; translateY = 0;
        applyTransform();
      });

      // ズーム状態を共有オブジェクトとして window に露出（_centerOnDevice から利用）
      // _zoomState 経由で scale/translateX/translateY を読み書きし applyTransform を呼ぶ。
      window._zoomState = {
        get scale() { return scale; },
        set scale(v) { scale = v; },
        get translateX() { return translateX; },
        set translateX(v) { translateX = v; },
        get translateY() { return translateY; },
        set translateY(v) { translateY = v; },
      };
      window._applyTransform = applyTransform;
      window._zoomFit = zoomFit;
      window._zoomReset = function() { scale = 1.0; translateX = 0; translateY = 0; applyTransform(); };
    })();

    // ============================================================
    // 上下スプリットディバイダ ドラッグリサイズ
    // ============================================================
    (function() {
      var divider = document.getElementById('split-divider');
      var svgContainer = document.getElementById('svg-container');
      if (!divider || !svgContainer) return;

      var isDraggingDivider = false;
      var dragStartY = 0;
      var startHeight = 0;

      divider.addEventListener('mousedown', function(e) {
        isDraggingDivider = true;
        dragStartY = e.clientY;
        startHeight = svgContainer.offsetHeight;
        e.preventDefault();
        e.stopPropagation();
      });

      document.addEventListener('mousemove', function(e) {
        if (!isDraggingDivider) return;
        var delta = e.clientY - dragStartY;
        var newHeight = startHeight + delta;
        // minH: 図ペインの最小高（SVG が潰れないよう 120px を確保）
        var minH = 120;
        // maxH: ヘッダ(~50px) + タブ(~38px) + サーチ(~40px) + フィルタ(~36px) ≈ 200px を
        //        下ペインに残し、上ペインが window 全高を超えないよう制限。
        //        さらに maxH >= minH+1 を保証し、上ペインが 0 になるのを防ぐ。
        var maxH = Math.max(minH + 1, window.innerHeight - 200);
        newHeight = Math.max(minH, Math.min(maxH, newHeight));
        svgContainer.style.flex = 'none';
        svgContainer.style.height = newHeight + 'px';
      });

      document.addEventListener('mouseup', function() {
        isDraggingDivider = false;
      });
    })();

    // ============================================================
    // ホバー & 選択ハイライト
    // ============================================================
    (function() {
      const allNodes = document.querySelectorAll('.device-node');
      const allLinks = document.querySelectorAll('.link-edge');

      function highlight(deviceId) {
        allNodes.forEach(function(n) {
          if (n.dataset.device === deviceId) {
            n.classList.add('highlighted');
          }
        });
        allLinks.forEach(function(l) {
          if (l.dataset.a === deviceId || l.dataset.b === deviceId) {
            l.classList.add('highlighted');
          }
        });
      }

      function clearHighlight() {
        allNodes.forEach(function(n) { n.classList.remove('highlighted'); });
        // リンクの highlighted 除去:
        // _selectedLinks（IF行クリック固定）と _selectedStaticEdges（static経路固定）は保持
        allLinks.forEach(function(l) {
          var lid = l.getAttribute('data-link-id');
          if (!_selectedLinks.has(lid) && !_selectedStaticEdges.has(lid)) {
            l.classList.remove('highlighted');
          }
        });
      }

      // ノードホバー
      allNodes.forEach(function(node) {
        node.addEventListener('mouseover', function(e) {
          e.stopPropagation();
          clearHighlight();
          highlight(node.dataset.device);
        });
        node.addEventListener('mouseenter', function() {
          highlight(node.dataset.device);
        });
        node.addEventListener('mouseleave', function() {
          clearHighlight();
        });
      });

      // リンクホバー
      allLinks.forEach(function(link) {
        link.addEventListener('mouseover', function(e) {
          e.stopPropagation();
          clearHighlight();
          link.classList.add('highlighted');
          if (link.dataset.a) highlight(link.dataset.a);
          if (link.dataset.b) highlight(link.dataset.b);
        });
        link.addEventListener('mouseleave', function() {
          clearHighlight();
        });
      });

      // ノードクリックで選択強調（累積トグル対応・即時実行）
      allNodes.forEach(function(node) {
        node.addEventListener('click', function(e) {
          e.stopPropagation();
          var deviceId = node.dataset.device;
          var wasSelected = node.classList.contains('selected');
          if (wasSelected) {
            // トグル: 解除
            node.classList.remove('selected');
            var card = document.querySelector('.device-card[data-device="' + CSS.escape(deviceId) + '"]');
            if (card) card.classList.remove('selected');
            _selectedNodes.delete(deviceId);
          } else {
            // 累積選択
            node.classList.add('selected');
            var card = document.querySelector('.device-card[data-device="' + CSS.escape(deviceId) + '"]');
            if (card) {
              card.classList.add('selected');
              card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
            _selectedNodes.add(deviceId);
          }
          _updateCardFilter();
        });
      });

      document.getElementById('topology-svg').addEventListener('click', function() {
        clearSelection();
      });
    })();

    // ============================================================
    // レイヤートグル
    // ============================================================
    function handleLayerToggle(checkbox) {
      const layer = checkbox.dataset.layer;
      if (checkbox.checked) {
        document.body.classList.remove('hide-' + layer);
      } else {
        document.body.classList.add('hide-' + layer);
      }
    }

    // ============================================================
    // カード↔ノード双方向選択・複数累積トグル / IF行↔リンク連動
    // （宣言を参照より前に配置して TDZ を回避）
    // ============================================================
    var _selectedNodes = new Set();
    var _selectedLinks = new Set();
    var _selectedStaticRows = new Set();    // #2: static 行 data-route-id 集合（行ごと独立累積）
    var _selectedStaticEdges = new Set();   // HC1: static 経路で固定中のエッジ link-id / seg-id 集合
    var _selectedStaticNodes = new Set();   // HC2: static 経路 next-hop 機器（手動選択と独立）
    var _selectedSegs = new Set();          // #7: seg-id set
    var _selectedBgp = new Set();           // #5: bgp-id set
    var _selectedOspf = new Set();          // #1B: ospf-id set

    // clearSelection: ノード選択(.selected)解除 + clearLinkHighlight() + _updateCardFilter()
    function clearSelection() {
      document.querySelectorAll('.device-node.selected').forEach(function(n) {
        n.classList.remove('selected');
      });
      document.querySelectorAll('.device-card.selected').forEach(function(c) {
        c.classList.remove('selected');
      });
      _selectedNodes.clear();
      // リンク・IF 行・static・セグメント・BGP ハイライトも同時解除
      clearLinkHighlight();
      // 多ノードC: カード絞り込みを同期
      _updateCardFilter();
    }

    // clearLinkHighlight: リンク/IF行/static経路/セグメント/BGP ハイライトを解除する。
    function clearLinkHighlight() {
      document.querySelectorAll('.link-edge.highlighted').forEach(function(l) {
        l.classList.remove('highlighted');
      });
      document.querySelectorAll('tr.highlighted').forEach(function(r) {
        r.classList.remove('highlighted');
      });
      _selectedLinks.clear();
      // #6: static ルート経路ハイライト解除
      document.querySelectorAll('[data-route-edge].highlighted').forEach(function(el) {
        el.classList.remove('highlighted');
      });
      // #2/#3: static 行マーキング解除（_selectedStaticRows + route-row-selected）
      document.querySelectorAll('tr.route-row-selected').forEach(function(r) {
        r.classList.remove('route-row-selected');
      });
      _selectedStaticRows.clear();
      _selectedStaticEdges.clear();
      // HC2: static 経路 next-hop ノードも解除
      document.querySelectorAll('.device-node.route-target').forEach(function(n) {
        n.classList.remove('route-target');
      });
      document.querySelectorAll('.device-card.route-target').forEach(function(c) {
        c.classList.remove('route-target');
      });
      _selectedStaticNodes.clear();
      // #7: セグメントハイライト解除
      document.querySelectorAll('[data-seg-id].highlighted').forEach(function(el) {
        el.classList.remove('highlighted');
      });
      _selectedSegs.clear();
      // #5: BGP ハイライト解除
      document.querySelectorAll('[data-bgp-id].highlighted').forEach(function(el) {
        el.classList.remove('highlighted');
      });
      _selectedBgp.clear();
      // #1B: OSPF ハイライト解除
      document.querySelectorAll('[data-ospf-id].highlighted').forEach(function(el) {
        el.classList.remove('highlighted');
      });
      _selectedOspf.clear();
    }

    // カード→ノード選択（カードクリックで対応ノードを selected 強調・累積トグル）
    (function() {
      document.querySelectorAll('.device-card').forEach(function(card) {
        card.addEventListener('click', function(e) {
          // IF 行クリックは別ハンドラが処理するので tr 上のクリックは除外
          if (e.target.closest('tr')) return;
          var deviceId = card.dataset.device;
          var wasCardSelected = card.classList.contains('selected');
          if (wasCardSelected) {
            // トグル: 選択解除
            card.classList.remove('selected');
            _selectedNodes.delete(deviceId);
            document.querySelectorAll('.device-node[data-device="' + CSS.escape(deviceId) + '"]')
              .forEach(function(n) { n.classList.remove('selected'); });
          } else {
            // 累積選択
            card.classList.add('selected');
            _selectedNodes.add(deviceId);
            document.querySelectorAll('.device-node[data-device="' + CSS.escape(deviceId) + '"]')
              .forEach(function(n) { n.classList.add('selected'); });
          }
          // 多ノードC: 選択変化をカード絞り込みに反映
          _updateCardFilter();
        });
      });
    })();

    // ============================================================
    // 修正8: toggle*Highlight の共通ヘルパー
    // ============================================================
    // _toggleSelection(id, selectedSet, dataAttr): CSS.escape 込みで data-{attr} 要素を
    // highlighted クラスでトグルし、selectedSet を更新する（挙動・クラス(.highlighted)不変）
    function _toggleSelection(id, selectedSet, dataAttr) {
      if (!id) return;
      var isHighlighted = selectedSet.has(id);
      var selector = '[' + dataAttr + '="' + CSS.escape(id) + '"]';
      if (isHighlighted) {
        selectedSet.delete(id);
        document.querySelectorAll(selector).forEach(function(el) {
          el.classList.remove('highlighted');
        });
      } else {
        selectedSet.add(id);
        document.querySelectorAll(selector).forEach(function(el) {
          el.classList.add('highlighted');
        });
      }
    }

    // IF行↔リンク双方向ハイライト（トグル: 2回目クリックで解除）
    function toggleIfRowHighlight(linkId) {
      _toggleSelection(linkId, _selectedLinks, 'data-link-id');
    }

    // IF 行・リンクエッジ クリックイベントの登録
    (function() {
      document.querySelectorAll('tr[data-link-id]').forEach(function(row) {
        var linkId = row.getAttribute('data-link-id');
        if (!linkId) return;
        row.style.cursor = 'pointer';
        row.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleIfRowHighlight(linkId);
        });
      });

      // リンクエッジクリックで対応 IF 行ハイライト
      document.querySelectorAll('.link-edge[data-link-id]').forEach(function(edge) {
        var linkId = edge.getAttribute('data-link-id');
        if (!linkId) return;
        edge.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleIfRowHighlight(linkId);
        });
      });
    })();

    // ============================================================
    // ノード表示フィルタ
    // ============================================================
    // 非表示デバイスの集合（両端判定に使用）
    var _hiddenNodes = new Set();

    function setNodeVisibility(deviceId, visible) {
      // 非表示デバイス集合を更新
      if (visible) {
        _hiddenNodes.delete(deviceId);
      } else {
        _hiddenNodes.add(deviceId);
      }

      // 全ビューのノードを制御（CSS.escape でセレクタインジェクション防御）
      document.querySelectorAll('.device-node[data-device="' + CSS.escape(deviceId) + '"]')
        .forEach(function(node) {
          node.classList.toggle('node-filtered', !visible);
        });

      // エッジの制御（全種別: link-edge / bgp-session / seg-edge）
      // link-edge: data-a / data-b 両端判定
      document.querySelectorAll('.link-edge').forEach(function(edge) {
        var a = edge.dataset.a;
        var b = edge.dataset.b;
        if (a === deviceId || b === deviceId) {
          var aHidden = _hiddenNodes.has(a);
          var bHidden = _hiddenNodes.has(b);
          // いずれかの端点が非表示なら隠す。両端が表示のときのみ表示に戻す
          edge.classList.toggle('node-filtered', aHidden || bHidden);
        }
      });

      // bgp-session: data-a / data-b 両端判定（svg.py で付与）
      document.querySelectorAll('.bgp-session').forEach(function(edge) {
        var a = edge.dataset.a;
        var b = edge.dataset.b;
        if (!a || !b) return;
        if (a === deviceId || b === deviceId) {
          var aHidden = _hiddenNodes.has(a);
          var bHidden = _hiddenNodes.has(b);
          edge.classList.toggle('node-filtered', aHidden || bHidden);
        }
      });

      // seg-edge: data-device で単端点デバイスに対応
      document.querySelectorAll('.seg-edge').forEach(function(edge) {
        var dev = edge.dataset.device;
        if (dev === deviceId) {
          edge.classList.toggle('node-filtered', !visible);
        }
      });

      // カードの制御
      var card = document.querySelector('.device-card[data-device="' + CSS.escape(deviceId) + '"]');
      if (card) {
        card.classList.toggle('node-filtered', !visible);
      }
    }

    function selectAllNodes() {
      document.querySelectorAll('.node-filter-cb').forEach(function(cb) {
        cb.checked = true;
        setNodeVisibility(cb.dataset.nodeFilter, true);
      });
    }

    function clearAllNodes() {
      document.querySelectorAll('.node-filter-cb').forEach(function(cb) {
        cb.checked = false;
        setNodeVisibility(cb.dataset.nodeFilter, false);
      });
    }

    // ノードフィルタ checkbox のイベントリスナー登録（DC5: onchange インライン不使用）
    (function() {
      document.querySelectorAll('.node-filter-cb').forEach(function(cb) {
        cb.addEventListener('change', function() {
          setNodeVisibility(cb.dataset.nodeFilter, cb.checked);
        });
      });
    })();

    // ============================================================
    // #2: Static Route 行クリック -> 行ごと独立・複数累積マーク
    // ============================================================
    // 設計:
    //   - _selectedStaticRows: data-route-id の集合（行ごと独立）
    //   - 行クリックで data-route-id をトグル（1行のみ route-row-selected を付け外し）
    //   - エッジ/next-hop ハイライトは _selectedStaticRows の和から再計算
    //   - 旧: data-route-edge 全行巻き込みは廃止

    // _applyStaticRowHighlights: _selectedStaticRows の現状から
    // エッジ highlighted + next-hop route-target を一括再計算する。
    function _applyStaticRowHighlights() {
      // まず全ての経路エッジ/next-hop ハイライトをクリア
      document.querySelectorAll('[data-link-id].highlighted').forEach(function(el) {
        if (_selectedStaticEdges.has(el.getAttribute('data-link-id'))) {
          el.classList.remove('highlighted');
        }
      });
      document.querySelectorAll('[data-seg-id].highlighted').forEach(function(el) {
        if (_selectedStaticEdges.has(el.getAttribute('data-seg-id'))) {
          el.classList.remove('highlighted');
        }
      });
      _selectedStaticEdges.clear();
      document.querySelectorAll('.device-node.route-target').forEach(function(n) {
        n.classList.remove('route-target');
      });
      document.querySelectorAll('.device-card.route-target').forEach(function(c) {
        c.classList.remove('route-target');
      });
      _selectedStaticNodes.clear();

      // 選択中の全行から route-edge / nexthop-device を収集して再点灯
      _selectedStaticRows.forEach(function(rowId) {
        var row = document.querySelector('tr[data-route-id="' + CSS.escape(rowId) + '"]');
        if (!row) return;
        var routeEdgeId = row.getAttribute('data-route-edge') || '';
        var nexthopDeviceId = row.getAttribute('data-route-nexthop-device') || '';
        if (routeEdgeId) {
          _selectedStaticEdges.add(routeEdgeId);
          document.querySelectorAll('[data-link-id="' + CSS.escape(routeEdgeId) + '"]').forEach(function(el) {
            el.classList.add('highlighted');
          });
          document.querySelectorAll('[data-seg-id="' + CSS.escape(routeEdgeId) + '"]').forEach(function(el) {
            el.classList.add('highlighted');
          });
        }
        if (nexthopDeviceId) {
          _selectedStaticNodes.add(nexthopDeviceId);
          document.querySelectorAll('.device-node[data-device="' + CSS.escape(nexthopDeviceId) + '"]').forEach(function(n) {
            n.classList.add('route-target');
          });
          var card = document.querySelector('.device-card[data-device="' + CSS.escape(nexthopDeviceId) + '"]');
          if (card) card.classList.add('route-target');
        }
      });
    }

    function toggleStaticRouteHighlight(routeId) {
      // routeId = data-route-id（例 "r1::0.0.0.0/0"）
      if (!routeId) return;
      var row = document.querySelector('tr[data-route-id="' + CSS.escape(routeId) + '"]');
      if (!row) return;
      var isSelected = _selectedStaticRows.has(routeId);
      if (isSelected) {
        _selectedStaticRows.delete(routeId);
        row.classList.remove('route-row-selected');
      } else {
        _selectedStaticRows.add(routeId);
        row.classList.add('route-row-selected');
        row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
      // エッジ/next-hop ハイライトを _selectedStaticRows の和から再計算
      _applyStaticRowHighlights();
    }

    // Static route 行クリックイベント登録（#2: data-route-id で1行特定）
    (function() {
      document.querySelectorAll('tr[data-route-id]').forEach(function(row) {
        var routeId = row.getAttribute('data-route-id');
        if (!routeId) return;
        row.style.cursor = 'pointer';
        row.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleStaticRouteHighlight(routeId);
        });
      });
    })();

    // ============================================================
    // #7: セグメントノード / IF 行双方向ハイライト
    // ============================================================
    function toggleSegHighlight(segId) {
      if (!segId) return;
      var isHighlighted = _selectedSegs.has(segId);
      if (isHighlighted) {
        _selectedSegs.delete(segId);
        document.querySelectorAll('[data-seg-id="' + CSS.escape(segId) + '"]').forEach(function(el) {
          el.classList.remove('highlighted');
        });
      } else {
        _selectedSegs.add(segId);
        document.querySelectorAll('[data-seg-id="' + CSS.escape(segId) + '"]').forEach(function(el) {
          el.classList.add('highlighted');
        });
      }
    }

    // セグメントノード / seg-edge クリックイベント登録
    (function() {
      // segment-node <g> クリック
      document.querySelectorAll('.segment-node[data-seg-id]').forEach(function(node) {
        var segId = node.getAttribute('data-seg-id');
        if (!segId) return;
        node.style.cursor = 'pointer';
        node.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleSegHighlight(segId);
        });
      });

      // seg-edge <line> クリック
      document.querySelectorAll('.seg-edge[data-seg-id]').forEach(function(edge) {
        var segId = edge.getAttribute('data-seg-id');
        if (!segId) return;
        edge.style.cursor = 'pointer';
        edge.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleSegHighlight(segId);
        });
      });

      // IF 行クリック（data-seg-id を持つ行）
      document.querySelectorAll('tr[data-seg-id]').forEach(function(row) {
        var segId = row.getAttribute('data-seg-id');
        if (!segId) return;
        row.style.cursor = 'pointer';
        row.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleSegHighlight(segId);
        });
      });
    })();

    // ============================================================
    // #5: BGP Session ↔ 表の双方向ハイライト
    // ============================================================
    function toggleBgpHighlight(bgpId) {
      _toggleSelection(bgpId, _selectedBgp, 'data-bgp-id');
    }

    // BGP セッション <g> クリック + BGP 行 <tr> クリックイベント登録
    (function() {
      // bgp-session SVG 要素クリック
      document.querySelectorAll('.bgp-session[data-bgp-id]').forEach(function(el) {
        var bgpId = el.getAttribute('data-bgp-id');
        if (!bgpId) return;
        el.style.cursor = 'pointer';
        el.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleBgpHighlight(bgpId);
        });
      });

      // BGP 行 <tr> クリック
      document.querySelectorAll('tr[data-bgp-id]').forEach(function(row) {
        var bgpId = row.getAttribute('data-bgp-id');
        if (!bgpId) return;
        row.style.cursor = 'pointer';
        row.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleBgpHighlight(bgpId);
        });
      });
    })();

    // ============================================================
    // #1B: OSPF リンク/セグメント ↔ OSPF Networks 表の双方向ハイライト
    // ============================================================
    // Phase 3H: dual-stack 対応 token セレクタ版
    // - 統合エッジ data-ospf-id は空白区切り複数 token（例: "10.0.0.0/30 2001:db8:1::/127"）
    // - OSPF Networks 行は単一 token（例: "10.0.0.0/30" または "2001:db8:1::/127"）
    //
    // 双方向連動ルール:
    // - 行（単一 id）クリック → [data-ospf-id~="id"] で token 照合し統合エッジをハイライト
    // - 統合エッジ（複数 token）クリック → token を split して各行/要素を全ハイライト
    // - single-stack（単一 token）は ~= でも完全一致と同等に動作するため非回帰

    // _ospfHighlightToken: 単一 token id に対して [data-ospf-id~="id"] セレクタで
    // ハイライト/解除を実行し、_selectedOspf Set を更新する。
    // BGP/seg の _toggleSelection と独立した OSPF 専用実装。
    function _ospfHighlightToken(id, on) {
      if (!id) return;
      var selector = '[data-ospf-id~="' + CSS.escape(id) + '"]';
      document.querySelectorAll(selector).forEach(function(el) {
        if (on) {
          el.classList.add('highlighted');
        } else {
          el.classList.remove('highlighted');
        }
      });
    }

    // toggleOspfHighlight: ospfIdStr（空白区切り 1 or 複数 token）をトグルする。
    // - 行クリック時は単一 token（ospfId = "10.0.0.0/30"）
    // - エッジクリック時は複数 token（ospfId = "10.0.0.0/30 2001:db8:1::/127"）
    // どちらの場合も token 単位で _selectedOspf を更新し ~= で双方向連動する。
    function toggleOspfHighlight(ospfIdStr) {
      if (!ospfIdStr) return;
      var tokens = ospfIdStr.split(' ').filter(function(t) { return t.length > 0; });
      if (tokens.length === 0) return;

      // 全 token がハイライト済みかどうかを確認
      var allHighlighted = tokens.every(function(t) { return _selectedOspf.has(t); });

      if (allHighlighted) {
        // トグル: 全 token を解除
        tokens.forEach(function(t) {
          _selectedOspf.delete(t);
          _ospfHighlightToken(t, false);
        });
      } else {
        // ハイライト: 全 token を追加
        tokens.forEach(function(t) {
          _selectedOspf.add(t);
          _ospfHighlightToken(t, true);
        });
      }
    }

    // OSPF リンク・セグメント・OSPF Networks 行 クリックイベント登録
    (function() {
      // OSPF ビューの link-edge[data-ospf-id] クリック
      // Phase 3H: data-ospf-id は複数 token になりうる（統合エッジ）
      document.querySelectorAll('.link-edge[data-ospf-id]').forEach(function(el) {
        var ospfIdStr = el.getAttribute('data-ospf-id');
        if (!ospfIdStr) return;
        el.style.cursor = 'pointer';
        el.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleOspfHighlight(ospfIdStr);
        });
      });

      // OSPF セグメントノード クリック（セグメントは単一 token）
      document.querySelectorAll('.segment-node[data-ospf-id]').forEach(function(el) {
        var ospfIdStr = el.getAttribute('data-ospf-id');
        if (!ospfIdStr) return;
        el.style.cursor = 'pointer';
        el.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleOspfHighlight(ospfIdStr);
        });
      });

      // OSPF セグメントエッジ クリック（セグメントは単一 token）
      document.querySelectorAll('.seg-edge[data-ospf-id]').forEach(function(el) {
        var ospfIdStr = el.getAttribute('data-ospf-id');
        if (!ospfIdStr) return;
        el.style.cursor = 'pointer';
        el.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleOspfHighlight(ospfIdStr);
        });
      });

      // OSPF Networks 行 <tr>[data-ospf-id] クリック（行は単一 token）
      document.querySelectorAll('tr[data-ospf-id]').forEach(function(row) {
        var ospfIdStr = row.getAttribute('data-ospf-id');
        if (!ospfIdStr) return;
        row.style.cursor = 'pointer';
        row.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleOspfHighlight(ospfIdStr);
        });
      });
    })();

    // ============================================================
    // 多ノードC: カード選択連動絞り込みトグル
    // ============================================================
    // _updateCardFilter: card-filter-toggle ON 時に _selectedNodes に基づいてカードを絞り込む。
    // _selectedNodes 変更・clearSelection 等の選択変化から呼び出す。
    function _updateCardFilter() {
      var cb = document.getElementById('card-filter-toggle');
      if (!cb || !cb.checked) {
        // OFF: 全カードを表示（card-unselected を除去）
        document.querySelectorAll('.device-card.card-unselected').forEach(function(c) {
          c.classList.remove('card-unselected');
        });
        return;
      }
      // ON: _selectedNodes の機器のカードのみ表示
      var visibleDevices = new Set(_selectedNodes);

      document.querySelectorAll('.device-card').forEach(function(card) {
        var dev = card.dataset.device || card.getAttribute('data-device');
        if (!dev) return;
        if (visibleDevices.size === 0 || visibleDevices.has(dev)) {
          card.classList.remove('card-unselected');
        } else {
          card.classList.add('card-unselected');
        }
      });
    }

    (function() {
      var cb = document.getElementById('card-filter-toggle');
      if (cb) {
        cb.addEventListener('change', _updateCardFilter);
      }
    })();

    // ============================================================
    // Phase2E: IF 一覧/棚卸しビュー — 検索・ソート・未使用トグル
    // ============================================================

    // 検索クエリ状態と未使用トグル状態（単一の真実源）
    var _ifinvSearchQuery = '';
    var _ifinvUnusedOnly = false;

    // _applyIfFilters: 検索クエリ (_ifinvSearchQuery) と未使用トグル (_ifinvUnusedOnly) の
    // 両条件 AND で全行の表示/非表示を一括再評価する。
    // グローバル検索から _ifinvSearchQuery が更新される（#ifinv-search は撤去済み）。
    // CIDR クエリの場合は data-ips も参照してマッチ判定する（_ipsMatchCidr を使用）。
    function _applyIfFilters() {
      var q = _ifinvSearchQuery.toLowerCase().trim();
      var isCidrMode = q.indexOf('/') !== -1 && (_isV4Cidr(q) || _isV6Cidr(q));
      var rows = document.querySelectorAll('#ifinv-table-body tr');
      rows.forEach(function(row) {
        var matchSearch;
        if (!q) {
          matchSearch = true;
        } else if (isCidrMode) {
          // CIDR 内包: data-ips（行に付与された全アドレス）で判定（_ipsMatchCidr を再利用）
          var ipsAttr = row.getAttribute('data-ips') || '';
          matchSearch = _ipsMatchCidr(ipsAttr, q);
        } else {
          var searchVal = (row.getAttribute('data-search') || '').toLowerCase();
          matchSearch = searchVal.indexOf(q) !== -1;
        }
        var matchUnused = !_ifinvUnusedOnly || row.getAttribute('data-unused') === '1';
        // 両条件を AND で評価して表示/非表示を決定（クラスは ifinv-row-hidden に一本化）
        if (matchSearch && matchUnused) {
          row.classList.remove('ifinv-row-hidden');
          // マッチ行に search-match クラスを付与（強調表示）
          if (q) {
            row.classList.add('search-match');
          } else {
            row.classList.remove('search-match');
          }
        } else {
          row.classList.add('ifinv-row-hidden');
          row.classList.remove('search-match');
        }
      });
    }

    // filterIfRows: 検索クエリ更新 → _applyIfFilters() 呼び出し
    function filterIfRows(query) {
      _ifinvSearchQuery = query || '';
      _applyIfFilters();
    }

    // toggleUnused: 未使用トグル状態更新 → _applyIfFilters() 呼び出し
    function toggleUnused(checked) {
      _ifinvUnusedOnly = checked;
      _applyIfFilters();
    }

    // ifinv-unused-toggle のイベント登録（DC5: addEventListener）
    // #ifinv-search は撤去済み（グローバル検索 #search-input に統合）のためリスナーなし
    (function() {
      var unusedToggle = document.getElementById('ifinv-unused-toggle');
      if (unusedToggle) {
        unusedToggle.addEventListener('change', function() {
          toggleUnused(unusedToggle.checked);
        });
      }
    })();

    // _ifinvSortState: {col: string, asc: boolean} — ソート状態
    var _ifinvSortState = { col: null, asc: true };

    // sortIfTable: IF 一覧テーブルをクリック列でソート（昇順/降順トグル）
    // 列インデックスは DOM の data-col から取得（colOrder ハードコードを廃止）。
    // 将来 th に子要素が入っても壊れないよう data-label で元ラベルを保持し
    // th.textContent を label + 記号で書き換える。
    // MTU/VLAN 列（data-num 属性が存在）は数値ソート、他は文字列ソート。
    function sortIfTable(col) {
      var tbody = document.getElementById('ifinv-table-body');
      if (!tbody) return;
      var asc = (_ifinvSortState.col === col) ? !_ifinvSortState.asc : true;
      _ifinvSortState = { col: col, asc: asc };

      // ヘッダの昇降指示記号を更新（data-label で元ラベルを取得してから書き換え）
      var colIdx = -1;
      var colHeaders = document.querySelectorAll('.ifinv-th');
      colHeaders.forEach(function(th, idx) {
        var colKey = th.getAttribute('data-col');
        var label = th.getAttribute('data-label') || th.textContent.replace(/[ \t]*[▲▼]$/, '');
        if (colKey === col) {
          th.textContent = label + (asc ? ' ▲' : ' ▼');
          colIdx = idx;
        } else {
          th.textContent = label;
        }
      });
      if (colIdx === -1) return;

      var rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort(function(a, b) {
        var cellA = a.querySelectorAll('td')[colIdx];
        var cellB = b.querySelectorAll('td')[colIdx];
        if (!cellA || !cellB) return 0;
        // 数値列（mtu/vlan）は data-num 属性で判定
        var numA = cellA.getAttribute('data-num');
        var numB = cellB.getAttribute('data-num');
        var valA, valB;
        if (numA !== null && numB !== null) {
          // 数値ソート（空は末尾）
          valA = numA === '' ? Infinity : parseFloat(numA);
          valB = numB === '' ? Infinity : parseFloat(numB);
          return asc ? valA - valB : valB - valA;
        } else {
          valA = (cellA.textContent || '').toLowerCase();
          valB = (cellB.textContent || '').toLowerCase();
          return asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
      });

      rows.forEach(function(row) { tbody.appendChild(row); });
    }\
"""


def _node_filter_ui(devices: list[dict]) -> str:
    """ノード表示フィルタ チェックリスト UI を生成して返す。

    デバイスを hostname 昇順にソートし、各チェックボックスは ``data-node-filter="{device_id}"``
    でデフォルト checked。「全選択」「全解除」ボタンも生成する。
    デバイスが0件の場合は空文字列を返す。

    Args:
        devices: topology の devices リスト（各要素は id/hostname を持つ）
    """
    if not devices:
        return ""

    sorted_devs = sorted(devices, key=lambda d: d.get("hostname", d["id"]))

    checkboxes = []
    for dev in sorted_devs:
        dev_id = _esc(dev["id"])
        hostname = _esc(dev.get("hostname", dev["id"]))
        checkboxes.append(
            f'<label class="node-filter-label">'
            f'<input type="checkbox" class="node-filter-cb" '
            f'data-node-filter="{dev_id}" checked> {hostname}'
            f'</label>'
        )

    checkboxes_html = "\n    ".join(checkboxes)
    return (
        f'<div class="node-filter-panel">'
        f'<span class="controls-label">Nodes:</span>\n    '
        f'{checkboxes_html}\n    '
        f'<button class="node-filter-btn" onclick="selectAllNodes()">全選択</button>'
        f'<button class="node-filter-btn" onclick="clearAllNodes()">全解除</button>'
        f'</div>'
    )


def _layer_toggles(active_keys: list[str]) -> str:
    """レイヤートグルチェックボックスを生成して返す。

    Args:
        active_keys: データが1件以上ある routing キーの昇順リスト（呼び出し側で計算済み）。
                     physical トグルは常に先頭に生成する。
    """
    layers = [("physical", "Physical", True)]
    for key in active_keys:
        layers.append((key, key.upper(), True))

    toggles = []
    for layer_id, label, checked in layers:
        checked_attr = "checked" if checked else ""
        toggles.append(
            f'<label class="layer-toggle">'
            f'<input type="checkbox" id="toggle-{_esc(layer_id)}" '
            f'data-layer="{_esc(layer_id)}" {checked_attr} '
            f'onchange="handleLayerToggle(this)"> {_esc(label)}'
            f'</label>'
        )
    return "\n".join(toggles)


def build_html(
    *,
    title: str,
    layer_hide_css: str,
    tabs_html: str,
    toggles_html: str,
    node_filter_html: str,
    svg_height: int,
    vb_min_x: float,
    vb_min_y: float,
    svg_width: int,
    all_views_svg: str,
    cards_html: str,
    topology_json_safe: str,
    ifinv_table_html: str = "",
) -> str:
    """HTML シェルを組み立てて返す"""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
{_CSS}

    /* レイヤー表示制御（routing キーから動的生成） */
{layer_hide_css}
  </style>
</head>
<body>
  <header>
    <h1 id="topo-title">{title}</h1>
    <span style="font-size:0.75rem;opacity:0.7;">
      <kbd>F</kbd> 全体表示　<kbd>Esc</kbd> リセット　ホイール=ズーム　ドラッグ=パン　クリック=ノード選択
    </span>
  </header>

  <!-- ビュー切替タブ -->
  <div class="view-tabs" id="view-tabs">
    {tabs_html}
  </div>

  <div class="controls">
    <span class="controls-label" style="margin-left:0;">Search:</span>
    <input type="search" id="search-input" placeholder="hostname / IP / CIDR..." oninput="filterNodes(this.value)">
    <button id="search-next" class="zoom-btn" title="次のマッチへ（Enter）" style="margin-left:4px;">次へ</button>
    <span id="search-count" style="margin-left:8px;font-size:0.8rem;color:#6b7280;"></span>
  </div>

  {node_filter_html}

  <!-- 上下スプリットペインコンテナ -->
  <div id="split-pane-container">
    <!-- 上ペイン: 図 -->
    <div id="svg-container">
      <svg id="topology-svg"
           width="100%" height="100%"
           viewBox="{vb_min_x:.1f} {vb_min_y:.1f} {svg_width} {svg_height}"
           xmlns="http://www.w3.org/2000/svg">
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8"
                  refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="#6b7280"/>
          </marker>
        </defs>
        <!-- ズーム/パン用グループ -->
        <g id="viewport">
          {all_views_svg}
        </g>
      </svg>
      <!-- ズーム操作ボタン群（図ペイン右上） -->
      <div id="zoom-controls">
        <button id="zoom-fit" class="zoom-btn" title="全体表示">⛶ fit</button>
        <button id="zoom-in" class="zoom-btn" title="拡大">+</button>
        <button id="zoom-out" class="zoom-btn" title="縮小">−</button>
        <button id="zoom-reset" class="zoom-btn" title="等倍リセット">1:1</button>
      </div>
      <!-- #7: IF チップ凡例（左下固定オーバーレイ）。スタイルは CSS #chip-legend で管理 -->
      <div id="chip-legend">
        <svg width="12" height="12" style="flex-shrink:0"><g class="if-chip"><circle cx="6" cy="6" r="5"/></g></svg><span>接続IF</span>
        <svg width="12" height="12" style="flex-shrink:0"><g class="if-chip if-chip-loopback"><circle cx="6" cy="6" r="5"/></g></svg><span>Loopback</span>
      </div>
    </div>

    <!-- Phase2E: IF 一覧/棚卸しビュー（ifinv 選択時のみ表示・初期非表示） -->
    {ifinv_table_html}

    <!-- 境界ディバイダ（ドラッグで上下ペイン高を可変） -->
    <div id="split-divider"></div>

    <!-- 下ペイン: Device Details -->
    <div id="cards-section">
      <!-- LAYERS トグル（Device Details 見出し付近） -->
      <div class="controls" id="layers-controls" style="padding:6px 0 10px;border:none;">
        <span class="controls-label">Layers:</span>
        {toggles_html}
      </div>
      <h2>Device Details
        <label style="font-size:0.8rem;font-weight:400;margin-left:16px;cursor:pointer;">
          <input type="checkbox" id="card-filter-toggle" style="vertical-align:middle;">
          選択中の機器のみ表示
        </label>
      </h2>
      <div class="cards-grid">
        {cards_html}
      </div>
    </div>
  </div>

  <!-- 埋め込み topology データ -->
  <script type="application/json" id="topology-data">
{topology_json_safe}
  </script>

  <script>
{_JS}
  </script>
</body>
</html>"""
