"""Tests for UCW capture health: capture-test CLI and dashboard integration."""

import sqlite3
import time

import pytest
from click.testing import CliRunner

from ucw.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def _create_schema(db_path):
    """Create minimal schema for capture health tests."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cognitive_events (
            event_id        TEXT PRIMARY KEY,
            session_id      TEXT,
            timestamp_ns    INTEGER NOT NULL,
            direction       TEXT NOT NULL,
            stage           TEXT NOT NULL,
            method          TEXT,
            content_length  INTEGER DEFAULT 0,
            data_content    TEXT,
            light_intent    TEXT,
            light_topic     TEXT,
            instinct_gut_signal TEXT,
            coherence_sig   TEXT,
            platform        TEXT DEFAULT 'claude-desktop',
            protocol        TEXT DEFAULT 'mcp',
            created_at      TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sessions (
            session_id  TEXT PRIMARY KEY,
            started_ns  INTEGER NOT NULL,
            ended_ns    INTEGER,
            platform    TEXT DEFAULT 'claude-desktop',
            event_count INTEGER DEFAULT 0,
            turn_count  INTEGER DEFAULT 0
        );
    """)
    conn.close()


def _insert_event(db_path, event_id, timestamp_ns, platform):
    """Insert a single cognitive event for testing."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cognitive_events "
        "(event_id, session_id, timestamp_ns, direction, "
        "stage, method, content_length, platform, protocol) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_id, "test-session", timestamp_ns,
            "inbound", "complete", "test", 42,
            platform, "mcp",
        ),
    )
    conn.execute(
        "INSERT OR IGNORE INTO sessions "
        "(session_id, started_ns, platform, event_count) "
        "VALUES (?, ?, ?, ?)",
        ("test-session", timestamp_ns, platform, 1),
    )
    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# capture-test CLI tests
# -------------------------------------------------------------------

class TestCaptureTestCommand:
    def test_capture_test_no_db(self, runner, tmp_ucw_dir):
        """capture-test with no DB shows FAIL."""
        result = runner.invoke(main, ["capture-test"])
        assert result.exit_code == 0
        assert "[FAIL]" in result.output
        assert "Database" in result.output

    def test_capture_test_with_data(self, runner, tmp_ucw_dir):
        """capture-test with recent events shows PASS."""
        from ucw.config import Config

        _create_schema(Config.DB_PATH)
        now_ns = time.time_ns()
        _insert_event(
            Config.DB_PATH, "evt-1", now_ns - 10**9,
            "claude-desktop",
        )
        _insert_event(
            Config.DB_PATH, "evt-2", now_ns - 2 * 10**9,
            "chatgpt",
        )

        result = runner.invoke(main, ["capture-test"])
        assert result.exit_code == 0
        assert "[PASS] Database: 2 events" in result.output
        assert "[PASS] Recent activity:" in result.output
        assert "2 events in last 24h" in result.output
        assert "[PASS] Platforms:" in result.output

    def test_capture_test_no_recent(self, runner, tmp_ucw_dir):
        """capture-test with only old events shows WARN."""
        from ucw.config import Config

        _create_schema(Config.DB_PATH)
        old_ns = time.time_ns() - 2 * 86400 * 10**9
        _insert_event(
            Config.DB_PATH, "old-1", old_ns,
            "claude-desktop",
        )

        result = runner.invoke(main, ["capture-test"])
        assert result.exit_code == 0
        assert "[PASS] Database: 1 events" in result.output
        assert "[WARN]" in result.output
        assert "No events in last 24h" in result.output

    def test_capture_test_no_mcp_config(
        self, runner, tmp_ucw_dir, tmp_path, monkeypatch
    ):
        """capture-test shows FAIL for MCP config when not found."""
        from ucw.config import Config

        _create_schema(Config.DB_PATH)
        now_ns = time.time_ns()
        _insert_event(
            Config.DB_PATH, "evt-1", now_ns,
            "claude-desktop",
        )

        # Point home to a temp dir with no MCP configs
        monkeypatch.setattr(
            "pathlib.Path.home",
            lambda: tmp_path,
        )

        result = runner.invoke(main, ["capture-test"])
        assert result.exit_code == 0
        assert "[FAIL] MCP config: Not found" in result.output

    def test_capture_test_summary_line(
        self, runner, tmp_ucw_dir
    ):
        """capture-test always shows a summary line."""
        result = runner.invoke(main, ["capture-test"])
        assert "passed" in result.output
        assert "failed" in result.output
        assert "warnings" in result.output


# -------------------------------------------------------------------
# Dashboard capture_health tests
# -------------------------------------------------------------------

class TestDashboardCaptureHealth:
    def test_dashboard_capture_health(self, tmp_ucw_dir):
        """get_dashboard_data returns capture_health fields."""
        from ucw.config import Config
        from ucw.dashboard import get_dashboard_data

        _create_schema(Config.DB_PATH)
        now_ns = time.time_ns()
        _insert_event(
            Config.DB_PATH, "evt-1", now_ns,
            "claude-desktop",
        )

        data = get_dashboard_data(Config.DB_PATH)
        assert data is not None
        assert 'capture_health' in data

        ch = data['capture_health']
        assert 'last_event_age_seconds' in ch
        assert 'events_last_24h' in ch
        assert 'events_last_7d' in ch
        assert 'active_platforms' in ch

    def test_dashboard_capture_health_empty_db(
        self, tmp_ucw_dir
    ):
        """Empty DB returns zeros for capture health."""
        from ucw.config import Config
        from ucw.dashboard import get_dashboard_data

        _create_schema(Config.DB_PATH)

        data = get_dashboard_data(Config.DB_PATH)
        ch = data['capture_health']
        assert ch['events_last_24h'] == 0
        assert ch['events_last_7d'] == 0
        assert ch['last_event_age_seconds'] is None
        assert ch['active_platforms'] == []

    def test_dashboard_capture_health_with_events(
        self, tmp_ucw_dir
    ):
        """Events in DB return correct counts."""
        from ucw.config import Config
        from ucw.dashboard import get_dashboard_data

        _create_schema(Config.DB_PATH)
        now_ns = time.time_ns()

        # 2 recent events
        _insert_event(
            Config.DB_PATH, "r1", now_ns - 10**9,
            "claude-desktop",
        )
        _insert_event(
            Config.DB_PATH, "r2", now_ns - 2 * 10**9,
            "chatgpt",
        )
        # 1 old event (8 days ago)
        old_ns = now_ns - 8 * 86400 * 10**9
        _insert_event(
            Config.DB_PATH, "o1", old_ns, "cursor",
        )

        data = get_dashboard_data(Config.DB_PATH)
        ch = data['capture_health']
        assert ch['events_last_24h'] == 2
        assert ch['events_last_7d'] == 2
        assert ch['last_event_age_seconds'] is not None
        assert ch['last_event_age_seconds'] < 10
        assert set(ch['active_platforms']) == {
            "claude-desktop", "chatgpt",
        }

    def test_render_plain_capture_health(self, tmp_ucw_dir):
        """render_plain includes capture health section."""
        from ucw.config import Config
        from ucw.dashboard import (
            get_dashboard_data,
            render_plain,
        )

        _create_schema(Config.DB_PATH)
        now_ns = time.time_ns()
        _insert_event(
            Config.DB_PATH, "evt-1", now_ns,
            "claude-desktop",
        )

        data = get_dashboard_data(Config.DB_PATH)
        text = render_plain(data)
        assert "Capture Health:" in text
        assert "1 events in last 24h" in text
        assert "Last capture:" in text
        assert "Active:" in text
