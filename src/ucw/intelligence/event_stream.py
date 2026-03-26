"""
Event Stream — In-process pub/sub for real-time cognitive events.

Channels:
  capture          — All captured events
  high_coherence   — Events with coherence > 0.7
  emergence        — Breakthrough signals
  cross_platform   — Cross-platform matches
"""

from typing import Any, Callable, Dict, List

from ucw.server.logger import get_logger

log = get_logger("intelligence.event_stream")


class EventStream:
    """Pub/sub for real-time cognitive events."""

    CHANNELS = ("capture", "high_coherence", "emergence", "cross_platform")

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, channel: str, callback: Callable) -> None:
        """Register a callback for a channel."""
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        if callback not in self._subscribers[channel]:
            self._subscribers[channel].append(callback)
            log.debug(f"Subscriber added to '{channel}' (total: {len(self._subscribers[channel])})")

    def unsubscribe(self, channel: str, callback: Callable) -> None:
        """Remove a callback from a channel."""
        if channel in self._subscribers:
            try:
                self._subscribers[channel].remove(callback)
                log.debug(f"Subscriber removed from '{channel}'")
            except ValueError:
                pass

    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        """Publish an event to all subscribers on a channel.

        Each callback is called independently — a failure in one does not
        block the others.
        """
        callbacks = self._subscribers.get(channel, [])
        for cb in callbacks:
            try:
                result = cb(event)
                # Support both sync and async callbacks
                if hasattr(result, "__await__"):
                    await result
            except Exception as exc:
                log.error(f"Subscriber error on '{channel}': {exc}")

    def subscriber_count(self, channel: str = None) -> int:
        """Return subscriber count for a channel, or total across all channels."""
        if channel is not None:
            return len(self._subscribers.get(channel, []))
        return sum(len(cbs) for cbs in self._subscribers.values())
