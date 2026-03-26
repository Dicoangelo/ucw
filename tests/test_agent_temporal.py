"""
Tests for Agent Memory (Epic 4) and Temporal Intelligence (Epic 5).

Covers:
- AgentMemory: store, search, get, update_confidence, stats, context
- TemporalAnalyzer: topic_evolution, skill_trajectory, knowledge_decay,
                    heatmap, session_comparison, stats
- agent_tools: handle_tool for all 3 tools
- temporal_tools: handle_tool for all 3 tools
- Edge cases: empty DB, no matching topics, future timestamps
"""

import json
import sqlite3
from datetime import datetime, timedelta

import pytest

from ucw.intelligence.agent_memory import AgentMemory
from ucw.intelligence.temporal import TemporalAnalyzer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_schema_sql():
    """Extract SCHEMA_SQL from sqlite.py without triggering circular imports."""
    import pathlib

    src_dir = pathlib.Path(__file__).parent.parent / "src"
    sqlite_file = src_dir / "ucw" / "db" / "sqlite.py"

    # Read the file and extract SCHEMA_SQL directly to avoid any import chain
    source = sqlite_file.read_text()
    # Find SCHEMA_SQL assignment
    start = source.index('SCHEMA_SQL = """')
    end = source.index('"""', start + len('SCHEMA_SQL = """')) + 3
    local_ns = {}
    exec(source[start:end], local_ns)
    return local_ns["SCHEMA_SQL"]


# Cache schema to avoid re-reading
_SCHEMA_SQL = None


