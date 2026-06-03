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
      --color-bgp-unknown: #9ca3af;
      --color-highlight: #f59e0b;
      --color-selected: #ef4444;
      --color-card-bg: #f9fafb;
      --color-card-border: #e5e7eb;
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
      font-size: 9px;
      fill: var(--color-bgp-ebgp);
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
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
    }

    .device-card {
      background: var(--color-card-bg);
      border: 1px solid var(--color-card-border);
      border-radius: 8px;
      padding: 16px;
      min-width: 280px;
      max-width: 480px;
      flex: 1;
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

    /* BGP ビュー AS グルーピング枠（iteration-3 Batch2 #4: 視認性改善） */
    .as-group {
      fill: rgba(219, 234, 254, 0.35);
      stroke: #3b82f6;
      stroke-width: 2;
      stroke-dasharray: none;
    }

    .as-group-label {
      font-size: 11px;
      font-weight: 700;
      fill: #1e3a5f;
      pointer-events: none;
      font-family: var(--font-mono);
    }

    .as-group-label-bg {
      fill: #3b82f6;
      opacity: 0.85;
    }

    /* #3: Static 行クリック時の行マーキング */
    tr.route-row-selected td {
      background: #d1fae5;
      outline: 2px solid #059669;
      outline-offset: -2px;
      font-weight: 600;
    }

    /* #5: BGP セッションハイライト */
    .bgp-session.highlighted .bgp-edge {
      stroke: var(--color-highlight);  /* seg-edge ハイライトと視覚的一貫性 */
      stroke-width: 4;
      opacity: 1;
    }

    /* 多ノードB: フォーカスモード（ダブルクリック）薄表示
       検索dimmed(0.4)より強く薄める意図で 0.12 を使用 */
    .focus-dimmed {
      opacity: 0.12;
      pointer-events: none;
    }

    /* 多ノードC: カード絞り込み（選択外カードを非表示） */
    .card-unselected {
      display: none;
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
      // ビュー切替時はフォーカスモードを解除（残留防止）
      clearFocusMode();

      _currentView = viewId;

      // ビュー <g> の表示切替
      var views = document.querySelectorAll('.view');
      views.forEach(function(v) {
        if (v.classList.contains('view-' + viewId)) {
          v.style.display = '';
        } else {
          v.style.display = 'none';
        }
      });

      // タブのアクティブ状態更新
      var tabs = document.querySelectorAll('.view-tab');
      tabs.forEach(function(tab) {
        if (tab.dataset.view === viewId) {
          tab.classList.add('active');
        } else {
          tab.classList.remove('active');
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

      // 検索状態をリセット
      var searchInput = document.getElementById('search-input');
      if (searchInput && searchInput.value) {
        filterNodes(searchInput.value);
      }
    }

    // 初期ビューを設定
    selectView('physical');

    // ============================================================
    // 検索 / フィルタ
    // ============================================================
    function filterNodes(query) {
      var q = (query || '').toLowerCase().trim();
      // 現在のビュー内のノードのみ対象
      var currentViewEl = document.querySelector('.view-' + _currentView);
      if (!currentViewEl) return;

      var nodes = currentViewEl.querySelectorAll('.device-node');
      nodes.forEach(function(node) {
        if (!q) {
          node.classList.remove('dimmed');
        } else {
          var searchVal = (node.getAttribute('data-search') || '').toLowerCase();
          if (searchVal.indexOf(q) !== -1) {
            node.classList.remove('dimmed');
          } else {
            node.classList.add('dimmed');
          }
        }
      });

      // エッジも淡色化（両端が dimmed のとき）
      var links = currentViewEl.querySelectorAll('.link-edge');
      links.forEach(function(link) {
        if (!q) {
          link.style.opacity = '';
          return;
        }
        var aNode = currentViewEl.querySelector('.device-node[data-device="' + CSS.escape(link.dataset.a) + '"]');
        var bNode = currentViewEl.querySelector('.device-node[data-device="' + CSS.escape(link.dataset.b) + '"]');
        var aDimmed = aNode && aNode.classList.contains('dimmed');
        var bDimmed = bNode && bNode.classList.contains('dimmed');
        link.style.opacity = (aDimmed && bDimmed) ? '0.15' : '';
      });
    }

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
          var parts = vb.split(/\s+/);
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

      // Phase2 向けにズーム制御を window に露出（selectView 等から呼べるよう）
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

      // ノードクリックで選択強調（累積トグル対応）
      // dblclick誤発火防止: 単クリック処理を setTimeout で遅延し
      // dblclick ハンドラ冒頭の clearTimeout でキャンセルする
      var _clickTimer = null;  // IIFE スコープで管理（dblclick側と共有）
      allNodes.forEach(function(node) {
        node.addEventListener('click', function(e) {
          e.stopPropagation();
          var deviceId = node.dataset.device;
          // 単クリックは 250ms 遅延: dblclick が来たらキャンセルされる
          _clickTimer = setTimeout(function() {
            _clickTimer = null;
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
          }, 250);
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
    var _selectedStaticRoutes = new Set();  // #6: static route key set
    var _selectedStaticEdges = new Set();   // HC1: static 経路で固定中のエッジ link-id / seg-id 集合
    var _selectedStaticNodes = new Set();   // HC2: static 経路 next-hop 機器（手動選択と独立）
    var _selectedSegs = new Set();          // #7: seg-id set
    var _selectedBgp = new Set();           // #5: bgp-id set

    // clearSelection: ノード選択(.selected)解除 + clearLinkHighlight() + clearFocusMode() + _updateCardFilter()
    // フォーカスは解除するが、clearLinkHighlight はフォーカスを解除しない方針（責務分離）
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
      // 多ノードB: フォーカスモード解除
      clearFocusMode();
      // 多ノードC: カード絞り込みを同期
      _updateCardFilter();
    }

    // clearLinkHighlight: リンク/IF行/static経路/セグメント/BGP ハイライトを解除する。
    // フォーカスモード（focus-dimmed）は解除しない（フォーカスは clearFocusMode / clearSelection 担当）。
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
      // #3: static 行マーキング解除
      document.querySelectorAll('tr.route-row-selected').forEach(function(r) {
        r.classList.remove('route-row-selected');
      });
      _selectedStaticRoutes.clear();
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
    // #6: Static Route 行クリック -> 経路エッジ + next-hop 機器 ハイライト
    // ============================================================
    // 修正4: 行マーキング（route-row-selected）を関数内部に一本化。
    //         クリックハンドラ側では addClass/removeClass を行わない。
    function toggleStaticRouteHighlight(routeEdgeId, nexthopDeviceId) {
      var routeKey = routeEdgeId + '|' + (nexthopDeviceId || '');
      var isHighlighted = _selectedStaticRoutes.has(routeKey);
      if (isHighlighted) {
        _selectedStaticRoutes.delete(routeKey);
        if (routeEdgeId) {
          // HC1: static 経路固定エッジ集合からも削除
          _selectedStaticEdges.delete(routeEdgeId);
          // link-edge または seg-id 一致の要素から highlighted を除去（CSS.escape でインジェクション防御）
          document.querySelectorAll('[data-link-id="' + CSS.escape(routeEdgeId) + '"]').forEach(function(el) {
            el.classList.remove('highlighted');
          });
          document.querySelectorAll('[data-seg-id="' + CSS.escape(routeEdgeId) + '"]').forEach(function(el) {
            el.classList.remove('highlighted');
          });
          // 修正4: 行マーキングを関数内部で管理（クリックハンドラ側では操作しない）
          document.querySelectorAll("tr[data-route-edge='" + CSS.escape(routeEdgeId) + "']").forEach(function(r) {
            r.classList.remove('route-row-selected');
          });
        }
        if (nexthopDeviceId) {
          // HC2: route-target クラスで手動選択と独立管理
          document.querySelectorAll('.device-node[data-device="' + CSS.escape(nexthopDeviceId) + '"]').forEach(function(n) {
            n.classList.remove('route-target');
          });
          var card = document.querySelector('.device-card[data-device="' + CSS.escape(nexthopDeviceId) + '"]');
          if (card) card.classList.remove('route-target');
          _selectedStaticNodes.delete(nexthopDeviceId);
        }
      } else {
        _selectedStaticRoutes.add(routeKey);
        if (routeEdgeId) {
          // HC1: static 経路固定エッジ集合に追加（clearHighlight で保護される）
          _selectedStaticEdges.add(routeEdgeId);
          document.querySelectorAll('[data-link-id="' + CSS.escape(routeEdgeId) + '"]').forEach(function(el) {
            el.classList.add('highlighted');
          });
          document.querySelectorAll('[data-seg-id="' + CSS.escape(routeEdgeId) + '"]').forEach(function(el) {
            el.classList.add('highlighted');
          });
          // 修正4: 行マーキングを関数内部で管理（追加時 add）
          document.querySelectorAll("tr[data-route-edge='" + CSS.escape(routeEdgeId) + "']").forEach(function(r) {
            r.classList.add('route-row-selected');
          });
        }
        if (nexthopDeviceId) {
          // HC2: route-target クラスで手動選択（_selectedNodes）と独立
          document.querySelectorAll('.device-node[data-device="' + CSS.escape(nexthopDeviceId) + '"]').forEach(function(n) {
            n.classList.add('route-target');
          });
          var card = document.querySelector('.device-card[data-device="' + CSS.escape(nexthopDeviceId) + '"]');
          if (card) {
            card.classList.add('route-target');
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
          _selectedStaticNodes.add(nexthopDeviceId);
        }
      }
    }

    // Static route 行クリックイベント登録（修正4: 行マーキングは toggleStaticRouteHighlight 内部で管理）
    (function() {
      document.querySelectorAll('tr[data-route-edge]').forEach(function(row) {
        var routeEdgeId = row.getAttribute('data-route-edge');
        if (!routeEdgeId) return;
        var nexthopDeviceId = row.getAttribute('data-route-nexthop-device') || '';
        row.style.cursor = 'pointer';
        row.addEventListener('click', function(e) {
          e.stopPropagation();
          // 行マーキングは toggleStaticRouteHighlight 内部で一元管理
          toggleStaticRouteHighlight(routeEdgeId, nexthopDeviceId);
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
    // 多ノードB: フォーカスモード（ダブルクリックで隣接機器のみ表示）
    // ============================================================
    var _focusDevice = null;  // 現在フォーカス中のデバイスID（null = フォーカスなし）

    function clearFocusMode() {
      if (_focusDevice === null) return;
      _focusDevice = null;
      // focus-dimmed を全要素から除去
      document.querySelectorAll('.focus-dimmed').forEach(function(el) {
        el.classList.remove('focus-dimmed');
      });
      // 多ノードC: フォーカス変化をカード絞り込みに反映（_selectedNodes 変化から呼ばれる場合も）
      _updateCardFilter();
    }

    function applyFocusMode(deviceId) {
      // 隣接の定義: 直接リンク(link-edge) + BGP セッション(bgp-session) + 同一セグメント(seg-edge)。
      // 現ビュー限定の理由: 他ビューのノードは display:none のため走査不要（パフォーマンス + 誤発火防止）。
      var currentViewEl = document.querySelector('.view-' + _currentView);
      if (!currentViewEl) return;

      // 隣接デバイスを収集（link-edge/bgp-session の data-a/data-b、seg-edge 同一セグメント）
      var neighbors = new Set([deviceId]);

      // link-edge: data-a/data-b
      currentViewEl.querySelectorAll('.link-edge[data-a][data-b]').forEach(function(edge) {
        var a = edge.dataset.a;
        var b = edge.dataset.b;
        if (a === deviceId) neighbors.add(b);
        if (b === deviceId) neighbors.add(a);
      });

      // bgp-session: data-a/data-b
      currentViewEl.querySelectorAll('.bgp-session[data-a][data-b]').forEach(function(edge) {
        var a = edge.dataset.a;
        var b = edge.dataset.b;
        if (a === deviceId) neighbors.add(b);
        if (b === deviceId) neighbors.add(a);
      });

      // seg-edge: 同一セグメントのメンバー機器を隣接とみなす
      // OSPFビューの seg-edge は data-seg-id 非保持のため空振り（Physicalのみ有効）。Phase3で data-seg-id 付与予定
      var mySegs = new Set();
      currentViewEl.querySelectorAll('.seg-edge[data-device="' + CSS.escape(deviceId) + '"][data-seg-id]')
        .forEach(function(edge) { mySegs.add(edge.dataset.segId || edge.getAttribute('data-seg-id')); });
      if (mySegs.size > 0) {
        mySegs.forEach(function(segId) {
          currentViewEl.querySelectorAll('.seg-edge[data-seg-id="' + CSS.escape(segId) + '"]')
            .forEach(function(edge) {
              var dev = edge.dataset.device || edge.getAttribute('data-device');
              if (dev) neighbors.add(dev);
            });
        });
      }

      // まず focus-dimmed を全 device-node / link-edge / bgp-session / seg-edge に付与
      currentViewEl.querySelectorAll('.device-node').forEach(function(node) {
        var dev = node.dataset.device || node.getAttribute('data-device');
        if (neighbors.has(dev)) {
          node.classList.remove('focus-dimmed');
        } else {
          node.classList.add('focus-dimmed');
        }
      });

      currentViewEl.querySelectorAll('.link-edge').forEach(function(edge) {
        var a = edge.dataset.a;
        var b = edge.dataset.b;
        if (neighbors.has(a) && neighbors.has(b)) {
          edge.classList.remove('focus-dimmed');
        } else {
          edge.classList.add('focus-dimmed');
        }
      });

      currentViewEl.querySelectorAll('.bgp-session').forEach(function(edge) {
        var a = edge.dataset.a;
        var b = edge.dataset.b;
        if (a && b && neighbors.has(a) && neighbors.has(b)) {
          edge.classList.remove('focus-dimmed');
        } else {
          edge.classList.add('focus-dimmed');
        }
      });

      currentViewEl.querySelectorAll('.segment-node').forEach(function(node) {
        // セグメントに接続している機器が隣接に含まれるなら表示
        var segId = node.getAttribute('data-seg-id') || node.getAttribute('data-segment');
        var hasNeighbor = false;
        if (segId) {
          currentViewEl.querySelectorAll('.seg-edge[data-seg-id="' + CSS.escape(segId) + '"]')
            .forEach(function(edge) {
              var dev = edge.getAttribute('data-device');
              if (dev && neighbors.has(dev)) hasNeighbor = true;
            });
        }
        node.classList.toggle('focus-dimmed', !hasNeighbor);
      });

      currentViewEl.querySelectorAll('.seg-edge').forEach(function(edge) {
        var dev = edge.getAttribute('data-device');
        if (dev && neighbors.has(dev)) {
          edge.classList.remove('focus-dimmed');
        } else {
          edge.classList.add('focus-dimmed');
        }
      });
      // 多ノードC: フォーカス変化（選択/フォーカス変化からも呼ぶ）をカード絞り込みに反映
      _updateCardFilter();
    }

    // ダブルクリックイベント登録（device-node）
    // 修正3: dblclick ハンドラ冒頭で _clickTimer を clearTimeout してキャンセル
    //        （dblclick 時は選択トグルを行わずフォーカスのみ）
    // 注: _clickTimer は上の IIFE スコープで宣言済みのため直接参照できる
    (function() {
      document.querySelectorAll('.device-node').forEach(function(node) {
        node.addEventListener('dblclick', function(e) {
          e.stopPropagation();
          // 単クリック遅延タイマーをキャンセル（選択トグルの誤発火防止）
          if (_clickTimer !== null) {
            clearTimeout(_clickTimer);
            _clickTimer = null;
          }
          var deviceId = node.dataset.device || node.getAttribute('data-device');
          if (_focusDevice === deviceId) {
            // 同じノードを再ダブルクリック → フォーカス解除
            clearFocusMode();
          } else {
            clearFocusMode();
            _focusDevice = deviceId;
            applyFocusMode(deviceId);
          }
        });
      });

      // 空白ダブルクリックでフォーカス解除
      document.getElementById('topology-svg').addEventListener('dblclick', function(e) {
        if (!e.target.closest('.device-node')) {
          clearFocusMode();
        }
      });
    })();

    // ============================================================
    // 多ノードC: カード選択連動絞り込みトグル
    // ============================================================
    // _updateCardFilter: card-filter-toggle ON 時に _selectedNodes + _focusDevice に基づいて
    // カードを絞り込む。_selectedNodes 変更・clearSelection・applyFocusMode・clearFocusMode
    // 等の選択/フォーカス変化から呼び出す（トグルの change イベントだけでなく変化時にも呼ぶ）。
    function _updateCardFilter() {
      var cb = document.getElementById('card-filter-toggle');
      if (!cb || !cb.checked) {
        // OFF: 全カードを表示（card-unselected を除去）
        document.querySelectorAll('.device-card.card-unselected').forEach(function(c) {
          c.classList.remove('card-unselected');
        });
        return;
      }
      // ON: _selectedNodes + _focusDevice の機器のカードのみ表示
      var visibleDevices = new Set(_selectedNodes);
      if (_focusDevice) visibleDevices.add(_focusDevice);

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
    })();\
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
      <kbd>F</kbd> 全体表示　<kbd>Esc</kbd> リセット　ホイール=ズーム　ドラッグ=パン　ダブルクリック=隣接フォーカス
    </span>
  </header>

  <!-- ビュー切替タブ -->
  <div class="view-tabs" id="view-tabs">
    {tabs_html}
  </div>

  <div class="controls">
    <span class="controls-label" style="margin-left:0;">Search:</span>
    <input type="search" id="search-input" placeholder="hostname / IP..." oninput="filterNodes(this.value)">
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
    </div>

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
