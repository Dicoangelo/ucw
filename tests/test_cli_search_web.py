"""Tests for UCW CLI search, index, and web commands."""

import importlib
import json
import sqlite3

import pytest
from click.testing import CliRunner

from ucw.cli import main
from ucw.db.sqlite import SCHEMA_SQL


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def search_ready_db(tmp_ucw_dir):
    """DB with schema + FTS5 + sample events for search tests."""
    import time

    db_path = tmp_ucw_dir / "cognitive.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)

    # Apply FTS5 migration
    mod = importlib.import_module(
        "ucw.db.migrations.006_fts5_search"
    )
    mod.up(conn)
    conn.commit()

    # Apply embedding cache migration
    mod = importlib.import_module(
        "ucw.db.migrations.007_embedding_cache"
    )
    mod.up(conn)
    conn.commit()

    now = time.time_ns()
    events = [
        ("evt-s01", "Building a Python MCP server for cognitive capture",
         "mcp-server", "MCP server implementation",
         "python,mcp,server", "claude-desktop"),
        ("evt-s02", "React 19 concurrent features and suspense boundaries",
         "react", "React 19 deep dive",
         "react,frontend,ui", "cursor"),
        ("evt-s03", "SQLite WAL mode and FTS5 full-text search indexing",
         "sqlite", "SQLite performance tuning",
         "sqlite,database,fts5", "claude-desktop"),
    ]

    for eid, content, topic, summary, concepts, platform in events:
        conn.execute(
            "INSERT INTO cognitive_events ("
            "  event_id, timestamp_ns, direction, stage,"
            "  data_content, light_topic, light_summary,"
            "  light_concepts, light_intent, platform"
            ") VALUES (?, ?, 'inbound', 'captured',"
            "  ?, ?, ?, ?, 'explore', ?)",
            (eid, now, content, topic, summary, concepts, platform),
        )
    conn.commit()
    conn.close()
    return db_path


# ── Search CLI Tests ──────────────────────────────────


class TestSearchCLI:
    def test_basic_search(self, runner, search_ready_db):
        result = runner.invoke(main, ["search", "Python MCP"])
        assert result.exit_code == 0
        assert "result" in result.output.lower() or "mcp" in result.output.lower()

    def test_search_no_results(self, runner, search_ready_db):
        result = runner.invoke(main, ["search", "quantum computing"])
        assert result.exit_code == 0
        assert "No results" in result.output

    def test_search_platform_filter(self, runner, search_ready_db):
        result = runner.invoke(
            main, ["search", "React", "--platform", "cursor"]
        )
        assert result.exit_code == 0

    def test_search_json_output(self, runner, search_ready_db):
        result = runner.invoke(
            main, ["search", "SQLite", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "event_id" in data[0]

    def test_search_limit(self, runner, search_ready_db):
        result = runner.invoke(
            main, ["search", "Python", "--limit", "1", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) <= 1

    def test_search_no_db(self, runner, tmp_ucw_dir):
        result = runner.invoke(main, ["search", "anything"])
        assert result.exit_code == 0
        assert "No database" in result.output

    def test_search_no_semantic_flag(self, runner, search_ready_db):
        result = runner.invoke(
            main, ["search", "SQLite", "--no-semantic"]
        )
        assert result.exit_code == 0
        assert "keyword" in result.output.lower()


# ── Index CLI Tests ───────────────────────────────────


class TestIndexCLI:
    def test_index_status(self, runner, search_ready_db):
        result = runner.invoke(main, ["index", "--status"])
        # May fail if embeddings not installed — that's ok
        if "requires embeddings" in result.output.lower():
            return
        assert result.exit_code == 0
        assert "Total events" in result.output

    def test_index_no_db(self, runner, tmp_ucw_dir):
        result = runner.invoke(main, ["index"])
        assert result.exit_code == 0
        # Either "No database" or "requires embeddings"
        assert (
            "No database" in result.output
            or "requires embeddings" in result.output.lower()
            or "Install with" in result.output
        )


# ── Web CLI Tests ─────────────────────────────────────


class TestWebCLI:
    def test_web_no_db(self, runner, tmp_ucw_dir):
        result = runner.invoke(main, ["web"])
        assert result.exit_code == 0
        assert "No database" in result.output

    def test_web_help(self, runner):
        result = runner.invoke(main, ["web", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.output
        assert "--host" in result.output
        assert "--no-open" in result.output
