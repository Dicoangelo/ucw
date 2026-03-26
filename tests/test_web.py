"""Tests for the UCW web dashboard server."""

import json
import sqlite3
import time
import urllib.error
import urllib.request

import pytest

from ucw.config import Config
from ucw.db.sqlite import SCHEMA_SQL
from ucw.web import UCWWebServer


def _find_free_port():
    """Find a free TCP port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _insert_sample_events(conn, count=5):
    """Insert sample cognitive events into the database."""
    now_ns = time.time_ns()
    for i in range(count):
        conn.execute(
            "INSERT INTO cognitive_events "
            "(event_id, session_id, timestamp_ns, direction, stage, "
            "method, platform, light_topic, light_summary, "
            "instinct_gut_signal, content_length, data_content) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"evt-{i}",
                "sess-1",
                now_ns - (i * 1_000_000_000),
                "inbound",
                "capture",
                "test_method",
                "claude" if i % 2 == 0 else "cursor",
                f"topic-{i}",
                f"Summary for event {i}",
                "neutral" if i % 2 == 0 else "curious",
                100 + i * 50,
                f"Content for event {i} about testing",
            ),
        )
    conn.execute(
        "INSERT INTO sessions (session_id, started_ns, platform) VALUES (?, ?, ?)",
        ("sess-1", now_ns - 10_000_000_000, "claude"),
    )
    conn.commit()


def _insert_sample_entities(conn):
    """Insert sample knowledge graph entities and relationships."""
    now_ns = time.time_ns()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entities (
            entity_id       TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            type            TEXT NOT NULL,
            confidence      REAL DEFAULT 0.5,
            first_seen_ns   INTEGER NOT NULL,
            last_seen_ns    INTEGER NOT NULL,
            event_count     INTEGER DEFAULT 1,
            metadata        TEXT
        );
        CREATE TABLE IF NOT EXISTS entity_relationships (
            rel_id              TEXT PRIMARY KEY,
            source_entity_id    TEXT NOT NULL,
            target_entity_id    TEXT NOT NULL,
            type                TEXT NOT NULL,
            weight              REAL DEFAULT 0.1,
            evidence_event_ids  TEXT,
            first_seen_ns       INTEGER NOT NULL,
            last_seen_ns        INTEGER NOT NULL,
            occurrence_count    INTEGER DEFAULT 1
        );
    """)
    conn.execute(
        "INSERT INTO entities (entity_id, name, type, first_seen_ns, last_seen_ns, event_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("ent-1", "Python", "technology", now_ns, now_ns, 5),
    )
    conn.execute(
        "INSERT INTO entities (entity_id, name, type, first_seen_ns, last_seen_ns, event_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("ent-2", "UCW", "project", now_ns, now_ns, 3),
    )
    conn.execute(
        "INSERT INTO entity_relationships "
        "(rel_id, source_entity_id, target_entity_id, type, first_seen_ns, last_seen_ns) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("rel-1", "ent-1", "ent-2", "used_in", now_ns, now_ns),
    )
    conn.commit()


def _insert_sample_moments(conn):
    """Insert sample coherence moments."""
    now_ns = time.time_ns()
    for i in range(3):
        conn.execute(
            "INSERT INTO coherence_moments "
            "(moment_id, detected_ns, platform, coherence_score, event_ids, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                f"mom-{i}",
                now_ns - (i * 1_000_000_000),
                "claude",
                0.85 + i * 0.05,
                json.dumps([f"evt-{i}"]),
                f"Coherence moment {i}",
            ),
        )
    conn.commit()


@pytest.fixture
def web_server(tmp_path):
    """Start web server with temp DB, yield base URL, stop after."""
    # Set up temp DB
    db_path = tmp_path / "test_cognitive.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    _insert_sample_events(conn)
    _insert_sample_entities(conn)
    _insert_sample_moments(conn)
    conn.close()

    # Patch Config
    original_db_path = Config.DB_PATH
    Config.DB_PATH = db_path

    # Start server
    port = _find_free_port()
    server = UCWWebServer()
    server.start("127.0.0.1", port)
    base_url = f"http://127.0.0.1:{port}"

    # Wait for server to be ready
    for _ in range(20):
        try:
            urllib.request.urlopen(f"{base_url}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.1)

    yield base_url

    server.stop()
    Config.DB_PATH = original_db_path


def _get(url):
    """Make a GET request and return (status, headers, parsed_json_or_body)."""
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=5)
        body = resp.read().decode("utf-8")
        content_type = resp.headers.get("Content-Type", "")
        if "json" in content_type:
            return resp.status, resp.headers, json.loads(body)
        return resp.status, resp.headers, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, e.headers, json.loads(body)
        except json.JSONDecodeError:
            return e.code, e.headers, body


