"""
Tests for Epic 2 (Real-Time Intelligence) + Epic 3 (Cross-Platform Fusion).

Covers:
  - EventStream pub/sub
  - AlertEngine creation, querying, acknowledgment, auto-detection
  - ThreadLinker linking, querying, cross-platform, stats
  - intelligence_tools MCP tool handlers
"""

import asyncio
import json
import sqlite3
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_conn(tmp_ucw_dir):
    """Create a fresh SQLite DB with base schema + migrations."""
    # Import SCHEMA_SQL — lazy to avoid circular import at collection time
    from ucw.db.sqlite import SCHEMA_SQL

    # migrations.py is shadowed by migrations/ package dir — load from file
    import importlib.util, pathlib
    _mig_path = pathlib.Path(__file__).resolve().parent.parent / "src" / "ucw" / "db" / "migrations.py"
    _spec = importlib.util.spec_from_file_location("_ucw_mig", str(_mig_path))
    _mig = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mig)
    migrate_up = _mig.migrate_up

    db_path = tmp_ucw_dir / "cognitive.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)
    migrate_up(conn)
    conn.commit()

    # Create a test session
    conn.execute(
        "INSERT INTO sessions (session_id, started_ns, platform) VALUES (?, ?, ?)",
        ("test-session-1", time.time_ns(), "claude-desktop"),
    )
    conn.commit()
    yield conn
    conn.close()


