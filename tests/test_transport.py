"""Tests for RawStdioTransport."""

import asyncio
import json
from io import BytesIO
from unittest.mock import AsyncMock

import pytest

from ucw.server.transport import RawStdioTransport


class TestRawStdioTransportInit:
    def test_initial_state(self):
        cb = AsyncMock()
        t = RawStdioTransport(on_capture=cb)
        assert t.on_capture is cb
        assert t.running is False
        assert t._reader is None
        assert t._stdout is None


class TestRawStdioTransportNotStarted:
    @pytest.mark.asyncio
    async def test_read_message_raises_if_not_started(self):
        t = RawStdioTransport(on_capture=AsyncMock())
        with pytest.raises(RuntimeError, match="not started"):
            await t.read_message()

    @pytest.mark.asyncio
    async def test_write_message_raises_if_not_started(self):
        t = RawStdioTransport(on_capture=AsyncMock())
        with pytest.raises(RuntimeError, match="not started"):
            await t.write_message({"jsonrpc": "2.0", "id": 1, "result": {}})


class TestRawStdioTransportWriteMessage:
    @pytest.mark.asyncio
    async def test_write_message_calls_capture_and_writes_bytes(self):
        captured_calls = []

        async def on_capture(**kwargs):
            captured_calls.append(kwargs)

        t = RawStdioTransport(on_capture=on_capture)

        buf = BytesIO()
        t._stdout = buf
        t.running = True

        msg = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        await t.write_message(msg)

        written = buf.getvalue()
        assert written.endswith(b"\n")
        parsed = json.loads(written.decode())
        assert parsed == msg

        assert len(captured_calls) == 1
        call = captured_calls[0]
        assert call["direction"] == "out"
        assert call["parsed"] == msg

    @pytest.mark.asyncio
    async def test_write_message_passes_request_id(self):
        captured_calls = []

        async def on_capture(**kwargs):
            captured_calls.append(kwargs)

        t = RawStdioTransport(on_capture=on_capture)
        t._stdout = BytesIO()
        t.running = True

        await t.write_message({"jsonrpc": "2.0", "id": 42, "result": {}}, request_id=42)

        assert captured_calls[0]["parent_protocol_id"] == "42"

    @pytest.mark.asyncio
    async def test_write_message_no_request_id(self):
        captured_calls = []

        async def on_capture(**kwargs):
            captured_calls.append(kwargs)

        t = RawStdioTransport(on_capture=on_capture)
        t._stdout = BytesIO()
        t.running = True

        await t.write_message({"jsonrpc": "2.0", "method": "ping"})
        assert captured_calls[0]["parent_protocol_id"] is None


class TestRawStdioTransportReadMessage:
    @pytest.mark.asyncio
    async def test_read_message_valid_json(self):
        captured_calls = []

        async def on_capture(**kwargs):
            captured_calls.append(kwargs)

        t = RawStdioTransport(on_capture=on_capture)

        reader = asyncio.StreamReader()
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        line = (json.dumps(msg) + "\n").encode()
        reader.feed_data(line)

        t._reader = reader
        t.running = True

        result = await t.read_message()

        assert result is not None
        raw_bytes, parsed = result
        assert parsed == msg
        assert raw_bytes == line

        assert len(captured_calls) == 1
        assert captured_calls[0]["direction"] == "in"
        assert captured_calls[0]["parsed"] == msg

    @pytest.mark.asyncio
    async def test_read_message_invalid_json_returns_none(self):
        captured_calls = []

        async def on_capture(**kwargs):
            captured_calls.append(kwargs)

        t = RawStdioTransport(on_capture=on_capture)

        reader = asyncio.StreamReader()
        reader.feed_data(b"not valid json\n")

        t._reader = reader
        t.running = True

        result = await t.read_message()

        assert result is None
        assert len(captured_calls) == 1
        call = captured_calls[0]
        assert call["direction"] == "in"
        assert "JSON parse error" in call.get("error", "")

    @pytest.mark.asyncio
    async def test_read_message_eof_returns_none(self):
        async def on_capture(**kwargs):
            pass

        t = RawStdioTransport(on_capture=on_capture)

        reader = asyncio.StreamReader()
        reader.feed_eof()

        t._reader = reader
        t.running = True

        result = await t.read_message()
        assert result is None


class TestRawStdioTransportClose:
    @pytest.mark.asyncio
    async def test_close_sets_running_false(self):
        t = RawStdioTransport(on_capture=AsyncMock())
        t.running = True
        await t.close()
        assert t.running is False
