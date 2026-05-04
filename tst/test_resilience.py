import unittest
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from src.blockchain import Block, Node, Transaction, compute_block_hash
from src.blockchain.core import make_genesis_block

def simple_signature_verifier(tx: Transaction) -> bool:
    return bool(tx.voter_public_key and tx.signature)

class ResilienceTests(unittest.TestCase):
    def test_tampered_block(self) -> None:
        n1 = Node("n1", difficulty_prefix="0", signature_verifier=simple_signature_verifier)
        tx = Transaction(
            voter_public_key="alice",
            timestamp=100.0,
            candidate_id="c1",
            signature="sig:alice",
            metadata={},
        )
        self.assertTrue(n1.submit_transaction(tx)[0])
        b = n1.mine_once()
        self.assertIsNotNone(b)
        tampered = Block(
            b.index,
            b.timestamp,
            Transaction("alice", 100.0, "STOLEN", "sig:alice", {}),
            b.previous_hash,
            b.nonce,
            b.hash,
        )
        n2 = Node("n2", difficulty_prefix="0", signature_verifier=simple_signature_verifier)
        ok, reason = n2.receive_block(tampered)
        self.assertFalse(ok)
        self.assertIn("hash mismatch", reason)

    def test_bad_previous_hash(self) -> None:
        n1 = Node("n1", difficulty_prefix="0", signature_verifier=simple_signature_verifier)
        self.assertTrue(n1.submit_transaction(Transaction("alice", 100.0, "c1", "sig:alice", {}))[0])
        self.assertIsNotNone(n1.mine_once())
        tx2 = Transaction("bob", 101.0, "c1", "sig:bob", {})
        tmp = Block(2, 101.0, tx2, "0" * 64, 0, "")
        h2 = compute_block_hash(tmp)
        bad_prev = Block(2, 101.0, tx2, "0" * 64, 0, h2)
        ok, reason = n1.receive_block(bad_prev)
        self.assertFalse(ok)
        self.assertIn("bad previous_hash", reason)

    def test_bad_index(self) -> None:
        n1 = Node("n1", difficulty_prefix="0", signature_verifier=simple_signature_verifier)
        self.assertTrue(n1.submit_transaction(Transaction("alice", 100.0, "c1", "sig:alice", {}))[0])
        self.assertIsNotNone(n1.mine_once())
        parent = n1.blockchain.tip
        body = Transaction("carol", 102.0, "c1", "sig:carol", {})
        tmp3 = Block(99, 102.0, body, parent.hash, 0, "")
        h3 = compute_block_hash(tmp3)
        bad_idx = Block(99, 102.0, body, parent.hash, 0, h3)
        ok, reason = n1.receive_block(bad_idx)
        self.assertFalse(ok)
        self.assertIn("bad index", reason)

    def test_invalid_signature(self) -> None:
        n = Node("n3", difficulty_prefix="0", signature_verifier=lambda t: False)
        tx = Transaction("d", 1.0, "c", "x", {})
        ok, reason = n.submit_transaction(tx)
        self.assertFalse(ok)
        self.assertIn("invalid signature", reason)

    def test_bad_genesis(self) -> None:
        n = Node("z", difficulty_prefix="0", signature_verifier=simple_signature_verifier)
        gen = make_genesis_block()
        wrong_gen = Block(gen.index, gen.timestamp, gen.transaction, gen.previous_hash, gen.nonce, "0" * 64)
        ok, reason = n.receive_chain([wrong_gen])
        self.assertFalse(ok)
        self.assertIn("bad genesis", reason)

if __name__ == "__main__":
    unittest.main()