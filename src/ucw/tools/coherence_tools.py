"""
Coherence Tools — MCP tools for querying cognitive coherence

Tools:
  coherence_status     — Quick stats: events, sessions, signals
  coherence_moments    — List high-coherence events
  coherence_search     — Semantic similarity search across events
  coherence_scan       — Scan for emergence patterns
"""

import json
from collections import Counter
from typing import Any, Dict, List

from ucw.server.protocol import tool_result_content, text_content
from ucw.server.logger import get_logger

log = get_logger("tools.coherence")

_db = None


def set_db(db):
    """Called by server to inject shared database instance."""
    global _db
    _db = db
    log.info("Coherence tools: DB injected")


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "coherence_status",
        "description": (
            "Get UCW Coherence Engine status: total events, session count, "
            "topic distribution, and gut signal breakdown."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "coherence_moments",
        "description": (
            "List high-coherence events with emergence indicators. "
            "Shows breakthrough potential, meta-cognitive events, and concept clusters."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_coherence": {
                    "type": "number",
                    "description": "Minimum coherence potential threshold 0-1 (default: 0.5)",
                    "default": 0.5,
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum events to return (default: 20)",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "coherence_search",
        "description": (
            "Semantic similarity search across captured events using embeddings. "
            "Finds events similar to a natural language query."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum results to return (default: 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "coherence_scan",
        "description": (
            "Scan recent events for coherence patterns and emergence signals. "
            "Returns a summary of detected patterns."
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
        "coherence_status": _coherence_status,
        "coherence_moments": _coherence_moments,
        "coherence_search": _coherence_search,
        "coherence_scan": _coherence_scan,
    }

    handler = handlers.get(name)
    if not handler:
        return tool_result_content(
            [text_content(f"Unknown coherence tool: {name}")], is_error=True
        )

    try:
        return await handler(args)
    except Exception as exc:
        log.error(f"Tool {name} failed: {exc}", exc_info=True)
        return tool_result_content(
            [text_content(f"Error in {name}: {exc}")], is_error=True
        )


async def _coherence_status(args: Dict) -> Dict:
    if not _db:
        return tool_result_content(
            [text_content("Database not initialized.")], is_error=True
        )

    all_stats = await _db.get_all_stats()
    session_stats = await _db.get_session_stats()

    out = "# UCW Coherence Status\n\n"
    out += f"| Metric | Value |\n|--------|-------|\n"
    out += f"| Total Events | {all_stats.get('total_events', 0):,} |\n"
    out += f"| Total Sessions | {all_stats.get('total_sessions', 0)} |\n"
    out += f"| Bytes Captured | {all_stats.get('total_bytes_captured', 0):,} |\n"
    out += f"| Current Session | {all_stats.get('current_session', '-')} |\n\n"

    signals = all_stats.get("gut_signals", {})
    if signals:
        out += "## Gut Signal Distribution\n\n"
        for signal, count in signals.items():
            out += f"- **{signal}**: {count}\n"

    if session_stats:
        topics = session_stats.get("topics", {})
        if topics:
            out += "\n## Current Session Topics\n\n"
            for topic, count in topics.items():
                out += f"- {topic}: {count}\n"

    return tool_result_content([text_content(out)])


async def _coherence_moments(args: Dict) -> Dict:
    if not _db:
        return tool_result_content(
            [text_content("Database not initialized.")], is_error=True
        )

    min_coherence = float(args.get("min_coherence", 0.5))
    limit = int(args.get("limit", 20))

    conn = _db._conn
    if not conn:
        return tool_result_content(
            [text_content("Database not initialized.")], is_error=True
        )

    cur = conn.execute(
        """SELECT event_id, timestamp_ns, method, platform,
                  light_topic, light_intent, light_summary,
                  instinct_coherence, instinct_indicators, instinct_gut_signal
           FROM cognitive_events
           WHERE instinct_coherence >= ?
           ORDER BY instinct_coherence DESC
           LIMIT ?""",
        (min_coherence, limit),
    )
    rows = cur.fetchall()

    if not rows:
        return tool_result_content([text_content(
            f"No events found above {min_coherence:.0%} coherence."
        )])

    out = f"# High Coherence Events ({len(rows)} shown)\n\n"

    for row in rows:
        (event_id, ts, method, platform, topic, intent,
         summary, coherence, indicators_json, gut) = row
        indicators = _parse_json_list(indicators_json)

        out += f"**{coherence:.3f}** [{platform}] {method or 'response'}\n"
        out += f"  Topic: {topic} | Intent: {intent} | Gut: {gut}\n"
        if indicators:
            out += f"  Emergence: {indicators}\n"
        out += f"  > {(summary or '')[:200]}\n\n"

    return tool_result_content([text_content(out)])


async def _coherence_search(args: Dict) -> Dict:
    if not _db:
        return tool_result_content(
            [text_content("Database not initialized.")], is_error=True
        )

    query = args.get("query", "")
    limit = int(args.get("limit", 10))

    if not query:
        return tool_result_content(
            [text_content("Query is required.")], is_error=True
        )

    try:
        from ucw.server.embeddings import embed_single, cosine_similarity, build_embed_text
    except ImportError as exc:
        return tool_result_content(
            [text_content(f"Embeddings not available: {exc}")], is_error=True
        )

    query_emb = embed_single(query)

    conn = _db._conn
    if not conn:
        return tool_result_content(
            [text_content("Database not initialized.")], is_error=True
        )

    cur = conn.execute(
        """SELECT event_id, platform, light_topic, light_intent,
                  light_summary, data_content, light_concepts,
                  instinct_gut_signal, instinct_coherence
           FROM cognitive_events
           WHERE data_content IS NOT NULL AND length(data_content) > 10
           ORDER BY timestamp_ns DESC LIMIT 5000"""
    )
    rows = cur.fetchall()

    results = []
    for row in rows:
        (event_id, platform, topic, intent, summary,
         content, concepts_json, gut, coherence) = row

        light = {"intent": intent or "explore", "topic": topic or "general",
                 "summary": summary or "", "concepts": _parse_json_list(concepts_json)}
        data = {"content": content or ""}
        text = build_embed_text({"light_layer": light, "data_layer": data})
        if not text or len(text) < 10:
            continue

        event_emb = embed_single(text)
        sim = cosine_similarity(query_emb, event_emb)
        if sim >= 0.3:
            results.append({
                "event_id": event_id,
                "platform": platform,
                "topic": topic,
                "intent": intent,
                "summary": (summary or "")[:200],
                "gut": gut,
                "similarity": round(sim, 4),
            })

    results.sort(key=lambda r: r["similarity"], reverse=True)
    results = results[:limit]

    if not results:
        return tool_result_content([text_content(
            f"No similar events found for: '{query}'"
        )])

    out = f"# Semantic Search: '{query}'\n\n"
    out += f"**Results:** {len(results)}\n\n"

    for r in results:
        out += f"**{r['similarity']:.0%}** [{r['platform']}] topic=`{r['topic']}` intent=`{r['intent']}` gut={r['gut']}\n"
        out += f"> {r['summary']}\n\n"

    return tool_result_content([text_content(out)])


async def _coherence_scan(args: Dict) -> Dict:
    if not _db:
        return tool_result_content(
            [text_content("Database not initialized.")], is_error=True
        )

    limit = int(args.get("limit", 200))

    conn = _db._conn
    if not conn:
        return tool_result_content(
            [text_content("Database not initialized.")], is_error=True
        )

    cur = conn.execute(
        """SELECT light_topic, light_intent, instinct_gut_signal,
                  instinct_coherence, instinct_indicators
           FROM cognitive_events
           ORDER BY timestamp_ns DESC LIMIT ?""",
        (limit,),
    )
    rows = cur.fetchall()

    if not rows:
        return tool_result_content([text_content("No events to scan.")])

    topic_counts = Counter()
    intent_counts = Counter()
    signal_counts = Counter()
    high_coherence = 0
    breakthroughs = 0
    meta_events = 0

    for row in rows:
        topic, intent, gut, coherence, indicators_json = row
        indicators = _parse_json_list(indicators_json)

        if topic:
            topic_counts[topic] += 1
        if intent:
            intent_counts[intent] += 1
        if gut:
            signal_counts[gut] += 1
        if coherence and coherence > 0.7:
            high_coherence += 1
        if gut == "breakthrough_potential":
            breakthroughs += 1
        if "meta_cognitive" in indicators:
            meta_events += 1

    out = f"# Coherence Scan ({len(rows)} events)\n\n"
    out += f"| Metric | Count |\n|--------|-------|\n"
    out += f"| High coherence (>0.7) | {high_coherence} |\n"
    out += f"| Breakthrough potential | {breakthroughs} |\n"
    out += f"| Meta-cognitive events | {meta_events} |\n\n"

    out += "## Topic Distribution\n\n"
    for topic, count in topic_counts.most_common(10):
        out += f"- {topic}: {count}\n"

    out += "\n## Intent Distribution\n\n"
    for intent, count in intent_counts.most_common(10):
        out += f"- {intent}: {count}\n"

    out += "\n## Gut Signals\n\n"
    for signal, count in signal_counts.most_common():
        out += f"- {signal}: {count}\n"

    return tool_result_content([text_content(out)])


def _parse_json_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []
