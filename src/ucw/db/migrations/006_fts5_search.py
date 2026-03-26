"""Migration 006: FTS5 full-text search on cognitive_events."""


def up(conn):
    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS cognitive_events_fts
        USING fts5(
            event_id UNINDEXED,
            data_content,
            light_topic,
            light_summary,
            light_concepts,
            content='cognitive_events',
            content_rowid='rowid'
        );

        INSERT INTO cognitive_events_fts(
            event_id, data_content, light_topic,
            light_summary, light_concepts
        )
        SELECT
            event_id, data_content, light_topic,
            light_summary, light_concepts
        FROM cognitive_events;

        CREATE TRIGGER IF NOT EXISTS ce_fts_insert
        AFTER INSERT ON cognitive_events BEGIN
            INSERT INTO cognitive_events_fts(
                event_id, data_content, light_topic,
                light_summary, light_concepts
            ) VALUES (
                new.event_id, new.data_content,
                new.light_topic, new.light_summary,
                new.light_concepts
            );
        END;

        CREATE TRIGGER IF NOT EXISTS ce_fts_delete
        AFTER DELETE ON cognitive_events BEGIN
            INSERT INTO cognitive_events_fts(
                cognitive_events_fts, event_id, data_content,
                light_topic, light_summary, light_concepts
            ) VALUES (
                'delete', old.event_id, old.data_content,
                old.light_topic, old.light_summary,
                old.light_concepts
            );
        END;

        CREATE TRIGGER IF NOT EXISTS ce_fts_update
        AFTER UPDATE ON cognitive_events BEGIN
            INSERT INTO cognitive_events_fts(
                cognitive_events_fts, event_id, data_content,
                light_topic, light_summary, light_concepts
            ) VALUES (
                'delete', old.event_id, old.data_content,
                old.light_topic, old.light_summary,
                old.light_concepts
            );
            INSERT INTO cognitive_events_fts(
                event_id, data_content, light_topic,
                light_summary, light_concepts
            ) VALUES (
                new.event_id, new.data_content,
                new.light_topic, new.light_summary,
                new.light_concepts
            );
        END;
    """)


def down(conn):
    conn.executescript("""
        DROP TRIGGER IF EXISTS ce_fts_update;
        DROP TRIGGER IF EXISTS ce_fts_delete;
        DROP TRIGGER IF EXISTS ce_fts_insert;
        DROP TABLE IF EXISTS cognitive_events_fts;
    """)
