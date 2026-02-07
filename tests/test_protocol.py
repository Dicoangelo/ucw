"""Tests for JSON-RPC 2.0 protocol module."""

import pytest
from ucw.server.protocol import (
    validate_message,
    make_response,
    make_error,
    make_notification,
    initialize_result,
    tools_list_result,
    tool_result_content,
    text_content,
    ProtocolError,
    INVALID_REQUEST,
    PARSE_ERROR,
)


class TestValidateMessage:
    def test_request(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        assert validate_message(msg) == "request"

    def test_notification(self):
        msg = {"jsonrpc": "2.0", "method": "initialized"}
        assert validate_message(msg) == "notification"

    def test_response(self):
        msg = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        assert validate_message(msg) == "response"

    def test_error_response(self):
        msg = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": "Invalid"}}
        assert validate_message(msg) == "error"

    def test_invalid_not_dict(self):
        with pytest.raises(ProtocolError):
            validate_message("not a dict")

    def test_invalid_missing_jsonrpc(self):
        with pytest.raises(ProtocolError):
            validate_message({"id": 1, "method": "test"})

    def test_invalid_wrong_version(self):
        with pytest.raises(ProtocolError):
            validate_message({"jsonrpc": "1.0", "id": 1, "method": "test"})

    def test_invalid_no_identifiers(self):
        with pytest.raises(ProtocolError):
            validate_message({"jsonrpc": "2.0"})


class TestMakeResponse:
    def test_basic(self):
        resp = make_response(1, {"tools": []})
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert resp["result"] == {"tools": []}

    def test_string_id(self):
        resp = make_response("abc", "ok")
        assert resp["id"] == "abc"


class TestMakeError:
    def test_basic(self):
        err = make_error(1, -32600, "Invalid Request")
        assert err["jsonrpc"] == "2.0"
        assert err["id"] == 1
        assert err["error"]["code"] == -32600
        assert err["error"]["message"] == "Invalid Request"

    def test_with_data(self):
        err = make_error(1, -32600, "Invalid", data={"detail": "missing field"})
        assert err["error"]["data"] == {"detail": "missing field"}

    def test_without_data(self):
        err = make_error(1, -32600, "Invalid")
        assert "data" not in err["error"]


class TestMakeNotification:
    def test_basic(self):
        n = make_notification("notifications/cancelled")
        assert n["jsonrpc"] == "2.0"
        assert n["method"] == "notifications/cancelled"
        assert "id" not in n
        assert "params" not in n

    def test_with_params(self):
        n = make_notification("test", {"key": "value"})
        assert n["params"] == {"key": "value"}


class TestMCPBuilders:
    def test_initialize_result(self):
        r = initialize_result("ucw", "0.1.0", "2024-11-05")
        assert r["protocolVersion"] == "2024-11-05"
        assert r["serverInfo"]["name"] == "ucw"
        assert r["serverInfo"]["version"] == "0.1.0"
        assert "tools" in r["capabilities"]

    def test_tools_list_result(self):
        tools = [{"name": "test", "description": "A test tool", "inputSchema": {"type": "object"}}]
        r = tools_list_result(tools)
        assert len(r["tools"]) == 1
        assert r["tools"][0]["name"] == "test"

    def test_tool_result_content(self):
        r = tool_result_content([text_content("hello")])
        assert r["content"][0]["type"] == "text"
        assert r["content"][0]["text"] == "hello"
        assert "isError" not in r

    def test_tool_result_content_error(self):
        r = tool_result_content([text_content("fail")], is_error=True)
        assert r["isError"] is True

    def test_text_content(self):
        tc = text_content("hello world")
        assert tc == {"type": "text", "text": "hello world"}