def _options(url):
    """Make an OPTIONS request."""
    req = urllib.request.Request(url, method="OPTIONS")
    resp = urllib.request.urlopen(req, timeout=5)
    return resp.status, resp.headers


class TestHealthEndpoint:
    def test_health_endpoint(self, web_server):
        status, headers, data = _get(f"{web_server}/api/health")
        assert status == 200
        assert data["status"] == "ok"
        assert "uptime" in data
        assert "db_size" in data
        assert "event_count" in data
        assert data["event_count"] == 5


class TestDashboardEndpoint:
    def test_dashboard_endpoint(self, web_server):
        status, headers, data = _get(f"{web_server}/api/dashboard")
        assert status == 200
        assert data["total_events"] == 5
        assert data["sessions"] == 1
        assert "platforms" in data
        assert "claude" in data["platforms"]
        assert "cursor" in data["platforms"]
        assert "top_topics" in data
        assert "capture_health" in data


class TestSearchEndpoint:
    def test_search_endpoint(self, web_server):
        status, headers, data = _get(f"{web_server}/api/search?q=testing")
        assert status == 200
        assert "results" in data
        assert "method" in data
        assert "query" in data
        assert data["query"] == "testing"

    def test_search_endpoint_empty_query(self, web_server):
        status, headers, data = _get(f"{web_server}/api/search?q=")
        assert status == 200
        assert data["results"] == []
        assert data["method"] == "none"


class TestEventsEndpoint:
    def test_events_endpoint(self, web_server):
        status, headers, data = _get(f"{web_server}/api/events")
        assert status == 200
        assert "events" in data
        assert "total" in data
        assert data["total"] == 5
        assert len(data["events"]) == 5
        assert "limit" in data
        assert "offset" in data

    def test_events_endpoint_with_pagination(self, web_server):
        status, headers, data = _get(f"{web_server}/api/events?limit=2&offset=1")
        assert status == 200
        assert len(data["events"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 1


class TestGraphEndpoint:
    def test_graph_endpoint(self, web_server):
        status, headers, data = _get(f"{web_server}/api/graph")
        assert status == 200
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) >= 1
        node = data["nodes"][0]
        assert "id" in node
        assert "label" in node
        assert "type" in node
        assert "count" in node
        edge = data["edges"][0]
        assert "source" in edge
        assert "target" in edge
        assert "label" in edge


class TestMomentsEndpoint:
    def test_moments_endpoint(self, web_server):
        status, headers, data = _get(f"{web_server}/api/moments")
        assert status == 200
        assert isinstance(data, list)
        assert len(data) == 3
        moment = data[0]
        assert "description" in moment
        assert "coherence_score" in moment
        assert "timestamp" in moment
        assert "platforms" in moment


class TestCORSHeaders:
    def test_cors_headers(self, web_server):
        status, headers, data = _get(f"{web_server}/api/health")
        assert headers.get("Access-Control-Allow-Origin") == "*"
        assert "GET" in headers.get("Access-Control-Allow-Methods", "")
        assert "Content-Type" in headers.get("Access-Control-Allow-Headers", "")

    def test_options_preflight(self, web_server):
        status, headers = _options(f"{web_server}/api/dashboard")
        assert status == 200
        assert headers.get("Access-Control-Allow-Origin") == "*"
        assert "GET" in headers.get("Access-Control-Allow-Methods", "")


class TestErrorHandling:
    def test_404_handler(self, web_server):
        status, headers, data = _get(f"{web_server}/api/nonexistent")
        assert status == 404
        assert "error" in data

    def test_error_response_format(self, web_server):
        status, headers, data = _get(f"{web_server}/api/nonexistent")
        assert status == 404
        assert isinstance(data, dict)
        assert "error" in data
        content_type = headers.get("Content-Type", "")
        assert "application/json" in content_type


class TestIndexPage:
    def test_index_serves_html(self, web_server):
        status, headers, body = _get(web_server)
        assert status == 200
        assert "text/html" in headers.get("Content-Type", "")
        assert "UCW Dashboard" in body
