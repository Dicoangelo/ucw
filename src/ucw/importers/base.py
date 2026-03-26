"""
Base importer — shared logic for importing conversations from external AI platforms.
"""

import hashlib
import sqlite3
import time
import uuid

from ucw.config import Config


class BaseImporter:
    def __init__(self, platform: str):
        self.platform = platform
        self.imported = 0
        self.skipped = 0

    def connect_db(self):
        conn = sqlite3.connect(str(Config.DB_PATH))
        conn.execute("PRAGMA journal_mode=wal")
        return conn

    def make_event_id(self):
        return str(uuid.uuid4())

    def make_session_id(self, conversation_id: str):
        return hashlib.sha256(
            f"{self.platform}:{conversation_id}".encode()
        ).hexdigest()[:16]

    def timestamp_to_ns(self, ts) -> int:
        """Convert various timestamp formats to nanoseconds."""
        if isinstance(ts, (int, float)):
            if ts < 1e12:  # seconds
                return int(ts * 1e9)
            elif ts < 1e15:  # milliseconds
                return int(ts * 1e6)
            return int(ts)  # already ns
        return int(time.time() * 1e9)

    def enrich_light(self, content: str) -> dict:
        """Run light-layer enrichment on content."""
        from ucw.server.ucw_bridge import extract_layers

        parsed = {"method": "import", "params": {"arguments": {"text": content}}}
        data, light, instinct = extract_layers(parsed, "in")
        return {"data": data, "light": light, "instinct": instinct}

    def event_exists(self, conn, content_hash: str) -> bool:
        """Check if event already imported (idempotent)."""
        cur = conn.execute(
            "SELECT 1 FROM cognitive_events WHERE content_hash = ? LIMIT 1",
            (content_hash,),
        )
        return cur.fetchone() is not None

    def content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def insert_event(self, conn, event: dict):
        """Insert a single cognitive_event matching the real schema."""
        conn.execute(
            """
            INSERT OR IGNORE INTO cognitive_events
            (event_id, session_id, timestamp_ns, direction, stage, method,
             content_length, data_content,
             platform, protocol,
             light_intent, light_topic, light_concepts,
             instinct_coherence, instinct_gut_signal,
             content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["session_id"],
                event["timestamp_ns"],
                event.get("direction", "inbound"),
                event.get("stage", "complete"),
                event.get("method", "import"),
                len(event.get("content", "")),
                event.get("content", ""),
                self.platform,
                "import",
                event.get("light_intent"),
                event.get("light_topic"),
                event.get("light_concepts"),
                event.get("instinct_coherence"),
                event.get("instinct_gut_signal"),
                event.get("content_hash"),
            ),
        )
