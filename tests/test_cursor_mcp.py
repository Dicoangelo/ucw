"""Tests for Cursor IDE MCP config support in UCW CLI."""

import json
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
# mcp-config --cursor
# -------------------------------------------------------------------

class TestMcpConfigCursor:
    def test_mcp_config_default_shows_cursor(self, runner):
        """Default mcp-config should mention Cursor IDE."""
        result = runner.invoke(main, ["mcp-config"])
        assert result.exit_code == 0
        assert "Cursor IDE" in result.output
        assert "mcpServers" in result.output

    def test_mcp_config_cursor_flag(self, runner):
        """--cursor flag outputs Cursor-specific config."""
        result = runner.invoke(main, ["mcp-config", "--cursor"])
        assert result.exit_code == 0
        assert "Cursor" in result.output
        # Should include env key (Cursor format)
        output_json = _extract_json(result.output)
        assert output_json is not None
        assert "env" in output_json["mcpServers"]["ucw"]

    def test_mcp_config_cursor_has_install_hint(self, runner):
        """--cursor output should mention --install-cursor."""
        result = runner.invoke(main, ["mcp-config", "--cursor"])
        assert result.exit_code == 0
        assert "--install-cursor" in result.output


# -------------------------------------------------------------------
# mcp-config --install-cursor
# -------------------------------------------------------------------

class TestInstallCursorMcp:
    def test_install_cursor_creates_file(self, runner, tmp_path, monkeypatch):
        """--install-cursor creates ~/.cursor/mcp.json."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        result = runner.invoke(main, ["mcp-config", "--install-cursor"])
        assert result.exit_code == 0
        assert "[OK]" in result.output

        mcp_file = tmp_path / ".cursor" / "mcp.json"
        assert mcp_file.exists()

        data = json.loads(mcp_file.read_text())
        assert "mcpServers" in data
        assert "ucw" in data["mcpServers"]
        assert data["mcpServers"]["ucw"]["args"] == ["server"]
        assert "env" in data["mcpServers"]["ucw"]

    def test_install_cursor_merges_existing(self, runner, tmp_path, monkeypatch):
        """--install-cursor merges with existing servers, preserving them."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        existing = {
            "mcpServers": {
                "other-server": {
                    "command": "other",
                    "args": ["run"],
                }
            }
        }
        (cursor_dir / "mcp.json").write_text(json.dumps(existing))

        result = runner.invoke(main, ["mcp-config", "--install-cursor"])
        assert result.exit_code == 0
        assert "[OK]" in result.output

        data = json.loads((cursor_dir / "mcp.json").read_text())
        # UCW added
        assert "ucw" in data["mcpServers"]
        # Other server preserved
        assert "other-server" in data["mcpServers"]
        assert data["mcpServers"]["other-server"]["command"] == "other"

    def test_install_cursor_updates_existing_ucw(
        self, runner, tmp_path, monkeypatch
    ):
        """--install-cursor updates existing UCW entry."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        existing = {
            "mcpServers": {
                "ucw": {
                    "command": "old-ucw-path",
                    "args": ["server"],
                }
            }
        }
        (cursor_dir / "mcp.json").write_text(json.dumps(existing))

        result = runner.invoke(main, ["mcp-config", "--install-cursor"])
        assert result.exit_code == 0

        data = json.loads((cursor_dir / "mcp.json").read_text())
        # Should be updated, not the old path
        assert data["mcpServers"]["ucw"]["command"] != "old-ucw-path"

    def test_install_cursor_bad_json(self, runner, tmp_path, monkeypatch):
        """--install-cursor handles corrupt mcp.json gracefully."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        (cursor_dir / "mcp.json").write_text("not valid json {{{")

        result = runner.invoke(main, ["mcp-config", "--install-cursor"])
        assert result.exit_code == 0
        assert "[FAIL]" in result.output

    def test_install_cursor_shows_restart_hint(
        self, runner, tmp_path, monkeypatch
    ):
        """--install-cursor reminds user to restart Cursor."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        result = runner.invoke(main, ["mcp-config", "--install-cursor"])
        assert result.exit_code == 0
        assert "Restart Cursor" in result.output


# -------------------------------------------------------------------
# capture-test Cursor detection
# -------------------------------------------------------------------

class TestCaptureTestCursor:
    def test_capture_test_detects_cursor_mcp(
        self, runner, tmp_ucw_dir, tmp_path, monkeypatch
    ):
        """capture-test detects Cursor MCP config with ucw entry."""
        from ucw.config import Config

        _create_schema(Config.DB_PATH)
        now_ns = time.time_ns()
        _insert_event(Config.DB_PATH, "evt-1", now_ns, "claude-desktop")

        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        # Create Cursor MCP config with ucw entry
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        cursor_mcp = {
            "mcpServers": {
                "ucw": {
                    "command": "ucw",
                    "args": ["server"],
                    "env": {},
                }
            }
        }
        (cursor_dir / "mcp.json").write_text(json.dumps(cursor_mcp))

        result = runner.invoke(main, ["capture-test"])
        assert result.exit_code == 0
        assert "Cursor" in result.output
        assert "[PASS] MCP config:" in result.output

    def test_capture_test_ignores_cursor_without_ucw(
        self, runner, tmp_ucw_dir, tmp_path, monkeypatch
    ):
        """capture-test ignores Cursor mcp.json if ucw server is not configured."""
        from ucw.config import Config

        _create_schema(Config.DB_PATH)
        now_ns = time.time_ns()
        _insert_event(Config.DB_PATH, "evt-1", now_ns, "claude-desktop")

        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        # Create Cursor MCP config WITHOUT ucw entry
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        other_config = {
            "mcpServers": {
                "some-other-server": {
                    "command": "other",
                    "args": [],
                }
            }
        }
        (cursor_dir / "mcp.json").write_text(json.dumps(other_config))

        result = runner.invoke(main, ["capture-test"])
        assert result.exit_code == 0
        # Cursor should NOT appear since ucw is not in its config
        assert "Cursor" not in result.output

    def test_capture_test_cursor_bad_json(
        self, runner, tmp_ucw_dir, tmp_path, monkeypatch
    ):
        """capture-test handles corrupt Cursor mcp.json gracefully."""
        from ucw.config import Config

        _create_schema(Config.DB_PATH)
        now_ns = time.time_ns()
        _insert_event(Config.DB_PATH, "evt-1", now_ns, "claude-desktop")

        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        (cursor_dir / "mcp.json").write_text("broken json!!!")

        result = runner.invoke(main, ["capture-test"])
        assert result.exit_code == 0
        # Should not crash, just skip Cursor
        assert "Cursor" not in result.output


def _extract_json(text):
    """Extract the first JSON object from CLI output."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None
