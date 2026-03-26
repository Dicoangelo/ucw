"""Tests for the UCW Knowledge Graph — Epic 1

Covers:
  - Entity extraction (entity_extractor.py)
  - Relationship mapping (relationship_mapper.py)
  - Graph store CRUD (graph_store.py)
  - Graph tools MCP dispatcher (graph_tools.py)
  - Edge cases: empty input, duplicates, unicode
"""

import hashlib
import importlib
import sqlite3
import time

import pytest

from ucw.intelligence.entity_extractor import extract_entities
from ucw.intelligence.relationship_mapper import map_relationships
from ucw.intelligence.graph_store import GraphStore


# Load the migration module (filename starts with digits, can't import normally)
_migration_mod = importlib.import_module("ucw.db.migrations.001_knowledge_graph")
apply_kg_migration = _migration_mod.up


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity_id(name: str, entity_type: str) -> str:
    return hashlib.sha256(f"{name}:{entity_type}".encode()).hexdigest()[:16]


def _make_rel_id(source: str, target: str, rel_type: str) -> str:
    return hashlib.sha256(f"{source}:{target}:{rel_type}".encode()).hexdigest()[:16]


@pytest.fixture
def kg_conn(tmp_path):
    """SQLite connection with knowledge graph tables applied."""
    db_path = tmp_path / "test_kg.db"
    conn = sqlite3.connect(str(db_path))
    apply_kg_migration(conn)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def graph_store(kg_conn):
    """GraphStore backed by a test database."""
    return GraphStore(kg_conn)


# ===========================================================================
# Entity Extractor Tests
# ===========================================================================

class TestEntityExtractor:

    def test_extract_technology_terms(self):
        text = "We built the API using Python and React with a PostgreSQL database."
        entities = extract_entities(text)
        names = {e["name"].lower() for e in entities}
        assert "python" in names
        assert "react" in names
        assert "postgresql" in names

    def test_extract_tool_terms(self):
        text = "I used Claude and ChatGPT to compare responses, then edited in Cursor."
        entities = extract_entities(text)
        names = {e["name"].lower() for e in entities}
        assert "claude" in names
        assert "chatgpt" in names
        assert "cursor" in names

    def test_extract_platform_terms(self):
        text = "Deployed on Vercel, code on GitHub, discussed on Discord."
        entities = extract_entities(text)
        names = {e["name"].lower() for e in entities}
        assert "vercel" in names
        assert "github" in names
        assert "discord" in names

    def test_extract_organization_terms(self):
        text = "Anthropic and OpenAI are leading the AI race."
        entities = extract_entities(text)
        names = {e["name"].lower() for e in entities}
        assert "anthropic" in names
        assert "openai" in names

    def test_extract_person_names(self):
        text = "John Smith presented the results to Jane Doe last week."
        entities = extract_entities(text)
        names = {e["name"] for e in entities}
        assert "John Smith" in names
        assert "Jane Doe" in names

    def test_extract_concepts_from_list(self):
        text = "Working on the new feature."
        concepts = ["cognitive equity", "knowledge graph", "emergence detection"]
        entities = extract_entities(text, concepts=concepts)
        names = {e["name"].lower() for e in entities}
        assert "cognitive equity" in names
        assert "knowledge graph" in names

    def test_extract_project_names(self):
        text = "The project UCW uses a SQLite database for storage."
        entities = extract_entities(text)
        names = {e["name"].lower() for e in entities}
        assert "ucw" in names or "sqlite" in names

    def test_empty_input(self):
        assert extract_entities("") == []
        assert extract_entities("", topic="", concepts=None) == []

    def test_dedup_by_lowercase(self):
        text = "Python is great. I love python. PYTHON rules."
        entities = extract_entities(text)
        python_entities = [e for e in entities if e["name"].lower() == "python"]
        assert len(python_entities) == 1

    def test_confidence_levels(self):
        text = "Using Docker and React in the project."
        concepts = ["microservices"]
        entities = extract_entities(text, concepts=concepts)
        emap = {e["name"].lower(): e for e in entities}
        # Keyword match = 0.9
        assert emap["docker"]["confidence"] == 0.9
        # Concept list = 0.7
        assert emap["microservices"]["confidence"] == 0.7

    def test_person_name_excludes_common_phrases(self):
        text = "The New York office handles North America operations."
        entities = extract_entities(text)
        names = {e["name"].lower() for e in entities}
        assert "new york" not in names
        assert "north america" not in names

    def test_mixed_content(self):
        text = (
            "Dico Angelo built a Python MCP server using Claude. "
            "The project ResearchGravity connects to Supabase and runs on Vercel."
        )
        entities = extract_entities(text)
        names = {e["name"].lower() for e in entities}
        assert "python" in names
        assert "claude" in names
        assert "supabase" in names
        assert "vercel" in names
        # Person
        person_entities = [e for e in entities if e["type"] == "person"]
        person_names = {e["name"] for e in person_entities}
        assert "Dico Angelo" in person_names

    def test_unicode_input(self):
        text = "Using Python to analyze data from Zurich."
        entities = extract_entities(text)
        names = {e["name"].lower() for e in entities}
        assert "python" in names

    def test_no_external_deps(self):
        """Ensure the extractor does not import spacy, nltk, etc."""
        import ucw.intelligence.entity_extractor as mod
        import sys
        for dep in ("spacy", "nltk", "transformers", "stanza"):
            assert dep not in sys.modules or dep not in dir(mod)


