"""Migration 008: Add is_noise flag to filter protocol overhead from real content."""


def up(conn):
    # Add the column (safe if already exists via IF NOT EXISTS not supported
    # for ALTER TABLE, so catch the error)
    try:
        conn.execute(
            "ALTER TABLE cognitive_events ADD COLUMN is_noise INTEGER DEFAULT 0"
        )
    except Exception:
        pass  # Column already exists

    # Backfill existing data — mark protocol overhead as noise
    conn.execute("""
        UPDATE cognitive_events SET is_noise = 1
        WHERE method IN (
            'initialize', 'initialized', 'notifications/initialized',
            'tools/list', 'resources/list'
        )
        OR (method = '' AND data_content LIKE '%inputSchema%')
        OR (method = '' AND direction = 'out' AND data_content LIKE '%protocolVersion%')
        OR (method = '' AND direction = 'out' AND data_content LIKE '{\"tools\":%')
        OR (method = '' AND direction = 'out' AND data_content LIKE '{\"resources\": []}')
    """)
    conn.commit()

    # Index for fast filtering
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_is_noise "
        "ON cognitive_events(is_noise)"
    )
    conn.commit()


def down(conn):
    conn.execute("DROP INDEX IF EXISTS idx_events_is_noise")
    # SQLite >= 3.35 supports DROP COLUMN
    try:
        conn.execute("ALTER TABLE cognitive_events DROP COLUMN is_noise")
    except Exception:
        pass  # Older SQLite, column remains but is unused
    conn.commit()
