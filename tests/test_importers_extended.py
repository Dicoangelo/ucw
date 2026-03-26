"""Extended importer tests — error handling, malformed input, edge cases."""

import json
import sqlite3
from pathlib import Path

import pytest

from ucw.importers.base import BaseImporter

FIXTURES = Path(__file__).parent / "fixtures"

# Schema DDL matching the real cognitive_events table
SCHEMA_DDL = """
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
def import_db(tmp_path, monkeypatch):
    """Create a temp DB with the full schema and point Config at it."""
    ucw_dir = tmp_path / ".ucw"
    ucw_dir.mkdir()
    (ucw_dir / "logs").mkdir()
    db_path = ucw_dir / "cognitive.db"

    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_DDL)
    conn.commit()
    conn.close()

    monkeypatch.setenv("UCW_DATA_DIR", str(ucw_dir))

    from ucw import config
    config.Config.UCW_DIR = ucw_dir
    config.Config.LOG_DIR = ucw_dir / "logs"
    config.Config.DB_PATH = db_path
    config.Config.LOG_FILE = ucw_dir / "logs" / "ucw.log"
    config.Config.ERROR_LOG = ucw_dir / "logs" / "ucw-errors.log"

    yield db_path


def _count_events(db_path, platform=None):
    conn = sqlite3.connect(str(db_path))
    if platform:
        cur = conn.execute(
            "SELECT COUNT(*) FROM cognitive_events WHERE platform = ?",
            (platform,),
        )
    else:
        cur = conn.execute("SELECT COUNT(*) FROM cognitive_events")
    count = cur.fetchone()[0]
    conn.close()
    return count


# ── BaseImporter tests ───────────────────────────────────────────────────

class TestBaseImporterExtended:
    def test_platform_attribute(self):
        imp = BaseImporter("my_platform")
        assert imp.platform == "my_platform"

    def test_initial_counters(self):
        imp = BaseImporter("test")
        assert imp.imported == 0
        assert imp.skipped == 0

    def test_make_event_id_unique(self):
        imp = BaseImporter("test")
        ids = {imp.make_event_id() for _ in range(100)}
        assert len(ids) == 100

    def test_make_session_id_deterministic(self):
        imp = BaseImporter("test")
        s1 = imp.make_session_id("conv-123")
        s2 = imp.make_session_id("conv-123")
        assert s1 == s2

    def test_make_session_id_differs_by_platform(self):
        imp1 = BaseImporter("chatgpt")
        imp2 = BaseImporter("grok")
        s1 = imp1.make_session_id("conv-123")
        s2 = imp2.make_session_id("conv-123")
        assert s1 != s2

    def test_make_session_id_length(self):
        imp = BaseImporter("test")
        sid = imp.make_session_id("conversation-1")
        assert len(sid) == 16

    def test_timestamp_to_ns_string_fallback(self):
        imp = BaseImporter("test")
        ns = imp.timestamp_to_ns("not a number")
        assert ns > 0  # Should use time.time() fallback

    def test_content_hash_empty_string(self):
        imp = BaseImporter("test")
        h = imp.content_hash("")
        assert len(h) == 32
        assert h == imp.content_hash("")  # Deterministic

    def test_event_exists_false(self, import_db):
        imp = BaseImporter("test")
        conn = sqlite3.connect(str(import_db))
        assert imp.event_exists(conn, "nonexistent_hash") is False
        conn.close()

    def test_insert_event_and_exists(self, import_db):
        imp = BaseImporter("test")
        conn = sqlite3.connect(str(import_db))
        event = {
            "event_id": imp.make_event_id(),
            "session_id": "test-session",
            "timestamp_ns": 1710000000000000000,
            "direction": "inbound",
            "stage": "complete",
            "method": "test",
            "content": "Hello world",
            "light_intent": "greeting",
            "light_topic": "testing",
            "light_concepts": "[]",
            "instinct_coherence": 0.5,
            "instinct_gut_signal": "routine",
            "content_hash": imp.content_hash("Hello world"),
        }
        imp.insert_event(conn, event)
        conn.commit()
        assert imp.event_exists(conn, event["content_hash"]) is True
        conn.close()


# ── ChatGPT error handling ───────────────────────────────────────────────

class TestChatGPTImporterErrors:
    def test_chatgpt_malformed_json(self, import_db, tmp_path):
        """ChatGPT importer with malformed JSON raises error."""
        from ucw.importers.chatgpt import ChatGPTImporter

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")

        importer = ChatGPTImporter()
        with pytest.raises(json.JSONDecodeError):
            importer.run(str(bad_file))

    def test_chatgpt_not_array(self, import_db, tmp_path, capsys):
        """ChatGPT importer with object instead of array shows error."""
        from ucw.importers.chatgpt import ChatGPTImporter

        bad_file = tmp_path / "object.json"
        bad_file.write_text('{"not": "an array"}')

        importer = ChatGPTImporter()
        importer.run(str(bad_file))
        captured = capsys.readouterr()
        assert "expected" in captured.out.lower() or "array" in captured.out.lower()

    def test_chatgpt_empty_array(self, import_db, tmp_path):
        """ChatGPT importer with empty array imports 0 events."""
        from ucw.importers.chatgpt import ChatGPTImporter

        empty_file = tmp_path / "empty.json"
        empty_file.write_text("[]")

        importer = ChatGPTImporter()
        importer.run(str(empty_file))
        assert importer.imported == 0

    def test_chatgpt_conversation_no_mapping(self, import_db, tmp_path):
        """ChatGPT conversation without mapping field imports 0 events."""
        from ucw.importers.chatgpt import ChatGPTImporter

        file = tmp_path / "no_mapping.json"
        file.write_text(json.dumps([{"title": "Empty", "id": "e1"}]))

        importer = ChatGPTImporter()
        importer.run(str(file))
        assert importer.imported == 0

    def test_chatgpt_empty_content_skipped(self, import_db, tmp_path):
        """Messages with empty content parts are skipped."""
        from ucw.importers.chatgpt import ChatGPTImporter

        file = tmp_path / "empty_content.json"
        data = [{
            "title": "Test",
            "id": "t1",
            "create_time": 1710000000.0,
            "mapping": {
                "n1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": [""]},
                        "create_time": 1710000000.0,
                    }
                }
            },
        }]
        file.write_text(json.dumps(data))

        importer = ChatGPTImporter()
        importer.run(str(file))
        assert importer.imported == 0


# ── Grok error handling ──────────────────────────────────────────────────

class TestGrokImporterErrors:
    def test_grok_malformed_json(self, import_db, tmp_path):
        """Grok importer with malformed JSON raises error."""
        from ucw.importers.grok import GrokImporter

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{broken")

        importer = GrokImporter()
        with pytest.raises(json.JSONDecodeError):
            importer.run(str(bad_file))

    def test_grok_unrecognized_format(self, import_db, tmp_path, capsys):
        """Grok importer with unrecognized format shows error."""
        from ucw.importers.grok import GrokImporter

        bad_file = tmp_path / "bad_format.json"
        bad_file.write_text('"just a string"')

        importer = GrokImporter()
        importer.run(str(bad_file))
        captured = capsys.readouterr()
        assert "unrecognized" in captured.out.lower()

    def test_grok_empty_conversations(self, import_db, tmp_path):
        """Grok importer with empty conversations imports 0."""
        from ucw.importers.grok import GrokImporter

        file = tmp_path / "empty.json"
        file.write_text(json.dumps({"conversations": []}))

        importer = GrokImporter()
        importer.run(str(file))
        assert importer.imported == 0

    def test_grok_iso_timestamp_parsing(self, import_db):
        """Grok importer parses ISO timestamps from fixture."""
        from ucw.importers.grok import GrokImporter

        importer = GrokImporter()
        importer.run(str(FIXTURES / "grok_export.json"))
        assert importer.imported == 8

    def test_grok_flat_array_format(self, import_db, tmp_path):
        """Grok importer accepts flat array format."""
        from ucw.importers.grok import GrokImporter

        file = tmp_path / "flat.json"
        data = [
            {
                "id": "flat-1",
                "messages": [
                    {"role": "user", "content": "Hello", "timestamp": 1710000000.0},
                    {"role": "assistant", "content": "Hi there", "timestamp": 1710000010.0},
                ],
            }
        ]
        file.write_text(json.dumps(data))

        importer = GrokImporter()
        importer.run(str(file))
        assert importer.imported == 2


# ── Cursor error handling ────────────────────────────────────────────────

class TestCursorImporterErrors:
    def test_cursor_missing_file(self, import_db, capsys):
        """Cursor importer with nonexistent path shows message."""
        from ucw.importers.cursor import CursorImporter

        importer = CursorImporter()
        importer.run("/tmp/nonexistent_cursor_file.json")
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "File not found" in captured.out

    def test_cursor_flat_array_format(self, import_db, tmp_path):
        """Cursor importer accepts flat array format."""
        from ucw.importers.cursor import CursorImporter

        file = tmp_path / "flat.json"
        data = [
            {
                "id": "flat-session",
                "messages": [
                    {"role": "user", "content": "Test message", "timestamp": 1710000000.0},
                    {"role": "assistant", "content": "Response here", "timestamp": 1710000010.0},
                ],
            }
        ]
        file.write_text(json.dumps(data))

        importer = CursorImporter()
        importer.run(str(file))
        assert importer.imported == 2

    def test_cursor_unrecognized_format(self, import_db, tmp_path, capsys):
        """Cursor importer with unrecognized JSON format shows error."""
        from ucw.importers.cursor import CursorImporter

        file = tmp_path / "bad.json"
        file.write_text('"just a string"')

        importer = CursorImporter()
        importer.run(str(file))
        captured = capsys.readouterr()
        assert "Unrecognized" in captured.out

    def test_cursor_looks_like_conversations_true(self, import_db, tmp_path):
        """_looks_like_conversations returns True for valid data."""
        from ucw.importers.cursor import CursorImporter

        file = tmp_path / "valid.json"
        data = {"conversations": [{"id": "1", "messages": []}]}
        file.write_text(json.dumps(data))

        importer = CursorImporter()
        assert importer._looks_like_conversations(file) is True

    def test_cursor_looks_like_conversations_false(self, import_db, tmp_path):
        """_looks_like_conversations returns False for non-conversation data."""
        from ucw.importers.cursor import CursorImporter

        file = tmp_path / "other.json"
        file.write_text(json.dumps({"settings": {"theme": "dark"}}))

        importer = CursorImporter()
        assert importer._looks_like_conversations(file) is False

    def test_cursor_looks_like_conversations_bad_json(self, import_db, tmp_path):
        """_looks_like_conversations returns False for invalid JSON."""
        from ucw.importers.cursor import CursorImporter

        file = tmp_path / "bad.json"
        file.write_text("not json")

        importer = CursorImporter()
        assert importer._looks_like_conversations(file) is False
