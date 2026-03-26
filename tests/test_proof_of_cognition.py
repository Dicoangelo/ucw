"""Tests for Proof-of-Cognition: hash chain, Merkle tree, receipts, and MCP tools."""

import hashlib
import importlib
import importlib.util
import time
from pathlib import Path

import pytest

from ucw.db.sqlite import CaptureDB

# migrations.py is shadowed by the migrations/ package, so load it directly
_mig_spec = importlib.util.spec_from_file_location(
    "ucw.db.migrations_runner",
    Path(__file__).resolve().parent.parent / "src" / "ucw" / "db" / "migrations.py",
)
_mig_mod = importlib.util.module_from_spec(_mig_spec)
_mig_spec.loader.exec_module(_mig_mod)
migrate_up = _mig_mod.migrate_up
from ucw.protocol.hash_chain import HashChain, HashChainStore  # noqa: E402
from ucw.protocol.merkle import MerkleStore, MerkleTree  # noqa: E402
from ucw.server.capture import CaptureEvent  # noqa: E402
from ucw.tools import proof_tools  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(content="test", direction="in", method="tools/call"):
    """Create a minimal CaptureEvent."""
    event = CaptureEvent(
        direction=direction,
        stage="received",
        raw_bytes=content.encode(),
        parsed={"jsonrpc": "2.0", "method": method},
        timestamp_ns=time.time_ns(),
    )
    event.data_layer = {"content": content, "tokens_est": len(content.split())}
    event.light_layer = {
        "intent": "explore",
        "topic": "testing",
        "concepts": [],
        "summary": content[:200],
    }
    event.instinct_layer = {
        "coherence_potential": 0.5,
        "emergence_indicators": [],
        "gut_signal": "routine",
    }
    return event


# ---------------------------------------------------------------------------
# HashChain unit tests
# ---------------------------------------------------------------------------

class TestHashChain:
    def test_content_hash_deterministic(self):
        chain = HashChain()
        h1 = chain.content_hash("hello")
        h2 = chain.content_hash("hello")
        assert h1 == h2

    def test_content_hash_differs_for_different_content(self):
        chain = HashChain()
        assert chain.content_hash("hello") != chain.content_hash("world")

    def test_content_hash_is_sha256(self):
        chain = HashChain()
        expected = hashlib.sha256("hello".encode("utf-8")).hexdigest()
        assert chain.content_hash("hello") == expected

    def test_chain_hash_deterministic(self):
        chain = HashChain()
        h = chain.chain_hash("abc", "def")
        expected = hashlib.sha256("abc:def".encode("utf-8")).hexdigest()
        assert h == expected

    def test_add_event_first_uses_genesis(self):
        chain = HashChain()
        result = chain.add_event("first event")
        assert result["prev_hash"] == "genesis"
        assert result["content_hash"] == chain.content_hash("first event")
        expected_chain = chain.chain_hash(result["content_hash"], "genesis")
        assert result["chain_hash"] == expected_chain

    def test_add_event_sequence_links(self):
        chain = HashChain()
        r1 = chain.add_event("event one")
        r2 = chain.add_event("event two")
        # Second event's prev_hash should be first event's chain_hash
        assert r2["prev_hash"] == r1["chain_hash"]

    def test_add_event_three_events(self):
        chain = HashChain()
        r1 = chain.add_event("a")
        r2 = chain.add_event("b")
        r3 = chain.add_event("c")
        assert r2["prev_hash"] == r1["chain_hash"]
        assert r3["prev_hash"] == r2["chain_hash"]

    def test_verify_chain_valid(self):
        chain = HashChain()
        events = [chain.add_event(f"event {i}") for i in range(5)]
        result = chain.verify_chain(events)
        assert result["valid"] is True
        assert result["verified_count"] == 5
        assert result["break_at"] is None
        assert result["errors"] == []

    def test_verify_chain_empty(self):
        chain = HashChain()
        result = chain.verify_chain([])
        assert result["valid"] is True
        assert result["verified_count"] == 0

    def test_verify_chain_single_event(self):
        chain = HashChain()
        events = [chain.add_event("only")]
        result = chain.verify_chain(events)
        assert result["valid"] is True
        assert result["verified_count"] == 1

    def test_verify_chain_detects_tampered_content_hash(self):
        chain = HashChain()
        events = [chain.add_event(f"event {i}") for i in range(3)]
        # Tamper with event 1's content_hash
        events[1]["content_hash"] = "tampered"
        verifier = HashChain()
        result = verifier.verify_chain(events)
        assert result["valid"] is False
        assert result["break_at"] == 1

    def test_verify_chain_detects_broken_link(self):
        chain = HashChain()
        events = [chain.add_event(f"event {i}") for i in range(3)]
        # Break the link: change event 2's prev_hash
        events[2]["prev_hash"] = "wrong"
        # Also need to recompute chain_hash for it to pass chain_hash check
        events[2]["chain_hash"] = chain.chain_hash(events[2]["content_hash"], "wrong")
        verifier = HashChain()
        result = verifier.verify_chain(events)
        assert result["valid"] is False
        assert result["break_at"] == 2


