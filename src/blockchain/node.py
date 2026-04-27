from __future__ import annotations

from dataclasses import asdict

from .core import Blockchain, transaction_id
from .models import Block, Transaction


class Node:
    """
    Thin node wrapper around the blockchain engine.
    Networking can call these methods from P2P message handlers.
    """

    def __init__(self, node_id: str, difficulty_prefix: str = "00") -> None:
        self.node_id = node_id
        self.blockchain = Blockchain(difficulty_prefix=difficulty_prefix)

    def submit_transaction(self, tx: Transaction) -> tuple[bool, str]:
        return self.blockchain.add_transaction(tx)

    def mine_once(self) -> Block | None:
        return self.blockchain.maybe_mine_and_append()

    def receive_block(self, block: Block) -> tuple[bool, str]:
        if block.hash in self.blockchain.seen_blocks:
            return False, "already seen"
        return self.blockchain.append_block(block)

    def receive_chain(self, blocks: list[Block]) -> tuple[bool, str]:
        return self.blockchain.replace_chain_if_longer(blocks)

    def tx_inventory(self) -> list[str]:
        return sorted(self.blockchain.mempool.keys())

    def export_chain_payload(self) -> list[dict]:
        return [asdict(b) for b in self.blockchain.chain]

    def height(self) -> int:
        return self.blockchain.tip.index

    def contains_tx(self, tx: Transaction) -> bool:
        txid = transaction_id(tx)
        return any(transaction_id(b.transaction) == txid for b in self.blockchain.chain[1:])
