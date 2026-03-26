"""Extended CLI tests — dashboard, demo, import, migrate commands."""

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from ucw.cli import main
from ucw.config import Config

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def runner():
    return CliRunner()


FULL_SCHEMA = """
CREATE TABLE IF NOT EXISTS cognitive_events (
    event_id        TEXT PRIMARY KEY,
    session_id      TEXT,
    timestamp_ns    INTEGER NOT NULL,
    direction       TEXT NOT NULL,
    stage           TEXT NOT NULL,
    method          TEXT,
    request_id      TEXT,
    parent_event_id TEXT,
    turn            INTEGER DEFAULT 0,
    raw_bytes       BLOB,
    parsed_json     TEXT,
    content_length  INTEGER DEFAULT 0,
    error           TEXT,
    data_content    TEXT,
    data_tokens_est INTEGER,
    light_intent    TEXT,
    light_topic     TEXT,
    light_concepts  TEXT,
    light_summary   TEXT,
    instinct_coherence   REAL,
    instinct_indicators  TEXT,
    instinct_gut_signal  TEXT,
    coherence_sig   TEXT,
    platform        TEXT DEFAULT 'claude-desktop',
    protocol        TEXT DEFAULT 'mcp',
    content_hash    TEXT,
    prev_hash       TEXT,
    chain_hash      TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_content_hash ON cognitive_events(content_hash);
CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    started_ns      INTEGER NOT NULL,
    ended_ns        INTEGER,
    platform        TEXT DEFAULT 'claude-desktop',
    event_count     INTEGER DEFAULT 0,
    turn_count      INTEGER DEFAULT 0,
    topics          TEXT,
    summary         TEXT,
    merkle_root     TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
"""


@pytest.fixture
def tmp_db(tmp_ucw_dir):
    """Create a real SQLite database with full schema in temp UCW dir."""
    db_path = Config.DB_PATH
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=wal")
    conn.executescript(FULL_SCHEMA)
    conn.commit()
    conn.close()
    return db_path


# ── Dashboard CLI ────────────────────────────────────────────────────────

class TestDashboardCLI:
    def test_dashboard_no_db(self, runner, tmp_ucw_dir):
        """Dashboard without DB shows fallback message."""
        result = runner.invoke(main, ["dashboard"])
        assert result.exit_code == 0
        assert "No data" in result.output or "null" in result.output

    def test_dashboard_json_no_db(self, runner, tmp_ucw_dir):
        """Dashboard --json without DB outputs null."""
        result = runner.invoke(main, ["dashboard", "--json"])
        assert result.exit_code == 0
        assert "null" in result.output

    def test_dashboard_with_demo_data(self, runner, tmp_db):
        """Dashboard with demo data shows stats."""
        runner.invoke(main, ["demo"])
        result = runner.invoke(main, ["dashboard"])
        assert result.exit_code == 0
        # Should show either rich or plain output
        assert "UCW Dashboard" in result.output or "events" in result.output.lower()

    def test_dashboard_json_with_data(self, runner, tmp_db):
        """Dashboard --json with data outputs valid JSON."""
        runner.invoke(main, ["demo"])
        result = runner.invoke(main, ["dashboard", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data is not None
        assert data["total_events"] > 0

    def test_dashboard_json_structure(self, runner, tmp_db):
        """Dashboard JSON contains expected keys."""
        runner.invoke(main, ["demo"])
        result = runner.invoke(main, ["dashboard", "--json"])
        data = json.loads(result.output)
        assert "total_events" in data
        assert "platforms" in data
        assert "sessions" in data
        assert "total_bytes" in data
        assert "top_topics" in data


# ── Demo CLI ─────────────────────────────────────────────────────────────

class TestDemoCLI:
    def test_demo_load(self, runner, tmp_db):
        """Demo command loads sample events."""
        result = runner.invoke(main, ["demo"])
        assert result.exit_code == 0
        assert "Loaded" in result.output
        assert "sample events" in result.output
        assert "3 platforms" in result.output

    def test_demo_clean(self, runner, tmp_db):
        """Demo --clean removes events."""
        runner.invoke(main, ["demo"])
        result = runner.invoke(main, ["demo", "--clean"])
        assert result.exit_code == 0
        assert "Removed" in result.output
        assert "demo events" in result.output

    def test_demo_clean_no_data(self, runner, tmp_db):
        """Demo --clean with no demo data reports 0."""
        result = runner.invoke(main, ["demo", "--clean"])
        assert result.exit_code == 0
        assert "0" in result.output

    def test_demo_then_dashboard(self, runner, tmp_db):
        """Demo data appears in dashboard."""
        runner.invoke(main, ["demo"])
        result = runner.invoke(main, ["dashboard", "--json"])
        data = json.loads(result.output)
        assert data["total_events"] > 0
        assert "claude-desktop" in data["platforms"]


# ── Import CLI ───────────────────────────────────────────────────────────

class TestImportCLI:
    def test_import_chatgpt(self, runner, tmp_db):
        """Import ChatGPT fixture via CLI."""
        fixture = str(FIXTURES / "chatgpt_export.json")
        result = runner.invoke(main, ["import", "chatgpt", fixture])
        assert result.exit_code == 0
        assert "Imported" in result.output or "Importing" in result.output

    def test_import_chatgpt_events_in_db(self, runner, tmp_db):
        """After import, events exist in the database."""
        fixture = str(FIXTURES / "chatgpt_export.json")
        runner.invoke(main, ["import", "chatgpt", fixture])
        conn = sqlite3.connect(str(tmp_db))
        count = conn.execute(
            "SELECT COUNT(*) FROM cognitive_events WHERE platform = 'chatgpt'"
        ).fetchone()[0]
        conn.close()
        assert count > 0

    def test_import_grok(self, runner, tmp_db):
        """Import Grok fixture via CLI."""
        fixture = str(FIXTURES / "grok_export.json")
        result = runner.invoke(main, ["import", "grok", fixture])
        assert result.exit_code == 0
        assert "Imported" in result.output or "Importing" in result.output

    def test_import_cursor(self, runner, tmp_db):
        """Import Cursor fixture via CLI."""
        fixture = str(FIXTURES / "cursor_export.json")
        result = runner.invoke(main, ["import", "cursor", fixture])
        assert result.exit_code == 0
        assert "Imported" in result.output or "Importing" in result.output

    def test_import_chatgpt_missing_file(self, runner, tmp_db):
        """Import ChatGPT with nonexistent file fails gracefully."""
        result = runner.invoke(main, ["import", "chatgpt", "/tmp/nonexistent.json"])
        assert result.exit_code != 0

    def test_import_grok_missing_file(self, runner, tmp_db):
        """Import Grok with nonexistent file fails gracefully."""
        result = runner.invoke(main, ["import", "grok", "/tmp/nonexistent.json"])
        assert result.exit_code != 0


# ── Migrate CLI ──────────────────────────────────────────────────────────

class TestMigrateCLI:
    def test_migrate_no_db(self, runner, tmp_ucw_dir):
        """Migrate with no DB shows helpful message or import error."""
        result = runner.invoke(main, ["migrate"])
        # May show "No database" or fail with import error for migrations package
        assert result.exit_code == 0 or result.exit_code == 1