# ---------------------------------------------------------------------------
# HashChainStore tests
# ---------------------------------------------------------------------------

class TestHashChainStore:
    @pytest.fixture
    async def db_and_conn(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "poc_chain_test.db")
        await db.initialize()
        migrate_up(db._conn)
        yield db, db._conn
        await db.close()

    @pytest.mark.asyncio
    async def test_update_event_hashes(self, db_and_conn):
        db, conn = db_and_conn
        event = _make_event("chain test")
        await db.store_event(event)

        store = HashChainStore(conn)
        ok = store.update_event_hashes(event.event_id, "ch", "ph", "chh")
        assert ok is True

        cur = conn.execute(
            "SELECT content_hash, prev_hash, chain_hash FROM cognitive_events WHERE event_id=?",
            (event.event_id,),
        )
        row = cur.fetchone()
        assert row == ("ch", "ph", "chh")

    @pytest.mark.asyncio
    async def test_get_last_chain_hash_genesis(self, db_and_conn):
        db, conn = db_and_conn
        store = HashChainStore(conn)
        assert store.get_last_chain_hash("nonexistent") == "genesis"

    @pytest.mark.asyncio
    async def test_get_last_chain_hash_returns_latest(self, db_and_conn):
        db, conn = db_and_conn
        chain = HashChain()
        # Store two events with hashes
        for i in range(2):
            event = _make_event(f"content {i}")
            await db.store_event(event)
            hashes = chain.add_event(f"content {i}")
            store = HashChainStore(conn)
            store.update_event_hashes(
                event.event_id, hashes["content_hash"],
                hashes["prev_hash"], hashes["chain_hash"],
            )

        result = store.get_last_chain_hash(db.session_id)
        assert result != "genesis"
        assert len(result) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_get_chain_events(self, db_and_conn):
        db, conn = db_and_conn
        chain = HashChain()
        store = HashChainStore(conn)

        for i in range(3):
            event = _make_event(f"chain event {i}")
            await db.store_event(event)
            hashes = chain.add_event(f"chain event {i}")
            store.update_event_hashes(
                event.event_id, hashes["content_hash"],
                hashes["prev_hash"], hashes["chain_hash"],
            )

        events = store.get_chain_events(db.session_id)
        assert len(events) == 3
        assert events[0]["prev_hash"] == "genesis"

    @pytest.mark.asyncio
    async def test_verify_session_chain_valid(self, db_and_conn):
        db, conn = db_and_conn
        chain = HashChain()
        store = HashChainStore(conn)

        for i in range(4):
            event = _make_event(f"verify event {i}")
            await db.store_event(event)
            hashes = chain.add_event(f"verify event {i}")
            store.update_event_hashes(
                event.event_id, hashes["content_hash"],
                hashes["prev_hash"], hashes["chain_hash"],
            )

        result = store.verify_session_chain(db.session_id)
        assert result["valid"] is True
        assert result["verified_count"] == 4
        assert result["session_id"] == db.session_id

    @pytest.mark.asyncio
    async def test_verify_session_chain_empty(self, db_and_conn):
        db, conn = db_and_conn
        store = HashChainStore(conn)
        result = store.verify_session_chain("empty-session")
        assert result["valid"] is True
        assert result["verified_count"] == 0


# ---------------------------------------------------------------------------
# MerkleTree unit tests
# ---------------------------------------------------------------------------

