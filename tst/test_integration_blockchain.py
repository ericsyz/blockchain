import pathlib
import random
import sys
import time
import unittest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from src.blockchain import Node, Transaction


def mk_tx(voter: str, candidate: str, ts: float | None = None) -> Transaction:
    return Transaction(
        voter_public_key=voter,
        timestamp=time.time() if ts is None else ts,
        candidate_id=candidate,
        signature=f"sig:{voter}",
        metadata={},
    )


class BlockchainIntegrationTests(unittest.TestCase):
    def test_three_node_eventual_convergence_after_fork(self) -> None:
        # Low difficulty for fast tests.
        n1 = Node("n1", difficulty_prefix="0")
        n2 = Node("n2", difficulty_prefix="0")
        n3 = Node("n3", difficulty_prefix="0")
        nodes = [n1, n2, n3]

        # All nodes receive two transactions.
        tx_a = mk_tx("alice", "c1", ts=100.0)
        tx_b = mk_tx("bob", "c2", ts=101.0)
        for n in nodes:
            self.assertTrue(n.submit_transaction(tx_a)[0])
            self.assertTrue(n.submit_transaction(tx_b)[0])

        # Simulate network delay: n1 and n2 mine independently before seeing each other's block.
        b1 = n1.mine_once()
        b2 = n2.mine_once()
        self.assertIsNotNone(b1)
        self.assertIsNotNone(b2)
        self.assertEqual(n1.height(), 1)
        self.assertEqual(n2.height(), 1)

        # n3 receives one branch first.
        n3.receive_block(b1)
        self.assertEqual(n3.height(), 1)

        # n2 mines another block on top of its own branch, making it longer.
        # Add one more tx so n2 can extend.
        tx_c = mk_tx("carol", "c1", ts=102.0)
        self.assertTrue(n2.submit_transaction(tx_c)[0])
        b2_next = n2.mine_once()
        self.assertIsNotNone(b2_next)
        self.assertEqual(n2.height(), 2)

        # Gossip chain snapshots in random order; everyone should converge to longest chain.
        snapshots = [n2.blockchain.chain, n1.blockchain.chain, n3.blockchain.chain]
        random.shuffle(snapshots)
        for snap in snapshots:
            for n in nodes:
                n.receive_chain(snap)

        heights = {n.height() for n in nodes}
        self.assertEqual(heights, {2})
        tip_hashes = {n.blockchain.tip.hash for n in nodes}
        self.assertEqual(len(tip_hashes), 1)

    def test_late_joiner_chain_sync(self) -> None:
        n1 = Node("n1", difficulty_prefix="0")
        n2 = Node("n2", difficulty_prefix="0")

        # Build 3 blocks on n1.
        for voter, cand, ts in [("a", "c1", 1.0), ("b", "c1", 2.0), ("c", "c2", 3.0)]:
            self.assertTrue(n1.submit_transaction(mk_tx(voter, cand, ts=ts))[0])
            mined = n1.mine_once()
            self.assertIsNotNone(mined)
        self.assertEqual(n1.height(), 3)
        self.assertEqual(n2.height(), 0)

        # Late joiner receives full chain and catches up.
        ok, reason = n2.receive_chain(n1.blockchain.chain)
        self.assertTrue(ok, reason)
        self.assertEqual(n2.height(), 3)
        self.assertEqual(n2.blockchain.tip.hash, n1.blockchain.tip.hash)


if __name__ == "__main__":
    unittest.main()
