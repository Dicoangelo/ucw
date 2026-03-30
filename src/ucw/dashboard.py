"""
UCW Dashboard — Aggregate statistics and rich display for the cognitive wallet.
"""

import sqlite3
from pathlib import Path

from ucw.config import Config


def get_dashboard_data(db_path=None):
    """Gather all dashboard statistics from the database."""
    db_path = db_path or Config.DB_PATH
    if not Path(db_path).exists():
        return None

    conn = sqlite3.connect(str(db_path))
    data = {}
    try:
        # Noise filter — only apply if the column exists (migration 008)
        try:
            conn.execute(
                "SELECT is_noise FROM cognitive_events LIMIT 1"
            )
            _nf = " AND (is_noise IS NULL OR is_noise = 0)"
        except sqlite3.OperationalError:
            _nf = ""

        # Total events (signal only)
        data['total_events'] = conn.execute(
            "SELECT COUNT(*) FROM cognitive_events WHERE 1=1" + _nf
        ).fetchone()[0]

        # Events by platform (signal only)
        rows = conn.execute(
            "SELECT platform, COUNT(*) FROM cognitive_events "
            "WHERE 1=1" + _nf + " "
            "GROUP BY platform ORDER BY COUNT(*) DESC"
        ).fetchall()
        data['platforms'] = {r[0] or 'unknown': r[1] for r in rows}

        # Top topics (signal only)
        rows = conn.execute(
            "SELECT light_topic, COUNT(*) FROM cognitive_events "
            "WHERE light_topic IS NOT NULL" + _nf + " "
            "GROUP BY light_topic ORDER BY COUNT(*) DESC LIMIT 10"
        ).fetchall()
        data['top_topics'] = [(r[0], r[1]) for r in rows]

        # Recent coherence moments (table may not exist yet)
        try:
            rows = conn.execute(
                "SELECT description, coherence_score, detected_ns "
                "FROM coherence_moments "
                "ORDER BY detected_ns DESC LIMIT 5"
            ).fetchall()
            data['recent_moments'] = rows
        except sqlite3.OperationalError:
            data['recent_moments'] = []

        # Knowledge graph stats (tables may not exist yet)
        try:
            entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            rels = conn.execute("SELECT COUNT(*) FROM entity_relationships").fetchone()[0]
            data['graph'] = {'entities': entities, 'relationships': rels}
        except sqlite3.OperationalError:
            data['graph'] = {'entities': 0, 'relationships': 0}

        # Total bytes (signal only)
        data['total_bytes'] = conn.execute(
            "SELECT COALESCE(SUM(content_length), 0) FROM cognitive_events "
            "WHERE 1=1" + _nf
        ).fetchone()[0]

        # Session count
        data['sessions'] = conn.execute(
            "SELECT COUNT(*) FROM sessions"
        ).fetchone()[0]

        # Date range
        rows = conn.execute(
            "SELECT MIN(timestamp_ns), MAX(timestamp_ns) FROM cognitive_events"
        ).fetchall()
        data['date_range'] = (rows[0][0], rows[0][1]) if rows and rows[0][0] else (None, None)

        # Gut signals distribution (signal only)
        rows = conn.execute(
            "SELECT instinct_gut_signal, COUNT(*) FROM cognitive_events "
            "WHERE instinct_gut_signal IS NOT NULL" + _nf + " "
            "GROUP BY instinct_gut_signal ORDER BY COUNT(*) DESC"
        ).fetchall()
        data['gut_signals'] = [(r[0], r[1]) for r in rows]

        # Projects breakdown — topics that look like project names (not generic)
        _generic = {
            'frontend', 'backend', 'auth', 'deployment', 'testing',
            'infrastructure', 'api', 'database', 'ui', 'ux', 'devops',
            'security', 'performance', 'debugging', 'refactoring',
            'documentation', 'configuration', 'monitoring', 'ci-cd',
            'migration', 'review', 'planning', 'design', 'general',
        }
        project_rows = conn.execute(
            "SELECT light_topic, COUNT(*) as c, MAX(timestamp_ns) as last_ns "
            "FROM cognitive_events "
            "WHERE light_topic IS NOT NULL" + _nf + " "
            "GROUP BY light_topic ORDER BY c DESC LIMIT 30"
        ).fetchall()
        total_for_pct = data['total_events'] or 1
        projects = []
        for row in project_rows:
            name = row[0]
            if name.lower() in _generic:
                continue
            projects.append({
                'name': name,
                'count': row[1],
                'last_active_ns': row[2],
                'pct': round(row[1] / total_for_pct * 100, 1),
            })
            if len(projects) >= 10:
                break
        data['projects'] = projects

        # Capture health
        import time as _time
        now_ns = _time.time_ns()
        day_ns = 86400 * 10**9
        week_ns = 7 * day_ns

        events_24h = conn.execute(
            "SELECT COUNT(*) FROM cognitive_events "
            "WHERE timestamp_ns > ?" + _nf,
            (now_ns - day_ns,),
        ).fetchone()[0]

        events_7d = conn.execute(
            "SELECT COUNT(*) FROM cognitive_events "
            "WHERE timestamp_ns > ?" + _nf,
            (now_ns - week_ns,),
        ).fetchone()[0]

        last_event = conn.execute(
            "SELECT MAX(timestamp_ns) FROM cognitive_events "
            "WHERE 1=1" + _nf
        ).fetchone()[0]

        last_age = (
            (now_ns - last_event) / 10**9
            if last_event else None
        )

        active_platforms = conn.execute(
            "SELECT DISTINCT platform FROM cognitive_events "
            "WHERE timestamp_ns > ?" + _nf,
            (now_ns - week_ns,),
        ).fetchall()

        data['capture_health'] = {
            'last_event_age_seconds': last_age,
            'events_last_24h': events_24h,
            'events_last_7d': events_7d,
            'active_platforms': [
                r[0] for r in active_platforms
            ],
        }

    finally:
        conn.close()

    return data


