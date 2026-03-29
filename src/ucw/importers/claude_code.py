"""
Claude Code Importer — Import sessions from Claude Code JSONL transcripts.

Session transcripts are stored at:
  ~/.claude/projects/<project-dir>/<session-uuid>.jsonl

Each line is a JSON object with type: user|assistant|system|progress|...
We import user and assistant messages as cognitive events.

Project context is extracted from:
  1. The JSONL parent directory name (e.g. -Users-dicoangelo-projects-products-friendlyface)
  2. The `cwd` field in JSONL entries (e.g. /Users/dicoangelo/projects/products/friendlyface)
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

    @staticmethod
    def _extract_project_from_dir_name(dir_name: str) -> str:
        """Extract project name from a dash-encoded directory name.

        Input: "-Users-dicoangelo-projects-products-friendlyface"
        Output: "friendlyface"

        Special cases:
        - "-Users-dicoangelo" -> "home"
        - "-Users-dicoangelo--claude" -> "claude-config"
        - "-Users-dicoangelo--agent-core-pitch-deck" -> "agent-core-pitch-deck"
        """
        # Double-dashes encode a dot-prefixed directory (e.g. .claude -> --claude)
        # Split on single dashes but preserve double-dash as marker for dotfiles
        # Step 1: Replace double-dash with a placeholder
        normalized = dir_name.replace("--", "/.")

        # Step 2: Replace remaining single dashes with /
        normalized = normalized.replace("-", "/")

        # Now we have a path like /Users/dicoangelo/projects/products/friendlyface
        # or /Users/dicoangelo/.agent/core/pitch/deck
        # But this breaks names with real dashes like meta-vengine.
        # The encoding is ambiguous for dash-containing names.

        # Better approach: strip known prefixes using the dash-separated parts
        parts = dir_name.lstrip("-").split("-")

        # Strip known home directory prefix segments
        skip_prefixes = {"Users", "dicoangelo", "home"}
        idx = 0
        while idx < len(parts) and parts[idx] in skip_prefixes:
            idx += 1

        remaining = parts[idx:]

        if not remaining:
            return "home"

        # Strip known intermediate directory segments (projects, apps, etc.)
        # but only from the front — these are path components, not project names
        path_segments = {"projects", "apps", "products", "core", "portfolio",
                         "decks", "Desktop", "Documents", "Downloads"}
        while remaining and remaining[0] in path_segments:
            remaining = remaining[1:]

        if not remaining:
            return "home"

        # Handle dotfile directories (encoded as empty string from leading -)
        # e.g. "-Users-dicoangelo--claude" splits as [..., "", "claude"]
        # After stripping prefix: ["", "claude"]
        if remaining[0] == "":
            remaining = remaining[1:]
            if not remaining:
                return "home"
            # Dotfile project: .claude -> "claude-config", .agent-core -> "agent-core"
            name = "-".join(remaining)
            if name == "claude":
                return "claude-config"
            return name

        # Join remaining parts — these form the project name
        # e.g. ["meta", "vengine"] -> "meta-vengine"
        name = "-".join(remaining)
        return name.lower()

    @staticmethod
    def _extract_project_from_cwd(cwd: str) -> str:
        """Extract project name from a CWD path.

        Input: "/Users/dicoangelo/projects/products/friendlyface"
        Output: "friendlyface"
        """
        if not cwd:
            return ""

        path = Path(cwd)

        # Find the last meaningful segment after known path prefixes
        # Check if it's just the home directory
        home = Path.home()
        if path == home:
            return "home"

        # Strip home prefix and known intermediate dirs
        try:
            rel = path.relative_to(home)
        except ValueError:
            # Not under home — just use the last component
            return path.name.lower()

        rel_parts = list(rel.parts)
        path_segments = {"projects", "apps", "products", "core", "portfolio",
                         "decks", "Desktop", "Documents", "Downloads"}

        # Strip leading path segments
        while rel_parts and rel_parts[0] in path_segments:
            rel_parts = rel_parts[1:]

        if not rel_parts:
            return "home"

        # Handle dotfile directories
        first = rel_parts[0]
        if first.startswith("."):
            name = "/".join(rel_parts).replace("/", "-")
            name = name.lstrip(".")
            if name == "claude":
                return "claude-config"
            return name

        # The first remaining part is the project name
        # For subprojects, use the immediate project name
        return rel_parts[0].lower()

    def _extract_project(self, fpath: Path) -> str:
        """Extract a readable project name from the JSONL file path."""
        dir_name = fpath.parent.name
        return self._extract_project_from_dir_name(dir_name)

    def _read_cwd_from_jsonl(self, fpath: Path) -> str:
        """Read the cwd field from the first JSONL entry that has one."""
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
                    cwd = entry.get("cwd", "")
                    if cwd:
                        return cwd
        except OSError:
            pass
        return ""

    def _import_session(self, conn, fpath, session_id_raw, project):
        """Import messages from a single session JSONL."""
        session_id = self.make_session_id(session_id_raw)
        count = 0
        first_ts_ns = None

        # Extract CWD from JSONL for better project detection
        cwd = self._read_cwd_from_jsonl(fpath)
        if cwd:
            cwd_project = self._extract_project_from_cwd(cwd)
            if cwd_project and cwd_project != "home":
                project = cwd_project
            elif project == "home" and cwd_project:
                project = cwd_project

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

                    if first_ts_ns is None:
                        first_ts_ns = ts_ns

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

                    # Enrich with project context — use enrichment module if available
                    try:
                        from ucw.enrichment import enrich_event
                        enriched = enrich_event(
                            content, {"project_dir": project, "cwd": cwd}
                        )
                        event["light_topic"] = enriched["topic"]
                        event["light_intent"] = enriched["intent"]
                        event["light_summary"] = enriched["summary"]
                        event["light_concepts"] = json.dumps(enriched["concepts"])
                    except ImportError:
                        event["light_topic"] = project or "general"

                    self.insert_event(conn, event)
                    self.imported += 1
                    count += 1

        except Exception as exc:
            click.echo(f"  Warning: {fpath.name}: {exc}", err=True)

        # Upsert session record
        if first_ts_ns is not None:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO sessions "
                    "(session_id, started_ns, platform, topics) "
                    "VALUES (?, ?, ?, ?)",
                    (session_id, first_ts_ns, "claude-code", project),
                )
            except Exception:
                pass  # Session table may not exist in all environments

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
