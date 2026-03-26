"""
UCW Dashboard SPA — Single-file HTML/CSS/JS dashboard.

Exports DASHBOARD_HTML: a complete self-contained web application string.
"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UCW Dashboard</title>
<style>
:root {
  --bg: #ffffff;
  --bg-card: #f8f9fa;
  --bg-input: #ffffff;
  --text: #1a1a2e;
  --text-secondary: #6b7280;
  --accent: #2563eb;
  --accent-light: #dbeafe;
  --border: #e5e7eb;
  --shadow: 0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06);
  --shadow-lg: 0 4px 6px rgba(0,0,0,0.1), 0 2px 4px rgba(0,0,0,0.06);
  --radius: 8px;
  --bar-bg: #e5e7eb;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --graph-node: #2563eb;
  --graph-edge: #94a3b8;
  --moment-line: #2563eb;
}

[data-theme="dark"] {
  --bg: #1a1a2e;
  --bg-card: #16213e;
  --bg-input: #0f3460;
  --text: #e2e8f0;
  --text-secondary: #94a3b8;
  --accent: #60a5fa;
  --accent-light: #1e3a5f;
  --border: #334155;
  --shadow: 0 1px 3px rgba(0,0,0,0.3);
  --shadow-lg: 0 4px 6px rgba(0,0,0,0.4);
  --bar-bg: #334155;
  --success: #34d399;
  --warning: #fbbf24;
  --danger: #f87171;
  --graph-node: #60a5fa;
  --graph-edge: #475569;
  --moment-line: #60a5fa;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
}

.container { max-width: 1200px; margin: 0 auto; padding: 16px; }

/* Header */
.header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 0; margin-bottom: 24px; border-bottom: 1px solid var(--border);
}
.header h1 { font-size: 1.5rem; font-weight: 700; }
.header h1 span { color: var(--accent); }
.header-actions { display: flex; gap: 12px; align-items: center; }
.theme-toggle {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 6px 12px; cursor: pointer;
  color: var(--text); font-size: 0.875rem;
}
.health-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--success); display: inline-block;
}
.health-dot.warn { background: var(--warning); }
.health-dot.error { background: var(--danger); }

/* Search */
.search-container { position: relative; margin-bottom: 24px; }
.search-input {
  width: 100%; padding: 10px 16px; font-size: 1rem;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--bg-input); color: var(--text);
  outline: none; transition: border-color 0.2s;
}
.search-input:focus { border-color: var(--accent); }
.search-results {
  position: absolute; top: 100%; left: 0; right: 0; z-index: 100;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow-lg);
  max-height: 400px; overflow-y: auto; display: none;
}
.search-results.active { display: block; }
.search-result-item {
  padding: 10px 16px; border-bottom: 1px solid var(--border);
  cursor: pointer; transition: background 0.15s;
}
.search-result-item:hover { background: var(--accent-light); }
.search-result-item:last-child { border-bottom: none; }
.search-result-topic { font-weight: 600; font-size: 0.875rem; }
.search-result-summary { font-size: 0.8rem; color: var(--text-secondary); margin-top: 2px; }
.search-result-meta { font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px; }
.search-no-results { padding: 16px; text-align: center; color: var(--text-secondary); }

/* Cards grid */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px; margin-bottom: 24px;
}
.card {
  background: var(--bg-card); border-radius: var(--radius);
  padding: 20px; box-shadow: var(--shadow);
  border: 1px solid var(--border);
}
.card-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin-bottom: 4px; }
.card-value { font-size: 1.75rem; font-weight: 700; color: var(--accent); }
.card-sub { font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px; }

/* Sections */
.section {
  background: var(--bg-card); border-radius: var(--radius);
  padding: 20px; box-shadow: var(--shadow); border: 1px solid var(--border);
  margin-bottom: 24px;
}
.section-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 16px; }

/* Platform bar chart */
.bar-chart { display: flex; flex-direction: column; gap: 8px; }
.bar-row { display: flex; align-items: center; gap: 12px; }
.bar-label { width: 120px; font-size: 0.85rem; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { flex: 1; height: 24px; background: var(--bar-bg); border-radius: 4px; overflow: hidden; position: relative; }
.bar-fill { height: 100%; background: var(--accent); border-radius: 4px; transition: width 0.5s ease; min-width: 2px; }
.bar-value { width: 60px; font-size: 0.8rem; color: var(--text-secondary); }

/* Timeline */
.timeline { display: flex; flex-direction: column; gap: 0; }
.timeline-item {
  display: flex; gap: 12px; padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.timeline-item:last-child { border-bottom: none; }
.timeline-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); margin-top: 8px; flex-shrink: 0; }
.timeline-content { flex: 1; }
.timeline-topic { font-weight: 600; font-size: 0.875rem; }
.timeline-summary { font-size: 0.8rem; color: var(--text-secondary); }
.timeline-meta { font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px; }

/* Topics */
.topics-list { display: flex; flex-wrap: wrap; gap: 8px; }
.topic-chip {
  background: var(--accent-light); color: var(--accent); border-radius: 16px;
  padding: 4px 12px; font-size: 0.8rem; font-weight: 500;
}
.topic-count { opacity: 0.7; margin-left: 4px; }

/* Graph canvas */
.graph-canvas { width: 100%; height: 400px; border-radius: var(--radius); background: var(--bg); }

/* Moments */
.moment-card {
  padding: 12px; border-left: 3px solid var(--moment-line);
  background: var(--bg); border-radius: 0 var(--radius) var(--radius) 0;
  margin-bottom: 12px;
}
.moment-score { font-weight: 700; color: var(--accent); }
.moment-desc { font-size: 0.875rem; margin-top: 4px; }
.moment-meta { font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px; }

/* Capture health */
.health-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.health-item { font-size: 0.875rem; }
.health-label { color: var(--text-secondary); font-size: 0.75rem; }

/* Two-column layout */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }

/* Loading */
.loading { text-align: center; padding: 40px; color: var(--text-secondary); }

/* Responsive */
@media (max-width: 768px) {
  .two-col { grid-template-columns: 1fr; }
  .cards { grid-template-columns: repeat(2, 1fr); }
  .bar-label { width: 80px; font-size: 0.75rem; }
  .health-grid { grid-template-columns: 1fr; }
}
@media (max-width: 480px) {
  .cards { grid-template-columns: 1fr; }
  .header { flex-direction: column; gap: 12px; }
}
</style>
</head>
<body>
<div class="container">
  <!-- Header -->
  <div class="header">
    <h1><span>UCW</span> Dashboard</h1>
    <div class="header-actions">
      <span class="health-dot" id="healthDot" title="Checking..."></span>
      <button class="theme-toggle" id="themeToggle">Toggle Theme</button>
    </div>
  </div>

  <!-- Search -->
  <div class="search-container">
    <input type="text" class="search-input" id="searchInput" placeholder="Search cognitive events..." autocomplete="off">
    <div class="search-results" id="searchResults"></div>
  </div>

  <!-- Summary cards -->
  <div class="cards" id="summaryCards">
    <div class="card"><div class="card-label">Total Events</div><div class="card-value" id="totalEvents">--</div></div>
    <div class="card"><div class="card-label">Sessions</div><div class="card-value" id="totalSessions">--</div></div>
    <div class="card"><div class="card-label">Data Size</div><div class="card-value" id="dataSize">--</div></div>
    <div class="card"><div class="card-label">Platforms</div><div class="card-value" id="platformCount">--</div></div>
  </div>

  <!-- Two column: platforms + topics -->
  <div class="two-col">
    <div class="section">
      <div class="section-title">Platform Breakdown</div>
      <div class="bar-chart" id="platformChart"></div>
    </div>
    <div class="section">
      <div class="section-title">Top Topics</div>
      <div class="topics-list" id="topicsList"></div>
    </div>
  </div>

  <!-- Recent activity -->
  <div class="section">
    <div class="section-title">Recent Activity</div>
    <div class="timeline" id="recentActivity"><div class="loading">Loading...</div></div>
  </div>

  <!-- Knowledge graph -->
  <div class="section" id="graphSection" style="display:none">
    <div class="section-title">Knowledge Graph</div>
    <canvas class="graph-canvas" id="graphCanvas"></canvas>
  </div>

  <!-- Coherence moments -->
  <div class="section" id="momentsSection" style="display:none">
    <div class="section-title">Coherence Moments</div>
    <div id="momentsList"></div>
  </div>

  <!-- Capture health -->
  <div class="section">
    <div class="section-title">Capture Health</div>
    <div class="health-grid" id="captureHealth"><div class="loading">Loading...</div></div>
  </div>
</div>

<script>
(function() {
  "use strict";

  // Theme
  const html = document.documentElement;
  const stored = localStorage.getItem("ucw-theme");
  if (stored) {
    html.setAttribute("data-theme", stored);
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    html.setAttribute("data-theme", "dark");
  }
  document.getElementById("themeToggle").addEventListener("click", function() {
    const current = html.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    localStorage.setItem("ucw-theme", next);
    if (_graphData) renderGraph(_graphData);
  });

  // Utility
  function fmt(n) {
    if (n == null) return "--";
    return n.toLocaleString();
  }
  function fmtBytes(b) {
    if (b == null || b === 0) return "0 B";
    var units = ["B","KB","MB","GB","TB"];
    var i = 0;
    var v = b;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return (i === 0 ? v : v.toFixed(1)) + " " + units[i];
  }
  function fmtAge(ns) {
    if (!ns) return "N/A";
    var d = new Date(ns / 1e6);
    var diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return Math.floor(diff) + "s ago";
    if (diff < 3600) return Math.floor(diff / 60) + "m ago";
    if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
    return Math.floor(diff / 86400) + "d ago";
  }
  function fmtTimestamp(ns) {
    if (!ns) return "";
    return new Date(ns / 1e6).toLocaleString();
  }

  // Fetch helpers
  function api(path) {
    return fetch(path).then(function(r) { return r.json(); });
  }

  // Render dashboard
  function renderDashboard(data) {
    if (!data || data.error) {
      document.getElementById("totalEvents").textContent = "0";
      return;
    }
    document.getElementById("totalEvents").textContent = fmt(data.total_events);
    document.getElementById("totalSessions").textContent = fmt(data.sessions);
    document.getElementById("dataSize").textContent = fmtBytes(data.total_bytes);
    var platforms = data.platforms || {};
    var pkeys = Object.keys(platforms);
    document.getElementById("platformCount").textContent = fmt(pkeys.length);

    // Platform chart
    var chart = document.getElementById("platformChart");
    chart.innerHTML = "";
    var maxVal = 0;
    pkeys.forEach(function(k) { if (platforms[k] > maxVal) maxVal = platforms[k]; });
    pkeys.forEach(function(k) {
      var pct = maxVal > 0 ? (platforms[k] / maxVal * 100) : 0;
      chart.innerHTML +=
        '<div class="bar-row">' +
          '<div class="bar-label">' + k + '</div>' +
          '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div>' +
          '<div class="bar-value">' + fmt(platforms[k]) + '</div>' +
        '</div>';
    });

    // Topics
    var topics = data.top_topics || [];
    var tlist = document.getElementById("topicsList");
    tlist.innerHTML = "";
    topics.forEach(function(t) {
      tlist.innerHTML += '<span class="topic-chip">' + (t[0] || "unknown") + '<span class="topic-count">(' + t[1] + ')</span></span>';
    });

    // Capture health
    var ch = data.capture_health;
    var healthEl = document.getElementById("captureHealth");
    if (ch) {
      var dot = document.getElementById("healthDot");
      if (ch.events_last_24h > 0) { dot.className = "health-dot"; dot.title = "Healthy"; }
      else if (ch.events_last_7d > 0) { dot.className = "health-dot warn"; dot.title = "Stale"; }
      else { dot.className = "health-dot error"; dot.title = "No recent events"; }

      healthEl.innerHTML =
        '<div class="health-item"><div class="health-label">Last 24h</div><div>' + fmt(ch.events_last_24h) + ' events</div></div>' +
        '<div class="health-item"><div class="health-label">Last 7d</div><div>' + fmt(ch.events_last_7d) + ' events</div></div>' +
        '<div class="health-item"><div class="health-label">Active Platforms</div><div>' + (ch.active_platforms || []).join(", ") + '</div></div>' +
        '<div class="health-item"><div class="health-label">Last Event</div><div>' +
          (ch.last_event_age_seconds != null ? Math.floor(ch.last_event_age_seconds) + 's ago' : 'never') +
        '</div></div>';
    } else {
      healthEl.innerHTML = '<div>No health data</div>';
    }
  }

  // Render recent events
  function renderEvents(data) {
    var el = document.getElementById("recentActivity");
    var events = (data && data.events) ? data.events : [];
    if (events.length === 0) {
      el.innerHTML = '<div class="loading">No events yet</div>';
      return;
    }
    el.innerHTML = "";
    events.slice(0, 10).forEach(function(ev) {
      el.innerHTML +=
        '<div class="timeline-item">' +
          '<div class="timeline-dot"></div>' +
          '<div class="timeline-content">' +
            '<div class="timeline-topic">' + (ev.light_topic || ev.method || "event") + '</div>' +
            '<div class="timeline-summary">' + (ev.light_summary || "") + '</div>' +
            '<div class="timeline-meta">' + (ev.platform || "") + ' &middot; ' + fmtAge(ev.timestamp_ns) + '</div>' +
          '</div>' +
        '</div>';
    });
  }

  // Graph
  var _graphData = null;
  function renderGraph(data) {
    _graphData = data;
    var section = document.getElementById("graphSection");
    if (!data || !data.nodes || data.nodes.length === 0) {
      section.style.display = "none";
      return;
    }
    section.style.display = "";

    var canvas = document.getElementById("graphCanvas");
    var ctx = canvas.getContext("2d");
    var rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * (window.devicePixelRatio || 1);
    canvas.height = rect.height * (window.devicePixelRatio || 1);
    ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    var W = rect.width, H = rect.height;

    var style = getComputedStyle(document.documentElement);
    var nodeColor = style.getPropertyValue("--graph-node").trim() || "#2563eb";
    var edgeColor = style.getPropertyValue("--graph-edge").trim() || "#94a3b8";
    var textColor = style.getPropertyValue("--text").trim() || "#1a1a2e";

    // Position nodes in a force-directed-ish layout (simple spring simulation)
    var nodes = data.nodes.map(function(n, i) {
      var angle = (2 * Math.PI * i) / data.nodes.length;
      var r = Math.min(W, H) * 0.35;
      return { id: n.id, label: n.label, type: n.type, count: n.count || 1,
               x: W/2 + r * Math.cos(angle) + (Math.random() - 0.5) * 30,
               y: H/2 + r * Math.sin(angle) + (Math.random() - 0.5) * 30,
               vx: 0, vy: 0 };
    });
    var nodeMap = {};
    nodes.forEach(function(n) { nodeMap[n.id] = n; });

    var edges = (data.edges || []).filter(function(e) {
      return nodeMap[e.source] && nodeMap[e.target];
    });

    // Simple force simulation (50 iterations)
    for (var iter = 0; iter < 50; iter++) {
      // Repulsion
      for (var i = 0; i < nodes.length; i++) {
        for (var j = i + 1; j < nodes.length; j++) {
          var dx = nodes[j].x - nodes[i].x;
          var dy = nodes[j].y - nodes[i].y;
          var dist = Math.sqrt(dx*dx + dy*dy) || 1;
          var force = 5000 / (dist * dist);
          var fx = (dx / dist) * force;
          var fy = (dy / dist) * force;
          nodes[i].vx -= fx; nodes[i].vy -= fy;
          nodes[j].vx += fx; nodes[j].vy += fy;
        }
      }
      // Attraction along edges
      edges.forEach(function(e) {
        var a = nodeMap[e.source], b = nodeMap[e.target];
        if (!a || !b) return;
        var dx = b.x - a.x, dy = b.y - a.y;
        var dist = Math.sqrt(dx*dx + dy*dy) || 1;
        var force = (dist - 100) * 0.01;
        var fx = (dx / dist) * force;
        var fy = (dy / dist) * force;
        a.vx += fx; a.vy += fy;
        b.vx -= fx; b.vy -= fy;
      });
      // Center gravity
      nodes.forEach(function(n) {
        n.vx += (W/2 - n.x) * 0.001;
        n.vy += (H/2 - n.y) * 0.001;
        n.x += n.vx * 0.5;
        n.y += n.vy * 0.5;
        n.vx *= 0.8; n.vy *= 0.8;
        n.x = Math.max(30, Math.min(W - 30, n.x));
        n.y = Math.max(30, Math.min(H - 30, n.y));
      });
    }

    // Draw
    ctx.clearRect(0, 0, W, H);
    // Edges
    ctx.strokeStyle = edgeColor;
    ctx.lineWidth = 1;
    edges.forEach(function(e) {
      var a = nodeMap[e.source], b = nodeMap[e.target];
      if (!a || !b) return;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    });
    // Nodes
    nodes.forEach(function(n) {
      var r = Math.max(5, Math.min(20, 3 + Math.sqrt(n.count) * 2));
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = nodeColor;
      ctx.fill();
      ctx.fillStyle = textColor;
      ctx.font = "11px -apple-system, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(n.label, n.x, n.y + r + 14);
    });
  }

  // Moments
  function renderMoments(data) {
    var section = document.getElementById("momentsSection");
    if (!data || !Array.isArray(data) || data.length === 0) {
      section.style.display = "none";
      return;
    }
    section.style.display = "";
    var el = document.getElementById("momentsList");
    el.innerHTML = "";
    data.forEach(function(m) {
      el.innerHTML +=
        '<div class="moment-card">' +
          '<span class="moment-score">' + (m.coherence_score != null ? m.coherence_score.toFixed(2) : "--") + '</span>' +
          '<div class="moment-desc">' + (m.description || "Coherence detected") + '</div>' +
          '<div class="moment-meta">' + (m.platforms || []).join(", ") + ' &middot; ' + fmtAge(m.timestamp) + '</div>' +
        '</div>';
    });
  }

  // Search with debounce
  var searchTimer = null;
  var searchInput = document.getElementById("searchInput");
  var searchResults = document.getElementById("searchResults");

  searchInput.addEventListener("input", function() {
    clearTimeout(searchTimer);
    var q = searchInput.value.trim();
    if (!q) {
      searchResults.classList.remove("active");
      searchResults.innerHTML = "";
      return;
    }
    searchTimer = setTimeout(function() {
      api("/api/search?q=" + encodeURIComponent(q) + "&limit=10").then(function(data) {
        var results = data.results || [];
        if (results.length === 0) {
          searchResults.innerHTML = '<div class="search-no-results">No results for "' + q + '"</div>';
        } else {
          searchResults.innerHTML = results.map(function(r) {
            return '<div class="search-result-item">' +
              '<div class="search-result-topic">' + (r.topic || r.event_id || "event") + '</div>' +
              '<div class="search-result-summary">' + (r.summary || r.snippet || "") + '</div>' +
              '<div class="search-result-meta">' + (r.platform || "") + ' &middot; ' + fmtAge(r.timestamp_ns) + '</div>' +
            '</div>';
          }).join("");
        }
        searchResults.classList.add("active");
      });
    }, 300);
  });

  // Close search on click outside
  document.addEventListener("click", function(e) {
    if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
      searchResults.classList.remove("active");
    }
  });

  // Load all data
  function loadAll() {
    api("/api/dashboard").then(renderDashboard).catch(function() {});
    api("/api/events?limit=10").then(renderEvents).catch(function() {});
    api("/api/graph?limit=50").then(renderGraph).catch(function() {});
    api("/api/moments?limit=20").then(renderMoments).catch(function() {});
  }

  loadAll();
  setInterval(loadAll, 30000);
})();
</script>
</body>
</html>
"""