def _make_db(tmp_ucw_dir):
    """Create a SQLite DB with schema + agent_learnings migration applied."""
    global _SCHEMA_SQL
    if _SCHEMA_SQL is None:
        _SCHEMA_SQL = _get_schema_sql()

    db_path = tmp_ucw_dir / "cognitive.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA_SQL)
    conn.commit()

    # Apply agent_learnings migration directly (avoid migration system import issues)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent_learnings (
            learning_id     TEXT PRIMARY KEY,
            text            TEXT NOT NULL,
            project         TEXT,
            tags            TEXT,
            confidence      REAL DEFAULT 0.5,
            source_session  TEXT,
            entity_ids      TEXT,
            timestamp_ns    INTEGER NOT NULL,
            light_intent    TEXT,
            light_topic     TEXT,
            light_concepts  TEXT,
            instinct_coherence REAL,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_learnings_project ON agent_learnings(project);
        CREATE INDEX IF NOT EXISTS idx_learnings_ts ON agent_learnings(timestamp_ns);
        CREATE INDEX IF NOT EXISTS idx_learnings_topic ON agent_learnings(light_topic);
    """)
    conn.commit()
    return conn


def _insert_event(conn, event_id, session_id="sess-1", topic="python",
                  coherence=0.5, concepts=None, summary=None,
                  days_ago=0, hour=12, intent="learn", gut_signal=None):
    """Insert a test cognitive event with controllable timestamp."""
    dt = datetime.now() - timedelta(days=days_ago, hours=0)
    dt = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
    ts_ns = int(dt.timestamp() * 1_000_000_000)

    conn.execute(
        """INSERT INTO cognitive_events (
            event_id, session_id, timestamp_ns, direction, stage, method,
            light_topic, light_intent, light_concepts, light_summary,
            instinct_coherence, instinct_gut_signal, created_at
        ) VALUES (?, ?, ?, 'in', 'data', 'test', ?, ?, ?, ?, ?, ?, ?)""",
        (
            event_id, session_id, ts_ns,
            topic, intent,
            json.dumps(concepts or []),
            summary or f"Summary for {event_id}",
            coherence, gut_signal, created_at,
        ),
    )
    conn.commit()


class FakeDB:
    """Minimal stand-in for CaptureDB so tool modules can access _conn and session_id."""
    def __init__(self, conn):
        self._conn = conn
        self._session_id = "test-session-1"

    @property
    def session_id(self):
        return self._session_id


# ---------------------------------------------------------------------------
# AgentMemory tests
# ---------------------------------------------------------------------------

class TestAgentMemory:

    def test_store_and_get(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        lid = mem.store_learning("SQLite WAL mode is faster for reads", project="ucw")
        assert len(lid) == 16
        result = mem.get_learning(lid)
        assert result is not None
        assert result["text"] == "SQLite WAL mode is faster for reads"
        assert result["project"] == "ucw"
        conn.close()

    def test_store_with_all_fields(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        lid = mem.store_learning(
            text="Coherence detection works best with >100 events",
            project="ucw",
            tags=["coherence", "detection"],
            confidence=0.9,
            source_session="sess-42",
            entity_ids=["ent-1", "ent-2"],
            intent="optimize",
            topic="coherence",
            concepts=["emergence", "signal"],
            coherence=0.85,
        )
        r = mem.get_learning(lid)
        assert r["tags"] == ["coherence", "detection"]
        assert r["confidence"] == 0.9
        assert r["entity_ids"] == ["ent-1", "ent-2"]
        assert r["topic"] == "coherence"
        assert r["concepts"] == ["emergence", "signal"]
        assert r["coherence"] == 0.85
        conn.close()

    def test_search_by_query(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        mem.store_learning("Python asyncio patterns", project="ucw")
        mem.store_learning("JavaScript promises", project="web")
        mem.store_learning("Python type hints guide", project="ucw")
        results = mem.search_learnings(query="Python")
        assert len(results) == 2
        conn.close()

    def test_search_by_project(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        mem.store_learning("A learning", project="alpha")
        mem.store_learning("B learning", project="beta")
        mem.store_learning("C learning", project="alpha")
        results = mem.search_learnings(project="alpha")
        assert len(results) == 2
        conn.close()

    def test_search_by_topic(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        mem.store_learning("Topic A insight", topic="architecture")
        mem.store_learning("Topic B insight", topic="testing")
        results = mem.search_learnings(topic="architecture")
        assert len(results) == 1
        assert results[0]["topic"] == "architecture"
        conn.close()

    def test_search_min_confidence(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        mem.store_learning("Low confidence", confidence=0.2)
        mem.store_learning("High confidence", confidence=0.9)
        results = mem.search_learnings(min_confidence=0.5)
        assert len(results) == 1
        assert results[0]["text"] == "High confidence"
        conn.close()

    def test_search_limit(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        for i in range(10):
            mem.store_learning(f"Learning {i}")
        results = mem.search_learnings(limit=3)
        assert len(results) == 3
        conn.close()

    def test_search_empty_db(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        results = mem.search_learnings(query="anything")
        assert results == []
        conn.close()

    def test_get_nonexistent(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        assert mem.get_learning("nonexistent") is None
        conn.close()

    def test_update_confidence(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        lid = mem.store_learning("Some learning", confidence=0.3)
        assert mem.update_confidence(lid, 0.95)
        r = mem.get_learning(lid)
        assert r["confidence"] == 0.95
        conn.close()

    def test_update_confidence_nonexistent(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        assert mem.update_confidence("nope", 0.5) is False
        conn.close()

    def test_get_learning_stats(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        mem.store_learning("A", project="p1", topic="t1", confidence=0.8)
        mem.store_learning("B", project="p1", topic="t2", confidence=0.6)
        mem.store_learning("C", project="p2", topic="t1", confidence=0.4)
        stats = mem.get_learning_stats()
        assert stats["total"] == 3
        assert stats["by_project"]["p1"] == 2
        assert stats["by_topic"]["t1"] == 2
        assert 0.5 <= stats["avg_confidence"] <= 0.7
        conn.close()

    def test_get_learning_stats_empty(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        stats = mem.get_learning_stats()
        assert stats["total"] == 0
        assert stats["avg_confidence"] == 0.0
        conn.close()

    def test_get_context_for_query(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        mem.store_learning("SQLite performance tuning tips", confidence=0.9)
        mem.store_learning("SQLite WAL mode explanation", confidence=0.7)
        mem.store_learning("Python packaging guide", confidence=0.8)
        results = mem.get_context_for_query("SQLite", limit=5)
        assert len(results) == 2
        # Sorted by confidence DESC
        assert results[0]["confidence"] >= results[1]["confidence"]
        conn.close()

    def test_get_context_no_match(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        mem.store_learning("Something else entirely")
        results = mem.get_context_for_query("quantum physics")
        assert results == []
        conn.close()


# ---------------------------------------------------------------------------
# TemporalAnalyzer tests
# ---------------------------------------------------------------------------

class TestTemporalAnalyzer:

    def test_topic_evolution(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        _insert_event(conn, "e1", topic="python", days_ago=2)
        _insert_event(conn, "e2", topic="python", days_ago=2)
        _insert_event(conn, "e3", topic="rust", days_ago=1)
        _insert_event(conn, "e4", topic="python", days_ago=0)
        analyzer = TemporalAnalyzer(conn)
        evo = analyzer.topic_evolution(days=7)
        assert len(evo) >= 3
        topics = {e["topic"] for e in evo}
        assert "python" in topics
        assert "rust" in topics
        conn.close()

    def test_topic_evolution_empty(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        analyzer = TemporalAnalyzer(conn)
        evo = analyzer.topic_evolution(days=7)
        assert evo == []
        conn.close()

    def test_skill_trajectory(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        _insert_event(conn, "e1", topic="python", coherence=0.3, days_ago=5)
        _insert_event(conn, "e2", topic="python", coherence=0.5, days_ago=3)
        _insert_event(conn, "e3", topic="python", coherence=0.8, days_ago=1)
        analyzer = TemporalAnalyzer(conn)
        result = analyzer.skill_trajectory("python", days=10)
        assert result["topic"] == "python"
        assert len(result["trajectory"]) == 3
        # Trajectory should be sorted by day
        days = [p["day"] for p in result["trajectory"]]
        assert days == sorted(days)
        conn.close()

    def test_skill_trajectory_no_data(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        analyzer = TemporalAnalyzer(conn)
        result = analyzer.skill_trajectory("nonexistent", days=30)
        assert result["trajectory"] == []
        conn.close()

    def test_knowledge_decay(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        # Old topic: active 30 days ago, silent since
        _insert_event(conn, "e1", topic="old-topic", days_ago=30)
        _insert_event(conn, "e2", topic="old-topic", days_ago=28)
        # Recent topic: still active
        _insert_event(conn, "e3", topic="active-topic", days_ago=1)
        analyzer = TemporalAnalyzer(conn)
        decay = analyzer.knowledge_decay(days=60)
        decaying_topics = [d["topic"] for d in decay]
        assert "old-topic" in decaying_topics
        assert "active-topic" not in decaying_topics
        conn.close()

    def test_knowledge_decay_empty(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        analyzer = TemporalAnalyzer(conn)
        decay = analyzer.knowledge_decay(days=90)
        assert decay == []
        conn.close()

    def test_activity_heatmap(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        _insert_event(conn, "e1", days_ago=1, hour=9)
        _insert_event(conn, "e2", days_ago=1, hour=9)
        _insert_event(conn, "e3", days_ago=1, hour=14)
        analyzer = TemporalAnalyzer(conn)
        hm = analyzer.activity_heatmap(days=7)
        assert "hours" in hm
        assert len(hm["hours"]) >= 1
        conn.close()

    def test_activity_heatmap_empty(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        analyzer = TemporalAnalyzer(conn)
        hm = analyzer.activity_heatmap(days=7)
        assert hm["hours"] == {}
        conn.close()

    def test_session_comparison(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        _insert_event(conn, "e1", session_id="sa", topic="python",
                      concepts=["async", "await"], coherence=0.6)
        _insert_event(conn, "e2", session_id="sa", topic="rust",
                      concepts=["ownership"], coherence=0.7)
        _insert_event(conn, "e3", session_id="sb", topic="python",
                      concepts=["async", "threading"], coherence=0.8)
        analyzer = TemporalAnalyzer(conn)
        cmp = analyzer.session_comparison("sa", "sb")
        assert "python" in cmp["topic_overlap"]
        assert "rust" not in cmp["topic_overlap"]
        assert "async" in cmp["concept_overlap"]
        assert cmp["coherence_diff"] > 0  # sb has higher coherence
        conn.close()

    def test_session_comparison_no_overlap(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        _insert_event(conn, "e1", session_id="sa", topic="python")
        _insert_event(conn, "e2", session_id="sb", topic="rust")
        analyzer = TemporalAnalyzer(conn)
        cmp = analyzer.session_comparison("sa", "sb")
        assert cmp["topic_overlap"] == []
        conn.close()

    def test_session_comparison_empty_sessions(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        analyzer = TemporalAnalyzer(conn)
        cmp = analyzer.session_comparison("nonexistent-a", "nonexistent-b")
        assert cmp["topic_overlap"] == []
        assert cmp["coherence_a"] == 0.0
        conn.close()

    def test_get_temporal_stats(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        _insert_event(conn, "e1", days_ago=5)
        _insert_event(conn, "e2", days_ago=3)
        _insert_event(conn, "e3", days_ago=0)
        analyzer = TemporalAnalyzer(conn)
        stats = analyzer.get_temporal_stats()
        assert stats["total_events"] == 3
        assert stats["first_day"] is not None
        assert stats["busiest_day"] is not None
        assert stats["avg_events_per_day"] > 0
        conn.close()

    def test_get_temporal_stats_empty(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        analyzer = TemporalAnalyzer(conn)
        stats = analyzer.get_temporal_stats()
        assert stats["total_events"] == 0
        conn.close()


# ---------------------------------------------------------------------------
# agent_tools handle_tool tests
# ---------------------------------------------------------------------------

class TestAgentTools:

    @pytest.mark.asyncio
    async def test_store_learning_tool(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        from ucw.tools import agent_tools
        agent_tools._db = FakeDB(conn)

        result = await agent_tools.handle_tool("store_learning", {
            "text": "MCP servers use JSON-RPC 2.0",
            "project": "ucw",
            "tags": "mcp,protocol",
            "confidence": 0.8,
        })
        assert "content" in result
        assert "Learning Stored" in result["content"][0]["text"]
        conn.close()

    @pytest.mark.asyncio
    async def test_store_learning_empty_text(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        from ucw.tools import agent_tools
        agent_tools._db = FakeDB(conn)

        result = await agent_tools.handle_tool("store_learning", {"text": ""})
        assert result.get("isError") is True
        conn.close()

    @pytest.mark.asyncio
    async def test_search_learnings_tool(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        mem.store_learning("Temporal analysis requires events", project="ucw")

        from ucw.tools import agent_tools
        agent_tools._db = FakeDB(conn)

        result = await agent_tools.handle_tool("search_learnings", {
            "query": "Temporal",
        })
        assert "content" in result
        assert "Temporal" in result["content"][0]["text"]
        conn.close()

    @pytest.mark.asyncio
    async def test_search_learnings_no_results(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        from ucw.tools import agent_tools
        agent_tools._db = FakeDB(conn)

        result = await agent_tools.handle_tool("search_learnings", {
            "query": "nonexistent-xyz",
        })
        assert "No learnings found" in result["content"][0]["text"]
        conn.close()

    @pytest.mark.asyncio
    async def test_get_context_tool(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        mem = AgentMemory(conn)
        mem.store_learning("SQLite WAL is fast", confidence=0.9)
        _insert_event(conn, "ev1", topic="sqlite", summary="SQLite tuning session")

        from ucw.tools import agent_tools
        agent_tools._db = FakeDB(conn)

        result = await agent_tools.handle_tool("get_context", {
            "query": "SQLite",
        })
        text = result["content"][0]["text"]
        assert "Context for" in text
        conn.close()

    @pytest.mark.asyncio
    async def test_get_context_missing_query(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        from ucw.tools import agent_tools
        agent_tools._db = FakeDB(conn)

        result = await agent_tools.handle_tool("get_context", {})
        assert result.get("isError") is True
        conn.close()

    @pytest.mark.asyncio
    async def test_unknown_tool(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        from ucw.tools import agent_tools
        agent_tools._db = FakeDB(conn)

        result = await agent_tools.handle_tool("nonexistent_tool", {})
        assert result.get("isError") is True
        assert "Unknown" in result["content"][0]["text"]
        conn.close()

    @pytest.mark.asyncio
    async def test_no_db(self, tmp_ucw_dir):
        from ucw.tools import agent_tools
        agent_tools._db = None

        result = await agent_tools.handle_tool("store_learning", {"text": "test"})
        assert result.get("isError") is True


# ---------------------------------------------------------------------------
# temporal_tools handle_tool tests
# ---------------------------------------------------------------------------

class TestTemporalTools:

    @pytest.mark.asyncio
    async def test_topic_evolution_tool(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        _insert_event(conn, "e1", topic="python", days_ago=2)
        _insert_event(conn, "e2", topic="rust", days_ago=1)

        from ucw.tools import temporal_tools
        temporal_tools._db = FakeDB(conn)

        result = await temporal_tools.handle_tool("topic_evolution", {"days": 7})
        assert "Topic Evolution" in result["content"][0]["text"]
        conn.close()

    @pytest.mark.asyncio
    async def test_topic_evolution_empty(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        from ucw.tools import temporal_tools
        temporal_tools._db = FakeDB(conn)

        result = await temporal_tools.handle_tool("topic_evolution", {"days": 7})
        assert "No topic data" in result["content"][0]["text"]
        conn.close()

    @pytest.mark.asyncio
    async def test_skill_trajectory_tool(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        _insert_event(conn, "e1", topic="python", coherence=0.4, days_ago=5)
        _insert_event(conn, "e2", topic="python", coherence=0.7, days_ago=1)

        from ucw.tools import temporal_tools
        temporal_tools._db = FakeDB(conn)

        result = await temporal_tools.handle_tool("skill_trajectory", {
            "topic": "python", "days": 10,
        })
        text = result["content"][0]["text"]
        assert "Skill Trajectory" in text
        assert "python" in text
        conn.close()

    @pytest.mark.asyncio
    async def test_skill_trajectory_missing_topic(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        from ucw.tools import temporal_tools
        temporal_tools._db = FakeDB(conn)

        result = await temporal_tools.handle_tool("skill_trajectory", {})
        assert result.get("isError") is True
        conn.close()

    @pytest.mark.asyncio
    async def test_temporal_insights_tool(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        _insert_event(conn, "e1", topic="python", days_ago=5, hour=10)
        _insert_event(conn, "e2", topic="rust", days_ago=1, hour=14)

        from ucw.tools import temporal_tools
        temporal_tools._db = FakeDB(conn)

        result = await temporal_tools.handle_tool("temporal_insights", {"days": 30})
        text = result["content"][0]["text"]
        assert "Temporal Insights" in text
        assert "Overview" in text
        conn.close()

    @pytest.mark.asyncio
    async def test_temporal_insights_empty(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        from ucw.tools import temporal_tools
        temporal_tools._db = FakeDB(conn)

        result = await temporal_tools.handle_tool("temporal_insights", {"days": 30})
        assert "content" in result
        conn.close()

    @pytest.mark.asyncio
    async def test_unknown_temporal_tool(self, tmp_ucw_dir):
        conn = _make_db(tmp_ucw_dir)
        from ucw.tools import temporal_tools
        temporal_tools._db = FakeDB(conn)

        result = await temporal_tools.handle_tool("nonexistent", {})
        assert result.get("isError") is True
        conn.close()

    @pytest.mark.asyncio
    async def test_no_db_temporal(self, tmp_ucw_dir):
        from ucw.tools import temporal_tools
        temporal_tools._db = None

        result = await temporal_tools.handle_tool("topic_evolution", {})
        assert result.get("isError") is True
