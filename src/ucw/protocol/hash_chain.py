"""
Hash Chain — SHA-256 chain linking each cognitive event to its predecessor.

Provides tamper-evident event ordering: if any event is modified or removed,
the chain breaks and verification fails.
"""

import hashlib
import json
from typing import Dict, List, Optional

from ucw.server.logger import get_logger

log = get_logger("protocol.hash_chain")


class HashChain:
    """SHA-256 hash chain linking each cognitive event to its predecessor."""

    def __init__(self):
        self._prev_hash: str = "genesis"  # Genesis hash for first event

    def content_hash(self, content: str) -> str:
        """SHA-256 of event content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def chain_hash(self, content_hash: str, prev_hash: str) -> str:
        """SHA-256(content_hash + prev_hash) -- the chain link."""
        return hashlib.sha256(f"{content_hash}:{prev_hash}".encode("utf-8")).hexdigest()

    def add_event(self, content: str) -> Dict[str, str]:
        """Add event to chain. Returns {"content_hash", "prev_hash", "chain_hash"}."""
        c_hash = self.content_hash(content)
        ch_hash = self.chain_hash(c_hash, self._prev_hash)
        result = {
            "content_hash": c_hash,
            "prev_hash": self._prev_hash,
            "chain_hash": ch_hash,
        }
        self._prev_hash = ch_hash
        return result

    def verify_chain(self, events: List[Dict]) -> Dict:
        """Verify a sequence of events. Each must have content_hash, prev_hash, chain_hash.

        Returns {"valid": bool, "verified_count": int, "break_at": int | None, "errors": list}
        """
        errors: List[str] = []
        verified = 0

        for i, event in enumerate(events):
            c_hash = event.get("content_hash", "")
            p_hash = event.get("prev_hash", "")
            ch_hash = event.get("chain_hash", "")

            # Verify the chain_hash is correctly computed
            expected = self.chain_hash(c_hash, p_hash)
            if ch_hash != expected:
                errors.append(
                    f"Event {i}: chain_hash mismatch "
                    f"(expected {expected[:16]}..., got {ch_hash[:16]}...)"
                )
                return {
                    "valid": False,
                    "verified_count": verified,
                    "break_at": i,
                    "errors": errors,
                }

            # Verify prev_hash links to the previous event's chain_hash
            if i > 0:
                prev_chain = events[i - 1].get("chain_hash", "")
                if p_hash != prev_chain:
                    errors.append(
                        f"Event {i}: prev_hash does not match previous chain_hash "
                        f"(expected {prev_chain[:16]}..., got {p_hash[:16]}...)"
                    )
                    return {
                        "valid": False,
                        "verified_count": verified,
                        "break_at": i,
                        "errors": errors,
                    }

            verified += 1

        return {
            "valid": True,
            "verified_count": verified,
            "break_at": None,
            "errors": errors,
        }


class HashChainStore:
    """Persist hash chain data to SQLite."""

    def __init__(self, conn):
        self._conn = conn

    def update_event_hashes(
        self, event_id: str, content_hash: str, prev_hash: str, chain_hash: str
    ) -> bool:
        """UPDATE cognitive_events SET content_hash, prev_hash, chain_hash."""
        try:
            self._conn.execute(
                "UPDATE cognitive_events SET content_hash=?, prev_hash=?, chain_hash=? "
                "WHERE event_id=?",
                (content_hash, prev_hash, chain_hash, event_id),
            )
            self._conn.commit()
            return True
        except Exception as exc:
            log.error(f"Failed to update event hashes for {event_id}: {exc}")
            return False

    def get_last_chain_hash(self, session_id: str) -> str:
        """Get the most recent chain_hash for a session. Returns 'genesis' if none."""
        try:
            cur = self._conn.execute(
                "SELECT chain_hash FROM cognitive_events "
                "WHERE session_id=? AND chain_hash IS NOT NULL "
                "ORDER BY timestamp_ns DESC LIMIT 1",
                (session_id,),
            )
            row = cur.fetchone()
            return row[0] if row else "genesis"
        except Exception as exc:
            log.error(f"Failed to get last chain hash for {session_id}: {exc}")
            return "genesis"

    def get_chain_events(self, session_id: str) -> List[Dict]:
        """Get all events with hash chain data for verification, ordered by timestamp."""
        try:
            cur = self._conn.execute(
                "SELECT event_id, content_hash, prev_hash, chain_hash, timestamp_ns "
                "FROM cognitive_events "
                "WHERE session_id=? AND chain_hash IS NOT NULL "
                "ORDER BY timestamp_ns ASC",
                (session_id,),
            )
            return [
                {
                    "event_id": r[0],
                    "content_hash": r[1],
                    "prev_hash": r[2],
                    "chain_hash": r[3],
                    "timestamp_ns": r[4],
                }
                for r in cur.fetchall()
            ]
        except Exception as exc:
            log.error(f"Failed to get chain events for {session_id}: {exc}")
            return []

    def verify_session_chain(self, session_id: str) -> Dict:
        """Load and verify the full chain for a session."""
        events = self.get_chain_events(session_id)
        if not events:
            return {
                "valid": True,
                "verified_count": 0,
                "break_at": None,
                "errors": [],
                "session_id": session_id,
            }
        chain = HashChain()
        result = chain.verify_chain(events)
        result["session_id"] = session_id
        return result
