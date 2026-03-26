"""
Proof-of-Cognition Tools — MCP tools for cryptographic proof generation and verification

Tools:
  verify_chain      -- Verify the hash chain integrity for a session
  generate_receipt  -- Generate a cryptographic proof-of-cognition receipt
  verify_receipt    -- Verify a previously generated receipt
  proof_status      -- Show proof-of-cognition status: chain length, receipts, integrity
"""

import json
from typing import Any, Dict, List

from ucw.server.logger import get_logger
from ucw.server.protocol import text_content, tool_result_content

log = get_logger("tools.proof")

_db = None


def set_db(db):
    """Called by server to inject shared database instance."""
    global _db
    _db = db
    log.info("Proof tools: DB injected")


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "verify_chain",
        "description": (
            "Verify the hash chain integrity for a session. "
            "Checks that every cognitive event links correctly to its predecessor, "
            "detecting any tampering or data corruption."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID to verify (defaults to current session)",
                },
            },
        },
    },
    {
        "name": "generate_receipt",
        "description": (
            "Generate a cryptographic proof-of-cognition receipt for a session. "
            "Builds a Merkle tree over event chain hashes and stores the receipt."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID (defaults to current session)",
                },
                "summary": {
                    "type": "string",
                    "description": "Optional human-readable summary for the receipt",
                },
            },
        },
    },
    {
        "name": "verify_receipt",
        "description": (
            "Verify a previously generated proof-of-cognition receipt. "
            "Rebuilds the Merkle tree from current events and compares roots."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "receipt_id": {
                    "type": "string",
                    "description": "Receipt ID to verify",
                },
            },
            "required": ["receipt_id"],
        },
    },
    {
        "name": "proof_status",
        "description": (
            "Show proof-of-cognition status: chain length, receipts generated, "
            "integrity check, and Merkle root for the current session."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


async def handle_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    handlers = {
        "verify_chain": _verify_chain,
        "generate_receipt": _generate_receipt,
        "verify_receipt": _verify_receipt,
        "proof_status": _proof_status,
    }

    handler = handlers.get(name)
    if not handler:
        return tool_result_content(
            [text_content(f"Unknown proof tool: {name}")], is_error=True
        )

    try:
        return await handler(args)
    except Exception as exc:
        log.error(f"Tool {name} failed: {exc}", exc_info=True)
        return tool_result_content(
            [text_content(f"Error in {name}: {exc}")], is_error=True
        )


async def _verify_chain(args: Dict) -> Dict:
    if not _db or not _db._conn:
        return tool_result_content(
            [text_content("Database not initialized. The UCW server may still be starting up — try again in a moment, or run `ucw doctor` to diagnose.")], is_error=True
        )

    from ucw.protocol.hash_chain import HashChainStore

    session_id = args.get("session_id") or _db.session_id
    if not session_id:
        return tool_result_content(
            [text_content("No session ID available.")], is_error=True
        )

    store = HashChainStore(_db._conn)
    result = store.verify_session_chain(session_id)

    status = "VALID" if result["valid"] else "BROKEN"
    out = f"# Chain Verification: {status}\n\n"
    out += f"| Field | Value |\n|-------|-------|\n"
    out += f"| Session | `{session_id}` |\n"
    out += f"| Events Verified | {result['verified_count']} |\n"
    out += f"| Chain Valid | {result['valid']} |\n"

    if result.get("break_at") is not None:
        out += f"| Break At Event | {result['break_at']} |\n"

    if result.get("errors"):
        out += "\n## Errors\n\n"
        for err in result["errors"]:
            out += f"- {err}\n"

    return tool_result_content([text_content(out)])


async def _generate_receipt(args: Dict) -> Dict:
    if not _db or not _db._conn:
        return tool_result_content(
            [text_content("Database not initialized. The UCW server may still be starting up — try again in a moment, or run `ucw doctor` to diagnose.")], is_error=True
        )

    from ucw.protocol.hash_chain import HashChainStore
    from ucw.protocol.merkle import MerkleStore, MerkleTree

    session_id = args.get("session_id") or _db.session_id
    summary = args.get("summary")

    if not session_id:
        return tool_result_content(
            [text_content("No session ID available.")], is_error=True
        )

    chain_store = HashChainStore(_db._conn)
    events = chain_store.get_chain_events(session_id)

    if not events:
        return tool_result_content(
            [text_content(f"No chain events found for session `{session_id}`. "
                          "Events must be hashed before generating a receipt.")]
        )

    # Build Merkle tree from chain hashes
    chain_hashes = [e["chain_hash"] for e in events]
    tree = MerkleTree(chain_hashes)
    merkle_root = tree.root

    # Generate proofs for all leaves
    proofs = {}
    for i, event in enumerate(events):
        proofs[event["event_id"]] = tree.get_proof(i)

    # Store
    merkle_store = MerkleStore(_db._conn)
    merkle_store.update_session_merkle(session_id, merkle_root)

    event_ids = [e["event_id"] for e in events]
    platform = "mcp"
    try:
        cur = _db._conn.execute(
            "SELECT platform FROM sessions WHERE session_id=?", (session_id,)
        )
        row = cur.fetchone()
        if row:
            platform = row[0] or "mcp"
    except Exception:
        pass

    receipt_id = merkle_store.create_receipt(
        session_id=session_id,
        event_ids=event_ids,
        merkle_root=merkle_root,
        merkle_proofs=proofs,
        platform=platform,
        summary=summary,
    )

    out = f"# Proof-of-Cognition Receipt Generated\n\n"
    out += f"| Field | Value |\n|-------|-------|\n"
    out += f"| Receipt ID | `{receipt_id}` |\n"
    out += f"| Session | `{session_id}` |\n"
    out += f"| Events | {len(events)} |\n"
    out += f"| Merkle Root | `{merkle_root[:32]}...` |\n"
    out += f"| Platform | {platform} |\n"

    if summary:
        out += f"\n**Summary:** {summary}\n"

    return tool_result_content([text_content(out)])


async def _verify_receipt(args: Dict) -> Dict:
    if not _db or not _db._conn:
        return tool_result_content(
            [text_content("Database not initialized. The UCW server may still be starting up — try again in a moment, or run `ucw doctor` to diagnose.")], is_error=True
        )

    from ucw.protocol.merkle import MerkleStore

    receipt_id = args.get("receipt_id")
    if not receipt_id:
        return tool_result_content(
            [text_content("receipt_id is required.")], is_error=True
        )

    store = MerkleStore(_db._conn)
    result = store.verify_receipt(receipt_id)

    status = "VALID" if result["valid"] else "INVALID"
    out = f"# Receipt Verification: {status}\n\n"
    out += f"| Field | Value |\n|-------|-------|\n"
    out += f"| Receipt ID | `{result['receipt_id']}` |\n"
    out += f"| Event Count | {result['event_count']} |\n"
    out += f"| Merkle Root | `{(result.get('merkle_root') or 'N/A')[:32]}` |\n"
    out += f"| Valid | {result['valid']} |\n"

    if result.get("error"):
        out += f"\n**Error:** {result['error']}\n"

    return tool_result_content([text_content(out)])


async def _proof_status(args: Dict) -> Dict:
    if not _db or not _db._conn:
        return tool_result_content(
            [text_content("Database not initialized. The UCW server may still be starting up — try again in a moment, or run `ucw doctor` to diagnose.")], is_error=True
        )

    from ucw.protocol.hash_chain import HashChainStore
    from ucw.protocol.merkle import MerkleStore

    session_id = _db.session_id
    conn = _db._conn

    # Chain stats
    chain_store = HashChainStore(conn)
    events = chain_store.get_chain_events(session_id) if session_id else []
    chain_result = chain_store.verify_session_chain(session_id) if session_id else {
        "valid": True, "verified_count": 0
    }

    # Receipt stats
    merkle_store = MerkleStore(conn)
    all_receipts = merkle_store.list_receipts(limit=100)
    session_receipts = merkle_store.list_receipts(session_id=session_id) if session_id else []

    # Session merkle root
    merkle_root = None
    if session_id:
        try:
            cur = conn.execute(
                "SELECT merkle_root FROM sessions WHERE session_id=?", (session_id,)
            )
            row = cur.fetchone()
            if row:
                merkle_root = row[0]
        except Exception:
            pass

    # Total chained events across all sessions
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM cognitive_events WHERE chain_hash IS NOT NULL"
        )
        total_chained = cur.fetchone()[0]
    except Exception:
        total_chained = 0

    chain_status = "VALID" if chain_result.get("valid", True) else "BROKEN"

    out = "# Proof-of-Cognition Status\n\n"
    out += "## Current Session\n\n"
    out += f"| Field | Value |\n|-------|-------|\n"
    out += f"| Session ID | `{session_id or 'N/A'}` |\n"
    out += f"| Chain Length | {len(events)} |\n"
    out += f"| Chain Integrity | {chain_status} |\n"
    out += f"| Merkle Root | `{(merkle_root or 'not yet generated')[:32]}` |\n"
    out += f"| Session Receipts | {len(session_receipts)} |\n\n"

    out += "## Global Stats\n\n"
    out += f"| Field | Value |\n|-------|-------|\n"
    out += f"| Total Chained Events | {total_chained} |\n"
    out += f"| Total Receipts | {len(all_receipts)} |\n"

    if session_receipts:
        out += "\n## Recent Receipts\n\n"
        for r in session_receipts[:5]:
            out += (
                f"- `{r['receipt_id']}` | "
                f"root=`{(r.get('merkle_root') or '')[:16]}...` | "
                f"{r.get('created_at', '')}\n"
            )

    return tool_result_content([text_content(out)])
