"""
UCW Search Engine — FTS5 keyword + semantic vector search

Provides:
  - keyword_search: BM25-ranked full-text search via FTS5
  - semantic_search: cosine-similarity over cached embeddings
  - search: unified entry point (auto-selects method)
  - build_embedding_index: batch embed all uncached events
  - embed_event: real-time single-event embedding
"""

import re
import sqlite3
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
)

from ucw.server.logger import get_logger

log = get_logger("search")

# Characters that need escaping in FTS5 queries
_FTS5_SPECIAL = re.compile(r'["\*\(\)\-\+\:]')


def _escape_fts5(query: str) -> str:
    """Escape special FTS5 characters in a query string."""
    # Wrap each term in double quotes to treat as literal
    terms = query.strip().split()
    escaped = []
    for term in terms:
        if _FTS5_SPECIAL.search(term):
            safe = term.replace('"', '""')
            escaped.append(f'"{safe}"')
        else:
            escaped.append(term)
    return " ".join(escaped)


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a read-only WAL-mode connection."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _has_noise_column(conn: sqlite3.Connection) -> bool:
    """Check if the is_noise column exists (migration 008)."""
    try:
        conn.execute("SELECT is_noise FROM cognitive_events LIMIT 1")
        return True
    except sqlite3.OperationalError:
        return False


def _noise_filter(conn: sqlite3.Connection, alias: str = "ce") -> str:
    """Return SQL fragment to exclude noise, or empty string if column missing."""
    if _has_noise_column(conn):
        return f" AND ({alias}.is_noise IS NULL OR {alias}.is_noise = 0)"
    return ""


