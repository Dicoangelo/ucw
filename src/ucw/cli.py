"""
UCW CLI — Command-line interface for the Universal Cognitive Wallet

Commands:
    ucw init        Create ~/.ucw/ and generate config
    ucw server      Start the MCP server (stdio mode)
    ucw status      Show database stats
    ucw mcp-config  Print Claude Desktop/Code JSON config
"""

import asyncio
import json
import sys

import click

from ucw import __version__
from ucw.config import Config


@click.group()
@click.version_option(version=__version__, prog_name="ucw")
def main():
    """Universal Cognitive Wallet — AI cognitive capture via MCP."""
    pass


@main.command()
def init():
    """Initialize UCW: create ~/.ucw/, detect AI tools, print setup instructions."""
    from pathlib import Path as _Path

    Config.ensure_dirs()

    config_env = Config.UCW_DIR / "config.env"
    if not config_env.exists():
        config_env.write_text(
            "# UCW Configuration\n"
            "# Uncomment and edit as needed.\n"
            "\n"
            "# UCW_DATA_DIR=~/.ucw\n"
            "# UCW_LOG_LEVEL=DEBUG\n"
            "# UCW_PLATFORM=claude-desktop\n"
        )

    click.echo(f"UCW initialized at {Config.UCW_DIR}")
    click.echo(f"  Config: {config_env}")
    click.echo(f"  Logs:   {Config.LOG_DIR}")
    click.echo(f"  DB:     {Config.DB_PATH}")

    # --- Detect installed AI tools ---
    home = _Path.home()
    detected = []

    # Claude Desktop
    claude_config = (
        home / "Library" / "Application Support"
        / "Claude" / "claude_desktop_config.json"
    )
    if claude_config.exists():
        detected.append("Claude Desktop (config found)")

    # Cursor
    cursor_dir = home / ".cursor"
    if cursor_dir.exists():
        detected.append("Cursor (sessions found \u2014 run `ucw import cursor` to import)")

    # ChatGPT — common export locations
    chatgpt_paths = [
        home / "Downloads" / "conversations.json",
        home / "Downloads" / "chatgpt-export" / "conversations.json",
        home / "Documents" / "conversations.json",
    ]
    if any(p.exists() for p in chatgpt_paths):
        export_path = next(p for p in chatgpt_paths if p.exists())
        detected.append(
            f"ChatGPT (export found at {export_path}"
            f" \u2014 run `ucw import chatgpt {export_path}`)"
        )

    # Grok
    grok_dir = home / "Library" / "Application Support" / "Grok"
    if grok_dir.exists():
        detected.append("Grok (app found \u2014 export and run `ucw import grok <file>`)")

    if detected:
        click.echo()
        click.echo("Detected AI tools:")
        for tool in detected:
            click.echo(f"  {tool}")

    # --- MCP config snippet ---
    ucw_path = _find_ucw_executable()
    mcp_snippet = {
        "mcpServers": {
            "ucw": {
                "command": ucw_path,
                "args": ["server"],
            }
        }
    }

    click.echo()
    click.echo("MCP config (add to Claude Desktop or Claude Code):")
    click.echo(json.dumps(mcp_snippet, indent=2))

    # --- Next steps ---
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Run `ucw mcp-config` to connect UCW to Claude")
    click.echo("  2. Run `ucw demo` to explore with sample data")
    click.echo("  3. Run `ucw dashboard` to see your AI memory")


@main.command()
def server():
    """Start the UCW MCP server (stdio mode)."""
    from ucw.server.server import RawMCPServer
    from ucw.tools import (
        agent_tools,
        coherence_tools,
        graph_tools,
        intelligence_tools,
        proof_tools,
        temporal_tools,
        ucw_tools,
    )

    async def _run():
        srv = RawMCPServer()
        for mod in [
            ucw_tools, coherence_tools, graph_tools,
            intelligence_tools, agent_tools, temporal_tools,
            proof_tools,
        ]:
            srv.register_tools(mod.TOOLS, mod.handle_tool)
        await srv.run()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


