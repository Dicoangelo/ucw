"""Tests for UCW Bridge — semantic layer extraction."""

from ucw.server.ucw_bridge import (
    extract_layers,
    coherence_signature,
    _classify,
    _extract_concepts,
    _DOMAIN_KEYWORDS,
    _INTENT_SIGNALS,
)


class TestExtractLayers:
    def test_inbound_tool_call(self):
        msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "ucw_capture_stats", "arguments": {}},
        }
        data, light, instinct = extract_layers(msg, "in")

        assert "Tool call: ucw_capture_stats" in data["content"]
        assert data["method"] == "tools/call"
        assert light["intent"] in ("execute", "retrieve", "explore")
        assert light["topic"] == "ucw"
        assert isinstance(instinct["coherence_potential"], float)
        assert instinct["gut_signal"] in ("routine", "interesting", "breakthrough_potential")

    def test_outbound_response(self):
        msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": "Events: 42, Sessions: 3"}]
            },
        }
        data, light, instinct = extract_layers(msg, "out")

        assert "Events: 42" in data["content"]
        assert light["summary"]
        assert isinstance(instinct["emergence_indicators"], list)

    def test_outbound_error(self):
        msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32603, "message": "Internal error"},
        }
        data, light, instinct = extract_layers(msg, "out")
        assert "Error:" in data["content"]

    def test_initialize_method(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        data, light, instinct = extract_layers(msg, "in")
        assert data["method"] == "initialize"

    def test_ucw_topic_detection(self):
        msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": "UCW cognitive wallet coherence sovereignty"}]
            },
        }
        _, light, instinct = extract_layers(msg, "out")
        assert light["topic"] == "ucw"
        assert "ucw" in light["concepts"]
        assert "cognitive" in light["concepts"]
        assert instinct["coherence_potential"] > 0.5


class TestCoherenceSignature:
    def test_same_inputs_same_signature(self):
        ts = 1000000000000000000
        sig1 = coherence_signature("create", "ucw", ts, "building wallet")
        sig2 = coherence_signature("create", "ucw", ts, "building wallet")
        assert sig1 == sig2

    def test_different_inputs_different_signature(self):
        ts = 1000000000000000000
        sig1 = coherence_signature("create", "ucw", ts, "building wallet")
        sig2 = coherence_signature("analyze", "database", ts, "checking schema")
        assert sig1 != sig2

    def test_time_bucket_same_5min(self):
        # Use a timestamp at the start of a 5-minute bucket
        bucket_size = 5 * 60 * 1_000_000_000
        ts1 = 3333333 * bucket_size + 10_000_000_000  # 10s into a bucket
        ts2 = ts1 + (2 * 60 * 1_000_000_000)  # +2 minutes (same bucket)
        sig1 = coherence_signature("create", "ucw", ts1, "x")
        sig2 = coherence_signature("create", "ucw", ts2, "x")
        assert sig1 == sig2

    def test_time_bucket_different(self):
        bucket_size = 5 * 60 * 1_000_000_000
        ts1 = 3333333 * bucket_size + 10_000_000_000
        ts2 = ts1 + (6 * 60 * 1_000_000_000)  # +6 minutes (different bucket)
        sig1 = coherence_signature("create", "ucw", ts1, "x")
        sig2 = coherence_signature("create", "ucw", ts2, "x")
        assert sig1 != sig2


class TestClassify:
    def test_search_intent(self):
        result = _classify("find the database schema", _INTENT_SIGNALS, default="explore")
        assert result == "search"

    def test_create_intent(self):
        result = _classify("build a new function", _INTENT_SIGNALS, default="explore")
        assert result == "create"

    def test_default_intent(self):
        result = _classify("hello world", _INTENT_SIGNALS, default="explore")
        assert result == "explore"

    def test_ucw_topic(self):
        result = _classify("ucw cognitive wallet coherence", _DOMAIN_KEYWORDS, default="general")
        assert result == "ucw"


class TestExtractConcepts:
    def test_multiple_concepts(self):
        concepts = _extract_concepts("ucw cognitive capture with embedding and coherence")
        assert "ucw" in concepts
        assert "cognitive" in concepts
        assert "capture" in concepts
        assert "embedding" in concepts
        assert "coherence" in concepts

    def test_no_concepts(self):
        concepts = _extract_concepts("hello world nothing special")
        assert concepts == []
