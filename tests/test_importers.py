"""Tests for UCW import adapters — ChatGPT, Cursor, Grok."""

import sqlite3
from pathlib import Path

import pytest

# Fixtures directory
FIXTURES = Path(__file__).parent / "fixtures"

# Schema DDL matching the real cognitive_events table + migration 005 columns
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


def _get_events(db_path, platform=None):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    if platform:
        cur = conn.execute(
            "SELECT * FROM cognitive_events WHERE platform = ?",
            (platform,),
        )
    else:
        cur = conn.execute("SELECT * FROM cognitive_events")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── ChatGPT ──────────────────────────────────────────────────────────────

class TestChatGPTImporter:
    def test_chatgpt_import(self, import_db):
        """Import ChatGPT fixture and verify event count."""
        from ucw.importers.chatgpt import ChatGPTImporter

        importer = ChatGPTImporter()
        importer.run(str(FIXTURES / "chatgpt_export.json"))

        # 3 conversations: conv1 has 6 user/assistant + 1 system + 1 null = 6,
        # conv2 has 6 user/assistant = 6, conv3 has 6 user/assistant = 6 → 18 total
        count = _count_events(import_db, platform="chatgpt")
        assert count == 18, f"Expected 18 ChatGPT events, got {count}"
        assert importer.imported == 18

    def test_chatgpt_idempotent(self, import_db):
        """Importing the same file twice should not create duplicate events."""
        from ucw.importers.chatgpt import ChatGPTImporter

        importer1 = ChatGPTImporter()
        importer1.run(str(FIXTURES / "chatgpt_export.json"))
        count1 = _count_events(import_db, platform="chatgpt")

        importer2 = ChatGPTImporter()
        importer2.run(str(FIXTURES / "chatgpt_export.json"))
        count2 = _count_events(import_db, platform="chatgpt")

        assert count1 == count2, "Idempotency failed: count changed on re-import"
        assert importer2.skipped > 0, "Expected skipped events on re-import"
        assert importer2.imported == 0, "Expected zero new imports on re-import"

    def test_chatgpt_enrichment(self, import_db):
        """Imported events should have light_intent and light_topic set."""
        from ucw.importers.chatgpt import ChatGPTImporter

        importer = ChatGPTImporter()
        importer.run(str(FIXTURES / "chatgpt_export.json"))

        events = _get_events(import_db, platform="chatgpt")
        for ev in events:
            assert ev["light_intent"] is not None, (
                f"Event {ev['event_id']} missing light_intent"
            )
            assert ev["light_topic"] is not None, (
                f"Event {ev['event_id']} missing light_topic"
            )


# ── Cursor ───────────────────────────────────────────────────────────────

class TestCursorImporter:
    def test_cursor_import(self, import_db):
        """Import Cursor fixture and verify event count."""
        from ucw.importers.cursor import CursorImporter

        importer = CursorImporter()
        importer.run(str(FIXTURES / "cursor_export.json"))

        # 2 sessions x 6 messages each = 12
        count = _count_events(import_db, platform="cursor")
        assert count == 12, f"Expected 12 Cursor events, got {count}"
        assert importer.imported == 12

    def test_cursor_default_path(self, import_db, capsys):
        """No path given: should show helpful message about Cursor data locations."""
        from ucw.importers.cursor import CursorImporter

        importer = CursorImporter()
        importer.run(None)

        captured = capsys.readouterr()
        # Should mention Cursor paths or show helpful info
        assert "cursor" in captured.out.lower() or "Cursor" in captured.out


# ── Grok ─────────────────────────────────────────────────────────────────

class TestGrokImporter:
    def test_grok_import(self, import_db):
        """Import Grok fixture and verify event count."""
        from ucw.importers.grok import GrokImporter

        importer = GrokImporter()
        importer.run(str(FIXTURES / "grok_export.json"))

        # 2 conversations x 4 messages each = 8
        count = _count_events(import_db, platform="grok")
        assert count == 8, f"Expected 8 Grok events, got {count}"
        assert importer.imported == 8


# ── Base ─────────────────────────────────────────────────────────────────

class TestBaseImporter:
    def test_timestamp_conversion(self):
        """Test various timestamp formats."""
        from ucw.importers.base import BaseImporter

        imp = BaseImporter("test")

        # Seconds
        ns = imp.timestamp_to_ns(1710000000.0)
        assert ns == 1710000000000000000

        # Milliseconds
        ns = imp.timestamp_to_ns(1710000000000)
        assert ns == 1710000000000000000

        # Already nanoseconds
        ns = imp.timestamp_to_ns(1710000000000000000)
        assert ns == 1710000000000000000

        # None / fallback
        ns = imp.timestamp_to_ns(None)
        assert ns > 0

    def test_content_hash(self):
        """Test hash generation is deterministic."""
        from ucw.importers.base import BaseImporter

        imp = BaseImporter("test")

        h1 = imp.content_hash("hello world")
        h2 = imp.content_hash("hello world")
        h3 = imp.content_hash("different content")

        assert h1 == h2, "Same content should produce same hash"
        assert h1 != h3, "Different content should produce different hash"
        assert len(h1) == 32, "Hash should be 32 chars"