@main.command()
def status():
    """Show UCW database statistics."""
    from ucw.errors import format_error, safe_db_connect

    conn, err = safe_db_connect(Config.DB_PATH)
    if err is not None:
        click.echo(format_error(err))
        return

    try:
        cur = conn.execute("SELECT COUNT(*) FROM cognitive_events")
        total_events = cur.fetchone()[0]

        cur = conn.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = cur.fetchone()[0]

        cur = conn.execute("SELECT SUM(content_length) FROM cognitive_events")
        total_bytes = cur.fetchone()[0] or 0

        cur = conn.execute(
            "SELECT light_topic, COUNT(*) FROM cognitive_events "
            "WHERE light_topic IS NOT NULL "
            "GROUP BY light_topic ORDER BY COUNT(*) DESC LIMIT 5"
        )
        topics = cur.fetchall()

        cur = conn.execute(
            "SELECT instinct_gut_signal, COUNT(*) FROM cognitive_events "
            "WHERE instinct_gut_signal IS NOT NULL "
            "GROUP BY instinct_gut_signal ORDER BY COUNT(*) DESC"
        )
        signals = cur.fetchall()
    finally:
        conn.close()

    click.echo("UCW Status")
    click.echo("=" * 40)
    click.echo(f"Events:   {total_events:,}")
    click.echo(f"Sessions: {total_sessions}")
    click.echo(f"Bytes:    {total_bytes:,}")
    click.echo()

    if topics:
        click.echo("Top Topics:")
        for topic, count in topics:
            click.echo(f"  {topic}: {count}")

    if signals:
        click.echo("Gut Signals:")
        for signal, count in signals:
            click.echo(f"  {signal}: {count}")


@main.command("mcp-config")
def mcp_config():
    """Print MCP config JSON for Claude Desktop or Claude Code."""
    ucw_path = _find_ucw_executable()

    config = {
        "mcpServers": {
            "ucw": {
                "command": ucw_path,
                "args": ["server"],
            }
        }
    }

    click.echo("Add this to your Claude settings:\n")
    click.echo(json.dumps(config, indent=2))
    click.echo()
    click.echo("Claude Desktop: Settings > Developer > Edit Config")
    click.echo("Claude Code:    .claude/settings.json or ~/.claude/settings.json")


@main.command()
def migrate():
    """Run database migrations to latest version."""
    from ucw.db.migrations import get_status, migrate_up

    if not Config.DB_PATH.exists():
        click.echo("No database found. Run `ucw init` and start a session first.")
        return

    import sqlite3
    conn = sqlite3.connect(str(Config.DB_PATH))
    try:
        get_status(conn)
        applied = migrate_up(conn)
        after = get_status(conn)
    finally:
        conn.close()

    if applied:
        click.echo(f"Applied {len(applied)} migration(s): {', '.join(applied)}")
    else:
        click.echo("Database already up to date.")

    click.echo(f"Current version: {after['current_version']}/{after['available']}")


