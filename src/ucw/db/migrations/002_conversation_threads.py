"""Migration 002: Conversation threads for cross-platform fusion."""


def up(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversation_threads (
            thread_id           TEXT PRIMARY KEY,
            topic               TEXT,
            platform_sessions   TEXT,
            entity_overlap_score REAL DEFAULT 0.0,
            semantic_score      REAL DEFAULT 0.0,
            temporal_score      REAL DEFAULT 0.0,
            combined_score      REAL DEFAULT 0.0,
            created_ns          INTEGER NOT NULL,
            updated_ns          INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_threads_topic ON conversation_threads(topic);
        CREATE INDEX IF NOT EXISTS idx_threads_score ON conversation_threads(combined_score);
    """)


def down(conn):
    conn.execute("DROP TABLE IF EXISTS conversation_threads")
