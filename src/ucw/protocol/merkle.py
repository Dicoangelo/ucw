"""
Merkle Tree — Binary Merkle tree over event hashes for session-level proof.

Produces a single root hash that commits to every event in a session.
Individual events can be verified against the root via audit proofs.
"""

import hashlib
import json
from typing import Dict, List, Optional

from ucw.server.logger import get_logger

log = get_logger("protocol.merkle")


class MerkleTree:
    """Binary Merkle tree over event hashes."""

    def __init__(self, leaves: List[str] = None):
        self._leaves: List[str] = list(leaves) if leaves else []
        self._tree: List[List[str]] = []
        if self._leaves:
            self._build()

    def _hash_pair(self, a: str, b: str) -> str:
        return hashlib.sha256(f"{a}:{b}".encode("utf-8")).hexdigest()

    def _build(self):
        """Build the tree bottom-up."""
        if not self._leaves:
            self._tree = []
            return

        # Level 0 = leaves
        self._tree = [list(self._leaves)]

        current = self._tree[0]
        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                left = current[i]
                # Odd leaf gets duplicated
                right = current[i + 1] if i + 1 < len(current) else current[i]
                next_level.append(self._hash_pair(left, right))
            self._tree.append(next_level)
            current = next_level

    def add_leaf(self, leaf_hash: str):
        """Add a leaf and rebuild."""
        self._leaves.append(leaf_hash)
        self._build()

    @property
    def root(self) -> Optional[str]:
        """The Merkle root hash."""
        if not self._tree:
            return None
        return self._tree[-1][0] if self._tree[-1] else None

    @property
    def leaf_count(self) -> int:
        return len(self._leaves)

    def get_proof(self, leaf_index: int) -> List[Dict]:
        """Get the Merkle proof (audit path) for a leaf.

        Returns [{"hash": str, "position": "left"|"right"}, ...]
        """
        if leaf_index < 0 or leaf_index >= len(self._leaves):
            return []
        if not self._tree or len(self._tree) < 2:
            return []

        proof = []
        idx = leaf_index

        for level in range(len(self._tree) - 1):
            layer = self._tree[level]
            # Determine sibling
            if idx % 2 == 0:
                # We're on the left, sibling is on the right
                sibling_idx = idx + 1
                if sibling_idx < len(layer):
                    proof.append({"hash": layer[sibling_idx], "position": "right"})
                else:
                    # Odd leaf — sibling is self (duplicated)
                    proof.append({"hash": layer[idx], "position": "right"})
            else:
                # We're on the right, sibling is on the left
                sibling_idx = idx - 1
                proof.append({"hash": layer[sibling_idx], "position": "left"})

            idx = idx // 2

        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: List[Dict], root: str) -> bool:
        """Verify a Merkle proof against a known root."""
        current = leaf_hash
        for step in proof:
            sibling = step["hash"]
            if step["position"] == "right":
                combined = f"{current}:{sibling}"
            else:
                combined = f"{sibling}:{current}"
            current = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return current == root


