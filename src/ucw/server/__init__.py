"""UCW MCP Server — Raw protocol implementation."""

from ucw.server.capture import CaptureEngine, CaptureEvent
from ucw.server.router import Router

# Lazy import to avoid circular dependency (server -> db -> server)


def __getattr__(name):
    if name == "RawMCPServer":
        from ucw.server.server import RawMCPServer
        return RawMCPServer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["RawMCPServer", "CaptureEngine", "CaptureEvent", "Router"]