@main.command()
def doctor():
    """Check UCW installation health: Python, SQLite, DB, migrations, deps."""
    import platform
    import sqlite3 as _sqlite3

    passed = 0
    failed = 0
    warnings = 0

    def _pass(msg):
        nonlocal passed
        passed += 1
        click.echo(f"[PASS] {msg}")

    def _fail(msg):
        nonlocal failed
        failed += 1
        click.echo(f"[FAIL] {msg}")

    def _warn(msg):
        nonlocal warnings
        warnings += 1
        click.echo(f"[WARN] {msg}")

    click.echo("UCW Doctor")
    click.echo("=" * 40)

    # Python version
    py_ver = platform.python_version()
    py_tuple = tuple(int(x) for x in py_ver.split(".")[:2])
    if py_tuple >= (3, 10):
        _pass(f"Python {py_ver}")
    else:
        _fail(f"Python {py_ver} (>=3.10 required)")

    # SQLite version
    sqlite_ver = _sqlite3.sqlite_version
    sqlite_tuple = tuple(int(x) for x in sqlite_ver.split(".")[:2])
    if sqlite_tuple >= (3, 35):
        _pass(f"SQLite {sqlite_ver}")
    else:
        _fail(f"SQLite {sqlite_ver} (>=3.35 required for DROP COLUMN)")

    # UCW directory
    if Config.UCW_DIR.exists():
        _pass(f"UCW directory: {Config.UCW_DIR}")
    else:
        _fail(f"UCW directory missing: {Config.UCW_DIR}")

    # Database file
    if Config.DB_PATH.exists():
        size_kb = Config.DB_PATH.stat().st_size / 1024
        _pass(f"Database: {Config.DB_PATH} ({size_kb:.0f} KB)")
    else:
        _fail(f"Database not found: {Config.DB_PATH}")

    # Database writable + WAL mode + migrations (only if DB exists)
    if Config.DB_PATH.exists():
        try:
            conn = _sqlite3.connect(str(Config.DB_PATH))
            # Writable test
            conn.execute("CREATE TABLE IF NOT EXISTS _doctor_test (x INTEGER)")
            conn.execute("DROP TABLE IF EXISTS _doctor_test")
            _pass("Database writable")

            # WAL mode
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            if journal == "wal":
                _pass("WAL mode enabled")
            else:
                _warn(f"Journal mode is '{journal}', not WAL")

            # Migration status
            try:
                from ucw.db.migrations import get_status as _get_migration_status
                statuses = _get_migration_status(conn)
                total = len(statuses)
                applied_count = sum(1 for s in statuses if s["applied"])
                if total == 0:
                    _pass("Migrations: no migrations defined")
                elif applied_count == total:
                    _pass(f"Migrations: {applied_count}/{total} applied")
                else:
                    pending = total - applied_count
                    _warn(
                        f"Migrations: {applied_count}/{total}"
                        f" applied ({pending} pending)"
                    )
            except Exception as exc:
                _warn(f"Migration check failed: {exc}")

            conn.close()
        except Exception as exc:
            _fail(f"Database error: {exc}")

    # Optional deps
    for pkg, extra in [("rich", "ui"), ("sentence_transformers", "embeddings")]:
        display_name = pkg.replace("_", "-")
        try:
            __import__(pkg)
            _pass(f"{display_name} installed")
        except ImportError:
            _warn(f"{display_name} not installed (install with: pip install ucw[{extra}])")

    click.echo()
    click.echo(f"{passed} passed, {failed} failed, {warnings} warnings")
    sys.exit(1 if failed > 0 else 0)


@main.command()
@click.option("--check", is_flag=True, help="Only run diagnostics, don't modify the database.")
def repair(check):
    """Repair and optimize the UCW database."""
    import sqlite3 as _sqlite3

    click.echo("UCW Repair")
    click.echo("=" * 40)

    if not Config.DB_PATH.exists():
        click.echo("[FAIL] Database not found. Run `ucw init` and start a session first.")
        sys.exit(1)

    conn = _sqlite3.connect(str(Config.DB_PATH))
    try:
        # Integrity check
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result == "ok":
            click.echo("[OK] Integrity check passed")
        else:
            click.echo(f"[FAIL] Integrity check: {result}")

        # Quick check
        result = conn.execute("PRAGMA quick_check").fetchone()[0]
        if result == "ok":
            click.echo("[OK] Quick check passed")
        else:
            click.echo(f"[FAIL] Quick check: {result}")

        # WAL mode
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        if journal == "wal":
            click.echo("[OK] WAL mode enabled")
        elif check:
            click.echo(f"[WARN] Journal mode is '{journal}', not WAL (run without --check to fix)")
        else:
            conn.execute("PRAGMA journal_mode=wal")
            click.echo("[FIX] WAL mode enabled")

        # Indexes
        cur = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
        )
        indexes = cur.fetchall()
        if indexes:
            if check:
                click.echo(f"[OK] {len(indexes)} indexes found (run without --check to rebuild)")
            else:
                for idx_name, idx_sql in indexes:
                    conn.execute(f"DROP INDEX IF EXISTS [{idx_name}]")
                for _, idx_sql in indexes:
                    conn.execute(idx_sql)
                conn.commit()
                click.echo(f"[FIX] Rebuilt {len(indexes)} indexes")
        else:
            click.echo("[OK] No indexes to rebuild")

        # VACUUM
        if check:
            db_size = Config.DB_PATH.stat().st_size
            click.echo(
                f"[OK] Database size: {db_size / 1024:.1f} KB"
                " (run without --check to VACUUM)"
            )
        else:
            size_before = Config.DB_PATH.stat().st_size
            conn.execute("VACUUM")
            size_after = Config.DB_PATH.stat().st_size
            saved = size_before - size_after
            if saved > 0:
                if saved > 1024 * 1024:
                    click.echo(f"[FIX] VACUUM complete (saved {saved / (1024*1024):.1f} MB)")
                else:
                    click.echo(f"[FIX] VACUUM complete (saved {saved / 1024:.1f} KB)")
            else:
                click.echo("[OK] VACUUM complete (no space to reclaim)")
    finally:
        conn.close()


