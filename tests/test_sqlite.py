"""Tests for SQLite database — round-trip store/retrieve."""

import pytest
from pathlib import Path
from ucw.db.sqlite import CaptureDB
from ucw.server.capture import CaptureEvent


class TestCaptureDB:
    @pytest.fixture
    async def db(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "test.db")
        await db.initialize()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_initialize(self, db):
        assert db.session_id is not None
        assert db.session_id.startswith("mcp-")

    @pytest.mark.asyncio
    async def test_store_and_retrieve_stats(self, db):
        event = CaptureEvent(
            direction="in",
            stage="received",
            raw_bytes=b'{"jsonrpc":"2.0","method":"ping"}',
            parsed={"jsonrpc": "2.0", "method": "ping"},
            timestamp_ns=1000000000,
        )
        event.data_layer = {"content": "test", "tokens_est": 1}
        event.light_layer = {"intent": "execute", "topic": "mcp_protocol", "concepts": [], "summary": "test"}
        event.instinct_layer = {"coherence_potential": 0.35, "emergence_indicators": [], "gut_signal": "routine"}
        event.coherence_signature = "abc123"

        await db.store_event(event)

        stats = await db.get_session_stats()
        assert stats["event_count"] == 1
        assert stats["turn_count"] == 0  # turn wasn't set

    @pytest.mark.asyncio
    async def test_all_stats(self, db):
        for i in range(3):
            event = CaptureEvent(
                direction="in",
                stage="received",
                raw_bytes=b'test',
                parsed={"jsonrpc": "2.0", "method": f"method_{i}"},
                timestamp_ns=i * 1000,
            )
            event.data_layer = {"content": f"content {i}"}
            event.light_layer = {"intent": "explore", "topic": "general", "concepts": [], "summary": f"test {i}"}
            event.instinct_layer = {"coherence_potential": 0.1, "emergence_indicators": [], "gut_signal": "routine"}
            await db.store_event(event)

        stats = await db.get_all_stats()
        assert stats["total_events"] == 3
        assert stats["total_sessions"] == 1

    @pytest.mark.asyncio
    async def test_store_event_with_all_layers(self, db):
        event = CaptureEvent(
            direction="out",
            stage="sent",
            raw_bytes=b'{"result":"ok"}',
            parsed={"jsonrpc": "2.0", "id": 1, "result": "ok"},
            timestamp_ns=5000000000,
        )
        event.data_layer = {
            "content": "UCW cognitive wallet coherence analysis",
            "tokens_est": 7,
        }
        event.light_layer = {
            "intent": "analyze",
            "topic": "ucw",
            "concepts": ["ucw", "cognitive", "coherence"],
            "summary": "UCW cognitive wallet coherence analysis",
        }
        event.instinct_layer = {
            "coherence_potential": 0.85,
            "emergence_indicators": ["high_coherence_potential", "concept_cluster", "meta_cognitive"],
            "gut_signal": "breakthrough_potential",
        }
        event.coherence_signature = "sig_abc123"

        await db.store_event(event)

        # Verify via raw SQL
        cur = db._conn.execute(
            "SELECT light_topic, instinct_gut_signal, coherence_sig FROM cognitive_events WHERE event_id = ?",
            (event.event_id,),
        )
        row = cur.fetchone()
        assert row[0] == "ucw"
        assert row[1] == "breakthrough_potential"
        assert row[2] == "sig_abc123"

    @pytest.mark.asyncio
    async def test_close_finalizes_session(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "finalize_test.db")
        await db.initialize()
        session_id = db.session_id

        event = CaptureEvent(
            direction="in", stage="received",
            raw_bytes=b'test', parsed={}, timestamp_ns=1000,
        )
        event.data_layer = {}
        event.light_layer = {}
        event.instinct_layer = {}
        await db.store_event(event)
        await db.close()

        # Reopen and verify session was finalized
        import sqlite3
        conn = sqlite3.connect(str(tmp_ucw_dir / "finalize_test.db"))
        cur = conn.execute(
            "SELECT ended_ns, event_count FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cur.fetchone()
        conn.close()
        assert row[0] is not None  # ended_ns is set
        assert row[1] == 1         # event_count is 1
