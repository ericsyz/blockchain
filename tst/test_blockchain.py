import time
import unittest
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from src.blockchain import Block, Node, Transaction, compute_block_hash


def mk_tx(voter: str, candidate: str, ts: float | None = None) -> Transaction:
    return Transaction(
        voter_public_key=voter,
        timestamp=time.time() if ts is None else ts,
        candidate_id=candidate,
        signature=f"sig:{voter}",
        metadata={},
    )


class BlockchainTests(unittest.TestCase):
    def test_add_transaction_and_mine_one_tx_per_block(self) -> None:
        node = Node("n1", difficulty_prefix="0")
        tx = mk_tx("alice", "c1")
        ok, _ = node.submit_transaction(tx)
        self.assertTrue(ok)
        mined = node.mine_once()
        self.assertIsNotNone(mined)
        self.assertEqual(node.height(), 1)
        self.assertTrue(node.contains_tx(tx))

    def test_duplicate_tx_rejected(self) -> None:
        node = Node("n1", difficulty_prefix="0")
        tx = mk_tx("alice", "c1", ts=1000.0)
        ok1, _ = node.submit_transaction(tx)
        ok2, _ = node.submit_transaction(tx)
        self.assertTrue(ok1)
        self.assertFalse(ok2)

    def test_one_vote_per_voter_enforced(self) -> None:
        node = Node("n1", difficulty_prefix="0")
        tx1 = mk_tx("alice", "c1")
        tx2 = mk_tx("alice", "c2")
        self.assertTrue(node.submit_transaction(tx1)[0])
        node.mine_once()
        self.assertFalse(node.submit_transaction(tx2)[0])

    def test_longest_chain_adopted(self) -> None:
        n1 = Node("n1", difficulty_prefix="0")
        n2 = Node("n2", difficulty_prefix="0")

        self.assertTrue(n1.submit_transaction(mk_tx("a", "c1"))[0])
        self.assertTrue(n2.submit_transaction(mk_tx("b", "c1"))[0])
        self.assertTrue(n2.submit_transaction(mk_tx("c", "c1"))[0])

        b1 = n1.mine_once()
        self.assertIsNotNone(b1)
        b2a = n2.mine_once()
        b2b = n2.mine_once()
        self.assertIsNotNone(b2a)
        self.assertIsNotNone(b2b)

        self.assertEqual(n1.height(), 1)
        self.assertEqual(n2.height(), 2)

        ok, _ = n1.receive_chain(n2.blockchain.chain)
        self.assertTrue(ok)
        self.assertEqual(n1.height(), 2)

    def test_receive_invalid_pow_block_rejected(self) -> None:
        node = Node("n1", difficulty_prefix="00")
        tx = mk_tx("alice", "c1", ts=111.0)
        node.submit_transaction(tx)

        parent = node.blockchain.tip
        invalid = Block(
            index=1,
            timestamp=111.0,
            transaction=tx,
            previous_hash=parent.hash,
            nonce=0,
            hash="deadbeef",
        )
        ok, _ = node.receive_block(invalid)
        self.assertFalse(ok)

    def test_mine_once_returns_none_for_empty_mempool(self) -> None:
        node = Node("n1", difficulty_prefix="0")
        self.assertIsNone(node.mine_once())
        self.assertEqual(node.height(), 0)

    def test_mining_uses_deterministic_mempool_order(self) -> None:
        node = Node("n1", difficulty_prefix="0")
        # Same timestamp; voter key should break ties lexicographically.
        tx_b = mk_tx("bob", "c2", ts=100.0)
        tx_a = mk_tx("alice", "c1", ts=100.0)
        node.submit_transaction(tx_b)
        node.submit_transaction(tx_a)

        mined = node.mine_once()
        self.assertIsNotNone(mined)
        self.assertEqual(mined.transaction.voter_public_key, "alice")

    def test_shorter_or_equal_chain_not_adopted(self) -> None:
        n1 = Node("n1", difficulty_prefix="0")
        n2 = Node("n2", difficulty_prefix="0")
        n1.submit_transaction(mk_tx("alice", "c1"))
        n2.submit_transaction(mk_tx("bob", "c1"))
        n1.mine_once()
        n2.mine_once()
        self.assertEqual(n1.height(), n2.height())

        ok, reason = n1.receive_chain(n2.blockchain.chain)
        self.assertFalse(ok)
        self.assertIn("not longer", reason)

    def test_longer_chain_with_duplicate_voter_rejected(self) -> None:
        node = Node("n1", difficulty_prefix="")
        genesis = node.blockchain.chain[0]

        tx1 = mk_tx("alice", "c1", ts=10.0)
        b1_tmp = Block(
            index=1,
            timestamp=10.0,
            transaction=tx1,
            previous_hash=genesis.hash,
            nonce=0,
            hash="",
        )
        b1 = Block(**{**b1_tmp.__dict__, "hash": compute_block_hash(b1_tmp)})

        # Duplicate voter "alice" in block 2 to violate chain invariants.
        tx2 = mk_tx("alice", "c2", ts=11.0)
        b2_tmp = Block(
            index=2,
            timestamp=11.0,
            transaction=tx2,
            previous_hash=b1.hash,
            nonce=0,
            hash="",
        )
        b2 = Block(**{**b2_tmp.__dict__, "hash": compute_block_hash(b2_tmp)})

        ok, reason = node.receive_chain([genesis, b1, b2])
        self.assertFalse(ok)
        self.assertIn("double vote", reason)


if __name__ == "__main__":
    unittest.main()
