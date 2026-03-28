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


# ── Export CLI Tests ─────────────────────────────────


@pytest.fixture
def export_ready_db(tmp_ucw_dir):
    """DB with schema + sample events for export tests."""
    import time

    db_path = tmp_ucw_dir / "cognitive.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)

    now = time.time_ns()
    events = [
        ("evt-e01", now - 3_000_000_000, "claude-desktop",
         "architecture", "Designing UCW layers", "high-signal", 1200),
        ("evt-e02", now - 2_000_000_000, "cursor",
         "debugging", "Fixing import cycle", "neutral", 800),
        ("evt-e03", now - 1_000_000_000, "claude-desktop",
         "testing", "Writing pytest fixtures", "high-signal", 950),
    ]

    for eid, ts, plat, topic, summary, gut, clen in events:
        conn.execute(
            "INSERT INTO cognitive_events ("
            "  event_id, timestamp_ns, direction, stage,"
            "  light_topic, light_summary, instinct_gut_signal,"
            "  content_length, platform"
            ") VALUES (?, ?, 'inbound', 'captured',"
            "  ?, ?, ?, ?, ?)",
            (eid, ts, topic, summary, gut, clen, plat),
        )
    conn.commit()
    conn.close()
    return db_path


class TestExportCLI:
    def test_export_json_default(self, runner, export_ready_db):
        result = runner.invoke(main, ["export"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3
        assert "event_id" in data[0]
        assert "timestamp_iso" in data[0]
        # Verify ISO timestamp was added
        assert data[0]["timestamp_iso"] is not None

    def test_export_csv(self, runner, export_ready_db):
        result = runner.invoke(main, ["export", "--format", "csv"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 4  # header + 3 rows
        header = lines[0]
        assert "event_id" in header
        assert "platform" in header
        assert "light_topic" in header

    def test_export_markdown(self, runner, export_ready_db):
        result = runner.invoke(main, ["export", "--format", "markdown"])
        assert result.exit_code == 0
        assert "# UCW Export" in result.output
        assert "## architecture" in result.output
        assert "## debugging" in result.output
        assert "**Platform:**" in result.output

    def test_export_platform_filter(self, runner, export_ready_db):
        result = runner.invoke(
            main, ["export", "--platform", "cursor", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["platform"] == "cursor"

    def test_export_to_file(self, runner, export_ready_db, tmp_path):
        out_file = str(tmp_path / "export.json")
        result = runner.invoke(main, ["export", "--output", out_file])
        assert result.exit_code == 0
        # Count message goes to stderr
        assert "Exported 3 events" in result.output
        # Verify file was written
        import json as json_mod
        with open(out_file) as f:
            data = json_mod.load(f)
        assert len(data) == 3

    def test_export_no_data(self, runner, tmp_ucw_dir):
        """Export with empty DB returns 'No events to export.'"""
        db_path = tmp_ucw_dir / "cognitive.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()

        result = runner.invoke(main, ["export"])
        assert result.exit_code == 0
        assert "No events to export." in result.output
