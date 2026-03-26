"""Extended dashboard tests — _fmt_bytes formatting and edge cases."""

import sqlite3

import pytest

from ucw.dashboard import _fmt_bytes, get_dashboard_data, render_plain


# ── _fmt_bytes formatting ────────────────────────────────────────────────

class TestFmtBytes:
    def test_zero_bytes(self):
        assert _fmt_bytes(0) == "0 B"

    def test_small_bytes(self):
        assert _fmt_bytes(500) == "500 B"

    def test_one_byte(self):
        assert _fmt_bytes(1) == "1 B"

    def test_exactly_1024(self):
        result = _fmt_bytes(1024)
        assert "KB" in result
        assert "1.0" in result

    def test_kilobytes(self):
        result = _fmt_bytes(2048)
        assert "KB" in result
        assert "2.0" in result

    def test_megabytes(self):
        result = _fmt_bytes(1048576)
        assert "MB" in result
        assert "1.0" in result

    def test_large_megabytes(self):
        result = _fmt_bytes(5 * 1048576)
        assert "MB" in result
        assert "5.0" in result

    def test_gigabytes(self):
        result = _fmt_bytes(1073741824)
        assert "GB" in result
        assert "1.0" in result

    def test_terabytes(self):
        result = _fmt_bytes(1099511627776)
        assert "TB" in result
        assert "1.0" in result

    def test_fractional_kb(self):
        result = _fmt_bytes(1536)
        assert "KB" in result
        assert "1.5" in result

    def test_bytes_just_under_1024(self):
        assert _fmt_bytes(1023) == "1023 B"


# ── render_plain edge cases ──────────────────────────────────────────────

class TestRenderPlainEdgeCases:
    def test_render_plain_empty_platforms(self):
        data = {
            "total_events": 0,
            "sessions": 0,
            "total_bytes": 0,
            "platforms": {},
            "top_topics": [],
            "recent_moments": [],
            "graph": {"entities": 0, "relationships": 0},
            "gut_signals": [],
            "date_range": (None, None),
        }
        text = render_plain(data)
        assert "UCW Dashboard" in text
        assert "Events:    0" in text

    def test_render_plain_with_graph_data(self):
        data = {
            "total_events": 10,
            "sessions": 2,
            "total_bytes": 5000,
            "platforms": {"claude-desktop": 10},
            "top_topics": [("testing", 5)],
            "recent_moments": [],
            "graph": {"entities": 50, "relationships": 100},
            "gut_signals": [("routine", 8), ("interesting", 2)],
            "date_range": (1000, 2000),
        }
        text = render_plain(data)
        assert "Knowledge Graph" in text
        assert "50 entities" in text
        assert "100 relationships" in text

    def test_render_plain_with_gut_signals(self):
        data = {
            "total_events": 5,
            "sessions": 1,
            "total_bytes": 100,
            "platforms": {"chatgpt": 5},
            "top_topics": [],
            "recent_moments": [],
            "graph": {"entities": 0, "relationships": 0},
            "gut_signals": [("breakthrough_potential", 3), ("routine", 2)],
            "date_range": (1000, 2000),
        }
        text = render_plain(data)
        assert "Gut Signals" in text
        assert "breakthrough_potential" in text

    def test_render_plain_percentage_calculation(self):
        data = {
            "total_events": 100,
            "sessions": 3,
            "total_bytes": 10000,
            "platforms": {"claude-desktop": 60, "chatgpt": 40},
            "top_topics": [],
            "recent_moments": [],
            "graph": {"entities": 0, "relationships": 0},
            "gut_signals": [],
            "date_range": (1000, 2000),
        }
        text = render_plain(data)
        assert "60%" in text
        assert "40%" in text


# ── get_dashboard_data edge cases ────────────────────────────────────────

class TestDashboardDataEdgeCases:
    def test_dashboard_returns_none_for_nonexistent_path(self, tmp_path):
        """get_dashboard_data returns None for a path that doesn't exist."""
        result = get_dashboard_data(tmp_path / "nope.db")
        assert result is None

    def test_dashboard_empty_db_has_all_keys(self, tmp_path):
        """Dashboard data from an empty DB has all expected keys."""
        from ucw.demo import _ensure_schema

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        _ensure_schema(conn)
        conn.close()

        data = get_dashboard_data(db_path)
        assert data is not None
        expected_keys = {
            "total_events", "platforms", "top_topics", "recent_moments",
            "graph", "total_bytes", "sessions", "date_range", "gut_signals",
        }
        assert expected_keys.issubset(data.keys())

    def test_dashboard_date_range_with_data(self, tmp_path):
        """Dashboard date_range is populated when events exist."""
        from ucw.demo import _ensure_schema, load_demo_data

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        _ensure_schema(conn)
        conn.close()

        load_demo_data(db_path)
        data = get_dashboard_data(db_path)
        assert data["date_range"][0] is not None
        assert data["date_range"][1] is not None
        assert data["date_range"][0] <= data["date_range"][1]
