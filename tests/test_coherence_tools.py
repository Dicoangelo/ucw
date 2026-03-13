"""Tests for coherence_tools module (coherence_status, moments, scan, cross-platform)."""

import pytest
from ucw.db.sqlite import CaptureDB
from ucw.server.capture import CaptureEvent
from ucw.tools import coherence_tools


class TestCoherenceTools:
    @pytest.fixture
    async def db(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "ctools_test.db")
        await db.initialize()
        coherence_tools.set_db(db)
        yield db
        coherence_tools.set_db(None)
        await db.close()

    async def _store_event(self, db, topic="general", intent="explore",
                           gut="routine", coherence=0.1,
                           indicators=None, content="test", sig=None,
                           platform="claude-desktop"):
        event = CaptureEvent(
            direction="in", stage="received",
            raw_bytes=content.encode(),
            parsed={"jsonrpc": "2.0", "method": "tools/call"},
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
        event.coherence_signature = sig
        await db.store_event(event)

    # -- coherence_status --

    @pytest.mark.asyncio
    async def test_status_no_db(self):
        coherence_tools.set_db(None)
        result = await coherence_tools.handle_tool("coherence_status", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_status_with_data(self, db):
        await self._store_event(db, topic="ucw")
        result = await coherence_tools.handle_tool("coherence_status", {})
        text = result["content"][0]["text"]
        assert "Coherence Status" in text
        assert "Total Events" in text

    # -- coherence_moments --

    @pytest.mark.asyncio
    async def test_moments_no_db(self):
        coherence_tools.set_db(None)
        result = await coherence_tools.handle_tool("coherence_moments", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_moments_empty(self, db):
        result = await coherence_tools.handle_tool("coherence_moments", {"min_coherence": 0.5})
        text = result["content"][0]["text"]
        assert "No events" in text

    @pytest.mark.asyncio
    async def test_moments_with_high_coherence(self, db):
        await self._store_event(
            db, topic="ucw", coherence=0.9,
            gut="breakthrough_potential",
            indicators=["high_coherence_potential", "meta_cognitive"],
        )
        result = await coherence_tools.handle_tool("coherence_moments", {"min_coherence": 0.5})
        text = result["content"][0]["text"]
        assert "High Coherence" in text

    # -- coherence_scan --

    @pytest.mark.asyncio
    async def test_scan_no_db(self):
        coherence_tools.set_db(None)
        result = await coherence_tools.handle_tool("coherence_scan", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_scan_empty(self, db):
        result = await coherence_tools.handle_tool("coherence_scan", {"limit": 10})
        text = result["content"][0]["text"]
        assert "No events" in text

    @pytest.mark.asyncio
    async def test_scan_with_events(self, db):
        await self._store_event(db, topic="research", intent="analyze", coherence=0.8)
        await self._store_event(
            db, topic="ucw", gut="breakthrough_potential", coherence=0.9,
        )
        result = await coherence_tools.handle_tool("coherence_scan", {"limit": 100})
        text = result["content"][0]["text"]
        assert "Coherence Scan" in text
        assert "Topic Distribution" in text

    @pytest.mark.asyncio
    async def test_scan_saves_breakthrough_moments(self, db):
        await self._store_event(
            db, topic="ucw", gut="breakthrough_potential",
            coherence=0.9, sig="sig1",
        )
        result = await coherence_tools.handle_tool("coherence_scan", {"limit": 100})
        text = result["content"][0]["text"]
        assert "Moments saved" in text

    # -- cross_platform_coherence --

    @pytest.mark.asyncio
    async def test_cross_platform_no_db(self):
        coherence_tools.set_db(None)
        result = await coherence_tools.handle_tool("cross_platform_coherence", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_cross_platform_no_matches(self, db):
        result = await coherence_tools.handle_tool("cross_platform_coherence", {})
        text = result["content"][0]["text"]
        assert "No cross-platform" in text

    # -- unknown tool --

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        result = await coherence_tools.handle_tool("nonexistent", {})
        assert result.get("isError") is True
        assert "Unknown" in result["content"][0]["text"]