@main.group(name="import")
def import_cmd():
    """Import conversations from other AI platforms."""
    pass


@import_cmd.command()
@click.argument("filepath", type=click.Path(exists=True))
def chatgpt(filepath):
    """Import ChatGPT conversations from export JSON."""
    from ucw.importers.chatgpt import ChatGPTImporter

    importer = ChatGPTImporter()
    importer.run(filepath)


@import_cmd.command()
@click.argument("filepath", type=click.Path(), required=False)
def cursor(filepath):
    """Import Cursor AI conversations."""
    from ucw.importers.cursor import CursorImporter

    importer = CursorImporter()
    importer.run(filepath)


@import_cmd.command()
@click.argument("filepath", type=click.Path(exists=True))
def grok(filepath):
    """Import Grok conversations from export."""
    from ucw.importers.grok import GrokImporter

    importer = GrokImporter()
    importer.run(filepath)


@main.command("capture-test")
def capture_test():
    """Check if UCW is actively capturing your AI conversations."""
    import time as _time
    from pathlib import Path as _Path

    from ucw.errors import format_error, safe_db_connect

    passed = 0
    failed = 0
    warnings = 0

    def _pass(msg):
        nonlocal passed
        passed += 1
        click.echo(f"[PASS] {msg}")

    def _fail(msg):
        nonlocal failed
        failed += 1
        click.echo(f"[FAIL] {msg}")

    def _warn(msg):
        nonlocal warnings
        warnings += 1
        click.echo(f"[WARN] {msg}")

    click.echo("UCW Capture Test")
    click.echo("=" * 40)

    # 1. DB exists and writable
    conn, err = safe_db_connect(Config.DB_PATH)
    if err is not None:
        _fail(f"Database: {format_error(err)}")
        click.echo()
        click.echo(
            f"{passed} passed, {failed} failed, "
            f"{warnings} warnings"
        )
        return

    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM cognitive_events"
        ).fetchone()[0]
        size_kb = Config.DB_PATH.stat().st_size / 1024
        _pass(f"Database: {total:,} events ({size_kb:.1f} KB)")

        # 2. Recent events (last 24h)
        now_ns = _time.time_ns()
        day_ns = 86400 * 10**9
        recent = conn.execute(
            "SELECT COUNT(*) FROM cognitive_events "
            "WHERE timestamp_ns > ?",
            (now_ns - day_ns,),
        ).fetchone()[0]
        last_ts = conn.execute(
            "SELECT MAX(timestamp_ns) FROM cognitive_events"
        ).fetchone()[0]

        if recent > 0 and last_ts:
            ago = _time_ago(last_ts)
            _pass(
                f"Recent activity: {recent} events in "
                f"last 24h (last: {ago})"
            )
        elif last_ts:
            ago = _time_ago(last_ts)
            _warn(
                "No events in last 24h "
                f"(last: {ago}) "
                "— is Claude running with UCW?"
            )
        else:
            _warn(
                "No events in last 24h "
                "— is Claude running with UCW?"
            )

        # 3. MCP config presence
        home = _Path.home()
        found_mcp = []

        claude_desktop = (
            home / "Library" / "Application Support"
            / "Claude" / "claude_desktop_config.json"
        )
        if claude_desktop.exists():
            found_mcp.append("Claude Desktop")

        claude_code = home / ".claude" / "settings.json"
        if claude_code.exists():
            found_mcp.append("Claude Code")

        if found_mcp:
            _pass(
                f"MCP config: Found in {', '.join(found_mcp)}"
            )
        else:
            _fail(
                "MCP config: Not found "
                "— run `ucw mcp-config` to set up"
            )

        # 4. Capture stats — platforms
        rows = conn.execute(
            "SELECT platform, COUNT(*) FROM cognitive_events "
            "GROUP BY platform ORDER BY COUNT(*) DESC"
        ).fetchall()
        if rows:
            parts = [
                f"{p or 'unknown'} ({c:,})" for p, c in rows
            ]
            _pass(f"Platforms: {', '.join(parts)}")
        else:
            _warn("No platform data recorded yet")

    finally:
        conn.close()

    click.echo()
    click.echo(
        f"{passed} passed, {failed} failed, "
        f"{warnings} warnings"
    )


