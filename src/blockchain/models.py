from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Transaction:
    voter_public_key: str
    timestamp: float
    candidate_id: str
    signature: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Block:
    index: int
    timestamp: float
    transaction: Transaction
    previous_hash: str
    nonce: int
    hash: str
