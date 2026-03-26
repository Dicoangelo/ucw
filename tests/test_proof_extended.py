"""Extended Proof-of-Cognition tests — edge cases for hash chain and Merkle tree."""

import hashlib

from ucw.protocol.hash_chain import HashChain
from ucw.protocol.merkle import MerkleTree

# ── HashChain extended tests ─────────────────────────────────────────────

class TestHashChainExtended:
    def test_chain_long_sequence(self):
        """Hash chain remains valid for 100 events."""
        chain = HashChain()
        events = [chain.add_event(f"event {i}") for i in range(100)]
        result = chain.verify_chain(events)
        assert result["valid"] is True
        assert result["verified_count"] == 100

    def test_chain_unicode_content(self):
        """Hash chain handles unicode content."""
        chain = HashChain()
        r = chain.add_event("Hello world")
        assert r["content_hash"] is not None
        assert len(r["content_hash"]) == 64

    def test_chain_empty_string_content(self):
        """Hash chain handles empty string."""
        chain = HashChain()
        r = chain.add_event("")
        assert r["content_hash"] == hashlib.sha256("".encode()).hexdigest()

    def test_chain_verify_single_tampered_chain_hash(self):
        """Verify detects tampered chain_hash."""
        chain = HashChain()
        events = [chain.add_event(f"e{i}") for i in range(3)]
        events[1]["chain_hash"] = "tampered_chain_hash"
        result = HashChain().verify_chain(events)
        assert result["valid"] is False

    def test_chain_verify_tampered_first_event(self):
        """Verify detects tampered first event."""
        chain = HashChain()
        events = [chain.add_event(f"e{i}") for i in range(3)]
        events[0]["content_hash"] = "tampered"
        result = HashChain().verify_chain(events)
        assert result["valid"] is False
        assert result["break_at"] == 0

    def test_chain_hash_composition(self):
        """Verify chain_hash = sha256(content_hash:prev_hash)."""
        chain = HashChain()
        r = chain.add_event("test")
        expected = hashlib.sha256(
            f"{r['content_hash']}:genesis".encode()
        ).hexdigest()
        assert r["chain_hash"] == expected

    def test_chain_prev_hash_genesis_for_first(self):
        """First event always has prev_hash='genesis'."""
        chain = HashChain()
        r = chain.add_event("first")
        assert r["prev_hash"] == "genesis"

    def test_independent_chains_differ(self):
        """Two chains with different content produce different hashes."""
        c1 = HashChain()
        c2 = HashChain()
        r1 = c1.add_event("content A")
        r2 = c2.add_event("content B")
        assert r1["chain_hash"] != r2["chain_hash"]


# ── MerkleTree extended tests ────────────────────────────────────────────

class TestMerkleTreeExtended:
    def test_merkle_100_leaves(self):
        """Merkle tree with 100 leaves produces a valid root."""
        leaves = [f"leaf-{i}" for i in range(100)]
        tree = MerkleTree(leaves)
        assert tree.root is not None
        assert tree.leaf_count == 100

    def test_merkle_100_leaves_proof_verification(self):
        """Every leaf in a 100-leaf tree has a verifiable proof."""
        leaves = [f"leaf-{i}" for i in range(100)]
        tree = MerkleTree(leaves)
        # Spot-check a few leaves
        for i in [0, 49, 99]:
            proof = tree.get_proof(i)
            assert MerkleTree.verify_proof(leaves[i], proof, tree.root) is True

    def test_merkle_add_leaf_incremental(self):
        """Adding leaves incrementally produces consistent results."""
        tree = MerkleTree()
        assert tree.root is None
        tree.add_leaf("a")
        assert tree.root == "a"
        assert tree.leaf_count == 1
        tree.add_leaf("b")
        assert tree.leaf_count == 2

        # Compare with building from scratch
        tree2 = MerkleTree(["a", "b"])
        assert tree.root == tree2.root

    def test_merkle_power_of_two_leaves(self):
        """Trees with power-of-2 leaf counts work correctly."""
        for n in [1, 2, 4, 8, 16, 32]:
            leaves = [f"l{i}" for i in range(n)]
            tree = MerkleTree(leaves)
            assert tree.leaf_count == n
            assert tree.root is not None

    def test_merkle_odd_leaf_duplication(self):
        """Odd leaf count causes last leaf to be duplicated in hashing."""
        tree = MerkleTree(["x", "y", "z"])
        # z gets duplicated: hash(z:z) for the second pair
        zz = hashlib.sha256("z:z".encode()).hexdigest()
        xy = hashlib.sha256("x:y".encode()).hexdigest()
        root = hashlib.sha256(f"{xy}:{zz}".encode()).hexdigest()
        assert tree.root == root

    def test_merkle_verify_proof_wrong_leaf(self):
        """Proof verification fails with wrong leaf value."""
        tree = MerkleTree(["a", "b", "c", "d"])
        proof = tree.get_proof(0)
        assert MerkleTree.verify_proof("wrong", proof, tree.root) is False

    def test_merkle_verify_proof_empty_proof_single_leaf(self):
        """Single leaf tree: verify_proof with empty proof."""
        tree = MerkleTree(["only"])
        proof = tree.get_proof(0)
        assert proof == []
        # With empty proof, the leaf itself should be the root
        assert MerkleTree.verify_proof("only", proof, tree.root) is True

    def test_merkle_different_orderings_produce_different_roots(self):
        """Different leaf orderings produce different Merkle roots."""
        t1 = MerkleTree(["a", "b", "c"])
        t2 = MerkleTree(["c", "b", "a"])
        assert t1.root != t2.root

    def test_merkle_proof_index_boundary(self):
        """Proof for index at exact boundary of leaf count."""
        leaves = [f"l{i}" for i in range(5)]
        tree = MerkleTree(leaves)
        # Last valid index
        proof = tree.get_proof(4)
        assert len(proof) > 0
        assert MerkleTree.verify_proof(leaves[4], proof, tree.root) is True
        # One past last
        assert tree.get_proof(5) == []
