"""Unit tests for server components (UCWBridgeAdapter, RawMCPServer setup)."""

from ucw.server.capture import CaptureEvent
from ucw.server.server import RawMCPServer, UCWBridgeAdapter


class TestUCWBridgeAdapter:
    def test_enrich_sets_all_layers(self):
        adapter = UCWBridgeAdapter()
        event = CaptureEvent(
            direction="in",
            stage="received",
            raw_bytes=b'{"jsonrpc":"2.0","method":"tools/call",'
                      b'"params":{"name":"search","arguments":{}}}',
            parsed={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "search", "arguments": {}},
            },
            timestamp_ns=1_000_000_000,
        )
        adapter.enrich(event)

        assert event.data_layer is not None
        assert event.light_layer is not None
        assert event.instinct_layer is not None
        assert event.coherence_signature is not None
        assert isinstance(event.coherence_signature, str)
        assert len(event.coherence_signature) == 64  # SHA-256 hex

    def test_enrich_data_layer(self):
        adapter = UCWBridgeAdapter()
        event = CaptureEvent(
            direction="in", stage="received",
            raw_bytes=b'{}',
            parsed={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "ucw_timeline", "arguments": {"limit": 10}},
            },
            timestamp_ns=1_000_000_000,
        )
        adapter.enrich(event)
        assert "Tool call" in event.data_layer["content"]
        assert event.data_layer["tokens_est"] >= 1

    def test_enrich_light_layer_intent(self):
        adapter = UCWBridgeAdapter()
        event = CaptureEvent(
            direction="in", stage="received",
            raw_bytes=b'{}',
            parsed={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "search_events",
                    "arguments": {"query": "find coherence patterns"},
                },
            },
            timestamp_ns=1_000_000_000,
        )
        adapter.enrich(event)
        assert event.light_layer["intent"] in (
            "search", "retrieve", "execute", "analyze", "create", "explore",
        )
        assert event.light_layer["topic"] is not None

    def test_enrich_outbound_error(self):
        adapter = UCWBridgeAdapter()
        event = CaptureEvent(
            direction="out", stage="sent",
            raw_bytes=b'{}',
            parsed={
                "jsonrpc": "2.0", "id": 1,
                "error": {"code": -32601, "message": "Method not found"},
            },
            timestamp_ns=1_000_000_000,
        )
        adapter.enrich(event)
        assert "Error" in event.data_layer["content"]

    def test_enrich_instinct_layer(self):
        adapter = UCWBridgeAdapter()
        # Use UCW-related content to trigger higher coherence
        event = CaptureEvent(
            direction="in", stage="received",
            raw_bytes=b'{}',
            parsed={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "analyze",
                    "arguments": {
                        "query": "UCW cognitive wallet coherence "
                                 "sovereign emergence protocol",
                    },
                },
            },
            timestamp_ns=1_000_000_000,
        )
        adapter.enrich(event)
        instinct = event.instinct_layer
        assert "coherence_potential" in instinct
        assert "emergence_indicators" in instinct
        assert "gut_signal" in instinct
        assert instinct["gut_signal"] in (
            "routine", "interesting", "breakthrough_potential",
        )


class TestRawMCPServerSetup:
    def test_server_creation(self, tmp_ucw_dir):
        server = RawMCPServer()
        assert server.capture_engine is not None
        assert server.db is None  # Not initialized until run()

    def test_register_tools(self, tmp_ucw_dir):
        server = RawMCPServer()

        async def handler(name, args):
            return {}

        server.register_tools(
            [{"name": "test", "description": "test", "inputSchema": {}}],
            handler,
        )
        # Tools registered on the internal router
        assert server.capture_engine.event_count == 0
