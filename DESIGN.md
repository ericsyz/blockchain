# Design / Implementation of Blockchain

## Data structure

The chain is a **linked list of `Block` objects** starting from a **genesis** block at index `0`, linked by each block’s **`previous_hash`**. Each peer keeps its own copy of the chain plus a **mempool** of transactions not yet in a block. **Exactly one `Transaction` per `Block`:** the proposer selects **one** tx from the mempool using a **fixed order** (e.g. by timestamp then voter key) so that, given the same mempool, every node would pick the same candidate.

Peers are **connected by the P2P architecture** (tracker registration and TCP links between peers). **Transactions** and **blocks** arrive over those sockets, update the mempool, and propagate so every authority can validate and extend the same chain.

## Block

| Field | Purpose |
|--------|---------|
| **Index** | Height; genesis is `0`, then `parent.index + 1`. |
| **Timestamp** | When the block was produced; can help order mempool picks. |
| **Transaction** | Exactly **one** vote object in this block (not a list). |
| **Previous hash** | Parent block’s hash; fixed constant for genesis. |
| **Hash** | Digest of a defined preimage **excluding** `hash` itself. |
| **Nonce** | Included in the preimage; often `0` under PoA. |

**Validity:** `index` and `previous_hash` match the parent; recomputed `hash` equals stored `hash`. All nodes use the **same encoding** for hashing (field order, key formats, etc.).

## Transaction

| Field | Purpose |
|--------|---------|
| **Voter public key** | Who is voting; must match the signing key. |
| **Timestamp** | When the vote was created. |
| **Candidate id** | Who or what they voted for. |
| **Signature** | Proof of possession of the voter’s private key over the signed payload below. |

The signed payload is a **canonical encoding** of `(public key, timestamp, candidate id)` (exclude `signature`). Verifiers recompute it and verify (e.g. ECDSA or Ed25519).

## Validation

| Stage | Checks |
|--------|--------|
| **Transaction** (mempool / before inclusion) | Well-formed fields; valid signature; voter **allowed to vote** (e.g. one vote per pubkey on chain, optional allowlist); reject duplicates. |
| **Block** (on receive) | Correct link to parent and matching `hash`; proposer is the **PoA** node for this height; the **single** transaction is valid against state after parent; no broken invariants (e.g. still ≤ one vote per pubkey). |
| **Forks** | Pick and document a simple rule (e.g. first valid block at height, or longest valid chain). |

## Consensus: Proof of Authority (PoA)

| Concept | Definition |
|--------|------------|
| **`total_nodes`** | Number of authorities in the rotation; must agree on every node. |
| **`authority_index`** | Stable rank in `0 .. total_nodes - 1` assigned at startup. |
| **Block height `h`** | **`h = tip.index + 1`**: index of the **next** block to append after the current tip (after genesis-only, the first appended block has `index == 1`). Same `h` on every node for the same tip. |
| **Proposer** | Only the node with `authority_index == h % total_nodes` may create the block at height `h`; others validate and append. |
| **Miner thread** | On your turn: if the mempool has a valid tx, build **one** block (single tx) and **broadcast** over P2P; if not, **do not publish**. Not necessarily proof-of-work. |