# ===========================================================================
# Relationship Mapper Tests
# ===========================================================================

class TestRelationshipMapper:

    def test_basic_co_occurrence(self):
        entities = [
            {"name": "Python", "type": "technology", "confidence": 0.9},
            {"name": "Claude", "type": "tool", "confidence": 0.9},
        ]
        rels = map_relationships(entities, "evt-1", time.time_ns())
        assert len(rels) == 1
        assert rels[0]["type"] == "co_occurrence"
        assert rels[0]["evidence_event_id"] == "evt-1"

    def test_topic_related_same_type(self):
        entities = [
            {"name": "Python", "type": "technology", "confidence": 0.9},
            {"name": "React", "type": "technology", "confidence": 0.9},
        ]
        rels = map_relationships(entities, "evt-2", time.time_ns())
        assert len(rels) == 1
        assert rels[0]["type"] == "topic_related"

    def test_empty_entities(self):
        assert map_relationships([], "evt-3", time.time_ns()) == []

    def test_single_entity(self):
        entities = [{"name": "Python", "type": "technology", "confidence": 0.9}]
        assert map_relationships(entities, "evt-4", time.time_ns()) == []

    def test_multiple_entities_pairwise(self):
        entities = [
            {"name": "Python", "type": "technology", "confidence": 0.9},
            {"name": "React", "type": "technology", "confidence": 0.9},
            {"name": "Claude", "type": "tool", "confidence": 0.9},
        ]
        rels = map_relationships(entities, "evt-5", time.time_ns())
        # 3 entities -> 3 pairs: (P,R), (P,C), (R,C)
        assert len(rels) == 3

    def test_no_duplicate_pairs(self):
        entities = [
            {"name": "A", "type": "concept", "confidence": 0.5},
            {"name": "B", "type": "concept", "confidence": 0.5},
        ]
        rels = map_relationships(entities, "evt-6", time.time_ns())
        assert len(rels) == 1

    def test_weight_calculation(self):
        entities = [
            {"name": "Python", "type": "technology", "confidence": 0.9},
            {"name": "Docker", "type": "technology", "confidence": 0.9},
        ]
        rels = map_relationships(entities, "evt-7", time.time_ns())
        # Same type gets 1.2x boost: (0.9+0.9)/2 * 1.2 = 1.08 -> capped at 1.0
        assert rels[0]["weight"] == 1.0


# ===========================================================================
# Graph Store Tests
# ===========================================================================