def _has_fts5(conn: sqlite3.Connection) -> bool:
    """Check if the FTS5 virtual table exists."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='cognitive_events_fts'"
    )
    return cur.fetchone() is not None


def _build_filters(
    platform: Optional[str] = None,
    after: Optional[int] = None,
    before: Optional[int] = None,
) -> Tuple[str, list]:
    """Build WHERE clause fragments for platform/date filters."""
    clauses = []
    params: list = []
    if platform:
        clauses.append("ce.platform = ?")
        params.append(platform)
    if after is not None:
        clauses.append("ce.timestamp_ns >= ?")
        params.append(after)
    if before is not None:
        clauses.append("ce.timestamp_ns <= ?")
        params.append(before)
    return (" AND " + " AND ".join(clauses) if clauses else ""), params


def keyword_search(
    db_path: Path,
    query: str,
    limit: int = 10,
    platform: Optional[str] = None,
    after: Optional[int] = None,
    before: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """FTS5 keyword search with BM25 ranking.

    Falls back to LIKE search if FTS5 table is missing.
    Returns list of result dicts.
    """
    conn = _connect(db_path)
    try:
        if _has_fts5(conn):
            return _fts5_search(
                conn, query, limit, platform, after, before
            )
        return _like_search(
            conn, query, limit, platform, after, before
        )
    finally:
        conn.close()


def _fts5_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    platform: Optional[str],
    after: Optional[int],
    before: Optional[int],
) -> List[Dict[str, Any]]:
    """Run FTS5 MATCH query with BM25 ranking."""
    escaped = _escape_fts5(query)
    if not escaped.strip():
        return []

    filter_sql, filter_params = _build_filters(
        platform, after, before
    )
    nf = _noise_filter(conn)

    sql = (
        "SELECT ce.event_id, ce.platform, ce.timestamp_ns,"
        " ce.light_topic, ce.light_summary,"
        " snippet(cognitive_events_fts, 1, '<b>', '</b>',"
        " '...', 32) AS snippet,"
        " bm25(cognitive_events_fts) AS score"
        " FROM cognitive_events_fts fts"
        " JOIN cognitive_events ce"
        " ON fts.event_id = ce.event_id"
        " WHERE fts.cognitive_events_fts MATCH ?"
        f"{nf}"
        f"{filter_sql}"
        " ORDER BY score"
        " LIMIT ?"
    )
    params = [escaped] + filter_params + [limit]

    try:
        cur = conn.execute(sql, params)
        return [
            {
                "event_id": r["event_id"],
                "platform": r["platform"],
                "timestamp_ns": r["timestamp_ns"],
                "topic": r["light_topic"],
                "summary": r["light_summary"],
                "snippet": r["snippet"],
                "score": r["score"],
            }
            for r in cur.fetchall()
        ]
    except sqlite3.OperationalError as exc:
        log.warning(f"FTS5 query failed, falling back: {exc}")
        return _like_search(
            conn, query, limit, platform, after, before
        )


def _like_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    platform: Optional[str],
    after: Optional[int],
    before: Optional[int],
) -> List[Dict[str, Any]]:
    """Fallback LIKE search when FTS5 is unavailable."""
    filter_sql, filter_params = _build_filters(
        platform, after, before
    )
    like_param = f"%{query}%"
    nf = _noise_filter(conn)

    sql = (
        "SELECT ce.event_id, ce.platform, ce.timestamp_ns,"
        " ce.light_topic, ce.light_summary,"
        " substr(ce.data_content, 1, 200) AS snippet,"
        " 0.0 AS score"
        " FROM cognitive_events ce"
        " WHERE ("
        "   ce.data_content LIKE ?"
        "   OR ce.light_summary LIKE ?"
        "   OR ce.light_topic LIKE ?"
        " )"
        f"{nf}"
        f"{filter_sql}"
        " ORDER BY ce.timestamp_ns DESC"
        " LIMIT ?"
    )
    params = (
        [like_param, like_param, like_param]
        + filter_params
        + [limit]
    )

    cur = conn.execute(sql, params)
    return [
        {
            "event_id": r["event_id"],
            "platform": r["platform"],
            "timestamp_ns": r["timestamp_ns"],
            "topic": r["light_topic"],
            "summary": r["light_summary"],
            "snippet": r["snippet"],
            "score": r["score"],
        }
        for r in cur.fetchall()
    ]


def build_embedding_index(
    db_path: Path,
    callback: Optional[Callable[[int, int], None]] = None,
) -> int:
    """Build/update embedding cache for all uncached events.

    Returns count of newly indexed events.
    """
    import numpy as np

    from ucw.server.embeddings import (
        build_embed_text,
        embed_single,
    )

    conn = _connect(db_path)
    try:
        # Ensure embedding_cache table exists
        conn.execute(
            "CREATE TABLE IF NOT EXISTS embedding_cache ("
            "  event_id TEXT PRIMARY KEY,"
            "  embedding BLOB NOT NULL,"
            "  model TEXT NOT NULL"
            "    DEFAULT 'all-MiniLM-L6-v2',"
            "  created_at TEXT DEFAULT (datetime('now'))"
            ")"
        )
        conn.commit()

        cur = conn.execute(
            "SELECT ce.event_id, ce.data_content,"
            " ce.light_topic, ce.light_summary,"
            " ce.light_concepts, ce.light_intent"
            " FROM cognitive_events ce"
            " LEFT JOIN embedding_cache ec"
            " ON ce.event_id = ec.event_id"
            " WHERE ec.event_id IS NULL"
        )
        rows = cur.fetchall()
        total = len(rows)
        count = 0

        for i, row in enumerate(rows):
            content_dict = {
                "light_layer": {
                    "intent": row["light_intent"] or "",
                    "topic": row["light_topic"] or "",
                    "summary": row["light_summary"] or "",
                    "concepts": (
                        row["light_concepts"].split(",")
                        if row["light_concepts"]
                        else []
                    ),
                },
                "data_layer": {
                    "content": row["data_content"] or "",
                },
            }
            text = build_embed_text(content_dict)
            if not text or len(text) < 10:
                if callback:
                    callback(i + 1, total)
                continue

            vec = embed_single(text)
            blob = np.array(vec, dtype=np.float32).tobytes()
            conn.execute(
                "INSERT OR REPLACE INTO embedding_cache"
                " (event_id, embedding) VALUES (?, ?)",
                (row["event_id"], blob),
            )
            count += 1
            if callback:
                callback(i + 1, total)

        conn.commit()
        return count
    finally:
        conn.close()


def embed_event(
    db_path: Path,
    event_id: str,
    content_dict: Dict[str, Any],
) -> bool:
    """Cache embedding for a single event.

    Returns True on success.
    """
    import numpy as np

    from ucw.server.embeddings import (
        build_embed_text,
        embed_single,
    )

    text = build_embed_text(content_dict)
    if not text or len(text) < 10:
        return False

    vec = embed_single(text)
    blob = np.array(vec, dtype=np.float32).tobytes()

    conn = _connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS embedding_cache ("
            "  event_id TEXT PRIMARY KEY,"
            "  embedding BLOB NOT NULL,"
            "  model TEXT NOT NULL"
            "    DEFAULT 'all-MiniLM-L6-v2',"
            "  created_at TEXT DEFAULT (datetime('now'))"
            ")"
        )
        conn.execute(
            "INSERT OR REPLACE INTO embedding_cache"
            " (event_id, embedding) VALUES (?, ?)",
            (event_id, blob),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def semantic_search(
    db_path: Path,
    query: str,
    limit: int = 10,
    platform: Optional[str] = None,
    after: Optional[int] = None,
    before: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Vector similarity search over cached embeddings.

    Raises ImportError if sentence-transformers unavailable.
    """
    import numpy as np

    from ucw.server.embeddings import (
        cosine_similarity,
        embed_single,
    )

    query_vec = embed_single(query)
    conn = _connect(db_path)
    try:
        filter_sql, filter_params = _build_filters(
            platform, after, before
        )
        nf = _noise_filter(conn)

        sql = (
            "SELECT ec.event_id, ec.embedding,"
            " ce.platform, ce.timestamp_ns,"
            " ce.light_topic, ce.light_summary,"
            " substr(ce.data_content, 1, 200) AS snippet"
            " FROM embedding_cache ec"
            " JOIN cognitive_events ce"
            " ON ec.event_id = ce.event_id"
            " WHERE 1=1"
            f"{nf}"
            f"{filter_sql}"
        )
        cur = conn.execute(sql, filter_params)
        rows = cur.fetchall()

        scored = []
        for row in rows:
            blob = row["embedding"]
            vec = np.frombuffer(blob, dtype=np.float32)
            sim = cosine_similarity(
                query_vec, vec.tolist()
            )
            scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for sim, row in scored[:limit]:
            results.append({
                "event_id": row["event_id"],
                "platform": row["platform"],
                "timestamp_ns": row["timestamp_ns"],
                "topic": row["light_topic"],
                "summary": row["light_summary"],
                "snippet": row["snippet"],
                "score": 0.0,
                "similarity": sim,
            })
        return results
    finally:
        conn.close()


