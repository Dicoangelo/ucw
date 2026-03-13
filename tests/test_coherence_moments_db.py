"""Tests for coherence_moments DB methods (insert, query, cross-platform)."""

import pytest

from ucw.db.sqlite import CaptureDB
from ucw.server.capture import CaptureEvent


class TestCoherenceMoments:
    @pytest.fixture
    async def db(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "cm_test.db")
        await db.initialize()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_insert_coherence_moment(self, db):
        ok = await db.insert_coherence_moment(
            moment_id="m1", platform="claude-desktop",
            cluster_id="cluster-1", coherence_score=0.85,
            event_ids=["e1", "e2"], signature="sig1",
            description="Test moment",
        )
        assert ok is True

    @pytest.mark.asyncio
    async def test_insert_duplicate_ignored(self, db):
        await db.insert_coherence_moment(
            moment_id="dup1", platform="claude-desktop",
            cluster_id="c1", coherence_score=0.9, event_ids=["e1"],
        )
        # Same moment_id should be ignored (INSERT OR IGNORE)
        ok = await db.insert_coherence_moment(
            moment_id="dup1", platform="chatgpt",
            cluster_id="c2", coherence_score=0.5, event_ids=["e2"],
        )
        assert ok is True  # No error, just ignored

        moments = await db.query_coherence_moments(min_score=0.0)
        assert len(moments) == 1
        assert moments[0]["platform"] == "claude-desktop"  # original kept

    @pytest.mark.asyncio
    async def test_query_coherence_moments(self, db):
        await db.insert_coherence_moment(
            moment_id="high", platform="claude",
            cluster_id="c1", coherence_score=0.9, event_ids=["e1"],
        )
        await db.insert_coherence_moment(
            moment_id="low", platform="chatgpt",
            cluster_id="c2", coherence_score=0.3, event_ids=["e2"],
        )

        # Default min_score=0.7
        moments = await db.query_coherence_moments()
        assert len(moments) == 1
        assert moments[0]["moment_id"] == "high"
        assert moments[0]["coherence_score"] == 0.9
        assert moments[0]["event_ids"] == ["e1"]

    @pytest.mark.asyncio
    async def test_query_coherence_moments_empty(self, db):
        moments = await db.query_coherence_moments()
        assert moments == []

    @pytest.mark.asyncio
    async def test_query_coherence_moments_limit(self, db):
        for i in range(5):
            await db.insert_coherence_moment(
                moment_id=f"m{i}", platform="claude",
                cluster_id=f"c{i}", coherence_score=0.8 + i * 0.01,
                event_ids=[f"e{i}"],
            )
        moments = await db.query_coherence_moments(min_score=0.0, limit=3)
        assert len(moments) == 3

    @pytest.mark.asyncio
    async def test_insert_no_connection_returns_false(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "noconn.db")
        # Not initialized — _conn is None
        ok = await db.insert_coherence_moment(
            moment_id="x", platform="x", cluster_id="x",
            coherence_score=0.5, event_ids=[],
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_query_no_connection_returns_empty(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "noconn2.db")
        moments = await db.query_coherence_moments()
        assert moments == []


class TestCrossPlatformSignatures:
    @pytest.fixture
    async def db(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "xplat_test.db")
        await db.initialize()
        yield db
        await db.close()

    async def _insert_event(self, db, event_id, platform, coherence_sig, coherence=0.8):
        event = CaptureEvent(
            direction="in", stage="received",
            raw_bytes=b'test', parsed={"jsonrpc": "2.0", "method": "test"},
            timestamp_ns=1000,
        )
        event.event_id = event_id
        event.data_layer = {"content": "test"}
        event.light_layer = {"intent": "analyze", "topic": "ucw", "concepts": [], "summary": "test"}
        event.instinct_layer = {
            "coherence_potential": coherence,
            "emergence_indicators": [],
            "gut_signal": "routine",
        }
        event.coherence_signature = coherence_sig
        # Override platform in the DB insert
        from ucw.config import Config
        original = Config.PLATFORM
        Config.PLATFORM = platform
        await db.store_event(event)
        Config.PLATFORM = original

    @pytest.mark.asyncio
    async def test_cross_platform_no_matches(self, db):
        result = await db.cross_platform_signatures()
        assert result == []

    @pytest.mark.asyncio
    async def test_cross_platform_single_platform_no_match(self, db):
        await self._insert_event(db, "e1", "claude", "sig_same")
        await self._insert_event(db, "e2", "claude", "sig_same")
        result = await db.cross_platform_signatures(min_platforms=2)
        assert result == []

    @pytest.mark.asyncio
    async def test_cross_platform_two_platforms_match(self, db):
        await self._insert_event(db, "e1", "claude", "sig_shared")
        await self._insert_event(db, "e2", "chatgpt", "sig_shared")
        result = await db.cross_platform_signatures(min_platforms=2)
        assert len(result) == 1
        assert result[0]["signature"] == "sig_shared"
        assert result[0]["platform_count"] == 2
        assert set(result[0]["platforms"]) == {"claude", "chatgpt"}

    @pytest.mark.asyncio
    async def test_cross_platform_no_connection(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "noconn.db")
        result = await db.cross_platform_signatures()
        assert result == []
