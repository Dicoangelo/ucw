"""
Graph Tools — MCP tools for querying and analyzing the knowledge graph

Tools:
  knowledge_graph  — Query the knowledge graph: search entities, get relationships, view stats
  graph_analyze    — Analyze entity clusters and relationship patterns
"""

from typing import Any, Dict, List

from ucw.intelligence.graph_store import GraphStore
from ucw.server.logger import get_logger
from ucw.server.protocol import text_content, tool_result_content

log = get_logger("tools.graph")

_db = None


def set_db(db):
    """Called by server to inject shared database instance."""
    global _db
    _db = db


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "knowledge_graph",
        "description": (
            "Query the UCW knowledge graph: search entities, "
            "get relationships, or view graph statistics"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for entity names (used with 'search' action)",
                },
                "entity_type": {
                    "type": "string",
                    "description": (
                        "Filter by entity type: person, organization, "
                        "technology, concept, project, tool, platform"
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": ["search", "relationships", "stats"],
                    "description": "Action to perform (default: search)",
                    "default": "search",
                },
            },
        },
    },
    {
        "name": "graph_analyze",
        "description": (
            "Analyze entity clusters and relationship patterns "
            "in the knowledge graph"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Entity name to analyze connections for",
                },
                "depth": {
                    "type": "number",
                    "description": "Depth of relationship traversal (default: 1)",
                    "default": 1,
                },
            },
        },
    },
]


async def handle_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    handlers = {
        "knowledge_graph": _knowledge_graph,
        "graph_analyze": _graph_analyze,
    }

    handler = handlers.get(name)
    if not handler:
        return tool_result_content(
            [text_content(f"Unknown graph tool: {name}")], is_error=True
        )

    try:
        return await handler(args)
    except Exception as exc:
        log.error(f"Tool {name} failed: {exc}", exc_info=True)
        return tool_result_content(
            [text_content(f"Error in {name}: {exc}")], is_error=True
        )


async def _knowledge_graph(args: Dict) -> Dict:
    if not _db or not _db._conn:
        return tool_result_content(
            [text_content(
                "Database not initialized. The UCW server may still be "
                "starting up — try again in a moment, or run "
                "`ucw doctor` to diagnose."
            )], is_error=True
        )

    store = GraphStore(_db._conn)
    action = args.get("action", "search")

    if action == "stats":
        return _format_stats(store)

    if action == "relationships":
        query = args.get("query", "")
        if not query:
            return tool_result_content(
                [text_content("Please provide a query (entity name) to get relationships.")]
            )
        return _format_relationships(store, query)

    # Default: search
    query = args.get("query", "")
    entity_type = args.get("entity_type")

    if not query:
        return _format_stats(store)

    entities = store.search_entities(query, type_filter=entity_type)

    if not entities:
        output = f"No entities found matching '{query}'"
        if entity_type:
            output += f" (type: {entity_type})"
        return tool_result_content([text_content(output)])

    output = f"# Knowledge Graph Search: '{query}'\n\n"
    output += f"**Found {len(entities)} entities**\n\n"

    for e in entities:
        output += (
            f"- **{e['name']}** ({e['type']}) "
            f"confidence={e['confidence']:.2f} "
            f"events={e['event_count']}\n"
        )

    return tool_result_content([text_content(output)])


