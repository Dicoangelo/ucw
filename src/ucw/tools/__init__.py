"""
UCW MCP Tools

Modules:
  ucw_tools        — 3 UCW-specific capture/emergence tools
  coherence_tools  — 4 cross-platform coherence query tools
"""

from ucw.tools import ucw_tools
from ucw.tools import coherence_tools

ALL_TOOLS = ucw_tools.TOOLS + coherence_tools.TOOLS

_DISPATCH = {}
for tool_def in ucw_tools.TOOLS:
    _DISPATCH[tool_def["name"]] = ucw_tools.handle_tool
for tool_def in coherence_tools.TOOLS:
    _DISPATCH[tool_def["name"]] = coherence_tools.handle_tool


async def handle_tool(name: str, args: dict) -> dict:
    """Unified dispatcher across all tool modules."""
    handler = _DISPATCH.get(name)
    if handler:
        return await handler(name, args)
    from ucw.server.protocol import tool_result_content, text_content
    return tool_result_content([text_content(f"Unknown tool: {name}")], is_error=True)
