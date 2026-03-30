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
  --bg-surface: #f8f9fa;
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
  --heatmap-0: #e5e7eb;
  --heatmap-1: #dbeafe;
  --heatmap-2: #93c5fd;
  --heatmap-3: #3b82f6;
  --heatmap-4: #1d4ed8;
}

[data-theme="dark"] {
  --bg: #0f1117;
  --bg-surface: #1a1d27;
  --bg-card: #1a1d27;
  --bg-input: #1a1d27;
  --text: #e2e8f0;
  --text-secondary: #94a3b8;
  --accent: #6366f1;
  --accent-light: #1e1b4b;
  --border: #2e3348;
  --shadow: 0 1px 3px rgba(0,0,0,0.3);
  --shadow-lg: 0 4px 6px rgba(0,0,0,0.4);
  --bar-bg: #2e3348;
  --success: #34d399;
  --warning: #fbbf24;
  --danger: #f87171;
  --graph-node: #6366f1;
  --graph-edge: #475569;
  --moment-line: #6366f1;
  --heatmap-0: #1a1d27;
  --heatmap-1: #1e1b4b;
  --heatmap-2: #4338ca;
  --heatmap-3: #6366f1;
  --heatmap-4: #818cf8;
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

/* Bar chart */
.bar-chart { display: flex; flex-direction: column; gap: 8px; }
.bar-row { display: flex; align-items: center; gap: 12px; cursor: pointer; border-radius: 4px; padding: 2px 4px; transition: background 0.15s; }
.bar-row:hover { background: var(--accent-light); }
.bar-label { width: 140px; font-size: 0.85rem; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { flex: 1; height: 24px; background: var(--bar-bg); border-radius: 4px; overflow: hidden; position: relative; }
.bar-fill { height: 100%; background: var(--accent); border-radius: 4px; transition: width 0.5s ease; min-width: 2px; }
.bar-value { width: 80px; font-size: 0.8rem; color: var(--text-secondary); }
.bar-pct { font-size: 0.75rem; color: var(--text-secondary); width: 40px; text-align: right; }

/* Heatmap */
.heatmap-container { overflow-x: auto; }
.heatmap-grid {
  display: grid;
  grid-template-rows: repeat(7, 16px);
  grid-auto-flow: column;
  gap: 3px;
}
.heatmap-cell {
  width: 16px; height: 16px; border-radius: 3px;
  background: var(--heatmap-0);
  transition: background 0.2s;
}
.heatmap-cell:hover { outline: 2px solid var(--accent); outline-offset: 1px; }
.heatmap-cell[data-level="0"] { background: var(--heatmap-0); }
.heatmap-cell[data-level="1"] { background: var(--heatmap-1); }
.heatmap-cell[data-level="2"] { background: var(--heatmap-2); }
.heatmap-cell[data-level="3"] { background: var(--heatmap-3); }
.heatmap-cell[data-level="4"] { background: var(--heatmap-4); }
.heatmap-legend { display: flex; gap: 4px; align-items: center; margin-top: 12px; font-size: 0.75rem; color: var(--text-secondary); }
.heatmap-legend-cell { width: 12px; height: 12px; border-radius: 2px; }
.heatmap-day-labels { display: grid; grid-template-rows: repeat(7, 16px); gap: 3px; margin-right: 6px; font-size: 0.65rem; color: var(--text-secondary); align-items: center; }
.heatmap-wrapper { display: flex; align-items: start; }
.heatmap-tooltip {
  position: fixed; background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 6px; padding: 6px 10px; font-size: 0.75rem;
  box-shadow: var(--shadow-lg); pointer-events: none; z-index: 1000; display: none;
}

/* Search */
.search-container { position: relative; margin-bottom: 24px; }
.search-input {
  width: 100%; padding: 10px 16px; font-size: 1rem;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--bg-input); color: var(--text);
  outline: none; transition: border-color 0.2s;
}
.search-input:focus { border-color: var(--accent); }
.search-hint { font-size: 0.75rem; color: var(--text-secondary); margin-top: 6px; }
.search-hint code { background: var(--bg-surface); padding: 1px 6px; border-radius: 4px; font-family: monospace; }
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

/* Topic trends canvas */
.trends-canvas { width: 100%; height: 220px; border-radius: var(--radius); background: var(--bg); }
.trends-legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; font-size: 0.8rem; }
.trends-legend-item { display: flex; align-items: center; gap: 6px; }
.trends-legend-dot { width: 10px; height: 10px; border-radius: 50%; }

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
  .bar-label { width: 100px; font-size: 0.75rem; }
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

  <!-- 1. Summary cards -->
  <div class="cards" id="summaryCards">
    <div class="card"><div class="card-label">Total Events</div><div class="card-value" id="totalEvents">--</div></div>
    <div class="card"><div class="card-label">Sessions</div><div class="card-value" id="totalSessions">--</div></div>
    <div class="card"><div class="card-label">Data Size</div><div class="card-value" id="dataSize">--</div></div>
    <div class="card"><div class="card-label">Platforms</div><div class="card-value" id="platformCount">--</div></div>
  </div>

  <!-- 2. Projects breakdown -->
  <div class="section" id="projectsSection" style="display:none">
    <div class="section-title">Projects Breakdown</div>
    <div class="bar-chart" id="projectsChart"></div>
  </div>

  <!-- 3. Activity heatmap -->
  <div class="section" id="heatmapSection" style="display:none">
    <div class="section-title">Activity (Last 30 Days)</div>
    <div class="heatmap-container">
      <div class="heatmap-wrapper">
        <div class="heatmap-day-labels" id="heatmapDayLabels"></div>
        <div class="heatmap-grid" id="heatmapGrid"></div>
      </div>
    </div>
    <div class="heatmap-legend" id="heatmapLegend">
      <span>Less</span>
      <div class="heatmap-legend-cell" style="background:var(--heatmap-0)"></div>
      <div class="heatmap-legend-cell" style="background:var(--heatmap-1)"></div>
      <div class="heatmap-legend-cell" style="background:var(--heatmap-2)"></div>
      <div class="heatmap-legend-cell" style="background:var(--heatmap-3)"></div>
      <div class="heatmap-legend-cell" style="background:var(--heatmap-4)"></div>
      <span>More</span>
    </div>
    <div class="heatmap-tooltip" id="heatmapTooltip"></div>
  </div>

  <!-- 4. Search -->
  <div class="search-container">
    <input type="text" class="search-input" id="searchInput" placeholder="Search cognitive events..." autocomplete="off">
    <div class="search-hint">Try <code>project:friendlyface</code> or <code>project:ucw</code> to filter by project</div>
    <div class="search-results" id="searchResults"></div>
  </div>

  <!-- 5. Topic trends -->
  <div class="section" id="trendsSection" style="display:none">
    <div class="section-title">Topic Trends (30 Days)</div>
    <canvas class="trends-canvas" id="trendsCanvas"></canvas>
    <div class="trends-legend" id="trendsLegend"></div>
  </div>

  <!-- 6. Recent activity -->
  <div class="section">
    <div class="section-title">Recent Activity</div>
    <div class="timeline" id="recentActivity"><div class="loading">Loading...</div></div>
  </div>

  <!-- 7. Capture health -->
  <div class="section">
    <div class="section-title">Capture Health</div>
    <div class="health-grid" id="captureHealth"><div class="loading">Loading...</div></div>
  </div>
