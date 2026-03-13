"""Tests for UCW tools module (ucw_capture_stats, ucw_timeline, detect_emergence)."""

import pytest
from ucw.db.sqlite import CaptureDB
from ucw.server.capture import CaptureEvent
from ucw.tools import ucw_tools


class TestUCWTools:
    @pytest.fixture
    async def db(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "tools_test.db")
        await db.initialize()
        ucw_tools.set_db(db)
        yield db
        ucw_tools.set_db(None)
        await db.close()

    async def _store_event(self, db, method="ping", topic="general",
                           intent="explore", gut="routine", coherence=0.1,
                           indicators=None, content="test content"):
        event = CaptureEvent(
            direction="in", stage="received",
            raw_bytes=content.encode(),
            parsed={"jsonrpc": "2.0", "method": method},
            timestamp_ns=1000,
        )
        event.data_layer = {"content": content, "tokens_est": 5}
        event.light_layer = {
            "intent": intent, "topic": topic,
            "concepts": [], "summary": content[:200],
        }
        event.instinct_layer = {
            "coherence_potential": coherence,
            "emergence_indicators": indicators or [],
            "gut_signal": gut,
        }
        await db.store_event(event)

    # -- ucw_capture_stats --

    @pytest.mark.asyncio
    async def test_capture_stats_no_db(self):
        ucw_tools.set_db(None)
        result = await ucw_tools.handle_tool("ucw_capture_stats", {})
        text = result["content"][0]["text"]
        assert "not" in text.lower() or "No capture" in text

    @pytest.mark.asyncio
    async def test_capture_stats_with_events(self, db):
        await self._store_event(db)
        result = await ucw_tools.handle_tool("ucw_capture_stats", {})
        text = result["content"][0]["text"]
        assert "Capture Statistics" in text
        assert "Events Captured" in text or "Total Events" in text

    # -- ucw_timeline --

    @pytest.mark.asyncio
    async def test_timeline_no_db(self):
        ucw_tools.set_db(None)
        result = await ucw_tools.handle_tool("ucw_timeline", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_timeline_with_events(self, db):
        await self._store_event(db, topic="ucw", intent="analyze")
        result = await ucw_tools.handle_tool("ucw_timeline", {"limit": 10})
        text = result["content"][0]["text"]
        assert "Timeline" in text

    @pytest.mark.asyncio
    async def test_timeline_empty(self, db):
        result = await ucw_tools.handle_tool("ucw_timeline", {"limit": 10})
        text = result["content"][0]["text"]
        assert "No events" in text

    # -- detect_emergence --

    @pytest.mark.asyncio
    async def test_detect_emergence_no_db(self):
        ucw_tools.set_db(None)
        result = await ucw_tools.handle_tool("detect_emergence", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_detect_emergence_empty(self, db):
        result = await ucw_tools.handle_tool("detect_emergence", {"limit": 10})
        text = result["content"][0]["text"]
        assert "No events" in text

    @pytest.mark.asyncio
    async def test_detect_emergence_with_signals(self, db):
        await self._store_event(
            db, topic="ucw", intent="analyze",
            gut="breakthrough_potential", coherence=0.85,
            indicators=["high_coherence_potential", "meta_cognitive"],
            content="UCW cognitive wallet coherence sovereign",
        )
        result = await ucw_tools.handle_tool("detect_emergence", {"limit": 100})
        text = result["content"][0]["text"]
        assert "Emergence" in text

    # -- unknown tool --

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        result = await ucw_tools.handle_tool("nonexistent_tool", {})
        assert result.get("isError") is True
        assert "Unknown" in result["content"][0]["text"]