def search(
    db_path: Path,
    query: str,
    semantic: Optional[bool] = None,
    **kwargs: Any,
) -> Tuple[List[Dict[str, Any]], str]:
    """Unified search entry point.

    Returns (results, method_used) where method_used is
    'semantic' or 'keyword'.
    """
    if semantic is True:
        try:
            results = semantic_search(
                db_path, query, **kwargs
            )
            return results, "semantic"
        except (ImportError, Exception) as exc:
            log.warning(
                f"Semantic search failed: {exc}"
            )
            results = keyword_search(
                db_path, query, **kwargs
            )
            return results, "keyword"

    if semantic is None:
        try:
            from ucw.server.embeddings import (  # noqa: F401
                embed_single,
            )
            # Check if there are cached embeddings
            conn = _connect(db_path)
            try:
                cur = conn.execute(
                    "SELECT COUNT(*) FROM embedding_cache"
                )
                count = cur.fetchone()[0]
            except sqlite3.OperationalError:
                count = 0
            finally:
                conn.close()

            if count > 0:
                results = semantic_search(
                    db_path, query, **kwargs
                )
                return results, "semantic"
        except (ImportError, Exception):
            pass

    results = keyword_search(db_path, query, **kwargs)
    return results, "keyword"


def backfill_noise_flags(db_path: Path) -> int:
    """Backfill is_noise flags on existing events.

    Returns the number of rows updated.
    """
    conn = _connect(db_path)
    try:
        cur = conn.execute("""
            UPDATE cognitive_events SET is_noise = 1
            WHERE is_noise = 0
              AND (
                method IN (
                    'initialize', 'initialized',
                    'notifications/initialized',
                    'tools/list', 'resources/list'
                )
                OR (method = '' AND data_content LIKE '%inputSchema%')
              )
        """)
        updated = cur.rowcount
        conn.commit()
        return updated
    finally:
        conn.close()