def _time_ago(timestamp_ns):
    """Format a nanosecond timestamp as a human-readable time ago."""
    import time as _time

    now = _time.time_ns()
    diff_s = (now - timestamp_ns) / 10**9
    if diff_s < 0:
        return "just now"
    if diff_s < 60:
        return f"{int(diff_s)}s ago"
    if diff_s < 3600:
        return f"{int(diff_s // 60)}m ago"
    if diff_s < 86400:
        return f"{int(diff_s // 3600)}h ago"
    return f"{int(diff_s // 86400)}d ago"


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def dashboard(as_json):
    """Show your AI memory dashboard."""
    from ucw.dashboard import get_dashboard_data, render_plain, render_rich

    data = get_dashboard_data()
    if as_json:
        import json as json_mod

        click.echo(json_mod.dumps(data, indent=2, default=str))
        return
    try:
        render_rich(data)
    except ImportError:
        click.echo(render_plain(data))


@main.command()
@click.option("--clean", is_flag=True, help="Remove demo data")
def demo(clean):
    """Load sample AI conversations to explore UCW features."""
    from ucw.demo import clean_demo_data, load_demo_data

    Config.ensure_dirs()
    if clean:
        deleted = clean_demo_data()
        click.echo(f"Removed {deleted} demo events.")
        return
    count = load_demo_data()
    click.echo(f"Loaded {count} sample events across 3 platforms.")
    click.echo("Run `ucw dashboard` to see your AI memory overview.")


@main.command()
@click.argument("query")
@click.option("--platform", default=None, help="Filter by platform")
@click.option("--after", default=None, help="After ISO date (YYYY-MM-DD)")
@click.option("--before", default=None, help="Before ISO date (YYYY-MM-DD)")
@click.option("--limit", default=10, help="Max results (default 10)")
@click.option("--semantic/--no-semantic", default=None,
              help="Force semantic or keyword search")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def search(query, platform, after, before, limit, semantic, as_json):
    """Search your AI conversations: ucw search 'that thing about auth'."""
    import json as json_mod
    from datetime import datetime

    from ucw.search import search as ucw_search

    db_path = Config.DB_PATH
    if not db_path.exists():
        click.echo("No database found. Run `ucw init` first.")
        return

    # Convert ISO dates to nanosecond timestamps
    after_ns = None
    before_ns = None
    if after:
        dt = datetime.fromisoformat(after)
        after_ns = int(dt.timestamp() * 10**9)
    if before:
        dt = datetime.fromisoformat(before)
        before_ns = int(dt.timestamp() * 10**9)

    results, method = ucw_search(
        db_path, query, semantic=semantic,
        limit=limit, platform=platform,
        after=after_ns, before=before_ns,
    )

    if as_json:
        click.echo(json_mod.dumps(results, indent=2, default=str))
        return

    if not results:
        click.echo(f"No results for '{query}'")
        if method == "keyword":
            try:
                from ucw.server.embeddings import embed_single  # noqa: F401
                click.echo("Tip: Run `ucw index` then search again for semantic results.")
            except ImportError:
                click.echo("Tip: Install ucw[embeddings] for semantic search.")
        return

    click.echo(f"Found {len(results)} results ({method} search):\n")
    for i, r in enumerate(results, 1):
        ts = r.get("timestamp_ns", 0)
        ago = _time_ago(ts) if ts else "unknown"
        plat = r.get("platform", "unknown")
        topic = r.get("topic") or "untitled"
        snippet = (r.get("snippet") or "")[:120]
        score = r.get("similarity") or r.get("score", 0)

        click.echo(f"  {i}. [{plat}] {topic}  ({ago})")
        if snippet:
            click.echo(f"     {snippet}")
        click.echo(f"     score: {score:.3f}")
        click.echo()


