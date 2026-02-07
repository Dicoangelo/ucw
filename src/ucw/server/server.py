"""
Raw MCP Server — Main Orchestrator

Ties together:
  Transport -> Protocol -> Router -> Capture -> Database

Flow:
  1. Transport reads raw bytes from stdin
  2. Protocol validates JSON-RPC 2.0
  3. Router dispatches to correct handler
  4. Capture engine records at every stage
  5. UCW Bridge enriches with semantic layers
  6. Database persists with perfect fidelity
  7. Transport writes response to stdout

Startup strategy (fast init for MCP handshake):
  - Transport starts IMMEDIATELY (respond to initialize within ms)
  - Database connects in BACKGROUND (lazy)
  - Embedding callbacks are NON-BLOCKING
"""

import asyncio
import signal
from typing import Optional

from ucw.config import Config
from ucw.server.logger import get_logger
from ucw.server.transport import RawStdioTransport
from ucw.server.protocol import (
    validate_message,
    make_response,
    make_error,
    ProtocolError,
    PARSE_ERROR,
    INTERNAL_ERROR,
)
from ucw.server.router import Router
from ucw.server.capture import CaptureEngine
from ucw.db.sqlite import CaptureDB
from ucw.server.ucw_bridge import extract_layers, coherence_signature
from ucw.server.embeddings import EmbeddingPipeline

log = get_logger("server")

# Protocol methods that should NEVER trigger embedding (fast-path)
_PROTOCOL_METHODS = frozenset({
    "initialize", "initialized", "notifications/initialized",
    "tools/list", "resources/list", "ping",
    "notifications/cancelled",
})


class UCWBridgeAdapter:
    """Adapts ucw_bridge module functions to the enrich(event) interface."""

    def enrich(self, event):
        data, light, instinct = extract_layers(event.parsed, event.direction)
        event.data_layer = data
        event.light_layer = light
        event.instinct_layer = instinct
        event.coherence_signature = coherence_signature(
            light.get("intent", ""),
            light.get("topic", ""),
            event.timestamp_ns,
            data.get("content", ""),
        )


class RawMCPServer:
    """
    Main server orchestrator.

    Usage:
        server = RawMCPServer()
        server.register_tools(TOOLS, handle_tool)
        await server.run()
    """

    def __init__(self):
        Config.ensure_dirs()

        self._capture = CaptureEngine()
        self._transport = RawStdioTransport(on_capture=self._capture.capture)
        self._router = Router()
        self._db: Optional[CaptureDB] = None
        self._embedding_pipeline: Optional[EmbeddingPipeline] = None
        self._running = False
        self._db_ready = False
        self._db_init_task: Optional[asyncio.Task] = None
        self._handshake_complete = False

    # -- tool/resource registration (call before run) --

    def register_tools(self, tools_list, handler):
        """Register a tools module with the router."""
        self._router.register_tools_module(tools_list, handler)

    def register_resources(self, resources, handler):
        """Register a resources provider with the router."""
        self._router.register_resources(resources, handler)

    @property
    def capture_engine(self) -> CaptureEngine:
        return self._capture

    @property
    def db(self) -> Optional[CaptureDB]:
        return self._db

    # -- lazy database initialization --

    async def _init_db_background(self):
        """Initialize database in background."""
        try:
            self._db = CaptureDB()
            await self._db.initialize()
            log.info("Using SQLite backend")

            self._capture.set_db_sink(self._db)
            self._embedding_pipeline = EmbeddingPipeline()
            self._inject_db()

            self._db_ready = True
            log.info(f"Database ready — session={self._db.session_id}")

        except Exception as exc:
            log.error(f"Background DB init failed: {exc}", exc_info=True)

    async def _ensure_db_ready(self):
        """Wait for DB to be ready (called before tool execution)."""
        if self._db_ready:
            return
        if self._db_init_task and not self._db_init_task.done():
            await self._db_init_task

    # -- main loop --

    async def run(self):
        """Start the server and process messages until EOF or signal."""
        log.info(f"Starting {Config.SERVER_NAME} v{Config.SERVER_VERSION}")

        self._capture.set_ucw_bridge(UCWBridgeAdapter())
        await self._transport.start()
        self._db_init_task = asyncio.create_task(self._init_db_background())

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            except NotImplementedError:
                pass

        self._running = True
        log.info(
            f"Server ready — tools={self._router.tool_count} "
            f"resources={self._router.resource_count} "
            f"(db initializing in background)"
        )

        try:
            while self._running:
                result = await self._transport.read_message()
                if result is None:
                    log.info("EOF on stdin — shutting down")
                    break

                raw_bytes, parsed = result
                await self._handle_message(parsed)

        except asyncio.CancelledError:
            log.info("Server cancelled")
        except Exception as exc:
            log.error(f"Server error: {exc}", exc_info=True)
        finally:
            await self.shutdown()

    async def _handle_message(self, msg: dict):
        """Process a single JSON-RPC message through the full pipeline."""
        request_id = msg.get("id")
        method = msg.get("method", "")

        if method in ("initialized", "notifications/initialized"):
            self._handshake_complete = True

        try:
            msg_type = validate_message(msg)

            if method == "tools/call":
                await self._ensure_db_ready()

            result = await self._router.route(msg_type, msg)

            if result is None:
                return

            response = make_response(request_id, result)
            await self._transport.write_message(response, request_id=request_id)

        except ProtocolError as exc:
            log.warning(f"Protocol error: {exc.message} (code={exc.code})")
            if request_id is not None:
                error_resp = make_error(request_id, exc.code, exc.message, exc.data)
                await self._transport.write_message(error_resp, request_id=request_id)

        except Exception as exc:
            log.error(f"Unhandled error: {exc}", exc_info=True)
            if request_id is not None:
                error_resp = make_error(request_id, INTERNAL_ERROR, str(exc))
                await self._transport.write_message(error_resp, request_id=request_id)

    def _inject_db(self):
        """Inject shared DB instance into tool modules that need it."""
        try:
            from ucw.tools import ucw_tools, coherence_tools
            if hasattr(ucw_tools, 'set_db'):
                ucw_tools.set_db(self._db)
            if hasattr(coherence_tools, 'set_db'):
                coherence_tools.set_db(self._db)
            log.info("DB injected into tool modules")
        except ImportError:
            pass

    async def shutdown(self):
        """Graceful shutdown — flush captures, close DB."""
        if not self._running:
            return
        self._running = False

        log.info(
            f"Shutting down — captured {self._capture.event_count} events, "
            f"{self._capture.turn_count} turns"
        )

        if self._db_init_task and not self._db_init_task.done():
            self._db_init_task.cancel()
            try:
                await self._db_init_task
            except (asyncio.CancelledError, Exception):
                pass

        await self._transport.close()
        if self._db:
            await self._db.close()

        log.info("Server stopped")
