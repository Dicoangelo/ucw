"""Integration tests for the full UCW capture pipeline.

Tests the chain: CaptureEngine -> UCWBridge enrichment -> CaptureDB
persistence -> ucw_tools queries -> dashboard aggregation.
"""

import json
import time

import pytest

from ucw.db.sqlite import CaptureDB
from ucw.server.capture import CaptureEngine
from ucw.server.server import UCWBridgeAdapter

# --------------- fixtures ---------------


@pytest.fixture
async def capture_db(tmp_path, tmp_ucw_dir):
    """Create a real SQLite DB with UCW schema."""
    db = CaptureDB(db_path=tmp_path / "test.db")
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
def engine():
    return CaptureEngine()


@pytest.fixture
def bridge():
    return UCWBridgeAdapter()


def _make_request(
    method="tools/call",
    req_id=1,
    params=None,
):
    """Build a minimal MCP-style parsed request dict."""
    return {
        "jsonrpc": "2.0",
        "method": method,
        "id": req_id,
        "params": params or {"name": "test_tool"},
    }


def _make_response(req_id=1, result=None):
    """Build a minimal MCP-style parsed response dict."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result or {
            "content": [{"type": "text", "text": "ok"}],
        },
    }


# --------------- tests ---------------


class TestCaptureEventCreation:
    """test_capture_event_creation"""

    async def test_fields_populated(self, engine):
        ts = time.time_ns()
        parsed = _make_request(method="tools/call", req_id=42)
        raw = json.dumps(parsed).encode()

        await engine.capture(
            raw_bytes=raw,
            parsed=parsed,
            timestamp_ns=ts,
            direction="in",
        )

        assert engine.event_count == 1
        evt = engine.recent_events(1)[0]
        assert evt["event_id"]
        assert evt["timestamp_ns"] == ts
        assert evt["direction"] == "in"
        assert evt["stage"] == "received"
        assert evt["method"] == "tools/call"
        assert evt["content_length"] == len(raw)


class TestCaptureEventEnrichment:
    """test_capture_event_enrichment"""

    async def test_bridge_populates_layers(self, engine, bridge):
        engine.set_ucw_bridge(bridge)
        parsed = _make_request(
            method="tools/call",
            params={
                "name": "search_database",
                "arguments": {
                    "query": "ucw cognitive coherence",
                },
            },
        )
        raw = json.dumps(parsed).encode()

        await engine.capture(
            raw_bytes=raw,
            parsed=parsed,
            timestamp_ns=time.time_ns(),
            direction="in",
        )

        evt = engine.recent_events(1)[0]
        assert "data_layer" in evt
        assert "light_layer" in evt
        assert "instinct_layer" in evt
        assert evt["coherence_signature"]
        assert evt["light_layer"]["intent"]
        assert evt["light_layer"]["topic"]


class TestCaptureDBPersistence:
    """test_capture_db_persistence"""

    async def test_store_and_retrieve(
        self, engine, bridge, capture_db,
    ):
        engine.set_ucw_bridge(bridge)
        engine.set_db_sink(capture_db)

        parsed = _make_request(method="tools/call", req_id=7)
        raw = json.dumps(parsed).encode()
        ts = time.time_ns()

        await engine.capture(
            raw_bytes=raw,
            parsed=parsed,
            timestamp_ns=ts,
            direction="in",
        )

        conn = capture_db._conn
        row = conn.execute(
            "SELECT event_id, timestamp_ns, direction, stage,"
            " method, content_length, light_intent, light_topic"
            " FROM cognitive_events WHERE timestamp_ns = ?",
            (ts,),
        ).fetchone()

        assert row is not None
        assert row[1] == ts
        assert row[2] == "in"
        assert row[3] == "received"
        assert row[4] == "tools/call"
        assert row[5] == len(raw)
        assert row[6] is not None  # light_intent
        assert row[7] is not None  # light_topic


class TestCaptureStatsTool:
    """test_capture_stats_tool"""

    async def test_returns_correct_counts(
        self, engine, bridge, capture_db,
    ):
        engine.set_ucw_bridge(bridge)
        engine.set_db_sink(capture_db)

        for i in range(3):
            parsed = _make_request(req_id=i + 1)
            raw = json.dumps(parsed).encode()
            await engine.capture(
                raw_bytes=raw,
                parsed=parsed,
                timestamp_ns=time.time_ns(),
                direction="in",
            )

        from ucw.tools import ucw_tools

        ucw_tools.set_db(capture_db)
        result = await ucw_tools.handle_tool(
            "ucw_capture_stats", {},
        )
        text = result["content"][0]["text"]

        assert "Events Captured:** 3" in text
        assert "Total Events:** 3" in text


class TestTimelineTool:
    """test_timeline_tool"""

    async def test_chronological_order(
        self, engine, bridge, capture_db,
    ):
        engine.set_ucw_bridge(bridge)
        engine.set_db_sink(capture_db)

        base_ts = time.time_ns()
        methods = [
            "tools/list",
            "tools/call",
            "resources/read",
        ]
        for i, method in enumerate(methods):
            parsed = _make_request(method=method, req_id=i + 1)
            raw = json.dumps(parsed).encode()
            await engine.capture(
                raw_bytes=raw,
                parsed=parsed,
                timestamp_ns=base_ts + i * 1_000_000,
                direction="in",
            )

        from ucw.tools import ucw_tools

        ucw_tools.set_db(capture_db)
        result = await ucw_tools.handle_tool(
            "ucw_timeline", {"limit": 10},
        )
        text = result["content"][0]["text"]

        assert "tools/list" in text
        assert "tools/call" in text
        assert "resources/read" in text

        # Chronological order in output
        pos_list = text.index("tools/list")
        pos_call = text.index("tools/call")
        pos_read = text.index("resources/read")
        assert pos_list < pos_call < pos_read


class TestDashboardShowsCapturedEvents:
    """test_dashboard_shows_captured_events"""

    async def test_total_events_count(
        self, engine, bridge, capture_db, tmp_path,
    ):
        engine.set_ucw_bridge(bridge)
        engine.set_db_sink(capture_db)

        for i in range(5):
            parsed = _make_request(req_id=i + 1)
            raw = json.dumps(parsed).encode()
            await engine.capture(
                raw_bytes=raw,
                parsed=parsed,
                timestamp_ns=time.time_ns(),
                direction="in",
            )

        from ucw.dashboard import get_dashboard_data

        data = get_dashboard_data(
            db_path=tmp_path / "test.db",
        )

        assert data is not None
        assert data["total_events"] == 5
        assert data["sessions"] >= 1


class TestTurnCounting:
    """test_turn_counting"""

    async def test_turns_increment_on_requests(self, engine):
        for i in range(4):
            parsed = _make_request(req_id=i + 1)
            raw = json.dumps(parsed).encode()
            await engine.capture(
                raw_bytes=raw,
                parsed=parsed,
                timestamp_ns=time.time_ns(),
                direction="in",
            )

        assert engine.turn_count == 4

        events = engine.recent_events(10)
        turns = [e["turn"] for e in events]
        assert turns == [1, 2, 3, 4]


class TestRequestResponseLineage:
    """test_request_response_lineage"""

    async def test_response_links_to_request(self, engine):
        req_parsed = _make_request(req_id=99)
        req_raw = json.dumps(req_parsed).encode()
        await engine.capture(
            raw_bytes=req_raw,
            parsed=req_parsed,
            timestamp_ns=time.time_ns(),
            direction="in",
        )

        req_event = engine.recent_events(1)[0]
        req_event_id = req_event["event_id"]

        resp_parsed = _make_response(req_id=99)
        resp_raw = json.dumps(resp_parsed).encode()
        await engine.capture(
            raw_bytes=resp_raw,
            parsed=resp_parsed,
            timestamp_ns=time.time_ns(),
            direction="out",
        )

        resp_event = engine.recent_events(2)[-1]
        assert resp_event["parent_protocol_id"] == req_event_id
        assert resp_event["turn"] == req_event["turn"]


class TestErrorEventCapture:
    """test_error_event_capture"""

    async def test_error_field_stored(
        self, engine, capture_db,
    ):
        engine.set_db_sink(capture_db)

        parsed = _make_request(req_id=1)
        raw = json.dumps(parsed).encode()
        await engine.capture(
            raw_bytes=raw,
            parsed=parsed,
            timestamp_ns=time.time_ns(),
            direction="in",
            error="Connection timeout",
        )

        evt = engine.recent_events(1)[0]
        assert evt["error"] == "Connection timeout"

        row = capture_db._conn.execute(
            "SELECT error FROM cognitive_events"
            " WHERE event_id = ?",
            (evt["event_id"],),
        ).fetchone()
        assert row[0] == "Connection timeout"


class TestMultipleSessions:
    """test_multiple_sessions"""

    async def test_independent_session_tracking(
        self, tmp_path, tmp_ucw_dir,
    ):
        db1 = CaptureDB(db_path=tmp_path / "multi.db")
        await db1.initialize()
        session1 = db1.session_id

        engine1 = CaptureEngine()
        engine1.set_db_sink(db1)

        for i in range(3):
            parsed = _make_request(req_id=i + 1)
            raw = json.dumps(parsed).encode()
            await engine1.capture(
                raw_bytes=raw,
                parsed=parsed,
                timestamp_ns=time.time_ns(),
                direction="in",
            )

        await db1.close()

        # Second session on same DB file.
        # Patch time.time so session_id (mcp-<epoch_s>) differs.
        import unittest.mock as _mock

        _real_time = time.time
        db2 = CaptureDB(db_path=tmp_path / "multi.db")
        with _mock.patch(
            "ucw.db.sqlite.time.time",
            return_value=_real_time() + 2,
        ):
            await db2.initialize()
        session2 = db2.session_id

        engine2 = CaptureEngine()
        engine2.set_db_sink(db2)

        for i in range(2):
            parsed = _make_request(req_id=i + 10)
            raw = json.dumps(parsed).encode()
            await engine2.capture(
                raw_bytes=raw,
                parsed=parsed,
                timestamp_ns=time.time_ns(),
                direction="in",
            )

        assert session1 != session2

        conn = db2._conn
        s1_count = conn.execute(
            "SELECT COUNT(*) FROM cognitive_events"
            " WHERE session_id = ?",
            (session1,),
        ).fetchone()[0]
        assert s1_count == 3

        s2_count = conn.execute(
            "SELECT COUNT(*) FROM cognitive_events"
            " WHERE session_id = ?",
            (session2,),
        ).fetchone()[0]
        assert s2_count == 2

        total = conn.execute(
            "SELECT COUNT(*) FROM cognitive_events",
        ).fetchone()[0]
        assert total == 5

        await db2.close()


class TestCaptureCallback:
    """test_capture_callback"""

    async def test_callbacks_triggered(self, engine):
        captured = []

        async def on_event(event):
            captured.append(event.to_dict())

        engine.on_event(on_event)

        for i in range(3):
            parsed = _make_request(req_id=i + 1)
            raw = json.dumps(parsed).encode()
            await engine.capture(
                raw_bytes=raw,
                parsed=parsed,
                timestamp_ns=time.time_ns(),
                direction="in",
            )

        assert len(captured) == 3
        assert all(e["event_id"] for e in captured)
        assert all(
            e["method"] == "tools/call" for e in captured
        )


class TestCaptureNoBridge:
    """test_capture_no_bridge"""

    async def test_events_captured_without_enrichment(
        self, engine, capture_db,
    ):
        engine.set_db_sink(capture_db)

        parsed = _make_request(req_id=1)
        raw = json.dumps(parsed).encode()
        await engine.capture(
            raw_bytes=raw,
            parsed=parsed,
            timestamp_ns=time.time_ns(),
            direction="in",
        )

        assert engine.event_count == 1

        evt = engine.recent_events(1)[0]
        assert "data_layer" not in evt
        assert "light_layer" not in evt
        assert "instinct_layer" not in evt

        assert evt["direction"] == "in"
        assert evt["method"] == "tools/call"

        row = capture_db._conn.execute(
            "SELECT light_intent, light_topic"
            " FROM cognitive_events WHERE event_id = ?",
            (evt["event_id"],),
        ).fetchone()
        assert row[0] is None
        assert row[1] is None