@main.command()
@click.option("--status", is_flag=True, help="Show index status")
@click.option("--rebuild", is_flag=True, help="Drop and rebuild cache")
def index(status, rebuild):
    """Build or manage the semantic search embedding index."""
    try:
        from ucw.server.embeddings import embed_single  # noqa: F401
    except ImportError:
        click.echo("Semantic search requires embeddings.")
        click.echo("Install with: pip install 'ucw[embeddings]'")
        return

    import sqlite3 as _sqlite3

    db_path = Config.DB_PATH
    if not db_path.exists():
        click.echo("No database found. Run `ucw init` first.")
        return

    if status:
        conn = _sqlite3.connect(str(db_path))
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM cognitive_events"
            ).fetchone()[0]
            try:
                cached = conn.execute(
                    "SELECT COUNT(*) FROM embedding_cache"
                ).fetchone()[0]
                model = conn.execute(
                    "SELECT model FROM embedding_cache LIMIT 1"
                ).fetchone()
                model_name = model[0] if model else "none"
            except _sqlite3.OperationalError:
                cached = 0
                model_name = "none"
            size = db_path.stat().st_size
        finally:
            conn.close()
        click.echo(f"Total events:  {total:,}")
        click.echo(f"Indexed:       {cached:,}")
        click.echo(f"Unindexed:     {total - cached:,}")
        click.echo(f"Model:         {model_name}")
        click.echo(f"DB size:       {size / 1024:.1f} KB")
        return

    if rebuild:
        conn = _sqlite3.connect(str(db_path))
        try:
            conn.execute("DELETE FROM embedding_cache")
            conn.commit()
        except _sqlite3.OperationalError:
            pass
        finally:
            conn.close()
        click.echo("Embedding cache cleared.")

    from ucw.search import build_embedding_index

    def _progress(current, total):
        if total > 0:
            pct = current * 100 // total
            bar = "=" * (pct // 5) + ">" + " " * (20 - pct // 5)
            click.echo(
                f"\rIndexing {current:,}/{total:,} [{bar}] {pct}%",
                nl=False,
            )

    click.echo("Building embedding index...")
    count = build_embedding_index(db_path, callback=_progress)
    click.echo()  # newline after progress
    if count > 0:
        click.echo(f"Indexed {count:,} new events.")
    else:
        click.echo("All events already indexed.")


@main.command()
@click.option("--port", default=7077, help="Port (default 7077)")
@click.option("--host", default="127.0.0.1", help="Host (default 127.0.0.1)")
@click.option("--no-open", is_flag=True, help="Don't open browser")
def web(port, host, no_open):
    """Launch the UCW web dashboard in your browser."""
    from ucw.web import UCWWebServer

    db_path = Config.DB_PATH
    if not db_path.exists():
        click.echo("No database found. Run `ucw init && ucw demo` first.")
        return

    # Find available port
    import socket
    actual_port = port
    for offset in range(11):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((host, port + offset))
            sock.close()
            actual_port = port + offset
            break
        except OSError:
            if offset == 10:
                click.echo(
                    f"Ports {port}-{port + 10} all in use."
                )
                return
            continue

    url = f"http://{host}:{actual_port}"
    click.echo(f"UCW Dashboard running at {url}")

    if not no_open:
        import webbrowser
        webbrowser.open(url)

    try:
        server = UCWWebServer(host, actual_port)
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nDashboard stopped.")


def _find_ucw_executable() -> str:
    """Find the ucw command path."""
    import shutil
    path = shutil.which("ucw")
    if path:
        return path
    # Fallback: use python -m ucw
    return sys.executable


if __name__ == "__main__":
    main()