</div>

<script>
(function() {
  "use strict";

  // Theme
  var html = document.documentElement;
  var stored = localStorage.getItem("ucw-theme");
  if (stored) {
    html.setAttribute("data-theme", stored);
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    html.setAttribute("data-theme", "dark");
  }
  document.getElementById("themeToggle").addEventListener("click", function() {
    var current = html.getAttribute("data-theme");
    var next = current === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    localStorage.setItem("ucw-theme", next);
    if (_topicsData) renderTrends(_topicsData);
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

    // Update search placeholder with event count
    var searchInput = document.getElementById("searchInput");
    if (data.total_events) {
      searchInput.placeholder = "Searching " + fmt(data.total_events) + " events...";
    }

    // Projects breakdown
    var projects = data.projects || [];
    var projSection = document.getElementById("projectsSection");
    var projChart = document.getElementById("projectsChart");
    if (projects.length > 0) {
      projSection.style.display = "";
      projChart.innerHTML = "";
      var maxCount = 0;
      projects.forEach(function(p) { if (p.count > maxCount) maxCount = p.count; });
      projects.forEach(function(p) {
        var pct = maxCount > 0 ? (p.count / maxCount * 100) : 0;
        var row = document.createElement("div");
        row.className = "bar-row";
        row.setAttribute("data-project", p.name);
        row.innerHTML =
          '<div class="bar-label">' + p.name + '</div>' +
          '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div>' +
          '<div class="bar-value">' + fmt(p.count) + '</div>' +
          '<div class="bar-pct">' + p.pct + '%</div>';
        row.addEventListener("click", function() {
          var input = document.getElementById("searchInput");
          input.value = "project:" + p.name;
          input.dispatchEvent(new Event("input"));
          input.focus();
        });
        projChart.appendChild(row);
      });
    } else {
      projSection.style.display = "none";
    }

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

  // Render activity heatmap
  function renderHeatmap(data) {
    var section = document.getElementById("heatmapSection");
    var grid = document.getElementById("heatmapGrid");
    var dayLabels = document.getElementById("heatmapDayLabels");
    var days = (data && data.days) ? data.days : [];

    if (days.length === 0) {
      section.style.display = "none";
      return;
    }
    section.style.display = "";

    // Build date->count map
    var countMap = {};
    var maxCount = 0;
    days.forEach(function(d) {
      countMap[d.date] = d.count;
      if (d.count > maxCount) maxCount = d.count;
    });

    // Generate last 35 days (5 weeks) to fill grid
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var allDays = [];
    // Start from the most recent Sunday that is >= 34 days ago
    var startDate = new Date(today);
    startDate.setDate(startDate.getDate() - 34);
    // Align to Sunday
    var dayOfWeek = startDate.getDay();
    startDate.setDate(startDate.getDate() - dayOfWeek);

    var d = new Date(startDate);
    while (d <= today) {
      allDays.push(new Date(d));
      d.setDate(d.getDate() + 1);
    }

    // Day labels
    var dayNames = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
    dayLabels.innerHTML = "";
    for (var i = 0; i < 7; i++) {
      var label = document.createElement("div");
      label.textContent = (i % 2 === 1) ? dayNames[i] : "";
      dayLabels.appendChild(label);
    }

    // Build grid cells
    grid.innerHTML = "";
    var tooltip = document.getElementById("heatmapTooltip");
    allDays.forEach(function(date) {
      var dateStr = date.toISOString().split("T")[0];
      var count = countMap[dateStr] || 0;
      var level = 0;
      if (count > 0 && maxCount > 0) {
        var ratio = count / maxCount;
        if (ratio > 0.75) level = 4;
        else if (ratio > 0.5) level = 3;
        else if (ratio > 0.25) level = 2;
        else level = 1;
      }
      var cell = document.createElement("div");
      cell.className = "heatmap-cell";
      cell.setAttribute("data-level", level);
      cell.setAttribute("data-date", dateStr);
      cell.setAttribute("data-count", count);
      cell.addEventListener("mouseenter", function(e) {
        tooltip.textContent = count + " events on " + dateStr;
        tooltip.style.display = "block";
        tooltip.style.left = (e.clientX + 10) + "px";
        tooltip.style.top = (e.clientY - 30) + "px";
      });
      cell.addEventListener("mouseleave", function() {
        tooltip.style.display = "none";
      });
      grid.appendChild(cell);
    });
  }

  // Topic trends
  var _topicsData = null;
  var TREND_COLORS = ["#6366f1","#10b981","#f59e0b","#ef4444","#3b82f6","#ec4899","#8b5cf6","#14b8a6"];

  function renderTrends(data) {
    _topicsData = data;
    var section = document.getElementById("trendsSection");
    var topics = (data && data.topics) ? data.topics : {};
    var topicNames = Object.keys(topics);

    if (topicNames.length === 0) {
      section.style.display = "none";
      return;
    }
    section.style.display = "";

    // Take top 5
    topicNames = topicNames.slice(0, 5);

    // Collect all dates and sort ascending
    var dateSet = {};
    topicNames.forEach(function(name) {
      topics[name].forEach(function(d) { dateSet[d.date] = true; });
    });
    var dates = Object.keys(dateSet).sort();
    if (dates.length < 2) {
      section.style.display = "none";
      return;
    }

    // Build series: for each topic, map date -> count
    var series = topicNames.map(function(name) {
      var map = {};
      topics[name].forEach(function(d) { map[d.date] = d.count; });
      return { name: name, values: dates.map(function(d) { return map[d] || 0; }) };
    });

    // Canvas setup
    var canvas = document.getElementById("trendsCanvas");
    var rect = canvas.getBoundingClientRect();
    var dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    var ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    var W = rect.width, H = rect.height;

    var style = getComputedStyle(document.documentElement);
    var bgColor = style.getPropertyValue("--bg").trim();
    var textColor = style.getPropertyValue("--text-secondary").trim();

    ctx.clearRect(0, 0, W, H);

    var padLeft = 40, padRight = 16, padTop = 16, padBottom = 30;
    var chartW = W - padLeft - padRight;
    var chartH = H - padTop - padBottom;

    // Stack the values
    var stacked = [];
    for (var di = 0; di < dates.length; di++) {
      var cumulative = 0;
      var col = [];
      for (var si = 0; si < series.length; si++) {
        var val = series[si].values[di];
        col.push({ y0: cumulative, y1: cumulative + val });
        cumulative += val;
      }
      stacked.push({ total: cumulative, layers: col });
    }

    var maxY = 0;
    stacked.forEach(function(s) { if (s.total > maxY) maxY = s.total; });
    if (maxY === 0) maxY = 1;

    function xPos(i) { return padLeft + (i / (dates.length - 1)) * chartW; }
    function yPos(v) { return padTop + chartH - (v / maxY) * chartH; }

    // Draw stacked areas (bottom to top)
    for (var si = series.length - 1; si >= 0; si--) {
      ctx.beginPath();
      ctx.moveTo(xPos(0), yPos(stacked[0].layers[si].y0));
      for (var di = 0; di < dates.length; di++) {
        ctx.lineTo(xPos(di), yPos(stacked[di].layers[si].y1));
      }
      for (var di = dates.length - 1; di >= 0; di--) {
        ctx.lineTo(xPos(di), yPos(stacked[di].layers[si].y0));
      }
      ctx.closePath();
      ctx.fillStyle = TREND_COLORS[si % TREND_COLORS.length] + "80";
      ctx.fill();
      ctx.strokeStyle = TREND_COLORS[si % TREND_COLORS.length];
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (var di = 0; di < dates.length; di++) {
        if (di === 0) ctx.moveTo(xPos(di), yPos(stacked[di].layers[si].y1));
        else ctx.lineTo(xPos(di), yPos(stacked[di].layers[si].y1));
      }
      ctx.stroke();
    }

    // Y axis labels
    ctx.fillStyle = textColor;
    ctx.font = "10px -apple-system, sans-serif";
    ctx.textAlign = "right";
    for (var i = 0; i <= 4; i++) {
      var yVal = Math.round(maxY * i / 4);
      var y = yPos(yVal);
      ctx.fillText(yVal, padLeft - 6, y + 3);
      ctx.strokeStyle = textColor + "30";
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(padLeft, y);
      ctx.lineTo(W - padRight, y);
      ctx.stroke();
    }

    // X axis labels (show ~5 dates)
    ctx.textAlign = "center";
    var step = Math.max(1, Math.floor(dates.length / 5));
    for (var i = 0; i < dates.length; i += step) {
      var parts = dates[i].split("-");
      ctx.fillText(parts[1] + "/" + parts[2], xPos(i), H - 8);
    }

    // Legend
    var legend = document.getElementById("trendsLegend");
    legend.innerHTML = "";
    topicNames.forEach(function(name, idx) {
      legend.innerHTML +=
        '<div class="trends-legend-item">' +
        '<div class="trends-legend-dot" style="background:' + TREND_COLORS[idx % TREND_COLORS.length] + '"></div>' +
        '<span>' + name + '</span></div>';
    });
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

  // Search with debounce
  var searchTimer = null;
  var searchInput = document.getElementById("searchInput");
  var searchResults = document.getElementById("searchResults");

  function doSearch(q) {
    // Handle project: filter syntax
    var searchQ = q;
    var match = q.match(/^project:(\S+)$/);
    if (match) {
      searchQ = match[1];
    }
    api("/api/search?q=" + encodeURIComponent(searchQ) + "&limit=10").then(function(data) {
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
  }

  searchInput.addEventListener("input", function() {
    clearTimeout(searchTimer);
    var q = searchInput.value.trim();
    if (!q) {
      searchResults.classList.remove("active");
      searchResults.innerHTML = "";
      return;
    }
    searchTimer = setTimeout(function() { doSearch(q); }, 300);
  });

  searchInput.addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
      clearTimeout(searchTimer);
      var q = searchInput.value.trim();
      if (!q) return;
      doSearch(q);
    }
  });

  document.addEventListener("click", function(e) {
    if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
      searchResults.classList.remove("active");
    }
  });

  // Load all data
  function loadAll() {
    api("/api/dashboard").then(renderDashboard).catch(function() {});
    api("/api/events?limit=10").then(renderEvents).catch(function() {});
    api("/api/activity?days=30").then(renderHeatmap).catch(function() {});
    api("/api/topics?days=30").then(renderTrends).catch(function() {});
  }

  loadAll();
  setInterval(loadAll, 30000);
})();
</script>
</body>
</html>
"""
