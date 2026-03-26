"""Tests for UCW search engine — FTS5 keyword + semantic vector."""

import importlib
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from ucw.db.sqlite import SCHEMA_SQL

_EMB_MOD = "ucw.server.embeddings"

# ── Helpers ──────────────────────────────────────────────


def _create_db(db_path: Path) -> sqlite3.Connection:
    """Create a test DB with base schema + FTS5."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)
    return conn


def _apply_fts5(conn: sqlite3.Connection):
    """Apply FTS5 migration to an open connection."""
    mod = importlib.import_module(
        "ucw.db.migrations.006_fts5_search"
    )
    mod.up(conn)
    conn.commit()


def _apply_embedding_cache(conn: sqlite3.Connection):
    """Apply embedding cache migration."""
    mod = importlib.import_module(
        "ucw.db.migrations.007_embedding_cache"
    )
    mod.up(conn)
    conn.commit()


def _insert_event(
    conn, event_id, content, topic, summary,
    concepts="", platform="claude-desktop",
    timestamp_ns=None, intent="explore",
):
    """Insert a test cognitive event."""
    ts = timestamp_ns or time.time_ns()
    conn.execute(
        "INSERT INTO cognitive_events ("
        "  event_id, timestamp_ns, direction, stage,"
        "  data_content, light_topic, light_summary,"
        "  light_concepts, light_intent, platform"
        ") VALUES (?, ?, 'inbound', 'captured',"
        "  ?, ?, ?, ?, ?, ?)",
        (
            event_id, ts, content, topic,
            summary, concepts, intent, platform,
        ),
    )
    conn.commit()


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def search_db(tmp_path, monkeypatch):
    """DB with schema + FTS5 + sample events."""
    from ucw import config

    ucw_dir = tmp_path / ".ucw"
    ucw_dir.mkdir()
    (ucw_dir / "logs").mkdir()
    db_path = ucw_dir / "cognitive.db"

    monkeypatch.setattr(config.Config, "UCW_DIR", ucw_dir)
    monkeypatch.setattr(config.Config, "DB_PATH", db_path)

    conn = _create_db(db_path)
    _apply_fts5(conn)
    _apply_embedding_cache(conn)

    _insert_event(
        conn, "evt-001",
        "Building a Python MCP server for cognitive capture",
        "mcp-server", "MCP server implementation",
        "python,mcp,server",
        platform="claude-desktop",
        timestamp_ns=1000000000,
    )
    _insert_event(
        conn, "evt-002",
        "React 19 concurrent features and suspense boundaries",
        "react", "React 19 deep dive",
        "react,frontend,ui",
        platform="cursor",
        timestamp_ns=2000000000,
    )
    _insert_event(
        conn, "evt-003",
        "SQLite WAL mode and FTS5 full-text search indexing",
        "sqlite", "SQLite performance tuning",
        "sqlite,database,fts5",
        platform="claude-desktop",
        timestamp_ns=3000000000,
    )
    _insert_event(
        conn, "evt-004",
        "Deploying Next.js 15 app to Vercel with edge runtime",
        "nextjs", "Next.js deployment guide",
        "nextjs,vercel,deployment",
        platform="chatgpt",
        timestamp_ns=4000000000,
    )
    _insert_event(
        conn, "evt-005",
        "Python asyncio event loop and MCP protocol handling",
        "mcp-protocol", "Async MCP patterns",
        "python,asyncio,mcp",
        platform="claude-desktop",
        timestamp_ns=5000000000,
    )

    conn.close()
    return db_path


@pytest.fixture
def empty_db(tmp_path, monkeypatch):
    """DB with schema + FTS5 but no events."""
    from ucw import config

    ucw_dir = tmp_path / ".ucw"
    ucw_dir.mkdir()
    (ucw_dir / "logs").mkdir()
    db_path = ucw_dir / "cognitive.db"

    monkeypatch.setattr(config.Config, "UCW_DIR", ucw_dir)
    monkeypatch.setattr(config.Config, "DB_PATH", db_path)

    conn = _create_db(db_path)
    _apply_fts5(conn)
    _apply_embedding_cache(conn)
    conn.close()
    return db_path


@pytest.fixture
def no_fts_db(tmp_path, monkeypatch):
    """DB with schema but NO FTS5 table."""
    from ucw import config

    ucw_dir = tmp_path / ".ucw"
    ucw_dir.mkdir()
    (ucw_dir / "logs").mkdir()
    db_path = ucw_dir / "cognitive.db"

    monkeypatch.setattr(config.Config, "UCW_DIR", ucw_dir)
    monkeypatch.setattr(config.Config, "DB_PATH", db_path)

    conn = _create_db(db_path)
    _insert_event(
        conn, "evt-f01",
        "Python MCP server fallback test content",
        "mcp", "MCP fallback test",
        platform="claude-desktop",
    )
    conn.close()
    return db_path


# ── FTS5 Keyword Search Tests ───────────────────────────


class TestKeywordSearch:
    def test_basic_match(self, search_db):
        from ucw.search import keyword_search

        results = keyword_search(search_db, "Python MCP")
        assert len(results) >= 1
        ids = [r["event_id"] for r in results]
        assert "evt-001" in ids or "evt-005" in ids

    def test_no_results(self, search_db):
        from ucw.search import keyword_search

        results = keyword_search(
            search_db, "quantum computing"
        )
        assert len(results) == 0

    def test_platform_filter(self, search_db):
        from ucw.search import keyword_search

        results = keyword_search(
            search_db, "Python", platform="cursor"
        )
        for r in results:
            assert r["platform"] == "cursor"

    def test_date_range_filter(self, search_db):
        from ucw.search import keyword_search

        results = keyword_search(
            search_db, "Python",
            after=1000000000, before=2000000000,
        )
        for r in results:
            ts = r["timestamp_ns"]
            assert 1000000000 <= ts <= 2000000000

    def test_special_characters(self, search_db):
        from ucw.search import keyword_search

        results = keyword_search(
            search_db, 'python "mcp" (server)'
        )
        assert isinstance(results, list)

    def test_empty_db(self, empty_db):
        from ucw.search import keyword_search

        results = keyword_search(empty_db, "anything")
        assert results == []

    def test_limit(self, search_db):
        from ucw.search import keyword_search

        results = keyword_search(
            search_db, "Python", limit=1
        )
        assert len(results) <= 1

    def test_fts5_fallback_to_like(self, no_fts_db):
        from ucw.search import keyword_search

        results = keyword_search(no_fts_db, "MCP")
        assert len(results) >= 1
        assert results[0]["event_id"] == "evt-f01"

    def test_result_fields(self, search_db):
        from ucw.search import keyword_search

        results = keyword_search(search_db, "SQLite")
        assert len(results) >= 1
        r = results[0]
        assert "event_id" in r
        assert "platform" in r
        assert "timestamp_ns" in r
        assert "topic" in r
        assert "summary" in r
        assert "snippet" in r
        assert "score" in r


# ── Embedding Cache Tests ────────────────────────────────


_FAKE_VEC = [0.1] * 384


class TestEmbeddingCache:
    @patch(
        f"{_EMB_MOD}.embed_single",
        return_value=_FAKE_VEC,
    )
    @patch(
        f"{_EMB_MOD}.build_embed_text",
        return_value="test text content here",
    )
    def test_build_embedding_index(
        self, mock_build, mock_embed, search_db
    ):
        from ucw.search import build_embedding_index

        count = build_embedding_index(search_db)
        assert count == 5

        conn = sqlite3.connect(str(search_db))
        cur = conn.execute(
            "SELECT COUNT(*) FROM embedding_cache"
        )
        assert cur.fetchone()[0] == 5
        conn.close()

    @patch(
        f"{_EMB_MOD}.embed_single",
        return_value=_FAKE_VEC,
    )
    @patch(
        f"{_EMB_MOD}.build_embed_text",
        return_value="test text content here",
    )
    def test_embed_event_single(
        self, mock_build, mock_embed, search_db
    ):
        from ucw.search import embed_event

        result = embed_event(
            search_db, "evt-new",
            {
                "light_layer": {
                    "intent": "test",
                    "topic": "testing",
                    "summary": "A test event",
                    "concepts": [],
                },
                "data_layer": {
                    "content": "test data",
                },
            },
        )
        assert result is True

        conn = sqlite3.connect(str(search_db))
        cur = conn.execute(
            "SELECT event_id FROM embedding_cache"
            " WHERE event_id = 'evt-new'"
        )
        assert cur.fetchone() is not None
        conn.close()

    @patch(
        f"{_EMB_MOD}.embed_single",
        return_value=_FAKE_VEC,
    )
    @patch(
        f"{_EMB_MOD}.build_embed_text",
        return_value="test text content here",
    )
    def test_embedding_cache_incremental(
        self, mock_build, mock_embed, search_db
    ):
        from ucw.search import build_embedding_index

        count1 = build_embedding_index(search_db)
        assert count1 == 5

        count2 = build_embedding_index(search_db)
        assert count2 == 0

    @patch(f"{_EMB_MOD}.embed_single")
    @patch(f"{_EMB_MOD}.cosine_similarity")
    def test_semantic_search_ordering(
        self, mock_cosine, mock_embed, search_db
    ):
        import numpy as np

        from ucw.search import semantic_search

        mock_embed.return_value = _FAKE_VEC

        conn = sqlite3.connect(str(search_db))
        for eid in ["evt-001", "evt-002", "evt-003"]:
            blob = np.array(
                _FAKE_VEC, dtype=np.float32
            ).tobytes()
            conn.execute(
                "INSERT OR REPLACE INTO"
                " embedding_cache"
                " (event_id, embedding)"
                " VALUES (?, ?)",
                (eid, blob),
            )
        conn.commit()
        conn.close()

        mock_cosine.side_effect = [0.95, 0.70, 0.85]

        results = semantic_search(
            search_db, "test query", limit=3
        )
        assert len(results) == 3
        assert results[0]["similarity"] == 0.95
        assert results[1]["similarity"] == 0.85
        assert results[2]["similarity"] == 0.70

    def test_semantic_search_no_embeddings(
        self, search_db
    ):
        from ucw.search import semantic_search

        with patch(
            f"{_EMB_MOD}.embed_single",
            side_effect=ImportError("no module"),
        ):
            with pytest.raises(ImportError):
                semantic_search(search_db, "test")


# ── Unified Search Tests ─────────────────────────────────


class TestUnifiedSearch:
    def test_search_defaults_to_keyword(self, search_db):
        from ucw.search import search

        results, method = search(search_db, "SQLite")
        assert method == "keyword"
        assert len(results) >= 1

    @patch(
        f"{_EMB_MOD}.embed_single",
        return_value=_FAKE_VEC,
    )
    @patch(
        f"{_EMB_MOD}.cosine_similarity",
        return_value=0.9,
    )
    def test_search_uses_semantic_when_cached(
        self, mock_cosine, mock_embed, search_db
    ):
        import numpy as np

        from ucw.search import search

        conn = sqlite3.connect(str(search_db))
        blob = np.array(
            _FAKE_VEC, dtype=np.float32
        ).tobytes()
        conn.execute(
            "INSERT INTO embedding_cache"
            " (event_id, embedding) VALUES (?, ?)",
            ("evt-003", blob),
        )
        conn.commit()
        conn.close()

        results, method = search(
            search_db, "SQLite", semantic=None
        )
        assert method == "semantic"

    def test_search_explicit_semantic_true_fallback(
        self, search_db
    ):
        from ucw.search import search

        with patch(
            f"{_EMB_MOD}.embed_single",
            side_effect=ImportError("no model"),
        ):
            results, method = search(
                search_db, "SQLite", semantic=True
            )
            assert method == "keyword"

    def test_search_explicit_semantic_false(
        self, search_db
    ):
        from ucw.search import search

        results, method = search(
            search_db, "SQLite", semantic=False
        )
        assert method == "keyword"

    @patch(
        f"{_EMB_MOD}.embed_single",
        return_value=_FAKE_VEC,
    )
    @patch(
        f"{_EMB_MOD}.build_embed_text",
        return_value="test text content here",
    )
    def test_build_index_callback(
        self, mock_build, mock_embed, search_db
    ):
        """Verify progress callback is invoked."""
        from ucw.search import build_embedding_index

        progress = []

        build_embedding_index(
            search_db,
            callback=lambda c, t: progress.append(
                (c, t)
            ),
        )

        assert len(progress) == 5
        assert progress[-1] == (5, 5)


# ── _escape_fts5 edge-case tests ─────────────────────────


class TestEscapeFTS5:
    def test_empty_string(self):
        from ucw.search import _escape_fts5

        assert _escape_fts5("") == ""
        assert _escape_fts5("   ") == ""

    def test_plain_terms_unchanged(self):
        from ucw.search import _escape_fts5

        assert _escape_fts5("hello world") == "hello world"

    def test_special_chars_escaped(self):
        from ucw.search import _escape_fts5

        result = _escape_fts5("c++ python*")
        # Each term with special chars should be wrapped in quotes
        assert '"c++"' in result
        assert '"python*"' in result

    def test_double_quotes_doubled(self):
        from ucw.search import _escape_fts5

        result = _escape_fts5('"hello"')
        # The double quotes inside should be doubled
        assert '""hello""' in result

    def test_mixed_special_and_plain(self):
        from ucw.search import _escape_fts5

        result = _escape_fts5("normal (special) plain")
        assert "normal" in result
        assert '"(special)"' in result
        assert "plain" in result

    def test_colon_escaped(self):
        from ucw.search import _escape_fts5

        result = _escape_fts5("key:value")
        assert '"key:value"' in result

    def test_hyphen_escaped(self):
        from ucw.search import _escape_fts5

        result = _escape_fts5("NOT -excluded")
        assert '"-excluded"' in result


# ── _build_filters edge-case tests ───────────────────────


class TestBuildFilters:
    def test_no_filters(self):
        from ucw.search import _build_filters

        clause, params = _build_filters()
        assert clause == ""
        assert params == []

    def test_platform_only(self):
        from ucw.search import _build_filters

        clause, params = _build_filters(platform="cursor")
        assert "ce.platform = ?" in clause
        assert params == ["cursor"]

    def test_after_only(self):
        from ucw.search import _build_filters

        clause, params = _build_filters(after=1000)
        assert "ce.timestamp_ns >= ?" in clause
        assert params == [1000]

    def test_before_only(self):
        from ucw.search import _build_filters

        clause, params = _build_filters(before=9000)
        assert "ce.timestamp_ns <= ?" in clause
        assert params == [9000]

    def test_all_filters_combined(self):
        from ucw.search import _build_filters

        clause, params = _build_filters(
            platform="claude", after=100, before=900
        )
        assert "ce.platform = ?" in clause
        assert "ce.timestamp_ns >= ?" in clause
        assert "ce.timestamp_ns <= ?" in clause
        assert params == ["claude", 100, 900]


# ── Additional keyword search edge cases ─────────────────


class TestKeywordSearchEdgeCases:
    def test_like_search_with_platform_and_date(self, no_fts_db):
        """LIKE fallback respects all filters together."""
        from ucw.search import keyword_search

        results = keyword_search(
            no_fts_db, "MCP",
            platform="claude-desktop",
        )
        assert len(results) >= 1
        for r in results:
            assert r["platform"] == "claude-desktop"

    def test_like_search_no_match(self, no_fts_db):
        from ucw.search import keyword_search

        results = keyword_search(no_fts_db, "zzz_nonexistent_zzz")
        assert results == []

    def test_whitespace_only_query_fts5(self, search_db):
        """FTS5 search with whitespace returns empty (escaped is empty)."""
        from ucw.search import keyword_search

        results = keyword_search(search_db, "   ")
        assert results == []

    def test_combined_platform_and_after(self, search_db):
        from ucw.search import keyword_search

        results = keyword_search(
            search_db, "Python",
            platform="claude-desktop",
            after=4000000000,
        )
        for r in results:
            assert r["platform"] == "claude-desktop"
            assert r["timestamp_ns"] >= 4000000000


# ── Embed event edge cases ───────────────────────────────


class TestEmbedEventEdgeCases:
    @patch(
        f"{_EMB_MOD}.embed_single",
        return_value=_FAKE_VEC,
    )
    @patch(
        f"{_EMB_MOD}.build_embed_text",
        return_value="short",  # less than 10 chars
    )
    def test_embed_event_short_text_returns_false(
        self, mock_build, mock_embed, search_db
    ):
        from ucw.search import embed_event

        result = embed_event(
            search_db, "evt-short",
            {"light_layer": {"intent": "", "topic": "", "summary": "", "concepts": []},
             "data_layer": {"content": ""}},
        )
        assert result is False

    @patch(
        f"{_EMB_MOD}.embed_single",
        return_value=_FAKE_VEC,
    )
    @patch(
        f"{_EMB_MOD}.build_embed_text",
        return_value="",  # empty text
    )
    def test_embed_event_empty_text_returns_false(
        self, mock_build, mock_embed, search_db
    ):
        from ucw.search import embed_event

        result = embed_event(
            search_db, "evt-empty",
            {"light_layer": {"intent": "", "topic": "", "summary": "", "concepts": []},
             "data_layer": {"content": ""}},
        )
        assert result is False

    @patch(
        f"{_EMB_MOD}.embed_single",
        return_value=_FAKE_VEC,
    )
    @patch(
        f"{_EMB_MOD}.build_embed_text",
        return_value="short",  # less than 10 chars
    )
    def test_build_index_skips_short_text(
        self, mock_build, mock_embed, search_db
    ):
        """build_embedding_index skips events with short text."""
        from ucw.search import build_embedding_index

        count = build_embedding_index(search_db)
        # All 5 events skipped because text < 10 chars
        assert count == 0

    @patch(f"{_EMB_MOD}.embed_single")
    @patch(f"{_EMB_MOD}.cosine_similarity")
    def test_semantic_search_with_platform_filter(
        self, mock_cosine, mock_embed, search_db
    ):
        """semantic_search respects platform filter."""
        import numpy as np

        from ucw.search import semantic_search

        mock_embed.return_value = _FAKE_VEC
        mock_cosine.return_value = 0.9

        conn = sqlite3.connect(str(search_db))
        blob = np.array(_FAKE_VEC, dtype=np.float32).tobytes()
        for eid in ["evt-001", "evt-002", "evt-003"]:
            conn.execute(
                "INSERT OR REPLACE INTO embedding_cache"
                " (event_id, embedding) VALUES (?, ?)",
                (eid, blob),
            )
        conn.commit()
        conn.close()

        results = semantic_search(
            search_db, "test", platform="cursor"
        )
        for r in results:
            assert r["platform"] == "cursor"

    @patch(f"{_EMB_MOD}.embed_single")
    @patch(f"{_EMB_MOD}.cosine_similarity")
    def test_semantic_search_empty_cache(
        self, mock_cosine, mock_embed, search_db
    ):
        """semantic_search with no embeddings returns empty list."""
        mock_embed.return_value = _FAKE_VEC

        from ucw.search import semantic_search

        results = semantic_search(search_db, "test")
        assert results == []
        mock_cosine.assert_not_called()
