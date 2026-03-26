"""
Cursor Importer — Import conversations from Cursor AI.

Accepts a JSON file with conversation format:
{
  "conversations": [
    {
      "id": "...",
      "messages": [
        {"role": "user", "content": "...", "timestamp": ...},
        {"role": "assistant", "content": "...", "timestamp": ...}
      ]
    }
  ]
}

Or a flat messages array:
[
  {
    "id": "session-1",
    "messages": [...]
  }
]
"""

import json
from pathlib import Path

import click

from ucw.importers.base import BaseImporter

# Common Cursor data locations
CURSOR_PATHS = [
    Path.home() / ".cursor",
    Path.home() / "Library" / "Application Support" / "Cursor",
    Path.home() / ".config" / "Cursor",
]


class CursorImporter(BaseImporter):
    def __init__(self):
        super().__init__(platform="cursor")

    def run(self, filepath: str = None):
        if filepath:
            path = Path(filepath)
            if not path.exists():
                click.echo(f"File not found: {filepath}")
                return
            self._import_file(path)
        else:
            self._scan_default_paths()

    def _scan_default_paths(self):
        """Scan common Cursor directories for conversation data."""
        found = False
        for base in CURSOR_PATHS:
            if base.exists():
                click.echo(f"Found Cursor directory: {base}")
                json_files = list(base.rglob("*.json"))
                for jf in json_files:
                    if self._looks_like_conversations(jf):
                        click.echo(f"  Importing: {jf}")
                        self._import_file(jf)
                        found = True

        if not found:
            click.echo("No Cursor conversation data found.")
            click.echo("Checked paths:")
            for p in CURSOR_PATHS:
                status = "exists" if p.exists() else "not found"
                click.echo(f"  {p} ({status})")
            click.echo(
                "\nTo import manually, export your Cursor conversations "
                "to JSON and run: ucw import cursor <filepath>"
            )

    def _looks_like_conversations(self, path: Path) -> bool:
        """Quick check if a JSON file contains conversation data."""
        try:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, dict) and "conversations" in data:
                return True
            if isinstance(data, list) and data and "messages" in data[0]:
                return True
        except (json.JSONDecodeError, KeyError, IndexError, OSError):
            pass
        return False

    def _import_file(self, path: Path):
        with open(path) as f:
            data = json.load(f)

        if isinstance(data, dict) and "conversations" in data:
            conversations = data["conversations"]
        elif isinstance(data, list):
            conversations = data
        else:
            click.echo(f"Unrecognized format in {path}")
            return

        conn = self.connect_db()
        total = len(conversations)

        try:
            for idx, convo in enumerate(conversations, 1):
                convo_id = convo.get("id", f"cursor-{idx}")
                title = convo.get("title", convo_id)
                click.echo(
                    f"Importing session {idx}/{total}: '{title}'..."
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
                    timestamp_ns = self.timestamp_to_ns(ts)
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
                        "method": "import/cursor",
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
