"""
ChatGPT Importer — Import conversations from OpenAI ChatGPT data export.

Export format: Settings > Data Controls > Export data
Produces a ZIP containing conversations.json with the structure:
[
  {
    "title": "...",
    "create_time": 1710000000.0,
    "mapping": {
      "node-id": {
        "message": {
          "author": {"role": "user"},
          "content": {"parts": ["Hello"]},
          "create_time": 1710000000.0
        }
      }
    }
  }
]
"""

import json
from pathlib import Path

import click

from ucw.importers.base import BaseImporter


class ChatGPTImporter(BaseImporter):
    def __init__(self):
        super().__init__(platform="chatgpt")

    def run(self, filepath: str):
        path = Path(filepath)
        with open(path) as f:
            conversations = json.load(f)

        if not isinstance(conversations, list):
            click.echo("Error: expected a JSON array of conversations.")
            return

        conn = self.connect_db()
        total = len(conversations)

        try:
            for idx, convo in enumerate(conversations, 1):
                title = convo.get("title", "Untitled")
                click.echo(
                    f"Importing conversation {idx}/{total}: '{title}'..."
                )

                convo_id = convo.get("id") or f"chatgpt-{idx}"
                session_id = self.make_session_id(convo_id)
                mapping = convo.get("mapping", {})

                for node_id, node in mapping.items():
                    msg = node.get("message")
                    if msg is None:
                        continue

                    author = msg.get("author", {})
                    role = author.get("role", "unknown")
                    if role not in ("user", "assistant"):
                        continue

                    content_obj = msg.get("content", {})
                    parts = content_obj.get("parts", [])
                    # Parts can contain strings or dicts (attachments)
                    text_parts = [
                        p for p in parts if isinstance(p, str)
                    ]
                    content = " ".join(text_parts).strip()
                    if not content:
                        continue

                    ts = msg.get("create_time") or convo.get("create_time")
                    timestamp_ns = self.timestamp_to_ns(ts)
                    direction = "inbound" if role == "user" else "outbound"
                    c_hash = self.content_hash(content)

                    if self.event_exists(conn, c_hash):
                        self.skipped += 1
                        continue

                    # Use smart enrichment if available
                    try:
                        from ucw.enrichment import enrich_event
                        enriched = enrich_event(content, {"title": title})
                        light_topic = enriched["topic"]
                        light_intent = enriched["intent"]
                        light_concepts = json.dumps(enriched["concepts"])
                    except ImportError:
                        enrichment = self.enrich_light(content)
                        light = enrichment["light"]
                        light_topic = light.get("topic")
                        light_intent = light.get("intent")
                        light_concepts = json.dumps(
                            light.get("concepts", [])
                        )

                    instinct_data = self.enrich_light(content)["instinct"]

                    self.insert_event(conn, {
                        "event_id": self.make_event_id(),
                        "session_id": session_id,
                        "timestamp_ns": timestamp_ns,
                        "direction": direction,
                        "method": "import/chatgpt",
                        "content": content,
                        "light_intent": light_intent,
                        "light_topic": light_topic,
                        "light_concepts": light_concepts,
                        "instinct_coherence": instinct_data.get(
                            "coherence_potential"
                        ),
                        "instinct_gut_signal": instinct_data.get(
                            "gut_signal"
                        ),
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
