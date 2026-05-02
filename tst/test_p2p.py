import pathlib
import socket
import sys
import threading
import time
import unittest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from src.blockchain import Node, Transaction
from src.p2p import protocol
from src.p2p.peer import Peer
from src.p2p.serialization import block_to_dict
from src.p2p.tracker import Tracker

def simple_signature_verifier(tx: Transaction) -> bool:
    return bool(tx.voter_public_key and tx.signature)

def mk_tx(voter: str, candidate: str, ts: float | None = None) -> Transaction:
    return Transaction(
        voter_public_key=voter,
        timestamp=time.time() if ts is None else ts,
        candidate_id=candidate,
        signature=f"sig:{voter}",
        metadata={},
    )

def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    _, p = sock.getsockname()
    sock.close()
    return int(p)


class P2PForkTest(unittest.TestCase):
    def test_peer_adopts_longer_fork_over_p2p(self) -> None:
        host = "127.0.0.1"
        tracker_port, portA, portB = _free_port(), _free_port(), _free_port()
        tracker = Tracker(host, tracker_port)
        threading.Thread(target=tracker.start, name="test-tracker", daemon=True).start()
        time.sleep(0.5)  # tracker loops ready

        # Build 1 block on n1 and 2 blocks on n2
        n1 = Node("n1", difficulty_prefix="0", signature_verifier=simple_signature_verifier)
        n2 = Node("n2", difficulty_prefix="0", signature_verifier=simple_signature_verifier)
        self.assertTrue(n1.submit_transaction(mk_tx("a", "c1", 1.0))[0])
        self.assertTrue(n2.submit_transaction(mk_tx("b", "c1", 2.0))[0])
        self.assertTrue(n2.submit_transaction(mk_tx("c", "c1", 3.0))[0])
        self.assertIsNotNone(n1.mine_once())
        self.assertIsNotNone(n2.mine_once())
        self.assertIsNotNone(n2.mine_once())
        self.assertEqual(n1.height(), 1)
        self.assertEqual(n2.height(), 2)

        # build peers
        p1 = Peer(peer_id="pA", node=n1, listen_host=host, listen_port=portA, tracker_host=host, tracker_port=tracker_port)
        p2 = Peer(peer_id="pB", node=n2, listen_host=host, listen_port=portB, tracker_host=host, tracker_port=tracker_port)
        try:
            p1.start()
            time.sleep(0.2)  # wait so p1 tracker threads are up before p2 joins
            p2.start()
            time.sleep(1)  # time for peer list
            # One new block so n1 can switch to the longer chain
            p2._broadcast(protocol.make_new_block(block_to_dict(n2.blockchain.chain[-1])))
            time.sleep(1)  # time for n1 to apply the block
            self.assertEqual(n1.height(), 2)
            self.assertEqual(n1.blockchain.tip.hash, n2.blockchain.tip.hash)
        finally:
            p1.stop()
            p2.stop()
            tracker.stop()


if __name__ == "__main__":
    unittest.main()
