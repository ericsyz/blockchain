"""

This entire file is to serve as a converter between the dict format that our messages use and the dataclasses in the blockchain.
Note that since it's frozen we can't pass in an empty transaction and fill it later.
Also note that we have to recurse an additional level for blocks since d["transaction"] is a dict not a transaction.
"""

from __future__ import annotations
from dataclasses import asdict
from typing import Any
from src.blockchain.models import Block, Transaction

def tx_to_dict(tx: Transaction) -> dict[str, Any]:
    return asdict(tx)

def dict_to_tx(d: dict[str, Any]) -> Transaction:
    return Transaction(voter_public_key = d["voter_public_key"], timestamp = d["timestamp"], candidate_id = d["candidate_id"],
                       signature = d["signature"], metadata = d.get("metadata", {}))

def block_to_dict(b: Block) -> dict[str, Any]:
    return asdict(b)

def dict_to_block(d: dict[str, Any]) -> Block:
    return Block(index = d["index"], timestamp = d["timestamp"], transaction = dict_to_tx(d["transaction"]), previous_hash = d["previous_hash"], 
                 nonce = d["nonce"], hash = d["hash"])
