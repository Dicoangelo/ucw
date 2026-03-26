"""
Agent Tools — MCP tools for agent learning integration.

Tools:
  store_learning    — Store a learning/insight for future retrieval
  search_learnings  — Search stored agent learnings
  get_context       — Get relevant context for a query from learnings + recent events
"""

from typing import Any, Dict, List

from ucw.server.logger import get_logger
from ucw.server.protocol import text_content, tool_result_content

log = get_logger("tools.agent")

_db = None


def set_db(db):
    """Called by server to inject shared database instance."""
    global _db
    _db = db


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "store_learning",
        "description": (
            "Store a learning or insight for future retrieval. "
            "Agents can write back knowledge discovered during sessions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The learning text to store",
                },
                "project": {
                    "type": "string",
                    "description": "Project this learning relates to",
                },
                "tags": {
                    "type": "string",
                    "description": "Comma-separated tags for categorization",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence level 0.0-1.0 (default: 0.5)",
                    "default": 0.5,
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "search_learnings",
        "description": "Search stored agent learnings by query, project, or topic",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for in learnings",
                },
                "project": {
                    "type": "string",
                    "description": "Filter by project name",
                },
                "topic": {
                    "type": "string",
                    "description": "Filter by topic",
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
        "name": "get_context",
        "description": (
            "Get relevant context for a query from stored learnings "
            "and recent cognitive events"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query to find context for",
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum context items to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
]


async def handle_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    handlers = {
        "store_learning": _store_learning,
        "search_learnings": _search_learnings,
        "get_context": _get_context,
    }

    handler = handlers.get(name)
    if not handler:
        return tool_result_content(
            [text_content(f"Unknown agent tool: {name}")], is_error=True
        )

    try:
        return await handler(args)
    except Exception as exc:
        log.error(f"Tool {name} failed: {exc}", exc_info=True)
        return tool_result_content(
            [text_content(f"Error in {name}: {exc}")], is_error=True
        )


async def _store_learning(args: Dict) -> Dict:
    if not _db:
        return tool_result_content(
            [text_content(
                "Database not initialized. The UCW server may still be "
                "starting up — try again in a moment, or run "
                "`ucw doctor` to diagnose."
            )], is_error=True
        )

    conn = _db._conn
    if not conn:
        return tool_result_content(
            [text_content(
                "Database not initialized. The UCW server may still be "
                "starting up — try again in a moment, or run "
                "`ucw doctor` to diagnose."
            )], is_error=True
        )

    text_val = args.get("text", "").strip()
    if not text_val:
        return tool_result_content(
            [text_content("Error: 'text' is required.")], is_error=True
        )

    from ucw.intelligence.agent_memory import AgentMemory

    memory = AgentMemory(conn)

    tags_str = args.get("tags")
    tags = [t.strip() for t in tags_str.split(",")] if tags_str else None

    learning_id = memory.store_learning(
        text=text_val,
        project=args.get("project"),
        tags=tags,
        confidence=float(args.get("confidence", 0.5)),
        source_session=_db.session_id,
    )

    output = "# Learning Stored\n\n"
    output += f"**ID:** {learning_id}\n"
    output += f"**Text:** {text_val[:200]}\n"
    if args.get("project"):
        output += f"**Project:** {args['project']}\n"
    if tags:
        output += f"**Tags:** {', '.join(tags)}\n"
    output += f"**Confidence:** {args.get('confidence', 0.5)}\n"

    return tool_result_content([text_content(output)])


async def _search_learnings(args: Dict) -> Dict:
    if not _db:
        return tool_result_content(
            [text_content(
                "Database not initialized. The UCW server may still be "
                "starting up — try again in a moment, or run "
                "`ucw doctor` to diagnose."
            )], is_error=True
        )

    conn = _db._conn
    if not conn:
        return tool_result_content(
            [text_content(
                "Database not initialized. The UCW server may still be "
                "starting up — try again in a moment, or run "
                "`ucw doctor` to diagnose."
            )], is_error=True
        )

    from ucw.intelligence.agent_memory import AgentMemory

    memory = AgentMemory(conn)
    results = memory.search_learnings(
        query=args.get("query"),
        project=args.get("project"),
        topic=args.get("topic"),
        limit=int(args.get("limit", 20)),
    )

    if not results:
        return tool_result_content([text_content("No learnings found matching criteria.")])

    output = f"# Agent Learnings ({len(results)} results)\n\n"
    for r in results:
        output += f"**{r['learning_id']}** (confidence: {r['confidence']:.2f})\n"
        output += f"  {r['text'][:200]}\n"
        if r.get("project"):
            output += f"  Project: {r['project']}\n"
        if r.get("topic"):
            output += f"  Topic: {r['topic']}\n"
        output += "\n"

    return tool_result_content([text_content(output)])


async def _get_context(args: Dict) -> Dict:
    if not _db:
        return tool_result_content(
            [text_content(
                "Database not initialized. The UCW server may still be "
                "starting up — try again in a moment, or run "
                "`ucw doctor` to diagnose."
            )], is_error=True
        )

    conn = _db._conn
    if not conn:
        return tool_result_content(
            [text_content(
                "Database not initialized. The UCW server may still be "
                "starting up — try again in a moment, or run "
                "`ucw doctor` to diagnose."
            )], is_error=True
        )

    query = args.get("query", "").strip()
    if not query:
        return tool_result_content(
            [text_content("Error: 'query' is required.")], is_error=True
        )

    limit = int(args.get("limit", 5))

    from ucw.intelligence.agent_memory import AgentMemory

    memory = AgentMemory(conn)
    learnings = memory.get_context_for_query(query, limit=limit)

    # Also pull recent events matching the query
    cur = conn.execute(
        """SELECT event_id, light_topic, light_summary, instinct_coherence
           FROM cognitive_events
           WHERE light_summary LIKE ? OR light_topic LIKE ?
           ORDER BY timestamp_ns DESC LIMIT ?""",
        (f"%{query}%", f"%{query}%", limit),
    )
    events = cur.fetchall()

    output = f"# Context for: {query}\n\n"

    if learnings:
        output += f"## Learnings ({len(learnings)})\n\n"
        for r in learnings:
            output += f"- **{r['learning_id']}** (conf: {r['confidence']:.2f}): {r['text'][:150]}\n"
        output += "\n"

    if events:
        output += f"## Recent Events ({len(events)})\n\n"
        for e in events:
            event_id, topic, summary, coherence = e
            coh_str = f" [coherence={coherence:.2f}]" if coherence else ""
            output += f"- **{event_id}**: {topic}{coh_str} — {(summary or '')[:120]}\n"
        output += "\n"

    if not learnings and not events:
        output += "No relevant context found.\n"

    return tool_result_content([text_content(output)])