class TestGraphStore:

    def test_upsert_entity_insert(self, graph_store, kg_conn):
        eid = _make_entity_id("python", "technology")
        ts = time.time_ns()
        result = graph_store.upsert_entity(eid, "python", "technology", 0.9, ts)
        assert result is True

        entity = graph_store.get_entity("python")
        assert entity is not None
        assert entity["name"] == "python"
        assert entity["type"] == "technology"
        assert entity["event_count"] == 1

    def test_upsert_entity_update_increments_count(self, graph_store):
        eid = _make_entity_id("react", "technology")
        ts1 = time.time_ns()
        graph_store.upsert_entity(eid, "react", "technology", 0.8, ts1)

        ts2 = time.time_ns()
        graph_store.upsert_entity(eid, "react", "technology", 0.9, ts2)

        entity = graph_store.get_entity("react")
        assert entity["event_count"] == 2
        assert entity["confidence"] == 0.9  # Takes higher confidence

    def test_upsert_relationship_insert(self, graph_store):
        src_id = _make_entity_id("python", "technology")
        tgt_id = _make_entity_id("claude", "tool")
        graph_store.upsert_entity(src_id, "python", "technology", 0.9, time.time_ns())
        graph_store.upsert_entity(tgt_id, "claude", "tool", 0.9, time.time_ns())

        rel_id = _make_rel_id("python", "claude", "co_occurrence")
        ts = time.time_ns()
        result = graph_store.upsert_relationship(
            rel_id, src_id, tgt_id, "co_occurrence", 0.5, "evt-1", ts
        )
        assert result is True

    def test_upsert_relationship_increments_count(self, graph_store):
        src_id = _make_entity_id("docker", "technology")
        tgt_id = _make_entity_id("kubernetes", "technology")
        graph_store.upsert_entity(src_id, "docker", "technology", 0.9, time.time_ns())
        graph_store.upsert_entity(tgt_id, "kubernetes", "technology", 0.9, time.time_ns())

        rel_id = _make_rel_id("docker", "kubernetes", "topic_related")
        ts = time.time_ns()
        graph_store.upsert_relationship(rel_id, src_id, tgt_id, "topic_related", 0.5, "evt-1", ts)
        graph_store.upsert_relationship(rel_id, src_id, tgt_id, "topic_related", 0.5, "evt-2", ts)

        rels = graph_store.get_relationships(src_id)
        assert len(rels) == 1
        assert rels[0]["occurrence_count"] == 2
        assert "evt-1" in rels[0]["evidence_event_ids"]
        assert "evt-2" in rels[0]["evidence_event_ids"]

    def test_get_entity_case_insensitive(self, graph_store):
        eid = _make_entity_id("python", "technology")
        graph_store.upsert_entity(eid, "python", "technology", 0.9, time.time_ns())

        assert graph_store.get_entity("Python") is not None
        assert graph_store.get_entity("PYTHON") is not None

    def test_get_entity_not_found(self, graph_store):
        assert graph_store.get_entity("nonexistent") is None

    def test_search_entities(self, graph_store):
        graph_store.upsert_entity(
            _make_entity_id("python", "technology"), "python", "technology", 0.9, time.time_ns()
        )
        graph_store.upsert_entity(
            _make_entity_id("python3", "technology"), "python3", "technology", 0.8, time.time_ns()
        )
        graph_store.upsert_entity(
            _make_entity_id("claude", "tool"), "claude", "tool", 0.9, time.time_ns()
        )

        results = graph_store.search_entities("python")
        names = {r["name"] for r in results}
        assert "python" in names
        assert "python3" in names
        assert "claude" not in names

    def test_search_entities_with_type_filter(self, graph_store):
        graph_store.upsert_entity(
            _make_entity_id("python", "technology"), "python", "technology", 0.9, time.time_ns()
        )
        graph_store.upsert_entity(
            _make_entity_id("claude", "tool"), "claude", "tool", 0.9, time.time_ns()
        )

        results = graph_store.search_entities("", type_filter="tool")
        assert len(results) == 1
        assert results[0]["name"] == "claude"

    def test_get_graph_stats(self, graph_store):
        graph_store.upsert_entity(
            _make_entity_id("python", "technology"), "python", "technology", 0.9, time.time_ns()
        )
        graph_store.upsert_entity(
            _make_entity_id("claude", "tool"), "claude", "tool", 0.9, time.time_ns()
        )

        stats = graph_store.get_graph_stats()
        assert stats["entity_count"] == 2
        assert stats["relationship_count"] == 0
        assert "technology" in stats["entity_types"]
        assert "tool" in stats["entity_types"]

    def test_get_graph_stats_empty(self, graph_store):
        stats = graph_store.get_graph_stats()
        assert stats["entity_count"] == 0
        assert stats["relationship_count"] == 0


# ===========================================================================
# Graph Tools Tests
# ===========================================================================

class TestGraphTools:

    @pytest.fixture(autouse=True)
    def setup_tools_db(self, kg_conn, tmp_ucw_dir):
        """Inject a mock DB object into graph_tools."""
        from ucw.tools import graph_tools

        class MockDB:
            def __init__(self, conn):
                self._conn = conn

        mock_db = MockDB(kg_conn)
        graph_tools.set_db(mock_db)
        yield
        graph_tools.set_db(None)

    @pytest.mark.asyncio
    async def test_handle_tool_unknown(self):
        from ucw.tools.graph_tools import handle_tool
        result = await handle_tool("nonexistent_tool", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_knowledge_graph_stats(self, graph_store):
        graph_store.upsert_entity(
            _make_entity_id("python", "technology"), "python", "technology", 0.9, time.time_ns()
        )
        from ucw.tools.graph_tools import handle_tool
        result = await handle_tool("knowledge_graph", {"action": "stats"})
        text = result["content"][0]["text"]
        assert "Total Entities" in text
        assert "1" in text

    @pytest.mark.asyncio
    async def test_knowledge_graph_search(self, graph_store):
        graph_store.upsert_entity(
            _make_entity_id("python", "technology"), "python", "technology", 0.9, time.time_ns()
        )
        from ucw.tools.graph_tools import handle_tool
        result = await handle_tool("knowledge_graph", {"query": "python", "action": "search"})
        text = result["content"][0]["text"]
        assert "python" in text.lower()

    @pytest.mark.asyncio
    async def test_knowledge_graph_search_no_results(self):
        from ucw.tools.graph_tools import handle_tool
        result = await handle_tool("knowledge_graph", {"query": "zzzznothing", "action": "search"})
        text = result["content"][0]["text"]
        assert "No entities found" in text

    @pytest.mark.asyncio
    async def test_knowledge_graph_relationships(self, graph_store):
        src_id = _make_entity_id("python", "technology")
        tgt_id = _make_entity_id("claude", "tool")
        graph_store.upsert_entity(src_id, "python", "technology", 0.9, time.time_ns())
        graph_store.upsert_entity(tgt_id, "claude", "tool", 0.9, time.time_ns())
        rel_id = _make_rel_id("python", "claude", "co_occurrence")
        graph_store.upsert_relationship(rel_id, src_id, tgt_id, "co_occurrence", 0.5, "e1", time.time_ns())

        from ucw.tools.graph_tools import handle_tool
        result = await handle_tool("knowledge_graph", {"query": "python", "action": "relationships"})
        text = result["content"][0]["text"]
        assert "claude" in text.lower()

    @pytest.mark.asyncio
    async def test_graph_analyze_no_entity(self):
        from ucw.tools.graph_tools import handle_tool
        result = await handle_tool("graph_analyze", {})
        text = result["content"][0]["text"]
        assert "Knowledge Graph Analysis" in text

    @pytest.mark.asyncio
    async def test_graph_analyze_specific_entity(self, graph_store):
        eid = _make_entity_id("python", "technology")
        graph_store.upsert_entity(eid, "python", "technology", 0.9, time.time_ns())

        from ucw.tools.graph_tools import handle_tool
        result = await handle_tool("graph_analyze", {"entity_name": "python"})
        text = result["content"][0]["text"]
        assert "Entity Analysis" in text
        assert "python" in text.lower()

    @pytest.mark.asyncio
    async def test_graph_analyze_entity_not_found(self):
        from ucw.tools.graph_tools import handle_tool
        result = await handle_tool("graph_analyze", {"entity_name": "nonexistent"})
        text = result["content"][0]["text"]
        assert "not found" in text.lower()
