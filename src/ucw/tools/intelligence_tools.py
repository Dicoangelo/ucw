"""
Intelligence Tools — MCP tools for alerts, thread analysis, and thread linking.

Tools:
  alerts_query      — Query intelligence alerts with filters
  thread_analysis   — Analyze cross-platform conversation threads
  link_threads      — Trigger thread linking on recent events
"""

import json
from typing import Any, Dict, List

from ucw.server.logger import get_logger
from ucw.server.protocol import text_content, tool_result_content

log = get_logger("tools.intelligence")

_db = None


def set_db(db):
    """Called by server to inject shared database instance."""
    global _db
    _db = db
    log.info("Intelligence tools: DB injected")


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "alerts_query",
        "description": (
            "Query intelligence alerts with optional filters by type, severity, "
            "and acknowledgment status. Returns alerts in reverse chronological order."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Filter by alert type (e.g. 'high_coherence', 'emergence')",
                },
                "severity": {
                    "type": "string",
                    "description": "Filter by severity (e.g. 'info', 'warning', 'critical')",
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum alerts to return (default: 20)",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "thread_analysis",
        "description": (
            "Analyze cross-platform conversation threads. "
            "Actions: 'list' (all threads), 'cross_platform' (multi-platform), 'stats' (summary)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "cross_platform", "stats"],
                    "description": "Analysis action to perform (default: 'list')",
                    "default": "list",
                },
                "min_score": {
                    "type": "number",
                    "description": "Minimum combined score threshold (default: 0.3)",
                    "default": 0.3,
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum results to return (default: 20)",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "link_threads",
        "description": (
            "Trigger thread linking on recent captured events. "
            "Scans the last N events and groups them into conversation threads."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "number",
                    "description": "Number of recent events to scan (default: 200)",
                    "default": 200,
                },
            },
        },
    },
]


async def handle_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    handlers = {
        "alerts_query": _alerts_query,
        "thread_analysis": _thread_analysis,
        "link_threads": _link_threads,
    }

    handler = handlers.get(name)
    if not handler:
        return tool_result_content(
            [text_content(f"Unknown intelligence tool: {name}")], is_error=True
        )

    try:
        return await handler(args)
    except Exception as exc:
        log.error(f"Tool {name} failed: {exc}", exc_info=True)
        return tool_result_content(
            [text_content(f"Error in {name}: {exc}")], is_error=True
        )


async def _alerts_query(args: Dict) -> Dict:
    if not _db or not _db._conn:
        return tool_result_content(
            [text_content(
                "Database not initialized. The UCW server may still be "
                "starting up — try again in a moment, or run "
                "`ucw doctor` to diagnose."
            )], is_error=True
        )

    from ucw.intelligence.alerting import AlertEngine

    engine = AlertEngine(_db._conn)

    alert_type = args.get("type")
    severity = args.get("severity")
    limit = int(args.get("limit", 20))

    alerts = engine.get_alerts(type=alert_type, severity=severity, limit=limit)
    stats = engine.get_alert_stats()

    if not alerts:
        out = "# Intelligence Alerts\n\nNo alerts found matching filters.\n\n"
        out += f"**Total alerts in system:** {stats.get('total', 0)}"
        return tool_result_content([text_content(out)])

    out = f"# Intelligence Alerts ({len(alerts)} shown)\n\n"
    out += f"**Total:** {stats.get('total', 0)} | "
    out += f"Acknowledged: {stats.get('acknowledged', 0)} | "
    out += f"Unacknowledged: {stats.get('unacknowledged', 0)}\n\n"

    for a in alerts:
        ack = "yes" if a["acknowledged"] else "no"
        out += f"- **[{a['severity'].upper()}]** `{a['type']}` — {a['message']}\n"
        out += f"  ID: `{a['alert_id']}` | Acknowledged: {ack}\n"
        if a["evidence_event_ids"]:
            out += f"  Evidence: {len(a['evidence_event_ids'])} event(s)\n"
        out += "\n"

    return tool_result_content([text_content(out)])


