"""Tests for MCP Router — method dispatch."""

import pytest

from ucw.server.protocol import ProtocolError
from ucw.server.router import Router


class TestRouter:
    @pytest.fixture
    def router(self):
        r = Router()
        return r

    @pytest.fixture
    def router_with_tools(self):
        r = Router()

        async def handler(name, args):
            return {"content": [{"type": "text", "text": f"called {name}"}]}

        r.register_tools_module(
            [{"name": "test_tool", "description": "test", "inputSchema": {}}],
            handler,
        )
        return r

    @pytest.mark.asyncio
    async def test_initialize(self, router):
        result = await router.route("request", {
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        })
        assert result["serverInfo"]["name"] == "ucw"
        assert "protocolVersion" in result

    @pytest.mark.asyncio
    async def test_initialized_notification(self, router):
        result = await router.route("notification", {
            "method": "initialized",
        })
        assert result is None

    @pytest.mark.asyncio
    async def test_ping(self, router):
        result = await router.route("request", {"method": "ping"})
        assert result == {}

    @pytest.mark.asyncio
    async def test_tools_list(self, router_with_tools):
        result = await router_with_tools.route(
            "request", {"method": "tools/list"},
        )
        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "test_tool"

    @pytest.mark.asyncio
    async def test_tools_call(self, router_with_tools):
        result = await router_with_tools.route("request", {
            "method": "tools/call",
            "params": {"name": "test_tool", "arguments": {}},
        })
        assert result["content"][0]["text"] == "called test_tool"

    @pytest.mark.asyncio
    async def test_tools_call_missing_name(self, router_with_tools):
        with pytest.raises(ProtocolError) as exc_info:
            await router_with_tools.route("request", {
                "method": "tools/call",
                "params": {"arguments": {}},
            })
        assert "Missing tool name" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_tools_call_unknown_tool(self, router_with_tools):
        with pytest.raises(ProtocolError) as exc_info:
            await router_with_tools.route("request", {
                "method": "tools/call",
                "params": {"name": "no_such_tool", "arguments": {}},
            })
        assert "Unknown tool" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unknown_method(self, router):
        with pytest.raises(ProtocolError) as exc_info:
            await router.route("request", {"method": "foo/bar"})
        assert "Unknown method" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resources_list_empty(self, router):
        result = await router.route(
            "request", {"method": "resources/list"},
        )
        assert result == {"resources": []}

    @pytest.mark.asyncio
    async def test_resources_read_missing_uri(self, router):
        with pytest.raises(ProtocolError):
            await router.route("request", {
                "method": "resources/read",
                "params": {},
            })

    def test_tool_count(self, router_with_tools):
        assert router_with_tools.tool_count == 1

    def test_resource_count(self, router):
        assert router.resource_count == 0

    @pytest.mark.asyncio
    async def test_tool_handler_error_returns_error_content(self):
        r = Router()

        async def bad_handler(name, args):
            raise ValueError("boom")

        r.register_tools_module(
            [{"name": "boom_tool", "description": "x", "inputSchema": {}}],
            bad_handler,
        )
        result = await r.route("request", {
            "method": "tools/call",
            "params": {"name": "boom_tool", "arguments": {}},
        })
        assert result["isError"] is True
        assert "boom" in result["content"][0]["text"]