class TestMerkleTree:
    def test_empty_tree(self):
        tree = MerkleTree()
        assert tree.root is None
        assert tree.leaf_count == 0

    def test_single_leaf(self):
        tree = MerkleTree(["abc123"])
        assert tree.root == "abc123"
        assert tree.leaf_count == 1

    def test_two_leaves(self):
        tree = MerkleTree(["a", "b"])
        expected = hashlib.sha256("a:b".encode("utf-8")).hexdigest()
        assert tree.root == expected
        assert tree.leaf_count == 2

    def test_three_leaves_odd_duplication(self):
        tree = MerkleTree(["a", "b", "c"])
        # Level 0: [a, b, c]
        # Level 1: [hash(a:b), hash(c:c)]
        # Level 2: [hash(level1[0]:level1[1])]
        ab = hashlib.sha256("a:b".encode("utf-8")).hexdigest()
        cc = hashlib.sha256("c:c".encode("utf-8")).hexdigest()
        root = hashlib.sha256(f"{ab}:{cc}".encode("utf-8")).hexdigest()
        assert tree.root == root

    def test_seven_leaves(self):
        leaves = [f"leaf{i}" for i in range(7)]
        tree = MerkleTree(leaves)
        assert tree.root is not None
        assert tree.leaf_count == 7

    def test_eight_leaves(self):
        leaves = [f"leaf{i}" for i in range(8)]
        tree = MerkleTree(leaves)
        assert tree.root is not None
        assert tree.leaf_count == 8

    def test_sixteen_leaves(self):
        leaves = [f"leaf{i}" for i in range(16)]
        tree = MerkleTree(leaves)
        assert tree.root is not None
        assert tree.leaf_count == 16

    def test_add_leaf(self):
        tree = MerkleTree(["a"])
        assert tree.root == "a"
        tree.add_leaf("b")
        assert tree.leaf_count == 2
        expected = hashlib.sha256("a:b".encode("utf-8")).hexdigest()
        assert tree.root == expected

    def test_get_proof_and_verify_two_leaves(self):
        tree = MerkleTree(["a", "b"])
        proof = tree.get_proof(0)
        assert len(proof) == 1
        assert proof[0]["hash"] == "b"
        assert proof[0]["position"] == "right"
        assert MerkleTree.verify_proof("a", proof, tree.root) is True

    def test_get_proof_and_verify_all_leaves(self):
        leaves = [f"leaf{i}" for i in range(8)]
        tree = MerkleTree(leaves)
        for i in range(8):
            proof = tree.get_proof(i)
            assert MerkleTree.verify_proof(leaves[i], proof, tree.root) is True

    def test_proof_fails_wrong_root(self):
        tree = MerkleTree(["a", "b", "c"])
        proof = tree.get_proof(0)
        assert MerkleTree.verify_proof("a", proof, "wrongroot") is False

    def test_proof_fails_wrong_leaf(self):
        tree = MerkleTree(["a", "b", "c"])
        proof = tree.get_proof(0)
        assert MerkleTree.verify_proof("tampered", proof, tree.root) is False

    def test_get_proof_invalid_index(self):
        tree = MerkleTree(["a", "b"])
        assert tree.get_proof(-1) == []
        assert tree.get_proof(5) == []

    def test_get_proof_single_leaf_returns_empty(self):
        tree = MerkleTree(["only"])
        # Single leaf tree has no siblings to prove against
        proof = tree.get_proof(0)
        assert proof == []

    def test_deterministic_root(self):
        leaves = ["x", "y", "z"]
        t1 = MerkleTree(leaves)
        t2 = MerkleTree(leaves)
        assert t1.root == t2.root


# ---------------------------------------------------------------------------
# MerkleStore tests
# ---------------------------------------------------------------------------

