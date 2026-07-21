/*
 * callgraph.js — python-review-map の callgraph フェンスブロックをインタラクティブSVGとして描画する。
 *
 * 外部依存ゼロ・ネットワークアクセスゼロ。file:// で直接開いても動く素朴な非モジュールスクリプト。
 * ページ全体で1回だけ読み込まれ、複数の .callgraph コンテナをそれぞれ独立した状態で描画する。
 */
(function () {
  "use strict";

  var SVG_NS = "http://www.w3.org/2000/svg";
  var MIN_SCALE = 0.4;
  var MAX_SCALE = 3;
  var ROW_HEIGHT = 110;
  var COL_GAP = 40;
  var NODE_HEIGHT = 40;
  var NODE_PAD_X = 14;
  var MIN_NODE_WIDTH = 90;
  var MARGIN = 40;

  // モジュール色分け: ページ内に登場する全モジュール(コールフレーム見出し+全callgraph
  // データ)をソートした一覧に、離れた色相のパレットを順に割り当てる。ハッシュ方式は
  // 色相衝突が多発したため不採用。report_template.html 側と同一実装(スクリプト読込順の
  // 都合で重複定義。変更時は両方を揃えること)。DOMから決定的に計算するので両者の
  // 割り当ては必ず一致する。
  var MODULE_HUES = [210, 25, 130, 275, 55, 175, 330, 95, 240, 15, 155, 300];
  function moduleKey(path) {
    // 末尾2セグメントに正規化: "src/shaper_db/sync/rules.py" と "sync/rules.py" を同一視
    return path.split("/").slice(-2).join("/");
  }
  function collectModuleHues() {
    var keys = {};
    var re = /—\s*(\S+\.py):\d+/;
    Array.prototype.slice.call(document.querySelectorAll("main h4")).forEach(function (h4) {
      var m = re.exec(h4.textContent || "");
      if (m) keys[moduleKey(m[1])] = true;
    });
    Array.prototype.slice.call(
      document.querySelectorAll('script[type="application/json"]')
    ).forEach(function (s) {
      try {
        var data = JSON.parse(s.textContent);
        (data.nodes || []).forEach(function (n) {
          if (n.file) keys[moduleKey(n.file)] = true;
        });
      } catch (e) {}
    });
    var map = {};
    Object.keys(keys).sort().forEach(function (k, i) {
      map[k] = MODULE_HUES[i % MODULE_HUES.length];
    });
    return map;
  }
  var moduleHueMap = null;
  function moduleHue(path) {
    if (!moduleHueMap) moduleHueMap = collectModuleHues();
    return moduleHueMap[moduleKey(path)];
  }

  function escapeText(s) {
    // DOM API (textContent) を使うため実質不要だが、念のため文字列連結経路でも安全にしておく。
    return String(s == null ? "" : s);
  }

  // Python 側 slugify (build_report.py) と同じ規則で見出しidを再現する。
  // 完全な重複解決(seenカウンタ)までは追わず、初出相当のスラグのみを求める
  // (一致する見出しが無ければ何もしない、という仕様上それで十分)。
  function slugify(text) {
    var plain = String(text).replace(/`([^`]+)`/g, "$1");
    plain = plain.replace(/[^\p{L}\p{N}_\s\-]/gu, "");
    var slug = plain.trim().toLowerCase().replace(/ /g, "-");
    return slug || "section";
  }

  function svgElement(tag, attrs) {
    var el = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      for (var key in attrs) {
        if (Object.prototype.hasOwnProperty.call(attrs, key)) {
          el.setAttribute(key, attrs[key]);
        }
      }
    }
    return el;
  }

  function measureTextWidth(text, fontSize) {
    if (!measureTextWidth._ctx) {
      var canvas = document.createElement("canvas");
      measureTextWidth._ctx = canvas.getContext("2d");
    }
    var ctx = measureTextWidth._ctx;
    ctx.font = fontSize + "px -apple-system, 'Hiragino Kaku Gothic ProN', 'Yu Gothic', sans-serif";
    return ctx.measureText(text).width;
  }

  // ノードごとのレイヤー(根からの最長経路の長さ)を素朴な緩和法で求める。
  // 循環があってもノード数+1回で必ず打ち切るため無限ループにはならない。
  // ただし循環があると層値そのものは反復回数分まで飛び飛びに大きくなりうるため、
  // 最後に compressLayers で「実際に使われている値だけ」を0,1,2,...へ詰め直し、
  // 描画上の行数がノード数程度に収まるようにする。
  function computeLayers(nodeIds, edges) {
    var layer = {};
    nodeIds.forEach(function (id) {
      layer[id] = 0;
    });
    var maxIterations = nodeIds.length + 1;
    for (var iter = 0; iter < maxIterations; iter++) {
      var changed = false;
      for (var e = 0; e < edges.length; e++) {
        var edge = edges[e];
        if (!(edge.from in layer) || !(edge.to in layer)) continue;
        if (layer[edge.to] < layer[edge.from] + 1) {
          layer[edge.to] = layer[edge.from] + 1;
          changed = true;
        }
      }
      if (!changed) break;
    }
    return compressLayers(layer);
  }

  // 実際に使われている層値だけをソートして0,1,2,...へ再マッピングする。
  // 循環込みの緩和法では層値がO(反復回数)まで飛び飛びに膨張しうるが、
  // ノードの相対順序(大小関係)は変えずに詰め直すことで行数の爆発を防ぐ。
  function compressLayers(layer) {
    var used = {};
    Object.keys(layer).forEach(function (id) {
      used[layer[id]] = true;
    });
    var sortedValues = Object.keys(used)
      .map(Number)
      .sort(function (a, b) {
        return a - b;
      });
    var remap = {};
    sortedValues.forEach(function (v, idx) {
      remap[v] = idx;
    });
    var compressed = {};
    Object.keys(layer).forEach(function (id) {
      compressed[id] = remap[layer[id]];
    });
    return compressed;
  }

  function cubicPoint(t, p0, p1, p2, p3) {
    var mt = 1 - t;
    return (
      mt * mt * mt * p0 +
      3 * mt * mt * t * p1 +
      3 * mt * t * t * p2 +
      t * t * t * p3
    );
  }

  function buildLayout(data) {
    var nodeIds = data.nodes.map(function (n) {
      return n.id;
    });
    var layer = computeLayers(nodeIds, data.edges);

    var rows = {};
    data.nodes.forEach(function (n) {
      var row = layer[n.id] || 0;
      if (!rows[row]) rows[row] = [];
      rows[row].push(n);
    });

    var fontSize = 12;
    var positions = {};
    var rowKeys = Object.keys(rows)
      .map(Number)
      .sort(function (a, b) {
        return a - b;
      });

    var maxWidth = 0;
    var maxRowRight = MARGIN;

    rowKeys.forEach(function (rowIdx) {
      var nodesInRow = rows[rowIdx];
      var x = MARGIN;
      var y = MARGIN + rowIdx * ROW_HEIGHT;
      nodesInRow.forEach(function (n) {
        var textW = measureTextWidth(n.id, fontSize);
        var w = Math.max(MIN_NODE_WIDTH, textW + NODE_PAD_X * 2);
        positions[n.id] = {
          x: x,
          y: y,
          w: w,
          h: NODE_HEIGHT,
          cx: x + w / 2,
          cy: y + NODE_HEIGHT / 2,
        };
        x += w + COL_GAP;
      });
      if (x > maxRowRight) maxRowRight = x;
    });

    var maxRow = rowKeys.length ? rowKeys[rowKeys.length - 1] : 0;
    var contentWidth = maxRowRight - COL_GAP + MARGIN;
    var contentHeight = MARGIN * 2 + (maxRow + 1) * ROW_HEIGHT;

    return { positions: positions, width: contentWidth, height: contentHeight };
  }

  function buildAdjacency(data) {
    var adj = {}; // nodeId -> [{edgeIndex, other}]
    data.nodes.forEach(function (n) {
      adj[n.id] = [];
    });
    data.edges.forEach(function (edge, idx) {
      if (adj[edge.from]) adj[edge.from].push(idx);
      if (adj[edge.to]) adj[edge.to].push(idx);
    });
    return adj;
  }

  function initGraph(container) {
    var graphId = container.id;
    var dataScript = document.getElementById(graphId + "-data");
    if (!dataScript) return;
    var data;
    try {
      data = JSON.parse(dataScript.textContent);
    } catch (err) {
      return;
    }
    if (!data.nodes || !data.nodes.length) return;

    var layout = buildLayout(data);
    var adjacency = buildAdjacency(data);
    var nodesById = {};
    data.nodes.forEach(function (n) {
      nodesById[n.id] = n;
    });

    var state = {
      scale: 1,
      tx: MARGIN,
      ty: MARGIN,
      activeNode: null,
      filterText: "",
    };

    var svg = svgElement("svg", {
      viewBox: "0 0 " + layout.width + " " + layout.height,
      preserveAspectRatio: "xMinYMin meet",
    });
    var defs = svgElement("defs");
    var arrowId = graphId + "-arrowhead";
    var marker = svgElement("marker", {
      id: arrowId,
      viewBox: "0 0 10 10",
      refX: "8",
      refY: "5",
      markerWidth: "7",
      markerHeight: "7",
      orient: "auto-start-reverse",
    });
    var arrowPath = svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z" });
    arrowPath.setAttribute("class", "callgraph-arrowhead");
    arrowPath.style.fill = "var(--muted)";
    marker.appendChild(arrowPath);
    defs.appendChild(marker);
    svg.appendChild(defs);

    var viewport = svgElement("g", { class: "callgraph-viewport" });
    svg.appendChild(viewport);

    var edgeGroup = svgElement("g", { class: "callgraph-edges" });
    var nodeGroup = svgElement("g", { class: "callgraph-nodes" });
    viewport.appendChild(edgeGroup);
    viewport.appendChild(nodeGroup);

    var edgeEls = [];
    data.edges.forEach(function (edge, idx) {
      var from = layout.positions[edge.from];
      var to = layout.positions[edge.to];
      if (!from || !to) return;
      var x1 = from.cx;
      var y1 = from.y + from.h;
      var x2 = to.cx;
      var y2 = to.y;
      var dy = Math.max(Math.abs(y2 - y1) / 2, 30);
      var c1x = x1;
      var c1y = y1 + dy;
      var c2x = x2;
      var c2y = y2 - dy;
      var d =
        "M " + x1 + " " + y1 + " C " + c1x + " " + c1y + " " + c2x + " " + c2y + " " + x2 + " " + y2;

      var g = svgElement("g", { class: "callgraph-edge" });
      var path = svgElement("path", {
        d: d,
        "marker-end": "url(#" + arrowId + ")",
      });
      g.appendChild(path);

      if (edge.label) {
        var mx = cubicPoint(0.5, x1, c1x, c2x, x2);
        var my = cubicPoint(0.5, y1, c1y, c2y, y2);
        var labelText = edge.label;
        var labelW = measureTextWidth(labelText, 10) + 8;
        var lg = svgElement("g", {
          class: "callgraph-edge-label",
          transform: "translate(" + (mx - labelW / 2) + "," + (my - 7) + ")",
        });
        var rect = svgElement("rect", {
          x: "0",
          y: "0",
          width: String(labelW),
          height: "14",
          rx: "3",
        });
        var text = svgElement("text", { x: String(labelW / 2), y: "10", "text-anchor": "middle" });
        text.textContent = escapeText(labelText);
        lg.appendChild(rect);
        lg.appendChild(text);
        g.appendChild(lg);
      }

      edgeGroup.appendChild(g);
      edgeEls.push({ el: g, from: edge.from, to: edge.to, edgeIndex: idx });
    });

    var nodeEls = {};
    data.nodes.forEach(function (n) {
      var pos = layout.positions[n.id];
      if (!pos) return;
      var isTerminal = !n.ref;
      var g = svgElement("g", {
        class: "callgraph-node" + (isTerminal ? " callgraph-terminal" : ""),
        transform: "translate(" + pos.x + "," + pos.y + ")",
      });
      var rect = svgElement("rect", {
        x: "0",
        y: "0",
        width: String(pos.w),
        height: String(pos.h),
        rx: "8",
      });
      if (n.file) {
        // file:line を持つノードはモジュール色で枠と背景を染める(凡例・コールフレームの
        // バッジと同じ割り当てなので、図と本文の対応が色で追える)
        var hue = moduleHue(n.file);
        if (hue !== undefined) {
          rect.style.stroke =
            "light-dark(hsl(" + hue + " 65% 45%), hsl(" + hue + " 65% 60%))";
          rect.style.fill =
            "light-dark(hsl(" + hue + " 65% 50% / 0.12), hsl(" + hue + " 60% 55% / 0.18))";
        }
      }
      var text = svgElement("text", {
        x: String(pos.w / 2),
        y: String(pos.h / 2 + 4),
        "text-anchor": "middle",
      });
      text.textContent = escapeText(n.id);
      g.appendChild(rect);
      g.appendChild(text);
      g.setAttribute("data-node-id", n.id);

      var titleParts = [n.id];
      if (n.ref) titleParts.push(n.ref);
      var title = svgElement("title");
      title.textContent = titleParts.join(" — ");
      g.appendChild(title);

      nodeGroup.appendChild(g);
      nodeEls[n.id] = g;
    });

    container.appendChild(svg);

    // ---- パン/ズーム ----
    function applyTransform() {
      viewport.setAttribute(
        "transform",
        "translate(" + state.tx + "," + state.ty + ") scale(" + state.scale + ")"
      );
    }
    applyTransform();

    function clampScale(s) {
      return Math.max(MIN_SCALE, Math.min(MAX_SCALE, s));
    }

    function zoomAt(factor, cx, cy) {
      var newScale = clampScale(state.scale * factor);
      var ratio = newScale / state.scale;
      state.tx = cx - (cx - state.tx) * ratio;
      state.ty = cy - (cy - state.ty) * ratio;
      state.scale = newScale;
      applyTransform();
    }

    svg.addEventListener(
      "wheel",
      function (evt) {
        evt.preventDefault();
        var rect = svg.getBoundingClientRect();
        var mx = evt.clientX - rect.left;
        var my = evt.clientY - rect.top;
        var factor = evt.deltaY < 0 ? 1.1 : 1 / 1.1;
        zoomAt(factor, mx, my);
      },
      { passive: false }
    );

    var dragging = false;
    var didDrag = false;
    var dragStartX = 0;
    var dragStartY = 0;
    var startTx = 0;
    var startTy = 0;
    // pointerdown時点(setPointerCaptureで後続イベントがsvgへ付け替えられる前)に押された
    // ノードidを記録しておく。setPointerCaptureはpointerup以降のイベントのtargetをsvg自身に
    // 付け替えるため、その後生成される"click"イベントも大抵のブラウザでsvgがtargetになり、
    // 個々のノード要素に付けたclickリスナーは発火しない(ノードクリックが無反応になる主因)。
    // pointerdown時点ならまだ付け替わっていないので、ここで拾っておく。
    var pointerDownNodeId = null;

    svg.addEventListener("pointerdown", function (evt) {
      dragging = true;
      didDrag = false;
      dragStartX = evt.clientX;
      dragStartY = evt.clientY;
      startTx = state.tx;
      startTy = state.ty;
      var nodeEl = evt.target.closest ? evt.target.closest(".callgraph-node") : null;
      pointerDownNodeId = nodeEl ? nodeEl.getAttribute("data-node-id") : null;
      container.classList.add("callgraph-dragging");
      if (svg.setPointerCapture) {
        try {
          svg.setPointerCapture(evt.pointerId);
        } catch (e) {
          /* noop */
        }
      }
    });

    svg.addEventListener("pointermove", function (evt) {
      if (!dragging) return;
      var dx = evt.clientX - dragStartX;
      var dy = evt.clientY - dragStartY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) didDrag = true;
      state.tx = startTx + dx;
      state.ty = startTy + dy;
      applyTransform();
    });

    function endDrag() {
      dragging = false;
      container.classList.remove("callgraph-dragging");
    }
    svg.addEventListener("pointerup", endDrag);
    svg.addEventListener("pointerleave", endDrag);

    svg.addEventListener("click", function () {
      if (didDrag) {
        didDrag = false;
        return;
      }
      if (pointerDownNodeId) {
        onNodeClick(pointerDownNodeId);
        return;
      }
      clearHighlight();
    });

    // ---- クリックハイライト ----
    function clearHighlight() {
      state.activeNode = null;
      Object.keys(nodeEls).forEach(function (id) {
        nodeEls[id].classList.remove("callgraph-active", "callgraph-dim");
      });
      edgeEls.forEach(function (e) {
        e.el.classList.remove("callgraph-active", "callgraph-dim");
      });
      applyFilter();
    }

    function onNodeClick(nodeId) {
      var node = nodesById[nodeId];
      if (node && node.href) {
        // 別ページへの直接リンクを持つノード(全体構成図のモジュールノード等)は
        // ローカルのハイライト/スクロールをせず、そのままページ遷移する。
        window.location.href = node.href;
        return;
      }
      if (state.activeNode === nodeId) {
        clearHighlight();
        return;
      }
      state.activeNode = nodeId;
      var connected = { nodeIds: {}, edgeIndexes: {} };
      connected.nodeIds[nodeId] = true;
      (adjacency[nodeId] || []).forEach(function (edgeIdx) {
        connected.edgeIndexes[edgeIdx] = true;
        var edge = data.edges[edgeIdx];
        connected.nodeIds[edge.from] = true;
        connected.nodeIds[edge.to] = true;
      });

      Object.keys(nodeEls).forEach(function (id) {
        var el = nodeEls[id];
        el.classList.remove("callgraph-active", "callgraph-dim");
        if (connected.nodeIds[id]) {
          el.classList.add("callgraph-active");
        } else {
          el.classList.add("callgraph-dim");
        }
      });
      edgeEls.forEach(function (e) {
        e.el.classList.remove("callgraph-active", "callgraph-dim");
        if (connected.edgeIndexes[e.edgeIndex]) {
          e.el.classList.add("callgraph-active");
        } else {
          e.el.classList.add("callgraph-dim");
        }
      });

      scrollToHeading(nodeId);
    }

    function scrollToHeading(nodeLabel) {
      // 関数連携図のノードidは関数名そのもの(references/flow-map-format.md
      // 「見出しへの明示的アンカー」節の`{#fn-関数名}`規約)なので、まず`fn-`付きの
      // 明示的アンカーを探す。無ければ旧来の自動slugify一致(全体構成図の見出し等、
      // fn-規約が無いノード向け)にフォールバックする。
      var candidates = ["fn-" + nodeLabel, slugify(nodeLabel)];
      var heading = null;
      for (var i = 0; i < candidates.length; i++) {
        heading = document.getElementById(candidates[i]);
        if (heading) break;
      }
      if (!heading) return;
      heading.scrollIntoView({ behavior: "smooth", block: "center" });
      heading.classList.add("callgraph-heading-flash");
      setTimeout(function () {
        heading.classList.remove("callgraph-heading-flash");
      }, 1500);
    }

    // ---- フィルタ ----
    function applyFilter() {
      var text = state.filterText.trim().toLowerCase();
      if (!text) {
        if (!state.activeNode) {
          Object.keys(nodeEls).forEach(function (id) {
            nodeEls[id].classList.remove("callgraph-match", "callgraph-dim");
          });
        }
        return;
      }
      Object.keys(nodeEls).forEach(function (id) {
        var el = nodeEls[id];
        var matches = id.toLowerCase().indexOf(text) !== -1;
        el.classList.toggle("callgraph-match", matches);
        el.classList.toggle("callgraph-dim", !matches);
      });
    }

    // ---- ツールバー ----
    // callgraph-wrap 内で callgraph-toolbar と callgraph はきょうだい要素(1組につき1つずつ)。
    var toolbar = container.parentNode
      ? container.parentNode.querySelector(".callgraph-toolbar")
      : null;
    if (toolbar) {
      var filterInput = toolbar.querySelector(
        '.callgraph-filter[data-graph="' + graphId + '"]'
      );
      var zoomInBtn = toolbar.querySelector(
        '.callgraph-zoom-in[data-graph="' + graphId + '"]'
      );
      var zoomOutBtn = toolbar.querySelector(
        '.callgraph-zoom-out[data-graph="' + graphId + '"]'
      );
      var zoomResetBtn = toolbar.querySelector(
        '.callgraph-zoom-reset[data-graph="' + graphId + '"]'
      );
      if (filterInput) {
        filterInput.addEventListener("input", function () {
          state.filterText = filterInput.value;
          applyFilter();
        });
      }
      if (zoomInBtn) {
        zoomInBtn.addEventListener("click", function () {
          var rect = svg.getBoundingClientRect();
          zoomAt(1.2, rect.width / 2, rect.height / 2);
        });
      }
      if (zoomOutBtn) {
        zoomOutBtn.addEventListener("click", function () {
          var rect = svg.getBoundingClientRect();
          zoomAt(1 / 1.2, rect.width / 2, rect.height / 2);
        });
      }
      if (zoomResetBtn) {
        zoomResetBtn.addEventListener("click", function () {
          state.scale = 1;
          state.tx = MARGIN;
          state.ty = MARGIN;
          applyTransform();
        });
      }
    }
  }

  function init() {
    var containers = document.querySelectorAll(".callgraph");
    containers.forEach(function (container) {
      try {
        initGraph(container);
      } catch (err) {
        // 1つのグラフの描画失敗が他のグラフやページ全体を壊さないようにする。
        if (window.console && console.warn) {
          console.warn("callgraph render failed for #" + container.id, err);
        }
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
