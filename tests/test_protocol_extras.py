"""Tests for protocol extras (ProtocolError, resources builders)."""

import pytest
from ucw.server.protocol import (
    ProtocolError,
    resources_list_result,
    resource_read_result,
    validate_message,
    PARSE_ERROR,
    INVALID_REQUEST,
)


class TestProtocolError:
    def test_error_attributes(self):
        err = ProtocolError(code=-32600, message="Bad request", data={"key": "val"})
        assert err.code == -32600
        assert err.message == "Bad request"
        assert err.data == {"key": "val"}
        assert str(err) == "Bad request"

    def test_error_without_data(self):
        err = ProtocolError(code=-32700, message="Parse error")
        assert err.data is None


class TestResourceBuilders:
    def test_resources_list_result(self):
        resources = [{"uri": "ucw://stats", "name": "Stats"}]
        result = resources_list_result(resources)
        assert result == {"resources": resources}

    def test_resources_list_empty(self):
        result = resources_list_result([])
        assert result == {"resources": []}

    def test_resource_read_result(self):
        contents = [{"uri": "ucw://stats", "text": "data here"}]
        result = resource_read_result(contents)
        assert result == {"contents": contents}


class TestValidateEdgeCases:
    def test_error_constants(self):
        assert PARSE_ERROR == -32700
        assert INVALID_REQUEST == -32600

    def test_response_without_id_raises(self):
        with pytest.raises(ProtocolError):
            validate_message({"jsonrpc": "2.0", "result": {}})

    def test_result_and_error_both_present(self):
        # Has both — id + result takes precedence
        msg_type = validate_message({"jsonrpc": "2.0", "id": 1, "result": {}, "error": {}})
        assert msg_type == "response"
