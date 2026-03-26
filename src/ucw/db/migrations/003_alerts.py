"""Migration 003: Alerts table for real-time intelligence."""


def up(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id            TEXT PRIMARY KEY,
            type                TEXT NOT NULL,
            severity            TEXT NOT NULL DEFAULT 'info',
            message             TEXT NOT NULL,
            evidence_event_ids  TEXT,
            timestamp_ns        INTEGER NOT NULL,
            acknowledged        INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(type);
        CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
        CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp_ns);
    """)


def down(conn):
    conn.execute("DROP TABLE IF EXISTS alerts")
