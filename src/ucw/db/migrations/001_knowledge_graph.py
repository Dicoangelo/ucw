"""Migration 001: Knowledge Graph tables — entities and relationships."""


def up(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entities (
            entity_id       TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            type            TEXT NOT NULL,
            confidence      REAL DEFAULT 0.5,
            first_seen_ns   INTEGER NOT NULL,
            last_seen_ns    INTEGER NOT NULL,
            event_count     INTEGER DEFAULT 1,
            metadata        TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
        CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
        CREATE INDEX IF NOT EXISTS idx_entities_last_seen ON entities(last_seen_ns);

        CREATE TABLE IF NOT EXISTS entity_relationships (
            rel_id              TEXT PRIMARY KEY,
            source_entity_id    TEXT NOT NULL,
            target_entity_id    TEXT NOT NULL,
            type                TEXT NOT NULL,
            weight              REAL DEFAULT 0.1,
            evidence_event_ids  TEXT,
            first_seen_ns       INTEGER NOT NULL,
            last_seen_ns        INTEGER NOT NULL,
            occurrence_count    INTEGER DEFAULT 1,
            FOREIGN KEY (source_entity_id) REFERENCES entities(entity_id),
            FOREIGN KEY (target_entity_id) REFERENCES entities(entity_id)
        );

        CREATE INDEX IF NOT EXISTS idx_rel_source ON entity_relationships(source_entity_id);
        CREATE INDEX IF NOT EXISTS idx_rel_target ON entity_relationships(target_entity_id);
        CREATE INDEX IF NOT EXISTS idx_rel_type ON entity_relationships(type);
    """)


def down(conn):
    conn.executescript("""
        DROP TABLE IF EXISTS entity_relationships;
        DROP TABLE IF EXISTS entities;
    """)
