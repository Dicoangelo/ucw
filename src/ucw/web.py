"""
UCW Web Dashboard Server — stdlib HTTP server with JSON API endpoints.

Serves a single-page dashboard app and exposes REST-ish API endpoints
for dashboard data, search, events, graph, moments, and health.
"""

import json
import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ucw.config import Config

# Server start time for uptime calculation
_start_time = None


def _json_response(handler, data, status=200):
    """Send a JSON response with CORS headers."""
    body = json.dumps(data, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    _add_cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler, html, status=200):
    """Send an HTML response with CORS headers."""
    body = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    _add_cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)


def _add_cors_headers(handler):
    """Add CORS headers to response."""
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def _get_db_path():
    """Get the database path from Config."""
    return Config.DB_PATH


def _get_db_size():
    """Get database file size in bytes."""
    db_path = _get_db_path()
    try:
        return os.path.getsize(str(db_path))
    except OSError:
        return 0


def _get_event_count():
    """Get total event count from database."""
    db_path = _get_db_path()
    if not Path(db_path).exists():
        return 0
    try:
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM cognitive_events").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


class _RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for UCW dashboard API."""

    def log_message(self, format, *args):
        """Suppress default stderr logging."""
        pass

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        _add_cors_headers(self)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        """Route GET requests to appropriate handler."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        routes = {
            "/": self._handle_index,
            "/api/dashboard": self._handle_dashboard,
            "/api/search": self._handle_search,
            "/api/events": self._handle_events,
            "/api/activity": self._handle_activity,
            "/api/topics": self._handle_topics,
            "/api/health": self._handle_health,
            "/api/graph": self._handle_graph,
            "/api/moments": self._handle_moments,
        }

        handler = routes.get(path)
        if handler:
            try:
                handler(params)
            except Exception as exc:
                _json_response(self, {"error": str(exc)}, status=500)
        else:
            _json_response(self, {"error": "Not found"}, status=404)

    def _handle_index(self, params):
        """Serve the SPA HTML."""
        from ucw.web_ui import DASHBOARD_HTML
        _html_response(self, DASHBOARD_HTML)

    def _handle_dashboard(self, params):
        """Return dashboard aggregate data."""
        from ucw.dashboard import get_dashboard_data
        data = get_dashboard_data()
        if data is None:
            _json_response(self, {"error": "No database found"}, status=404)
        else:
            _json_response(self, data)

    def _handle_search(self, params):
        """Search cognitive events."""
        query = params.get("q", [""])[0]
        if not query:
            _json_response(self, {"results": [], "method": "none", "query": ""})
            return

        limit = int(params.get("limit", ["10"])[0])
        platform = params.get("platform", [None])[0]

        try:
            from ucw.search import search as ucw_search
            kwargs = {"limit": limit}
            if platform:
                kwargs["platform"] = platform
            results, method = ucw_search(_get_db_path(), query, **kwargs)
            _json_response(self, {
                "results": results,
                "method": method,
                "query": query,
                "count": len(results),
            })
        except Exception as exc:
            _json_response(self, {"error": str(exc), "results": []}, status=500)

    def _handle_events(self, params):
        """Return paginated cognitive events."""
        limit = int(params.get("limit", ["20"])[0])
        offset = int(params.get("offset", ["0"])[0])
        platform = params.get("platform", [None])[0]

        db_path = _get_db_path()
        if not Path(db_path).exists():
            _json_response(self, {"events": [], "total": 0, "limit": limit, "offset": offset})
            return

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            where = ""
            query_params = []
            if platform:
                where = "WHERE platform = ?"
                query_params.append(platform)

            total = conn.execute(
                f"SELECT COUNT(*) FROM cognitive_events {where}",
                query_params,
            ).fetchone()[0]

            rows = conn.execute(
                f"SELECT event_id, session_id, timestamp_ns, direction, stage, "
                f"method, platform, light_topic, light_summary, "
                f"instinct_gut_signal, content_length "
                f"FROM cognitive_events {where} "
                f"ORDER BY timestamp_ns DESC LIMIT ? OFFSET ?",
                query_params + [limit, offset],
            ).fetchall()

            events = [dict(r) for r in rows]
            _json_response(self, {
                "events": events,
                "total": total,
                "limit": limit,
                "offset": offset,
            })
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)
        finally:
            conn.close()

    def _handle_activity(self, params):
        """Return daily event counts for a heatmap."""
        days = int(params.get("days", ["30"])[0])
        db_path = _get_db_path()
        if not Path(db_path).exists():
            _json_response(self, {"days": []})
            return

        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT date(timestamp_ns/1000000000, 'unixepoch') as d, "
                "COUNT(*) as c FROM cognitive_events "
                "WHERE is_noise=0 OR is_noise IS NULL "
                "GROUP BY d ORDER BY d DESC LIMIT ?",
                (days,),
            ).fetchall()
            result = [{"date": r[0], "count": r[1]} for r in rows]
            _json_response(self, {"days": result})
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)
        finally:
            conn.close()

    def _handle_topics(self, params):
        """Return topic counts per day for trend chart."""
        days = int(params.get("days", ["30"])[0])
        db_path = _get_db_path()
        if not Path(db_path).exists():
            _json_response(self, {"topics": {}})
            return

        conn = sqlite3.connect(str(db_path))
        try:
            # Get top 8 topics
            top = conn.execute(
                "SELECT light_topic, COUNT(*) as c FROM cognitive_events "
                "WHERE light_topic IS NOT NULL "
                "AND (is_noise=0 OR is_noise IS NULL) "
                "GROUP BY light_topic ORDER BY c DESC LIMIT 8",
            ).fetchall()
            topic_names = [r[0] for r in top]

            topics = {}
            for name in topic_names:
                rows = conn.execute(
                    "SELECT date(timestamp_ns/1000000000, 'unixepoch') as d, "
                    "COUNT(*) as c FROM cognitive_events "
                    "WHERE light_topic = ? "
                    "AND (is_noise=0 OR is_noise IS NULL) "
                    "GROUP BY d ORDER BY d DESC LIMIT ?",
                    (name, days),
                ).fetchall()
                topics[name] = [{"date": r[0], "count": r[1]} for r in rows]

            _json_response(self, {"topics": topics})
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)
        finally:
            conn.close()

    def _handle_health(self, params):
        """Return server health status."""
        global _start_time
        uptime = time.time() - _start_time if _start_time else 0
        _json_response(self, {
            "status": "ok",
            "uptime": round(uptime, 2),
            "db_size": _get_db_size(),
            "event_count": _get_event_count(),
        })

    def _handle_graph(self, params):
        """Return knowledge graph nodes and edges."""
        limit = int(params.get("limit", ["50"])[0])
        db_path = _get_db_path()
        if not Path(db_path).exists():
            _json_response(self, {"nodes": [], "edges": []})
            return

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Entities as nodes
            rows = conn.execute(
                "SELECT entity_id, name, type, event_count "
                "FROM entities ORDER BY event_count DESC LIMIT ?",
                (limit,),
            ).fetchall()
            nodes = [
                {"id": r["entity_id"], "label": r["name"],
                 "type": r["type"], "count": r["event_count"]}
                for r in rows
            ]

            # Relationships as edges
            entity_ids = [n["id"] for n in nodes]
            if entity_ids:
                placeholders = ",".join("?" for _ in entity_ids)
                edge_rows = conn.execute(
                    f"SELECT source_entity_id, target_entity_id, type "
                    f"FROM entity_relationships "
                    f"WHERE source_entity_id IN ({placeholders}) "
                    f"OR target_entity_id IN ({placeholders}) "
                    f"LIMIT ?",
                    entity_ids + entity_ids + [limit * 2],
                ).fetchall()
                edges = [
                    {"source": r["source_entity_id"],
                     "target": r["target_entity_id"],
                     "label": r["type"]}
                    for r in edge_rows
                ]
            else:
                edges = []

            _json_response(self, {"nodes": nodes, "edges": edges})
        except sqlite3.OperationalError:
            # Tables don't exist yet
            _json_response(self, {"nodes": [], "edges": []})
        finally:
            conn.close()

    def _handle_moments(self, params):
        """Return coherence moments."""
        limit = int(params.get("limit", ["20"])[0])
        db_path = _get_db_path()
        if not Path(db_path).exists():
            _json_response(self, [])
            return

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT description, coherence_score, detected_ns, platform "
                "FROM coherence_moments "
                "ORDER BY detected_ns DESC LIMIT ?",
                (limit,),
            ).fetchall()

            moments = [
                {
                    "description": r["description"],
                    "coherence_score": r["coherence_score"],
                    "timestamp": r["detected_ns"],
                    "platforms": [r["platform"]],
                }
                for r in rows
            ]
            _json_response(self, moments)
        except sqlite3.OperationalError:
            _json_response(self, [])
        finally:
            conn.close()


class UCWWebServer:
    """UCW Dashboard web server.

    Usage (blocking, for CLI):
        server = UCWWebServer("127.0.0.1", 7077)
        server.serve_forever()

    Usage (background, for tests):
        server = UCWWebServer()
        server.start("127.0.0.1", 7077)
        ...
        server.stop()
    """

    def __init__(self, host=None, port=None):
        self._host = host
        self._port = port
        self._server = None
        self._thread = None

    def serve_forever(self):
        """Start the server (blocking). Uses host/port from constructor."""
        global _start_time
        _start_time = time.time()
        host = self._host or "127.0.0.1"
        port = self._port or 7077
        self._server = HTTPServer((host, port), _RequestHandler)
        self._server.serve_forever()

    def start(self, host="127.0.0.1", port=7077):
        """Start the web server in a background thread."""
        global _start_time
        _start_time = time.time()
        self._server = HTTPServer((host, port), _RequestHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True,
        )
        self._thread.start()
        return self._server

    def stop(self):
        """Stop the web server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
