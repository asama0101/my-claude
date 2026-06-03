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

    body {
      font-family: var(--font-main);
      background: #f3f4f6;
      color: #111827;
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

    #svg-container {
      overflow: hidden;
      background: #fff;
      border-bottom: 1px solid var(--color-card-border);
      cursor: grab;
      position: relative;
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
        var aNode = currentViewEl.querySelector('.device-node[data-device="' + link.dataset.a + '"]');
        var bNode = currentViewEl.querySelector('.device-node[data-device="' + link.dataset.b + '"]');
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
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        scale = Math.max(0.2, Math.min(5.0, scale * delta));
        applyTransform();
      }, { passive: false });

      // パン（マウスドラッグ）
      container.addEventListener('mousedown', function(e) {
        if (e.target.closest('.device-node') || e.target.closest('.link-edge')) return;
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

      // キーボード
      document.addEventListener('keydown', function(e) {
        if (e.key === 'f' || e.key === 'F') {
          // 全体表示（リセット）
          scale = 1.0;
          translateX = 0;
          translateY = 0;
          applyTransform();
        } else if (e.key === 'Escape') {
          // 選択/ハイライト解除 + 表示リセット
          clearSelection();
          scale = 1.0;
          translateX = 0;
          translateY = 0;
          applyTransform();
        }
      });

      applyTransform();
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
        // リンクの highlighted 除去: _selectedLinks に含まれるものは固定ハイライトを保持
        allLinks.forEach(function(l) {
          var lid = l.getAttribute('data-link-id');
          if (!_selectedLinks.has(lid)) {
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
      allNodes.forEach(function(node) {
        node.addEventListener('click', function(e) {
          e.stopPropagation();
          var deviceId = node.dataset.device;
          var wasSelected = node.classList.contains('selected');
          if (wasSelected) {
            // トグル: 解除
            node.classList.remove('selected');
            var card = document.querySelector('.device-card[data-device="' + deviceId + '"]');
            if (card) card.classList.remove('selected');
            _selectedNodes.delete(deviceId);
          } else {
            // 累積選択
            node.classList.add('selected');
            var card = document.querySelector('.device-card[data-device="' + deviceId + '"]');
            if (card) {
              card.classList.add('selected');
              card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
            _selectedNodes.add(deviceId);
          }
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

    function clearSelection() {
      document.querySelectorAll('.device-node.selected').forEach(function(n) {
        n.classList.remove('selected');
      });
      document.querySelectorAll('.device-card.selected').forEach(function(c) {
        c.classList.remove('selected');
      });
      _selectedNodes.clear();
      // リンク・IF 行ハイライトも同時解除（Esc で全解除）
      clearLinkHighlight();
    }

    function clearLinkHighlight() {
      document.querySelectorAll('.link-edge.highlighted').forEach(function(l) {
        l.classList.remove('highlighted');
      });
      document.querySelectorAll('tr.highlighted').forEach(function(r) {
        r.classList.remove('highlighted');
      });
      _selectedLinks.clear();
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
            document.querySelectorAll('.device-node[data-device="' + deviceId + '"]')
              .forEach(function(n) { n.classList.remove('selected'); });
          } else {
            // 累積選択
            card.classList.add('selected');
            _selectedNodes.add(deviceId);
            document.querySelectorAll('.device-node[data-device="' + deviceId + '"]')
              .forEach(function(n) { n.classList.add('selected'); });
          }
        });
      });
    })();

    // IF行↔リンク双方向ハイライト（トグル: 2回目クリックで解除）
    function toggleIfRowHighlight(linkId) {
      if (!linkId) return;
      var isHighlighted = _selectedLinks.has(linkId);
      if (isHighlighted) {
        // 解除
        _selectedLinks.delete(linkId);
        document.querySelectorAll('[data-link-id="' + linkId + '"]').forEach(function(el) {
          el.classList.remove('highlighted');
        });
      } else {
        // 追加ハイライト
        _selectedLinks.add(linkId);
        document.querySelectorAll('[data-link-id="' + linkId + '"]').forEach(function(el) {
          el.classList.add('highlighted');
        });
      }
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

      // 全ビューのノードを制御
      document.querySelectorAll('.device-node[data-device="' + deviceId + '"]')
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
      var card = document.querySelector('.device-card[data-device="' + deviceId + '"]');
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
      <kbd>F</kbd> 全体表示　<kbd>Esc</kbd> リセット　ホイール=ズーム　ドラッグ=パン
    </span>
  </header>

  <!-- ビュー切替タブ -->
  <div class="view-tabs" id="view-tabs">
    {tabs_html}
  </div>

  <div class="controls">
    <span class="controls-label">Layers:</span>
    {toggles_html}
    <span class="controls-label" style="margin-left:12px;">Search:</span>
    <input type="search" id="search-input" placeholder="hostname / IP..." oninput="filterNodes(this.value)">
  </div>

  {node_filter_html}

  <div id="svg-container" style="width:100%;height:{svg_height}px;">
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
  </div>

  <div id="cards-section">
    <h2>Device Details</h2>
    <div class="cards-grid">
      {cards_html}
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
