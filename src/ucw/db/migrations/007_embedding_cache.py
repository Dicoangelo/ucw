"""Migration 007: Embedding cache for semantic search vectors."""


def up(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS embedding_cache (
            event_id    TEXT PRIMARY KEY,
            embedding   BLOB NOT NULL,
            model       TEXT NOT NULL
                        DEFAULT 'all-MiniLM-L6-v2',
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_emb_model
            ON embedding_cache(model);
    """)


def down(conn):
    conn.executescript("""
        DROP INDEX IF EXISTS idx_emb_model;
        DROP TABLE IF EXISTS embedding_cache;
    """)