class TestMerkleStore:
    @pytest.fixture
    async def db_and_conn(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "poc_merkle_test.db")
        await db.initialize()
        migrate_up(db._conn)
        yield db, db._conn
        await db.close()

    @pytest.mark.asyncio
    async def test_update_session_merkle(self, db_and_conn):
        db, conn = db_and_conn
        store = MerkleStore(conn)
        ok = store.update_session_merkle(db.session_id, "root123")
        assert ok is True

        cur = conn.execute(
            "SELECT merkle_root FROM sessions WHERE session_id=?",
            (db.session_id,),
        )
        assert cur.fetchone()[0] == "root123"

    @pytest.mark.asyncio
    async def test_create_and_get_receipt(self, db_and_conn):
        db, conn = db_and_conn
        store = MerkleStore(conn)

        receipt_id = store.create_receipt(
            session_id=db.session_id,
            event_ids=["e1", "e2"],
            merkle_root="rootABC",
            merkle_proofs={"e1": [{"hash": "x", "position": "right"}]},
            platform="test",
            summary="Test receipt",
        )
        assert receipt_id != ""
        assert len(receipt_id) == 16

        receipt = store.get_receipt(receipt_id)
        assert receipt is not None
        assert receipt["session_id"] == db.session_id
        assert receipt["event_ids"] == ["e1", "e2"]
        assert receipt["merkle_root"] == "rootABC"
        assert receipt["platform"] == "test"
        assert receipt["summary"] == "Test receipt"

    @pytest.mark.asyncio
    async def test_get_receipt_not_found(self, db_and_conn):
        _, conn = db_and_conn
        store = MerkleStore(conn)
        assert store.get_receipt("nonexistent") is None

    @pytest.mark.asyncio
    async def test_verify_receipt_valid(self, db_and_conn):
        db, conn = db_and_conn
        chain = HashChain()
        chain_store = HashChainStore(conn)

        # Store events with chain hashes
        event_ids = []
        for i in range(3):
            event = _make_event(f"merkle verify {i}")
            await db.store_event(event)
            hashes = chain.add_event(f"merkle verify {i}")
            chain_store.update_event_hashes(
                event.event_id, hashes["content_hash"],
                hashes["prev_hash"], hashes["chain_hash"],
            )
            event_ids.append(event.event_id)

        # Build Merkle tree
        chain_events = chain_store.get_chain_events(db.session_id)
        chain_hashes = [e["chain_hash"] for e in chain_events]
        tree = MerkleTree(chain_hashes)

        store = MerkleStore(conn)
        receipt_id = store.create_receipt(
            session_id=db.session_id,
            event_ids=event_ids,
            merkle_root=tree.root,
            merkle_proofs={},
            platform="test",
        )

        result = store.verify_receipt(receipt_id)
        assert result["valid"] is True
        assert result["event_count"] == 3

    @pytest.mark.asyncio
    async def test_verify_receipt_not_found(self, db_and_conn):
        _, conn = db_and_conn
        store = MerkleStore(conn)
        result = store.verify_receipt("nope")
        assert result["valid"] is False
        assert "not found" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_list_receipts(self, db_and_conn):
        db, conn = db_and_conn
        store = MerkleStore(conn)

        store.create_receipt(
            session_id=db.session_id, event_ids=["a"],
            merkle_root="r1", merkle_proofs={}, platform="test",
        )

        receipts = store.list_receipts()
        assert len(receipts) >= 1
        assert receipts[0]["session_id"] == db.session_id

    @pytest.mark.asyncio
    async def test_list_receipts_by_session(self, db_and_conn):
        db, conn = db_and_conn
        store = MerkleStore(conn)

        store.create_receipt(
            session_id=db.session_id, event_ids=["a"],
            merkle_root="r1", merkle_proofs={}, platform="test",
        )

        receipts = store.list_receipts(session_id=db.session_id)
        assert len(receipts) >= 1

        receipts_other = store.list_receipts(session_id="other-session")
        assert len(receipts_other) == 0

    @pytest.mark.asyncio
    async def test_duplicate_receipt_replaces(self, db_and_conn):
        db, conn = db_and_conn
        store = MerkleStore(conn)

        rid1 = store.create_receipt(
            session_id=db.session_id, event_ids=["a"],
            merkle_root="r1", merkle_proofs={}, platform="test",
            summary="first",
        )
        rid2 = store.create_receipt(
            session_id=db.session_id, event_ids=["a", "b"],
            merkle_root="r1", merkle_proofs={}, platform="test",
            summary="second",
        )
        # Same session + merkle_root = same receipt_id
        assert rid1 == rid2
        receipt = store.get_receipt(rid1)
        assert receipt["summary"] == "second"
        assert receipt["event_ids"] == ["a", "b"]


# ---------------------------------------------------------------------------
# proof_tools MCP handler tests
# ---------------------------------------------------------------------------