def render_plain(data):
    """Render dashboard as plain text."""
    if not data:
        return "No data. Run `ucw demo` to load sample data or start capturing."

    lines = []
    lines.append("UCW Dashboard")
    lines.append("=" * 50)
    lines.append(f"  Events:    {data['total_events']:,}")
    lines.append(f"  Sessions:  {data['sessions']}")
    lines.append(f"  Data:      {_fmt_bytes(data['total_bytes'])}")
    lines.append("")

    if data['platforms']:
        lines.append("Platforms:")
        for p, c in data['platforms'].items():
            pct = (c / data['total_events'] * 100) if data['total_events'] else 0
            lines.append(f"  {p:20s} {c:>6,} ({pct:.0f}%)")
        lines.append("")

    if data['top_topics']:
        lines.append("Top Topics:")
        for topic, count in data['top_topics'][:5]:
            lines.append(f"  {topic:30s} {count:>5}")
        lines.append("")

    if data.get('graph', {}).get('entities', 0) > 0:
        g = data['graph']
        lines.append(
            f"Knowledge Graph: {g['entities']} entities, "
            f"{g['relationships']} relationships"
        )
        lines.append("")

    if data['gut_signals']:
        lines.append("Gut Signals:")
        for sig, count in data['gut_signals']:
            lines.append(f"  {sig:20s} {count:>5}")
        lines.append("")

    ch = data.get('capture_health')
    if ch:
        lines.append("Capture Health:")
        e24 = ch['events_last_24h']
        e7d = ch['events_last_7d']
        if e24 > 0:
            lines.append(
                f"  [OK] {e24} events in last 24h, "
                f"{e7d} in last 7d"
            )
        else:
            lines.append(
                f"  [--] 0 events in last 24h, "
                f"{e7d} in last 7d"
            )

        age = ch['last_event_age_seconds']
        if age is not None:
            lines.append(
                f"  Last capture: {_fmt_age(age)}"
            )
        else:
            lines.append("  Last capture: never")

        platforms = ch['active_platforms']
        if platforms:
            lines.append(
                f"  Active: {', '.join(platforms)}"
            )

    return "\n".join(lines)


def render_rich(data):
    """Render dashboard using rich library."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    if not data:
        console.print(Panel(
            "No data. Run [bold]ucw demo[/bold] to load sample data.",
            title="UCW Dashboard",
        ))
        return

    # Header
    console.print(Panel(
        f"[bold]{data['total_events']:,}[/bold] events | "
        f"[bold]{data['sessions']}[/bold] sessions | "
        f"[bold]{_fmt_bytes(data['total_bytes'])}[/bold]",
        title="[bold blue]UCW Dashboard[/bold blue]",
        subtitle="v0.4.0",
    ))

    # Platforms table
    if data['platforms']:
        table = Table(title="Platforms")
        table.add_column("Platform", style="cyan")
        table.add_column("Events", justify="right")
        table.add_column("%", justify="right")
        for p, c in data['platforms'].items():
            pct = f"{c / data['total_events'] * 100:.0f}%" if data['total_events'] else "0%"
            table.add_row(p, f"{c:,}", pct)
        console.print(table)

    # Topics table
    if data['top_topics']:
        table = Table(title="Top Topics")
        table.add_column("Topic", style="green")
        table.add_column("Count", justify="right")
        for topic, count in data['top_topics'][:5]:
            table.add_row(topic, str(count))
        console.print(table)

    # Knowledge graph
    g = data.get('graph', {})
    if g.get('entities', 0) > 0:
        console.print(
            f"\n[bold]Knowledge Graph:[/bold] "
            f"{g['entities']} entities, {g['relationships']} relationships"
        )

    # Gut signals
    if data['gut_signals']:
        table = Table(title="Gut Signals")
        table.add_column("Signal", style="yellow")
        table.add_column("Count", justify="right")
        for sig, count in data['gut_signals']:
            table.add_row(sig, str(count))
        console.print(table)

    # Capture health
    ch = data.get('capture_health')
    if ch:
        e24 = ch['events_last_24h']
        e7d = ch['events_last_7d']
        age = ch['last_event_age_seconds']
        platforms = ch['active_platforms']

        age_str = _fmt_age(age) if age is not None else "never"
        plat_str = (
            ", ".join(platforms) if platforms else "none"
        )
        status = "[green]OK[/green]" if e24 > 0 else "[yellow]--[/yellow]"

        console.print(Panel(
            f"{status} {e24} events in last 24h, "
            f"{e7d} in last 7d\n"
            f"Last capture: {age_str}\n"
            f"Active: {plat_str}",
            title="[bold]Capture Health[/bold]",
        ))


def _fmt_bytes(n):
    """Format byte count as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != 'B' else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _fmt_age(seconds):
    """Format seconds as a human-readable age string."""
    if seconds is None:
        return "never"
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{int(seconds)}s ago"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"