async def _thread_analysis(args: Dict) -> Dict:
    if not _db or not _db._conn:
        return tool_result_content(
            [text_content(
                "Database not initialized. The UCW server may still be "
                "starting up — try again in a moment, or run "
                "`ucw doctor` to diagnose."
            )], is_error=True
        )

    from ucw.intelligence.thread_linker import ThreadLinker

    linker = ThreadLinker(_db._conn)
    action = args.get("action", "list")
    min_score = float(args.get("min_score", 0.3))
    limit = int(args.get("limit", 20))

    if action == "stats":
        stats = linker.get_thread_stats()
        out = "# Thread Analysis — Statistics\n\n"
        out += "| Metric | Value |\n|--------|-------|\n"
        out += f"| Total Threads | {stats['total_threads']} |\n"
        out += f"| Avg Combined Score | {stats['avg_combined_score']:.4f} |\n"
        out += f"| Avg Entity Overlap | {stats['avg_entity_overlap']:.4f} |\n"
        out += f"| Avg Semantic Score | {stats['avg_semantic_score']:.4f} |\n"
        out += f"| Avg Temporal Score | {stats['avg_temporal_score']:.4f} |\n\n"

        if stats["topic_distribution"]:
            out += "## Topic Distribution\n\n"
            for topic, count in stats["topic_distribution"].items():
                out += f"- {topic}: {count}\n"

        return tool_result_content([text_content(out)])

    elif action == "cross_platform":
        threads = linker.find_cross_platform_threads(min_platforms=2)
        if not threads:
            return tool_result_content([text_content(
                "# Cross-Platform Threads\n\nNo cross-platform threads found."
            )])

        out = f"# Cross-Platform Threads ({len(threads)} found)\n\n"
        for t in threads[:limit]:
            out += f"**Thread:** `{t['thread_id']}` — {t['topic']}\n"
            out += (
                f"  Score: {t['combined_score']:.4f} "
                f"| Platforms: {t.get('platform_count', '?')}\n"
            )
            out += f"  Sessions: {json.dumps(t['platform_sessions'])}\n\n"

        return tool_result_content([text_content(out)])

    else:  # "list"
        threads = linker.get_threads(min_score=min_score, limit=limit)
        if not threads:
            return tool_result_content([text_content(
                f"# Conversation Threads\n\nNo threads found above {min_score:.2f} score."
            )])

        out = f"# Conversation Threads ({len(threads)} shown)\n\n"
        for t in threads:
            out += f"**Thread:** `{t['thread_id']}` — {t['topic']}\n"
            out += (
                f"  Combined: {t['combined_score']:.4f} | "
                f"Entity: {t['entity_overlap_score']:.4f} | "
                f"Semantic: {t['semantic_score']:.4f} | "
                f"Temporal: {t['temporal_score']:.4f}\n"
            )
            out += f"  Sessions: {json.dumps(t['platform_sessions'])}\n\n"

        return tool_result_content([text_content(out)])


async def _link_threads(args: Dict) -> Dict:
    if not _db or not _db._conn:
        return tool_result_content(
            [text_content(
                "Database not initialized. The UCW server may still be "
                "starting up — try again in a moment, or run "
                "`ucw doctor` to diagnose."
            )], is_error=True
        )

    from ucw.intelligence.thread_linker import ThreadLinker

    linker = ThreadLinker(_db._conn)
    limit = int(args.get("limit", 200))

    # Fetch recent events
    cur = _db._conn.execute(
        """SELECT event_id, session_id, timestamp_ns, light_topic, light_intent,
                  light_concepts, light_summary, instinct_coherence,
                  instinct_gut_signal, platform
           FROM cognitive_events
           ORDER BY timestamp_ns DESC LIMIT ?""",
        (limit,),
    )
    rows = cur.fetchall()

    if not rows:
        return tool_result_content([text_content(
            "# Link Threads\n\nNo events found to link."
        )])

    events = [
        {
            "event_id": r[0],
            "session_id": r[1],
            "timestamp_ns": r[2],
            "light_topic": r[3],
            "light_intent": r[4],
            "light_concepts": r[5],
            "light_summary": r[6],
            "instinct_coherence": r[7],
            "instinct_gut_signal": r[8],
            "platform": r[9],
        }
        for r in rows
    ]

    threads = linker.link_events_to_threads(events)

    out = "# Link Threads\n\n"
    out += f"**Scanned:** {len(events)} events\n"
    out += f"**Threads created/updated:** {len(threads)}\n\n"

    for t in threads[:20]:
        out += (
            f"- `{t['thread_id']}` — {t['topic']} "
            f"(score: {t['combined_score']:.4f}, "
            f"events: {t['event_count']})\n"
        )

    return tool_result_content([text_content(out)])
