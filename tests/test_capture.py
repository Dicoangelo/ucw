"""Tests for CaptureEngine."""

import pytest
from ucw.server.capture import CaptureEngine, CaptureEvent


class TestCaptureEvent:
    def test_creation(self):
        event = CaptureEvent(
            direction="in",
            stage="received",
            raw_bytes=b'{"jsonrpc":"2.0","method":"ping"}',
            parsed={"jsonrpc": "2.0", "method": "ping"},
            timestamp_ns=1000000000,
        )
        assert event.direction == "in"
        assert event.stage == "received"
        assert event.method == "ping"
        assert event.timestamp_ns == 1000000000
        assert len(event.event_id) == 16

    def test_to_dict(self):
        event = CaptureEvent(
            direction="out",
            stage="sent",
            raw_bytes=b"test",
            parsed={"jsonrpc": "2.0", "id": 1, "result": {}},
        )
        d = event.to_dict()
        assert d["direction"] == "out"
        assert d["stage"] == "sent"
        assert "event_id" in d

    def test_to_dict_with_layers(self):
        event = CaptureEvent(
            direction="in",
            stage="received",
            raw_bytes=b"test",
            parsed={},
        )
        event.data_layer = {"content": "hello"}
        event.light_layer = {"topic": "ucw"}
        event.instinct_layer = {"gut_signal": "interesting"}
        event.coherence_signature = "abc123"

        d = event.to_dict()
        assert d["data_layer"] == {"content": "hello"}
        assert d["light_layer"] == {"topic": "ucw"}
        assert d["instinct_layer"] == {"gut_signal": "interesting"}
        assert d["coherence_signature"] == "abc123"


class TestCaptureEngine:
    @pytest.fixture
    def engine(self):
        return CaptureEngine()

    @pytest.mark.asyncio
    async def test_capture_inbound(self, engine):
        await engine.capture(
            raw_bytes=b'{"jsonrpc":"2.0","id":1,"method":"ping"}',
            parsed={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            timestamp_ns=1000,
            direction="in",
        )
        assert engine.event_count == 1
        assert engine.turn_count == 1

    @pytest.mark.asyncio
    async def test_capture_outbound(self, engine):
        await engine.capture(
            raw_bytes=b'{"jsonrpc":"2.0","id":1,"result":{}}',
            parsed={"jsonrpc": "2.0", "id": 1, "result": {}},
            timestamp_ns=2000,
            direction="out",
        )
        assert engine.event_count == 1

    @pytest.mark.asyncio
    async def test_turn_counting(self, engine):
        for i in range(5):
            await engine.capture(
                raw_bytes=b'{}',
                parsed={"jsonrpc": "2.0", "id": i, "method": "ping"},
                timestamp_ns=i * 1000,
                direction="in",
            )
        assert engine.turn_count == 5

    @pytest.mark.asyncio
    async def test_request_response_lineage(self, engine):
        # Request
        await engine.capture(
            raw_bytes=b'{}',
            parsed={"jsonrpc": "2.0", "id": 42, "method": "tools/call"},
            timestamp_ns=1000,
            direction="in",
        )
        # Response
        await engine.capture(
            raw_bytes=b'{}',
            parsed={"jsonrpc": "2.0", "id": 42, "result": {}},
            timestamp_ns=2000,
            direction="out",
        )

        events = engine.recent_events(2)
        response = events[1]
        assert response["parent_protocol_id"] is not None

    @pytest.mark.asyncio
    async def test_recent_events(self, engine):
        for i in range(10):
            await engine.capture(
                raw_bytes=b'{}',
                parsed={"jsonrpc": "2.0", "method": f"method_{i}"},
                timestamp_ns=i,
                direction="in",
            )
        recent = engine.recent_events(3)
        assert len(recent) == 3

    @pytest.mark.asyncio
    async def test_stats(self, engine):
        await engine.capture(
            raw_bytes=b'{}', parsed={}, timestamp_ns=1, direction="in",
        )
        await engine.capture(
            raw_bytes=b'{}', parsed={}, timestamp_ns=2, direction="out",
        )
        stats = engine.stats
        assert stats["total"] == 2
        assert stats["in_received"] == 1
        assert stats["out_sent"] == 1

    @pytest.mark.asyncio
    async def test_ucw_bridge_enrichment(self, engine):
        class MockBridge:
            def enrich(self, event):
                event.data_layer = {"content": "enriched"}
                event.light_layer = {"topic": "test"}
                event.instinct_layer = {"gut_signal": "routine"}

        engine.set_ucw_bridge(MockBridge())
        await engine.capture(
            raw_bytes=b'{}', parsed={}, timestamp_ns=1, direction="in",
        )
        event = engine.recent_events(1)[0]
        assert event["data_layer"] == {"content": "enriched"}
        assert event["light_layer"] == {"topic": "test"}

    @pytest.mark.asyncio
    async def test_event_callback(self, engine):
        received = []

        async def callback(event):
            received.append(event)

        engine.on_event(callback)
        await engine.capture(
            raw_bytes=b'{}', parsed={}, timestamp_ns=1, direction="in",
        )
        assert len(received) == 1
