"""
Claude Code Importer — Import sessions from Claude Code JSONL transcripts.

Session transcripts are stored at:
  ~/.claude/projects/<project-dir>/<session-uuid>.jsonl

Each line is a JSON object with type: user|assistant|system|progress|...
We import user and assistant messages as cognitive events.
"""

import glob
import json
from pathlib import Path

import click

from ucw.importers.base import BaseImporter


class ClaudeCodeImporter(BaseImporter):
    def __init__(self):
        super().__init__(platform="claude-code")

    def run(self, filepath: str = None):
        """Import Claude Code sessions.

        If filepath is given, import that single JSONL file.
        Otherwise, auto-discover all sessions from ~/.claude/projects/.
        """
        if filepath:
            files = [Path(filepath)]
        else:
            files = self._discover_sessions()

        if not files:
            click.echo("No Claude Code sessions found.")
            return

        conn = self.connect_db()
        total_files = len(files)
        click.echo(f"Found {total_files} Claude Code sessions")

        try:
            for idx, fpath in enumerate(files, 1):
                project = self._extract_project(fpath)
                session_id_raw = fpath.stem
                count = self._import_session(conn, fpath, session_id_raw, project)
                if count > 0:
                    click.echo(
                        f"  [{idx}/{total_files}] {project}: "
                        f"{count} messages imported"
                    )

            conn.commit()
            click.echo(
                f"\nImported {self.imported} messages "
                f"({self.skipped} duplicates skipped)"
            )
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)
        finally:
            conn.close()

    def _discover_sessions(self):
        """Find all Claude Code session JSONL files."""
        base = Path.home() / ".claude" / "projects"
        if not base.exists():
            return []

        pattern = str(base / "*" / "*.jsonl")
        files = glob.glob(pattern)
        # Exclude subagent files
        files = [
            Path(f) for f in files
            if "/subagents/" not in f
        ]
        # Sort by modification time (newest first)
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return files

    def _extract_project(self, fpath: Path) -> str:
        """Extract a readable project name from the path."""
        parent = fpath.parent.name
        # Convert -Users-dicoangelo-projects-apps-CareerCoach to CareerCoach
        parts = parent.split("-")
        # Find last meaningful segment
        for skip in ("Users", "dicoangelo", "projects", "apps",
                      "products", "core", "portfolio"):
            while skip in parts:
                parts.remove(skip)
        return "-".join(parts) if parts else parent

    def _import_session(self, conn, fpath, session_id_raw, project):
        """Import messages from a single session JSONL."""
        session_id = self.make_session_id(session_id_raw)
        count = 0

        try:
            with open(fpath) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg_type = entry.get("type", "")
                    if msg_type not in ("user", "assistant"):
                        continue

                    message = entry.get("message", {})
                    role = message.get("role", msg_type)
                    content = self._extract_content(message)

                    if not content or len(content) < 5:
                        continue

                    chash = self.content_hash(content)
                    if self.event_exists(conn, chash):
                        self.skipped += 1
                        continue

                    timestamp = entry.get("timestamp", "")
                    ts_ns = self._parse_timestamp(timestamp)

                    layers = self.enrich_light(content)
                    light = layers["light"]
                    instinct = layers["instinct"]

                    event = {
                        "event_id": self.make_event_id(),
                        "session_id": session_id,
                        "timestamp_ns": ts_ns,
                        "direction": "inbound" if role == "user" else "outbound",
                        "stage": "complete",
                        "method": "import",
                        "content": content,
                        "light_intent": light.get("intent"),
                        "light_topic": light.get("topic"),
                        "light_concepts": json.dumps(light.get("concepts", [])),
                        "instinct_coherence": instinct.get("coherence_potential"),
                        "instinct_gut_signal": instinct.get("gut_signal"),
                        "content_hash": chash,
                    }
                    self.insert_event(conn, event)
                    self.imported += 1
                    count += 1

        except Exception as exc:
            click.echo(f"  Warning: {fpath.name}: {exc}", err=True)

        return count

    def _extract_content(self, message):
        """Extract text content from a Claude Code message."""
        content = message.get("content", "")

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            texts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        texts.append(part.get("text", ""))
                    elif part.get("type") == "tool_result":
                        # Tool results contain nested content
                        inner = part.get("content", "")
                        if isinstance(inner, str):
                            texts.append(inner[:500])
                        elif isinstance(inner, list):
                            for p in inner:
                                if isinstance(p, dict) and p.get("type") == "text":
                                    texts.append(p.get("text", "")[:500])
                elif isinstance(part, str):
                    texts.append(part)
            return " ".join(texts).strip()

        return ""

    def _parse_timestamp(self, ts_str):
        """Parse ISO timestamp string to nanoseconds."""
        if not ts_str:
            return self.timestamp_to_ns(0)
        try:
            from datetime import datetime
            # Handle "2026-03-09T16:21:46.563Z"
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            dt = datetime.fromisoformat(ts_str)
            return int(dt.timestamp() * 1e9)
        except Exception:
            return self.timestamp_to_ns(0)