class MerkleStore:
    """Persist Merkle roots and generate receipts."""

    def __init__(self, conn):
        self._conn = conn

    def update_session_merkle(self, session_id: str, merkle_root: str) -> bool:
        """UPDATE sessions SET merkle_root=? WHERE session_id=?"""
        try:
            self._conn.execute(
                "UPDATE sessions SET merkle_root=? WHERE session_id=?",
                (merkle_root, session_id),
            )
            self._conn.commit()
            return True
        except Exception as exc:
            log.error(f"Failed to update session merkle for {session_id}: {exc}")
            return False

    def create_receipt(
        self,
        session_id: str,
        event_ids: list,
        merkle_root: str,
        merkle_proofs: dict,
        platform: str,
        summary: str = None,
    ) -> str:
        """INSERT into cognition_receipts. Return receipt_id."""
        receipt_id = hashlib.sha256(
            f"{session_id}:{merkle_root}".encode()
        ).hexdigest()[:16]

        # Compute timestamp range from events if possible
        try:
            if event_ids:
                placeholders = ",".join("?" for _ in event_ids)
                cur = self._conn.execute(
                    f"SELECT MIN(timestamp_ns), MAX(timestamp_ns) "
                    f"FROM cognitive_events WHERE event_id IN ({placeholders})",
                    event_ids,
                )
                row = cur.fetchone()
                ts_range = (
                    json.dumps({"start_ns": row[0], "end_ns": row[1]})
                    if row and row[0] else None
                )
            else:
                ts_range = None
        except Exception:
            ts_range = None

        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO cognition_receipts "
                "(receipt_id, session_id, event_ids, merkle_root, merkle_proofs, "
                "timestamp_range, platform, summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt_id,
                    session_id,
                    json.dumps(event_ids),
                    merkle_root,
                    json.dumps(merkle_proofs),
                    ts_range,
                    platform,
                    summary,
                ),
            )
            self._conn.commit()
            log.info(f"Receipt {receipt_id} created for session {session_id}")
            return receipt_id
        except Exception as exc:
            log.error(f"Failed to create receipt: {exc}")
            return ""

    def get_receipt(self, receipt_id: str) -> Optional[Dict]:
        """Get a receipt by ID."""
        try:
            cur = self._conn.execute(
                "SELECT receipt_id, session_id, event_ids, merkle_root, "
                "merkle_proofs, timestamp_range, platform, summary, format, created_at "
                "FROM cognition_receipts WHERE receipt_id=?",
                (receipt_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "receipt_id": row[0],
                "session_id": row[1],
                "event_ids": json.loads(row[2]) if row[2] else [],
                "merkle_root": row[3],
                "merkle_proofs": json.loads(row[4]) if row[4] else {},
                "timestamp_range": json.loads(row[5]) if row[5] else None,
                "platform": row[6],
                "summary": row[7],
                "format": row[8],
                "created_at": row[9],
            }
        except Exception as exc:
            log.error(f"Failed to get receipt {receipt_id}: {exc}")
            return None

    def verify_receipt(self, receipt_id: str) -> Dict:
        """Load receipt, verify merkle_root matches event chain.

        Returns {"valid": bool, "receipt_id": str, "event_count": int, "merkle_root": str}
        """
        receipt = self.get_receipt(receipt_id)
        if not receipt:
            return {
                "valid": False,
                "receipt_id": receipt_id,
                "event_count": 0,
                "merkle_root": None,
                "error": "Receipt not found",
            }

        event_ids = receipt["event_ids"]
        stored_root = receipt["merkle_root"]

        # Rebuild Merkle tree from current event chain_hashes
        if not event_ids:
            return {
                "valid": stored_root is None,
                "receipt_id": receipt_id,
                "event_count": 0,
                "merkle_root": stored_root,
            }

        try:
            placeholders = ",".join("?" for _ in event_ids)
            cur = self._conn.execute(
                f"SELECT event_id, chain_hash FROM cognitive_events "
                f"WHERE event_id IN ({placeholders}) ORDER BY timestamp_ns ASC",
                event_ids,
            )
            rows = cur.fetchall()
            chain_hashes = [r[1] for r in rows if r[1]]

            if not chain_hashes:
                return {
                    "valid": False,
                    "receipt_id": receipt_id,
                    "event_count": len(event_ids),
                    "merkle_root": stored_root,
                    "error": "No chain hashes found for events",
                }

            tree = MerkleTree(chain_hashes)
            computed_root = tree.root

            return {
                "valid": computed_root == stored_root,
                "receipt_id": receipt_id,
                "event_count": len(chain_hashes),
                "merkle_root": stored_root,
                "computed_root": computed_root,
            }
        except Exception as exc:
            log.error(f"Failed to verify receipt {receipt_id}: {exc}")
            return {
                "valid": False,
                "receipt_id": receipt_id,
                "event_count": len(event_ids),
                "merkle_root": stored_root,
                "error": str(exc),
            }

    def list_receipts(self, session_id: str = None, limit: int = 20) -> List[Dict]:
        """List receipts, optionally filtered by session."""
        try:
            if session_id:
                cur = self._conn.execute(
                    "SELECT receipt_id, session_id, merkle_root, platform, summary, created_at "
                    "FROM cognition_receipts WHERE session_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (session_id, limit),
                )
            else:
                cur = self._conn.execute(
                    "SELECT receipt_id, session_id, merkle_root, platform, summary, created_at "
                    "FROM cognition_receipts ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            return [
                {
                    "receipt_id": r[0],
                    "session_id": r[1],
                    "merkle_root": r[2],
                    "platform": r[3],
                    "summary": r[4],
                    "created_at": r[5],
                }
                for r in cur.fetchall()
            ]
        except Exception as exc:
            log.error(f"Failed to list receipts: {exc}")
            return []
