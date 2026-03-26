"""
Grok Importer — Import conversations from X/Grok data export.

Expected format:
{
  "conversations": [
    {
      "id": "...",
      "messages": [
        {"role": "user", "content": "...", "timestamp": "2024-03-10T12:00:00Z"},
        {"role": "assistant", "content": "...", "timestamp": "2024-03-10T12:00:05Z"}
      ]
    }
  ]
}

Also supports a flat array of conversations:
[
  {"id": "...", "messages": [...]}
]
"""

import json
from datetime import datetime
from pathlib import Path

import click

from ucw.importers.base import BaseImporter


class GrokImporter(BaseImporter):
    def __init__(self):
        super().__init__(platform="grok")

    def run(self, filepath: str):
        path = Path(filepath)
        with open(path) as f:
            data = json.load(f)

        if isinstance(data, dict) and "conversations" in data:
            conversations = data["conversations"]
        elif isinstance(data, list):
            conversations = data
        else:
            click.echo("Error: unrecognized Grok export format.")
            return

        conn = self.connect_db()
        total = len(conversations)

        try:
            for idx, convo in enumerate(conversations, 1):
                convo_id = convo.get("id", f"grok-{idx}")
                title = convo.get("title", convo_id)
                click.echo(
                    f"Importing conversation {idx}/{total}: '{title}'..."
                )

                session_id = self.make_session_id(convo_id)
                messages = convo.get("messages", [])

                for msg in messages:
                    role = msg.get("role", "unknown")
                    if role not in ("user", "assistant"):
                        continue

                    content = msg.get("content", "").strip()
                    if not content:
                        continue

                    ts = msg.get("timestamp")
                    timestamp_ns = self._parse_timestamp(ts)
                    direction = "inbound" if role == "user" else "outbound"
                    c_hash = self.content_hash(content)

                    if self.event_exists(conn, c_hash):
                        self.skipped += 1
                        continue

                    enrichment = self.enrich_light(content)
                    light = enrichment["light"]
                    instinct = enrichment["instinct"]

                    self.insert_event(conn, {
                        "event_id": self.make_event_id(),
                        "session_id": session_id,
                        "timestamp_ns": timestamp_ns,
                        "direction": direction,
                        "method": "import/grok",
                        "content": content,
                        "light_intent": light.get("intent"),
                        "light_topic": light.get("topic"),
                        "light_concepts": json.dumps(light.get("concepts", [])),
                        "instinct_coherence": instinct.get("coherence_potential"),
                        "instinct_gut_signal": instinct.get("gut_signal"),
                        "content_hash": c_hash,
                    })
                    self.imported += 1

            conn.commit()
        finally:
            conn.close()

        click.echo(
            f"Done. Imported {self.imported} events, "
            f"skipped {self.skipped} duplicates."
        )

    def _parse_timestamp(self, ts) -> int:
        """Parse Grok timestamp — can be ISO string, epoch, or None."""
        if ts is None:
            return self.timestamp_to_ns(None)
        if isinstance(ts, (int, float)):
            return self.timestamp_to_ns(ts)
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1e9)
            except ValueError:
                pass
        return self.timestamp_to_ns(None)
