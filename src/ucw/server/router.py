"""
Method Router — Dispatch MCP methods to handlers

Routes:
  initialize       -> server capabilities handshake
  initialized      -> notification (no response)
  tools/list       -> registered tool definitions
  tools/call       -> tool handler dispatch
  resources/list   -> registered resource definitions
  resources/read   -> resource handler dispatch
  ping             -> pong
"""

from typing import Any, Callable, Awaitable, Dict, List, Optional

from ucw.config import Config
from ucw.server.logger import get_logger
from ucw.server.protocol import (
    initialize_result,
    tools_list_result,
    tool_result_content,
    text_content,
    resources_list_result,
    resource_read_result,
    ProtocolError,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)

log = get_logger("router")


class Router:
    """MCP method dispatcher."""

    def __init__(self):
        self._tools: List[Dict[str, Any]] = []
        self._tool_handlers: List = []
        self._resources: List[Dict[str, Any]] = []
        self._resource_handlers: List[Callable] = []
        self._initialized = False

    def register_tools_module(self, tools_list: List[Dict], handler: Callable):
        """Register a tools module."""
        self._tools.extend(tools_list)
        self._tool_handlers.append((
            {t["name"] for t in tools_list},
            handler,
        ))
        log.info(f"Registered {len(tools_list)} tools: {[t['name'] for t in tools_list]}")

    def register_resources(self, resources: List[Dict], handler: Callable):
        """Register a resources provider."""
        self._resources.extend(resources)
        self._resource_handlers.append(handler)
        log.info(f"Registered {len(resources)} resources")

    async def route(self, msg_type: str, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Route a validated message to the appropriate handler.
        Returns the result payload or None for notifications.
        """
        method = msg.get("method", "")
        params = msg.get("params", {})

        if method == "initialize":
            return self._handle_initialize(params)

        if method in ("initialized", "notifications/initialized"):
            self._initialized = True
            return None

        if method == "notifications/cancelled":
            return None

        if method == "ping":
            return {}

        if method == "tools/list":
            return self._handle_tools_list()

        if method == "tools/call":
            return await self._handle_tools_call(params)

        if method == "resources/list":
            return self._handle_resources_list()

        if method == "resources/read":
            return await self._handle_resources_read(params)

        raise ProtocolError(METHOD_NOT_FOUND, f"Unknown method: {method}")

    def _handle_initialize(self, params: Dict) -> Dict[str, Any]:
        log.info(
            f"Client initialize: {params.get('clientInfo', {}).get('name', '?')} "
            f"protocol={params.get('protocolVersion', '?')}"
        )
        return initialize_result(
            server_name=Config.SERVER_NAME,
            server_version=Config.SERVER_VERSION,
            protocol_version=Config.PROTOCOL_VERSION,
        )

    def _handle_tools_list(self) -> Dict[str, Any]:
        return tools_list_result(self._tools)

    async def _handle_tools_call(self, params: Dict) -> Dict[str, Any]:
        name = params.get("name", "")
        args = params.get("arguments", {})

        if not name:
            raise ProtocolError(INVALID_PARAMS, "Missing tool name")

        for tool_names, handler in self._tool_handlers:
            if name in tool_names:
                try:
                    result = await handler(name, args)
                    return result
                except Exception as exc:
                    log.error(f"Tool {name} error: {exc}")
                    return tool_result_content(
                        [text_content(f"Tool error: {exc}")],
                        is_error=True,
                    )

        raise ProtocolError(METHOD_NOT_FOUND, f"Unknown tool: {name}")

    def _handle_resources_list(self) -> Dict[str, Any]:
        return resources_list_result(self._resources)

    async def _handle_resources_read(self, params: Dict) -> Dict[str, Any]:
        uri = params.get("uri", "")
        if not uri:
            raise ProtocolError(INVALID_PARAMS, "Missing resource URI")

        for handler in self._resource_handlers:
            try:
                content = await handler(uri)
                if content is not None:
                    return resource_read_result([{
                        "uri": uri,
                        "mimeType": "text/plain",
                        "text": content,
                    }])
            except Exception as exc:
                log.error(f"Resource {uri} error: {exc}")
                raise ProtocolError(INTERNAL_ERROR, f"Resource error: {exc}")

        raise ProtocolError(INVALID_PARAMS, f"Resource not found: {uri}")

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def resource_count(self) -> int:
        return len(self._resources)
