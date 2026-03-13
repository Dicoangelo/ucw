"""Tests for embedding pipeline helper functions (no model loading)."""

from ucw.server.embeddings import build_embed_text, content_hash


class TestBuildEmbedText:
    def test_from_dict_with_layers(self):
        event = {
            "light_layer": {
                "intent": "analyze",
                "topic": "ucw",
                "summary": "Testing embeddings",
                "concepts": ["ucw", "cognitive"],
            },
            "data_layer": {"content": "raw content here"},
        }
        text = build_embed_text(event)
        assert "analyze: ucw" in text
        assert "Testing embeddings" in text
        assert "ucw cognitive" in text

    def test_from_dict_no_summary_uses_content(self):
        event = {
            "light_layer": {
                "intent": "search", "topic": "database",
                "summary": "", "concepts": [],
            },
            "data_layer": {"content": "SELECT * FROM events"},
        }
        text = build_embed_text(event)
        assert "search: database" in text
        assert "SELECT" in text

    def test_from_dict_empty_layers(self):
        event = {"light_layer": {}, "data_layer": {}}
        text = build_embed_text(event)
        assert "explore: general" in text

    def test_from_dict_string_layers(self):
        """Handles JSON string layers (as stored in DB)."""
        event = {
            "light_layer": (
                '{"intent": "create", "topic": "coding",'
                ' "summary": "func", "concepts": []}'
            ),
            "data_layer": '{"content": "def foo(): pass"}',
        }
        text = build_embed_text(event)
        assert "create: coding" in text

    def test_from_object_with_attributes(self):
        class FakeEvent:
            light_layer = {
                "intent": "analyze", "topic": "research",
                "summary": "Paper review", "concepts": ["arxiv"],
            }
            data_layer = {"content": "The paper shows..."}

        text = build_embed_text(FakeEvent())
        assert "analyze: research" in text
        assert "Paper review" in text

    def test_from_none_returns_empty(self):
        assert build_embed_text(42) == ""
        assert build_embed_text(None) == ""

    def test_from_dict_none_layers(self):
        event = {"light_layer": None, "data_layer": None}
        text = build_embed_text(event)
        assert "explore: general" in text


class TestContentHash:
    def test_deterministic(self):
        h1 = content_hash("hello world")
        h2 = content_hash("hello world")
        assert h1 == h2

    def test_different_inputs(self):
        h1 = content_hash("hello")
        h2 = content_hash("world")
        assert h1 != h2

    def test_returns_hex_string(self):
        h = content_hash("test")
        assert len(h) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in h)