class TestProofTools:
    @pytest.fixture
    async def db(self, tmp_ucw_dir):
        db = CaptureDB(db_path=tmp_ucw_dir / "poc_tools_test.db")
        await db.initialize()
        migrate_up(db._conn)
        proof_tools.set_db(db)
        yield db
        proof_tools.set_db(None)
        await db.close()

    async def _store_chained_events(self, db, count=5):
        """Store events with full hash chain."""
        chain = HashChain()
        chain_store = HashChainStore(db._conn)
        event_ids = []
        for i in range(count):
            event = _make_event(f"tool test event {i}")
            await db.store_event(event)
            hashes = chain.add_event(f"tool test event {i}")
            chain_store.update_event_hashes(
                event.event_id, hashes["content_hash"],
                hashes["prev_hash"], hashes["chain_hash"],
            )
            event_ids.append(event.event_id)
        return event_ids

    # -- verify_chain --

    @pytest.mark.asyncio
    async def test_verify_chain_no_db(self):
        proof_tools.set_db(None)
        result = await proof_tools.handle_tool("verify_chain", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_verify_chain_valid(self, db):
        await self._store_chained_events(db, 3)
        result = await proof_tools.handle_tool("verify_chain", {})
        text = result["content"][0]["text"]
        assert "VALID" in text
        assert "3" in text

    @pytest.mark.asyncio
    async def test_verify_chain_with_session_id(self, db):
        await self._store_chained_events(db, 2)
        result = await proof_tools.handle_tool(
            "verify_chain", {"session_id": db.session_id}
        )
        text = result["content"][0]["text"]
        assert "VALID" in text

    # -- generate_receipt --

    @pytest.mark.asyncio
    async def test_generate_receipt_no_db(self):
        proof_tools.set_db(None)
        result = await proof_tools.handle_tool("generate_receipt", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_generate_receipt_no_events(self, db):
        result = await proof_tools.handle_tool("generate_receipt", {})
        text = result["content"][0]["text"]
        assert "No chain events" in text

    @pytest.mark.asyncio
    async def test_generate_receipt_success(self, db):
        await self._store_chained_events(db, 4)
        result = await proof_tools.handle_tool(
            "generate_receipt", {"summary": "Test session"}
        )
        text = result["content"][0]["text"]
        assert "Receipt" in text
        assert "4" in text
        assert "Merkle Root" in text
        assert "Test session" in text

    # -- verify_receipt --

    @pytest.mark.asyncio
    async def test_verify_receipt_no_db(self):
        proof_tools.set_db(None)
        result = await proof_tools.handle_tool(
            "verify_receipt", {"receipt_id": "abc"}
        )
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_verify_receipt_missing_id(self, db):
        result = await proof_tools.handle_tool("verify_receipt", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_verify_receipt_not_found(self, db):
        result = await proof_tools.handle_tool(
            "verify_receipt", {"receipt_id": "nonexistent"}
        )
        text = result["content"][0]["text"]
        assert "INVALID" in text

    @pytest.mark.asyncio
    async def test_verify_receipt_roundtrip(self, db):
        await self._store_chained_events(db, 3)
        # Generate
        gen_result = await proof_tools.handle_tool("generate_receipt", {})
        gen_text = gen_result["content"][0]["text"]
        # Extract receipt_id from markdown table
        for line in gen_text.split("\n"):
            if "Receipt ID" in line and "`" in line:
                receipt_id = line.split("`")[1]
                break
        # Verify
        ver_result = await proof_tools.handle_tool(
            "verify_receipt", {"receipt_id": receipt_id}
        )
        ver_text = ver_result["content"][0]["text"]
        assert "VALID" in ver_text

    # -- proof_status --

    @pytest.mark.asyncio
    async def test_proof_status_no_db(self):
        proof_tools.set_db(None)
        result = await proof_tools.handle_tool("proof_status", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_proof_status_empty(self, db):
        result = await proof_tools.handle_tool("proof_status", {})
        text = result["content"][0]["text"]
        assert "Proof-of-Cognition Status" in text
        assert "Chain Length" in text

    @pytest.mark.asyncio
    async def test_proof_status_with_data(self, db):
        await self._store_chained_events(db, 5)
        await proof_tools.handle_tool("generate_receipt", {})
        result = await proof_tools.handle_tool("proof_status", {})
        text = result["content"][0]["text"]
        assert "5" in text  # chain length
        assert "VALID" in text

    # -- unknown tool --

    @pytest.mark.asyncio
    async def test_unknown_tool(self, db):
        result = await proof_tools.handle_tool("nonexistent", {})
        assert result.get("isError") is True
        assert "Unknown" in result["content"][0]["text"]
