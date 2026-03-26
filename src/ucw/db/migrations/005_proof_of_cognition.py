"""Migration 005: Proof-of-Cognition — hash chain and Merkle columns."""


def up(conn):
    # Add hash chain columns to cognitive_events
    # SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so check first
    cur = conn.execute("PRAGMA table_info(cognitive_events)")
    existing = {row[1] for row in cur.fetchall()}

    if "content_hash" not in existing:
        conn.execute("ALTER TABLE cognitive_events ADD COLUMN content_hash TEXT")
    if "prev_hash" not in existing:
        conn.execute("ALTER TABLE cognitive_events ADD COLUMN prev_hash TEXT")
    if "chain_hash" not in existing:
        conn.execute("ALTER TABLE cognitive_events ADD COLUMN chain_hash TEXT")

    # Add merkle_root to sessions
    cur = conn.execute("PRAGMA table_info(sessions)")
    existing_sess = {row[1] for row in cur.fetchall()}

    if "merkle_root" not in existing_sess:
        conn.execute("ALTER TABLE sessions ADD COLUMN merkle_root TEXT")

    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_events_chain_hash ON cognitive_events(chain_hash);
        CREATE INDEX IF NOT EXISTS idx_events_content_hash ON cognitive_events(content_hash);

        CREATE TABLE IF NOT EXISTS cognition_receipts (
            receipt_id      TEXT PRIMARY KEY,
            session_id      TEXT,
            event_ids       TEXT NOT NULL,
            merkle_root     TEXT,
            merkle_proofs   TEXT,
            timestamp_range TEXT,
            platform        TEXT,
            summary         TEXT,
            format          TEXT DEFAULT 'json',
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_receipts_session ON cognition_receipts(session_id);
    """)


def down(conn):
    conn.execute("DROP TABLE IF EXISTS cognition_receipts")
    # Note: SQLite doesn't support DROP COLUMN before 3.35.0
    # For safety, we don't remove columns in down()
