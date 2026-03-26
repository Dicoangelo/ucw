"""
Temporal Tools — MCP tools for temporal intelligence analysis.

Tools:
  topic_evolution    — Track how topics evolve over time
  skill_trajectory   — Track coherence progression for a specific topic
  temporal_insights  — Combined temporal analysis: decay, heatmap, stats
"""

from typing import Any, Dict, List

from ucw.server.logger import get_logger
from ucw.server.protocol import text_content, tool_result_content

log = get_logger("tools.temporal")

_db = None


def set_db(db):
    """Called by server to inject shared database instance."""
    global _db
    _db = db


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "topic_evolution",
        "description": (
            "Track how topics evolve over time. "
            "Shows daily topic frequency grouped by day."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "number",
                    "description": "Number of days to look back (default: 30)",
                    "default": 30,
                },
            },
        },
    },
    {
        "name": "skill_trajectory",
        "description": (
            "Track coherence progression for a specific topic over time. "
            "Shows how understanding deepens day by day."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic to track",
                },
                "days": {
                    "type": "number",
                    "description": "Number of days to look back (default: 30)",
                    "default": 30,
                },
            },
            "required": ["topic"],
        },
    },
    {
        "name": "temporal_insights",
        "description": (
            "Combined temporal analysis: knowledge decay detection, "
            "activity heatmap, and overall temporal stats"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "number",
                    "description": "Number of days to analyze (default: 30)",
                    "default": 30,
                },
            },
        },
    },
]


async def handle_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    handlers = {
        "topic_evolution": _topic_evolution,
        "skill_trajectory": _skill_trajectory,
        "temporal_insights": _temporal_insights,
    }

    handler = handlers.get(name)
    if not handler:
        return tool_result_content(
            [text_content(f"Unknown temporal tool: {name}")], is_error=True
        )

    try:
        return await handler(args)
    except Exception as exc:
        log.error(f"Tool {name} failed: {exc}", exc_info=True)
        return tool_result_content(
            [text_content(f"Error in {name}: {exc}")], is_error=True
        )


async def _topic_evolution(args: Dict) -> Dict:
    if not _db:
        return tool_result_content(
            [text_content("Database not initialized. The UCW server may still be starting up — try again in a moment, or run `ucw doctor` to diagnose.")], is_error=True
        )

    conn = _db._conn
    if not conn:
        return tool_result_content(
            [text_content("Database not initialized. The UCW server may still be starting up — try again in a moment, or run `ucw doctor` to diagnose.")], is_error=True
        )

    days = int(args.get("days", 30))

    from ucw.intelligence.temporal import TemporalAnalyzer

    analyzer = TemporalAnalyzer(conn)
    evolution = analyzer.topic_evolution(days=days)

    if not evolution:
        return tool_result_content(
            [text_content(f"No topic data found in the last {days} days.")]
        )

    output = f"# Topic Evolution (last {days} days)\n\n"

    current_day = None
    for entry in evolution:
        if entry["day"] != current_day:
            current_day = entry["day"]
            output += f"## {current_day}\n"
        output += f"- **{entry['topic']}**: {entry['count']} events\n"

    return tool_result_content([text_content(output)])


async def _skill_trajectory(args: Dict) -> Dict:
    if not _db:
        return tool_result_content(
            [text_content("Database not initialized. The UCW server may still be starting up — try again in a moment, or run `ucw doctor` to diagnose.")], is_error=True
        )

    conn = _db._conn
    if not conn:
        return tool_result_content(
            [text_content("Database not initialized. The UCW server may still be starting up — try again in a moment, or run `ucw doctor` to diagnose.")], is_error=True
        )

    topic = args.get("topic", "").strip()
    if not topic:
        return tool_result_content(
            [text_content("Error: 'topic' is required.")], is_error=True
        )

    days = int(args.get("days", 30))

    from ucw.intelligence.temporal import TemporalAnalyzer

    analyzer = TemporalAnalyzer(conn)
    result = analyzer.skill_trajectory(topic=topic, days=days)

    trajectory = result.get("trajectory", [])
    if not trajectory:
        return tool_result_content(
            [text_content(f"No coherence data found for topic '{topic}' in the last {days} days.")]
        )

    output = f"# Skill Trajectory: {topic}\n\n"
    output += f"**Period:** last {days} days\n"
    output += f"**Data Points:** {len(trajectory)}\n\n"

    output += "| Day | Avg Coherence | Events |\n"
    output += "|-----|--------------|--------|\n"
    for point in trajectory:
        output += f"| {point['day']} | {point['avg_coherence']:.3f} | {point['event_count']} |\n"

    if len(trajectory) >= 2:
        first_coh = trajectory[0]["avg_coherence"]
        last_coh = trajectory[-1]["avg_coherence"]
        diff = last_coh - first_coh
        trend = "improving" if diff > 0.05 else "declining" if diff < -0.05 else "stable"
        output += f"\n**Trend:** {trend} ({diff:+.3f})\n"

    return tool_result_content([text_content(output)])


async def _temporal_insights(args: Dict) -> Dict:
    if not _db:
        return tool_result_content(
            [text_content("Database not initialized. The UCW server may still be starting up — try again in a moment, or run `ucw doctor` to diagnose.")], is_error=True
        )

    conn = _db._conn
    if not conn:
        return tool_result_content(
            [text_content("Database not initialized. The UCW server may still be starting up — try again in a moment, or run `ucw doctor` to diagnose.")], is_error=True
        )

    days = int(args.get("days", 30))

    from ucw.intelligence.temporal import TemporalAnalyzer

    analyzer = TemporalAnalyzer(conn)

    stats = analyzer.get_temporal_stats()
    heatmap = analyzer.activity_heatmap(days=days)
    decay = analyzer.knowledge_decay(days=days)

    output = "# Temporal Insights\n\n"

    # Stats
    output += "## Overview\n\n"
    output += f"**Date Range:** {stats.get('first_day', 'N/A')} to {stats.get('last_day', 'N/A')}\n"
    output += f"**Total Events:** {stats.get('total_events', 0)}\n"
    output += f"**Span:** {stats.get('span_days', 0)} days\n"
    output += f"**Avg Events/Day:** {stats.get('avg_events_per_day', 0)}\n"
    if stats.get("busiest_day"):
        output += f"**Busiest Day:** {stats['busiest_day']} ({stats.get('busiest_count', 0)} events)\n"
    output += "\n"

    # Heatmap
    hours = heatmap.get("hours", {})
    if hours:
        output += "## Activity Heatmap (by hour)\n\n"
        for hour in sorted(hours.keys()):
            count = hours[hour]
            bar = "#" * min(count, 50)
            output += f"`{hour}:00` {bar} ({count})\n"
        output += "\n"

    # Decay
    if decay:
        output += f"## Knowledge Decay ({len(decay)} topics fading)\n\n"
        for d in decay[:10]:
            output += (
                f"- **{d['topic']}**: last seen {d['last_seen']}, "
                f"{d['days_inactive']} days inactive (peak: {d['peak_count']} events)\n"
            )
        output += "\n"

    if not hours and not decay and stats.get("total_events", 0) == 0:
        output += "*No temporal data available yet. Start capturing events to see insights.*\n"

    return tool_result_content([text_content(output)])