async def _graph_analyze(args: Dict) -> Dict:
    if not _db or not _db._conn:
        return tool_result_content(
            [text_content(
                "Database not initialized. The UCW server may still be "
                "starting up — try again in a moment, or run "
                "`ucw doctor` to diagnose."
            )], is_error=True
        )

    store = GraphStore(_db._conn)
    entity_name = args.get("entity_name")
    depth = int(args.get("depth", 1))

    if not entity_name:
        # Show top entities and their connection counts
        stats = store.get_graph_stats()
        output = "# Knowledge Graph Analysis\n\n"
        output += f"**Entities:** {stats['entity_count']}\n"
        output += f"**Relationships:** {stats['relationship_count']}\n\n"

        if stats["top_entities"]:
            output += "## Most Connected Entities\n\n"
            for e in stats["top_entities"]:
                output += f"- **{e['name']}** ({e['event_count']} events)\n"

        if stats["entity_types"]:
            output += "\n## Entity Type Distribution\n\n"
            for t, count in stats["entity_types"].items():
                output += f"- {t}: {count}\n"

        return tool_result_content([text_content(output)])

    # Analyze specific entity
    entity = store.get_entity(entity_name)
    if not entity:
        return tool_result_content(
            [text_content(f"Entity '{entity_name}' not found in knowledge graph.")]
        )

    output = f"# Entity Analysis: {entity['name']}\n\n"
    output += f"**Type:** {entity['type']}\n"
    output += f"**Confidence:** {entity['confidence']:.2f}\n"
    output += f"**Event Count:** {entity['event_count']}\n\n"

    # Get direct relationships
    rels = store.get_relationships(entity["entity_id"], limit=50)
    if rels:
        output += f"## Relationships ({len(rels)})\n\n"
        for r in rels:
            other_name = (
                r["target_name"]
                if r["source_entity_id"] == entity["entity_id"]
                else r["source_name"]
            )
            output += (
                f"- **{other_name}** ({r['type']}) "
                f"weight={r['weight']:.2f} "
                f"occurrences={r['occurrence_count']}\n"
            )

        # If depth > 1, gather second-hop entities
        if depth > 1:
            second_hop_entities = set()
            for r in rels:
                other_id = (
                    r["target_entity_id"]
                    if r["source_entity_id"] == entity["entity_id"]
                    else r["source_entity_id"]
                )
                second_rels = store.get_relationships(other_id, limit=10)
                for sr in second_rels:
                    for name_key in ("source_name", "target_name"):
                        n = sr.get(name_key)
                        if n and n.lower() != entity_name.lower():
                            second_hop_entities.add(n)

            if second_hop_entities:
                output += f"\n## Second-Hop Entities ({len(second_hop_entities)})\n\n"
                for name in sorted(second_hop_entities)[:20]:
                    output += f"- {name}\n"
    else:
        output += "*No relationships found for this entity.*\n"

    return tool_result_content([text_content(output)])


def _format_stats(store: GraphStore) -> Dict:
    stats = store.get_graph_stats()
    output = "# Knowledge Graph Statistics\n\n"
    output += f"**Total Entities:** {stats['entity_count']}\n"
    output += f"**Total Relationships:** {stats['relationship_count']}\n\n"

    if stats["entity_types"]:
        output += "## Entity Types\n\n"
        for t, count in stats["entity_types"].items():
            output += f"- {t}: {count}\n"
        output += "\n"

    if stats["relationship_types"]:
        output += "## Relationship Types\n\n"
        for t, count in stats["relationship_types"].items():
            output += f"- {t}: {count}\n"
        output += "\n"

    if stats["top_entities"]:
        output += "## Top Entities\n\n"
        for e in stats["top_entities"]:
            output += f"- **{e['name']}** ({e['event_count']} events)\n"

    return tool_result_content([text_content(output)])


def _format_relationships(store: GraphStore, name: str) -> Dict:
    entity = store.get_entity(name)
    if not entity:
        return tool_result_content(
            [text_content(f"Entity '{name}' not found.")]
        )

    rels = store.get_relationships(entity["entity_id"])
    if not rels:
        return tool_result_content(
            [text_content(f"No relationships found for '{name}'.")]
        )

    output = f"# Relationships for: {entity['name']}\n\n"
    for r in rels:
        other_name = (
            r["target_name"]
            if r["source_entity_id"] == entity["entity_id"]
            else r["source_name"]
        )
        output += (
            f"- **{other_name}** ({r['type']}) "
            f"weight={r['weight']:.2f} "
            f"occurrences={r['occurrence_count']}\n"
        )

    return tool_result_content([text_content(output)])
