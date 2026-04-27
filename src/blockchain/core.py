from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from typing import Callable

from .models import Block, Transaction

SignatureVerifier = Callable[[Transaction], bool]


def canonical_transaction_dict(tx: Transaction) -> dict:
    payload = asdict(tx)
    payload["metadata"] = dict(sorted((tx.metadata or {}).items()))
    return payload


def transaction_id(tx: Transaction) -> str:
    encoded = json.dumps(canonical_transaction_dict(tx), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def block_preimage(block: Block) -> bytes:
    block_data = {
        "index": block.index,
        "timestamp": block.timestamp,
        "transaction": canonical_transaction_dict(block.transaction),
        "previous_hash": block.previous_hash,
        "nonce": block.nonce,
    }
    encoded = json.dumps(block_data, sort_keys=True, separators=(",", ":"))
    return encoded.encode("utf-8")


def compute_block_hash(block: Block) -> str:
    return hashlib.sha256(block_preimage(block)).hexdigest()


def make_genesis_block() -> Block:
    genesis_tx = Transaction(
        voter_public_key="GENESIS",
        timestamp=0.0,
        candidate_id="GENESIS",
        signature="GENESIS",
        metadata={},
    )
    base = Block(
        index=0,
        timestamp=0.0,
        transaction=genesis_tx,
        previous_hash="0" * 64,
        nonce=0,
        hash="",
    )
    return Block(
        index=base.index,
        timestamp=base.timestamp,
        transaction=base.transaction,
        previous_hash=base.previous_hash,
        nonce=base.nonce,
        hash=compute_block_hash(base),
    )


def default_signature_verifier(tx: Transaction) -> bool:
    return bool(tx.voter_public_key and tx.signature)


class Blockchain:
    def __init__(
        self,
        difficulty_prefix: str = "00",
        signature_verifier: SignatureVerifier | None = None,
    ) -> None:
        self.difficulty_prefix = difficulty_prefix
        self.signature_verifier = signature_verifier or default_signature_verifier
        self.chain: list[Block] = [make_genesis_block()]
        self.mempool: dict[str, Transaction] = {}
        self.seen_blocks: set[str] = {self.chain[0].hash}
        self.used_voters: set[str] = set()
        self.block_index: dict[str, int] = {self.chain[0].hash: 0}

    @property
    def tip(self) -> Block:
        return self.chain[-1]

    def next_height(self) -> int:
        return self.tip.index + 1

    def valid_pow(self, block_hash: str) -> bool:
        return block_hash.startswith(self.difficulty_prefix)

    def _sorted_mempool_ids(self) -> list[str]:
        entries = list(self.mempool.items())
        entries.sort(key=lambda item: (item[1].timestamp, item[1].voter_public_key, item[0]))
        return [txid for txid, _ in entries]

    def _validate_transaction_fields(self, tx: Transaction) -> tuple[bool, str]:
        if not tx.voter_public_key:
            return False, "missing voter_public_key"
        if not tx.candidate_id:
            return False, "missing candidate_id"
        if not isinstance(tx.timestamp, (int, float)):
            return False, "invalid timestamp"
        if tx.timestamp < 0:
            return False, "negative timestamp"
        if not self.signature_verifier(tx):
            return False, "invalid signature"
        if tx.voter_public_key in self.used_voters:
            return False, "voter already voted on-chain"
        return True, "ok"

    def validate_transaction(self, tx: Transaction) -> tuple[bool, str]:
        ok, reason = self._validate_transaction_fields(tx)
        if not ok:
            return False, reason
        txid = transaction_id(tx)
        if txid in self.mempool:
            return False, "duplicate transaction"
        return True, "ok"

    def add_transaction(self, tx: Transaction) -> tuple[bool, str]:
        ok, reason = self.validate_transaction(tx)
        if not ok:
            return False, reason
        self.mempool[transaction_id(tx)] = tx
        return True, "accepted"

    def _validate_block_tx_against_chain(self, tx: Transaction) -> tuple[bool, str]:
        if tx.voter_public_key in self.used_voters:
            return False, "voter already used in chain"
        return self._validate_transaction_fields(tx)

    def validate_block(self, block: Block, parent: Block | None = None) -> tuple[bool, str]:
        parent_block = parent or self.tip
        if block.index != parent_block.index + 1:
            return False, "bad index"
        if block.previous_hash != parent_block.hash:
            return False, "bad previous_hash"
        if block.hash != compute_block_hash(block):
            return False, "hash mismatch"
        if not self.valid_pow(block.hash):
            return False, "pow condition not met"
        tx_ok, tx_reason = self._validate_block_tx_against_chain(block.transaction)
        if not tx_ok:
            return False, tx_reason
        return True, "ok"

    def append_block(self, block: Block) -> tuple[bool, str]:
        ok, reason = self.validate_block(block)
        if not ok:
            return False, reason

        self.chain.append(block)
        self.seen_blocks.add(block.hash)
        self.block_index[block.hash] = block.index
        self.used_voters.add(block.transaction.voter_public_key)

        txid = transaction_id(block.transaction)
        self.mempool.pop(txid, None)
        return True, "appended"

    def mine_next_block(self) -> Block | None:
        ordered_ids = self._sorted_mempool_ids()
        if not ordered_ids:
            return None

        txid = ordered_ids[0]
        tx = self.mempool[txid]
        index = self.next_height()
        prev = self.tip.hash
        timestamp = time.time()

        nonce = 0
        while True:
            candidate = Block(
                index=index,
                timestamp=timestamp,
                transaction=tx,
                previous_hash=prev,
                nonce=nonce,
                hash="",
            )
            block_hash = compute_block_hash(candidate)
            if block_hash.startswith(self.difficulty_prefix):
                return Block(
                    index=candidate.index,
                    timestamp=candidate.timestamp,
                    transaction=candidate.transaction,
                    previous_hash=candidate.previous_hash,
                    nonce=candidate.nonce,
                    hash=block_hash,
                )
            nonce += 1

    def maybe_mine_and_append(self) -> Block | None:
        mined = self.mine_next_block()
        if mined is None:
            return None
        ok, _ = self.append_block(mined)
        if not ok:
            return None
        return mined

    def replace_chain_if_longer(self, candidate_chain: list[Block]) -> tuple[bool, str]:
        if len(candidate_chain) <= len(self.chain):
            return False, "candidate not longer"

        if not candidate_chain:
            return False, "empty chain"
        if candidate_chain[0].hash != make_genesis_block().hash:
            return False, "bad genesis"

        used: set[str] = set()
        for i, block in enumerate(candidate_chain):
            if i == 0:
                if block.hash != compute_block_hash(block):
                    return False, "genesis hash mismatch"
                continue
            parent = candidate_chain[i - 1]
            if block.index != parent.index + 1:
                return False, "bad index in candidate"
            if block.previous_hash != parent.hash:
                return False, "bad link in candidate"
            if block.hash != compute_block_hash(block):
                return False, "candidate hash mismatch"
            if not self.valid_pow(block.hash):
                return False, "candidate pow invalid"
            tx = block.transaction
            if tx.voter_public_key in used:
                return False, "double vote in candidate"
            if not self.signature_verifier(tx):
                return False, "bad tx signature in candidate"
            used.add(tx.voter_public_key)

        self.chain = list(candidate_chain)
        self.used_voters = used
        self.seen_blocks = {b.hash for b in candidate_chain}
        self.block_index = {b.hash: b.index for b in candidate_chain}

        # Rebuild mempool by dropping any tx now committed on chain.
        committed_txids = {transaction_id(b.transaction) for b in self.chain[1:]}
        self.mempool = {k: v for k, v in self.mempool.items() if k not in committed_txids}
        return True, "chain replaced"
