"""Tests for UCW dashboard and demo commands."""

import json
import sqlite3

import pytest

from ucw.dashboard import get_dashboard_data, render_plain
from ucw.demo import DEMO_CONVERSATIONS, clean_demo_data, load_demo_data, _ensure_schema


@pytest.fixture
def demo_db(tmp_path, monkeypatch):
    """Create a temp DB with base schema and point Config at it."""
    from ucw import config

    ucw_dir = tmp_path / ".ucw"
    ucw_dir.mkdir()
    (ucw_dir / "logs").mkdir()
    db_path = ucw_dir / "cognitive.db"

    monkeypatch.setattr(config.Config, "UCW_DIR", ucw_dir)
    monkeypatch.setattr(config.Config, "LOG_DIR", ucw_dir / "logs")
    monkeypatch.setattr(config.Config, "DB_PATH", db_path)

    # Create schema
    conn = sqlite3.connect(str(db_path))
    _ensure_schema(conn)
    conn.close()

    return db_path


# --- Dashboard tests ---

def test_dashboard_empty_db(demo_db):
    """Dashboard on empty DB returns valid data with zero counts."""
    data = get_dashboard_data(demo_db)
    assert data is not None
    assert data['total_events'] == 0
    assert data['sessions'] == 0
    assert data['total_bytes'] == 0


def test_dashboard_no_db(tmp_path, monkeypatch):
    """Dashboard returns None when DB file does not exist."""
    from ucw import config

    monkeypatch.setattr(config.Config, "DB_PATH", tmp_path / "nonexistent.db")
    data = get_dashboard_data()
    assert data is None


def test_dashboard_with_data(demo_db):
    """After loading demo data, dashboard shows correct totals."""
    count = load_demo_data(demo_db)
    data = get_dashboard_data(demo_db)

    assert data['total_events'] == count
    assert data['sessions'] == len(DEMO_CONVERSATIONS)
    assert data['total_bytes'] > 0
    assert len(data['platforms']) == 3  # claude-desktop, chatgpt, cursor


def test_dashboard_json_output(demo_db):
    """Dashboard data is JSON-serializable."""
    load_demo_data(demo_db)
    data = get_dashboard_data(demo_db)

    # Should not raise
    output = json.dumps(data, indent=2, default=str)
    parsed = json.loads(output)
    assert parsed['total_events'] > 0


def test_dashboard_plain_fallback(demo_db):
    """render_plain produces readable string output."""
    load_demo_data(demo_db)
    data = get_dashboard_data(demo_db)
    text = render_plain(data)

    assert isinstance(text, str)
    assert "UCW Dashboard" in text
    assert "Events:" in text
    assert "Platforms:" in text


def test_dashboard_plain_no_data():
    """render_plain with None data shows helpful message."""
    text = render_plain(None)
    assert "No data" in text
    assert "ucw demo" in text


# --- Demo tests ---

def test_demo_load(demo_db):
    """Demo loads 50+ events."""
    count = load_demo_data(demo_db)
    assert count >= 50


def test_demo_platforms(demo_db):
    """Demo data spans 3 platforms."""
    load_demo_data(demo_db)
    conn = sqlite3.connect(str(demo_db))
    rows = conn.execute(
        "SELECT DISTINCT platform FROM cognitive_events WHERE protocol = 'demo'"
    ).fetchall()
    conn.close()
    platforms = {r[0] for r in rows}
    assert platforms == {"claude-desktop", "chatgpt", "cursor"}


def test_demo_idempotent(demo_db):
    """Loading demo twice doesn't double the event count (INSERT OR IGNORE)."""
    count1 = load_demo_data(demo_db)
    # Second load generates new UUIDs, so count increases.
    # But session inserts are OR IGNORE, so sessions stay the same.
    conn = sqlite3.connect(str(demo_db))
    sessions_before = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    conn.close()

    load_demo_data(demo_db)

    conn = sqlite3.connect(str(demo_db))
    sessions_after = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    conn.close()

    # Sessions should not duplicate (INSERT OR IGNORE on same session_id)
    assert sessions_after == sessions_before


def test_demo_clean(demo_db):
    """Clean removes all demo data."""
    load_demo_data(demo_db)

    conn = sqlite3.connect(str(demo_db))
    before = conn.execute("SELECT COUNT(*) FROM cognitive_events").fetchone()[0]
    conn.close()
    assert before > 0

    deleted = clean_demo_data(demo_db)
    assert deleted == before

    conn = sqlite3.connect(str(demo_db))
    after = conn.execute("SELECT COUNT(*) FROM cognitive_events").fetchone()[0]
    conn.close()
    assert after == 0


def test_demo_clean_leaves_real_data(demo_db):
    """Clean only removes protocol='demo' events, not real data."""
    # Insert a "real" event
    conn = sqlite3.connect(str(demo_db))
    conn.execute("""
        INSERT INTO cognitive_events
        (event_id, session_id, timestamp_ns, direction, stage, method,
         content_length, platform, protocol)
        VALUES ('real-001', 'real-session', 1000000, 'inbound', 'complete',
                'real', 42, 'claude-desktop', 'mcp')
    """)
    conn.commit()
    conn.close()

    # Load and then clean demo data
    load_demo_data(demo_db)
    clean_demo_data(demo_db)

    # Real event should survive
    conn = sqlite3.connect(str(demo_db))
    remaining = conn.execute("SELECT COUNT(*) FROM cognitive_events").fetchone()[0]
    real = conn.execute(
        "SELECT COUNT(*) FROM cognitive_events WHERE event_id = 'real-001'"
    ).fetchone()[0]
    conn.close()

    assert remaining == 1
    assert real == 1
