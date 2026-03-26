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
    claude_config = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
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
        detected.append(f"ChatGPT (export found at {export_path} \u2014 run `ucw import chatgpt {export_path}`)")

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
        before = get_status(conn)
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
                    _warn(f"Migrations: {applied_count}/{total} applied ({total - applied_count} pending)")
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
            click.echo(f"[OK] Database size: {db_size / 1024:.1f} KB (run without --check to VACUUM)")
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
