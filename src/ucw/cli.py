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
from pathlib import Path

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
    """Initialize UCW: create ~/.ucw/, generate config, print setup instructions."""
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
    click.echo()
    click.echo("Next: add UCW to your Claude settings.")
    click.echo("Run `ucw mcp-config` to get the JSON snippet.")


@main.command()
def server():
    """Start the UCW MCP server (stdio mode)."""
    from ucw.server.server import RawMCPServer
    from ucw.tools import ucw_tools, coherence_tools

    async def _run():
        srv = RawMCPServer()
        srv.register_tools(ucw_tools.TOOLS, ucw_tools.handle_tool)
        srv.register_tools(coherence_tools.TOOLS, coherence_tools.handle_tool)
        await srv.run()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


@main.command()
def status():
    """Show UCW database statistics."""
    import sqlite3

    if not Config.DB_PATH.exists():
        click.echo("No database found. Run `ucw init` and start a session first.")
        return

    conn = sqlite3.connect(str(Config.DB_PATH))
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
