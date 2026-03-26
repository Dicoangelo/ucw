"""Migration 004: Agent learnings table."""


def up(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent_learnings (
            learning_id     TEXT PRIMARY KEY,
            text            TEXT NOT NULL,
            project         TEXT,
            tags            TEXT,
            confidence      REAL DEFAULT 0.5,
            source_session  TEXT,
            entity_ids      TEXT,
            timestamp_ns    INTEGER NOT NULL,
            light_intent    TEXT,
            light_topic     TEXT,
            light_concepts  TEXT,
            instinct_coherence REAL,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_learnings_project ON agent_learnings(project);
        CREATE INDEX IF NOT EXISTS idx_learnings_ts ON agent_learnings(timestamp_ns);
        CREATE INDEX IF NOT EXISTS idx_learnings_topic ON agent_learnings(light_topic);
    """)


def down(conn):
    conn.execute("DROP TABLE IF EXISTS agent_learnings")