def _insert_event(conn, event_id, session_id="test-session-1", topic="ai-systems",
                  intent="explore", concepts=None, coherence=0.5,
                  gut_signal="standard", platform="claude-desktop",
                  timestamp_ns=None):
    """Helper to insert a test event."""
    conn.execute(
        """INSERT INTO cognitive_events
           (event_id, session_id, timestamp_ns, direction, stage,
            method, light_topic, light_intent, light_concepts,
            light_summary, instinct_coherence, instinct_gut_signal,
            platform, data_content, content_length)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event_id,
            session_id,
            timestamp_ns or time.time_ns(),
            "inbound",
            "parsed",
            "tools/call",
            topic,
            intent,
            json.dumps(concepts or ["concept-a", "concept-b"]),
            f"Summary for {event_id}",
            coherence,
            gut_signal,
            platform,
            f"Content for {event_id}",
            100,
        ),
    )
    conn.commit()


# ===========================================================================
# EventStream Tests
# ===========================================================================

class TestEventStream:

    def test_subscribe_and_count(self):
        from ucw.intelligence.event_stream import EventStream
        es = EventStream()
        cb = lambda e: None
        es.subscribe("capture", cb)
        assert es.subscriber_count("capture") == 1
        assert es.subscriber_count() == 1

    def test_subscribe_multiple_channels(self):
        from ucw.intelligence.event_stream import EventStream
        es = EventStream()
        cb1 = lambda e: None
        cb2 = lambda e: None
        es.subscribe("capture", cb1)
        es.subscribe("emergence", cb2)
        assert es.subscriber_count("capture") == 1
        assert es.subscriber_count("emergence") == 1
        assert es.subscriber_count() == 2

    def test_unsubscribe(self):
        from ucw.intelligence.event_stream import EventStream
        es = EventStream()
        cb = lambda e: None
        es.subscribe("capture", cb)
        assert es.subscriber_count("capture") == 1
        es.unsubscribe("capture", cb)
        assert es.subscriber_count("capture") == 0

    def test_unsubscribe_nonexistent(self):
        from ucw.intelligence.event_stream import EventStream
        es = EventStream()
        cb = lambda e: None
        # Should not raise
        es.unsubscribe("capture", cb)
        es.unsubscribe("nonexistent", cb)

    def test_duplicate_subscribe(self):
        from ucw.intelligence.event_stream import EventStream
        es = EventStream()
        cb = lambda e: None
        es.subscribe("capture", cb)
        es.subscribe("capture", cb)  # Duplicate
        assert es.subscriber_count("capture") == 1

    @pytest.mark.asyncio
    async def test_publish_calls_callback(self):
        from ucw.intelligence.event_stream import EventStream
        es = EventStream()
        received = []
        es.subscribe("capture", lambda e: received.append(e))
        await es.publish("capture", {"type": "test"})
        assert len(received) == 1
        assert received[0]["type"] == "test"

    @pytest.mark.asyncio
    async def test_publish_multiple_subscribers(self):
        from ucw.intelligence.event_stream import EventStream
        es = EventStream()
        results = {"a": [], "b": []}
        es.subscribe("capture", lambda e: results["a"].append(e))
        es.subscribe("capture", lambda e: results["b"].append(e))
        await es.publish("capture", {"data": 42})
        assert len(results["a"]) == 1
        assert len(results["b"]) == 1

    @pytest.mark.asyncio
    async def test_publish_error_in_callback_does_not_block(self):
        from ucw.intelligence.event_stream import EventStream
        es = EventStream()
        received = []

        def bad_cb(e):
            raise ValueError("boom")

        es.subscribe("capture", bad_cb)
        es.subscribe("capture", lambda e: received.append(e))
        await es.publish("capture", {"ok": True})
        # Second subscriber still called
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_publish_to_empty_channel(self):
        from ucw.intelligence.event_stream import EventStream
        es = EventStream()
        # Should not raise
        await es.publish("nonexistent", {"data": 1})

    @pytest.mark.asyncio
    async def test_publish_async_callback(self):
        from ucw.intelligence.event_stream import EventStream
        es = EventStream()
        received = []

        async def async_cb(e):
            received.append(e)

        es.subscribe("capture", async_cb)
        await es.publish("capture", {"async": True})
        assert len(received) == 1

    def test_subscriber_count_no_channel(self):
        from ucw.intelligence.event_stream import EventStream
        es = EventStream()
        assert es.subscriber_count() == 0
        assert es.subscriber_count("capture") == 0


# ===========================================================================
# AlertEngine Tests
# ===========================================================================

class TestAlertEngine:

    def test_create_alert(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        aid = engine.create_alert("test_type", "info", "Test message")
        assert isinstance(aid, str)
        assert len(aid) == 16

    def test_create_alert_with_evidence(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        aid = engine.create_alert("test", "warning", "Msg", evidence_event_ids=["e1", "e2"])
        alerts = engine.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]["evidence_event_ids"] == ["e1", "e2"]

    def test_get_alerts_empty(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        assert engine.get_alerts() == []

    def test_get_alerts_filter_type(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        engine.create_alert("high_coherence", "warning", "HC 1")
        engine.create_alert("emergence", "critical", "Em 1")
        hc = engine.get_alerts(type="high_coherence")
        assert len(hc) == 1
        assert hc[0]["type"] == "high_coherence"

    def test_get_alerts_filter_severity(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        engine.create_alert("a", "info", "Info alert")
        engine.create_alert("b", "critical", "Critical alert")
        critical = engine.get_alerts(severity="critical")
        assert len(critical) == 1
        assert critical[0]["severity"] == "critical"

    def test_acknowledge_alert(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        aid = engine.create_alert("test", "info", "Ack me")
        assert engine.acknowledge_alert(aid) is True
        alerts = engine.get_alerts(acknowledged=True)
        assert len(alerts) == 1
        assert alerts[0]["acknowledged"] is True

    def test_acknowledge_nonexistent(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        assert engine.acknowledge_alert("nonexistent-id") is False

    def test_check_coherence_alert_triggers(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        result = engine.check_coherence_alert({
            "instinct_coherence": 0.95,
            "event_id": "evt-1",
            "light_topic": "quantum",
        })
        assert result is not None
        assert result["type"] == "high_coherence"
        assert "0.950" in result["message"]

    def test_check_coherence_alert_no_trigger(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        result = engine.check_coherence_alert({
            "instinct_coherence": 0.5,
            "event_id": "evt-1",
        })
        assert result is None

    def test_check_coherence_alert_none_coherence(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        result = engine.check_coherence_alert({
            "instinct_coherence": None,
            "event_id": "evt-1",
        })
        assert result is None

    def test_check_emergence_alert_triggers(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        result = engine.check_emergence_alert({
            "instinct_gut_signal": "breakthrough_potential",
            "event_id": "evt-2",
            "light_topic": "emergence",
        })
        assert result is not None
        assert result["type"] == "emergence"
        assert result["severity"] == "critical"

    def test_check_emergence_alert_no_trigger(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        result = engine.check_emergence_alert({
            "instinct_gut_signal": "standard",
        })
        assert result is None

    def test_get_alert_stats(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        engine.create_alert("high_coherence", "warning", "HC 1")
        engine.create_alert("emergence", "critical", "Em 1")
        aid = engine.create_alert("emergence", "critical", "Em 2")
        engine.acknowledge_alert(aid)

        stats = engine.get_alert_stats()
        assert stats["total"] == 3
        assert stats["by_type"]["emergence"] == 2
        assert stats["by_severity"]["critical"] == 2
        assert stats["acknowledged"] == 1
        assert stats["unacknowledged"] == 2

    def test_get_alert_stats_empty(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        stats = engine.get_alert_stats()
        assert stats["total"] == 0

    def test_alert_unicode_message(self, db_conn):
        from ucw.intelligence.alerting import AlertEngine
        engine = AlertEngine(db_conn)
        aid = engine.create_alert("test", "info", "Alert: \u2728 breakthrough in \u00e9mergence")
        alerts = engine.get_alerts()
        assert len(alerts) == 1
        assert "\u2728" in alerts[0]["message"]


# ===========================================================================
# ThreadLinker Tests
# ===========================================================================

class TestThreadLinker:

    def test_link_empty_events(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        assert linker.link_events_to_threads([]) == []

    def test_link_single_event(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        events = [{
            "event_id": "e1",
            "session_id": "s1",
            "timestamp_ns": 1000000000000,
            "light_topic": "ai",
            "light_concepts": '["concept-a"]',
        }]
        threads = linker.link_events_to_threads(events)
        assert len(threads) == 1
        assert threads[0]["topic"] == "ai"

    def test_link_same_topic_same_bucket(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        base_ts = 5 * 60 * 1_000_000_000 * 100  # Some time bucket
        events = [
            {"event_id": "e1", "session_id": "s1", "timestamp_ns": base_ts,
             "light_topic": "ai", "light_concepts": '["a", "b"]'},
            {"event_id": "e2", "session_id": "s1", "timestamp_ns": base_ts + 1_000_000_000,
             "light_topic": "ai", "light_concepts": '["b", "c"]'},
        ]
        threads = linker.link_events_to_threads(events)
        assert len(threads) == 1
        assert threads[0]["entity_overlap_score"] > 0

    def test_link_different_topics(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        base_ts = 5 * 60 * 1_000_000_000 * 100
        events = [
            {"event_id": "e1", "session_id": "s1", "timestamp_ns": base_ts,
             "light_topic": "ai", "light_concepts": "[]"},
            {"event_id": "e2", "session_id": "s1", "timestamp_ns": base_ts,
             "light_topic": "biology", "light_concepts": "[]"},
        ]
        threads = linker.link_events_to_threads(events)
        assert len(threads) == 2
        topics = {t["topic"] for t in threads}
        assert topics == {"ai", "biology"}

    def test_link_different_time_buckets(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        bucket_ns = 5 * 60 * 1_000_000_000
        events = [
            {"event_id": "e1", "session_id": "s1", "timestamp_ns": bucket_ns * 10,
             "light_topic": "ai", "light_concepts": "[]"},
            {"event_id": "e2", "session_id": "s1", "timestamp_ns": bucket_ns * 12,
             "light_topic": "ai", "light_concepts": "[]"},
        ]
        threads = linker.link_events_to_threads(events)
        assert len(threads) == 2  # Different time buckets

    def test_get_threads(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        base_ts = 5 * 60 * 1_000_000_000 * 100
        events = [
            {"event_id": "e1", "session_id": "s1", "timestamp_ns": base_ts,
             "light_topic": "ai", "light_concepts": '["a", "b"]'},
            {"event_id": "e2", "session_id": "s1", "timestamp_ns": base_ts + 1_000,
             "light_topic": "ai", "light_concepts": '["a", "c"]'},
        ]
        linker.link_events_to_threads(events)
        threads = linker.get_threads(min_score=0.0)
        assert len(threads) >= 1
        assert threads[0]["combined_score"] > 0

    def test_get_threads_min_score_filter(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        base_ts = 5 * 60 * 1_000_000_000 * 100
        events = [
            {"event_id": "e1", "session_id": "s1", "timestamp_ns": base_ts,
             "light_topic": "ai", "light_concepts": "[]"},
        ]
        linker.link_events_to_threads(events)
        # Very high min_score should filter out
        threads = linker.get_threads(min_score=0.99)
        assert len(threads) == 0

    def test_get_thread_events(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        _insert_event(db_conn, "evt-t1", session_id="test-session-1", topic="ai")

        base_ts = 5 * 60 * 1_000_000_000 * 100
        events = [
            {"event_id": "evt-t1", "session_id": "test-session-1",
             "timestamp_ns": base_ts, "light_topic": "ai", "light_concepts": "[]"},
        ]
        threads = linker.link_events_to_threads(events)
        assert len(threads) == 1

        thread_events = linker.get_thread_events(threads[0]["thread_id"])
        assert len(thread_events) >= 1

    def test_get_thread_events_nonexistent(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        assert linker.get_thread_events("nonexistent") == []

    def test_find_cross_platform_threads(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)

        # Insert events from different platforms in same session
        _insert_event(db_conn, "cp-1", session_id="sess-cp", topic="ai", platform="claude-desktop")
        _insert_event(db_conn, "cp-2", session_id="sess-cp", topic="ai", platform="cursor")

        base_ts = 5 * 60 * 1_000_000_000 * 200
        events = [
            {"event_id": "cp-1", "session_id": "sess-cp", "timestamp_ns": base_ts,
             "light_topic": "ai", "light_concepts": "[]"},
            {"event_id": "cp-2", "session_id": "sess-cp", "timestamp_ns": base_ts + 1000,
             "light_topic": "ai", "light_concepts": "[]"},
        ]
        linker.link_events_to_threads(events)
        xplat = linker.find_cross_platform_threads(min_platforms=2)
        assert len(xplat) >= 1

    def test_get_thread_stats_empty(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        stats = linker.get_thread_stats()
        assert stats["total_threads"] == 0

    def test_get_thread_stats_populated(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        base_ts = 5 * 60 * 1_000_000_000 * 100
        events = [
            {"event_id": "e1", "session_id": "s1", "timestamp_ns": base_ts,
             "light_topic": "ai", "light_concepts": '["a"]'},
            {"event_id": "e2", "session_id": "s1", "timestamp_ns": base_ts + 1000,
             "light_topic": "ai", "light_concepts": '["a"]'},
        ]
        linker.link_events_to_threads(events)
        stats = linker.get_thread_stats()
        assert stats["total_threads"] >= 1
        assert stats["avg_combined_score"] > 0

    def test_entity_overlap_no_concepts(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        score = ThreadLinker._entity_overlap_score([
            {"light_concepts": "[]"},
            {"light_concepts": "[]"},
        ])
        assert score == 0.0

    def test_entity_overlap_perfect(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        score = ThreadLinker._entity_overlap_score([
            {"light_concepts": '["a", "b"]'},
            {"light_concepts": '["a", "b"]'},
        ])
        assert score == 1.0

    def test_temporal_score_same_time(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        score = ThreadLinker._temporal_score([
            {"timestamp_ns": 1000},
            {"timestamp_ns": 1000},
        ])
        assert score == 1.0

    def test_temporal_score_single_event(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        score = ThreadLinker._temporal_score([{"timestamp_ns": 1000}])
        assert score == 1.0

    def test_link_with_none_topic(self, db_conn):
        from ucw.intelligence.thread_linker import ThreadLinker
        linker = ThreadLinker(db_conn)
        events = [
            {"event_id": "e1", "session_id": "s1", "timestamp_ns": 1000000000000,
             "light_topic": None, "light_concepts": "[]"},
        ]
        threads = linker.link_events_to_threads(events)
        assert len(threads) == 1
        assert threads[0]["topic"] == "general"


# ===========================================================================
# Intelligence Tools Tests
# ===========================================================================

class TestIntelligenceTools:

    @pytest.fixture
    def mock_db(self, db_conn):
        """Create a mock DB object with _conn attribute."""

        class MockDB:
            def __init__(self, conn):
                self._conn = conn

        return MockDB(db_conn)

    @pytest.mark.asyncio
    async def test_alerts_query_empty(self, mock_db):
        from ucw.tools import intelligence_tools
        intelligence_tools._db = mock_db
        result = await intelligence_tools.handle_tool("alerts_query", {})
        assert "content" in result
        assert "No alerts found" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_alerts_query_with_data(self, mock_db):
        from ucw.intelligence.alerting import AlertEngine
        from ucw.tools import intelligence_tools
        intelligence_tools._db = mock_db

        engine = AlertEngine(mock_db._conn)
        engine.create_alert("high_coherence", "warning", "Test HC alert")

        result = await intelligence_tools.handle_tool("alerts_query", {})
        text = result["content"][0]["text"]
        assert "Test HC alert" in text
        assert "WARNING" in text

    @pytest.mark.asyncio
    async def test_alerts_query_filter(self, mock_db):
        from ucw.intelligence.alerting import AlertEngine
        from ucw.tools import intelligence_tools
        intelligence_tools._db = mock_db

        engine = AlertEngine(mock_db._conn)
        engine.create_alert("high_coherence", "warning", "HC")
        engine.create_alert("emergence", "critical", "EM")

        result = await intelligence_tools.handle_tool("alerts_query", {"type": "emergence"})
        text = result["content"][0]["text"]
        assert "EM" in text
        assert "1 shown" in text

    @pytest.mark.asyncio
    async def test_thread_analysis_list(self, mock_db):
        from ucw.tools import intelligence_tools
        intelligence_tools._db = mock_db
        result = await intelligence_tools.handle_tool("thread_analysis", {"action": "list"})
        assert "content" in result
        assert "Conversation Threads" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_thread_analysis_stats(self, mock_db):
        from ucw.tools import intelligence_tools
        intelligence_tools._db = mock_db
        result = await intelligence_tools.handle_tool("thread_analysis", {"action": "stats"})
        text = result["content"][0]["text"]
        assert "Statistics" in text
        assert "Total Threads" in text

    @pytest.mark.asyncio
    async def test_thread_analysis_cross_platform(self, mock_db):
        from ucw.tools import intelligence_tools
        intelligence_tools._db = mock_db
        result = await intelligence_tools.handle_tool("thread_analysis", {"action": "cross_platform"})
        assert "content" in result

    @pytest.mark.asyncio
    async def test_link_threads_empty(self, mock_db):
        from ucw.tools import intelligence_tools
        intelligence_tools._db = mock_db
        result = await intelligence_tools.handle_tool("link_threads", {})
        text = result["content"][0]["text"]
        assert "No events found" in text or "Link Threads" in text

    @pytest.mark.asyncio
    async def test_link_threads_with_events(self, mock_db, db_conn):
        from ucw.tools import intelligence_tools
        intelligence_tools._db = mock_db

        _insert_event(db_conn, "lt-1", topic="ai")
        _insert_event(db_conn, "lt-2", topic="ai")

        result = await intelligence_tools.handle_tool("link_threads", {"limit": 50})
        text = result["content"][0]["text"]
        assert "Scanned" in text

    @pytest.mark.asyncio
    async def test_unknown_tool(self, mock_db):
        from ucw.tools import intelligence_tools
        intelligence_tools._db = mock_db
        result = await intelligence_tools.handle_tool("nonexistent_tool", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_no_db(self):
        from ucw.tools import intelligence_tools
        intelligence_tools._db = None
        result = await intelligence_tools.handle_tool("alerts_query", {})
        assert result.get("isError") is True
        assert "not initialized" in result["content"][0]["text"]
