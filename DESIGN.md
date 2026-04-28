# Design / Implementation of Blockchain

## Data structure

The chain is a **linked list of `Block` objects** starting from a **genesis** block at index `0`, linked by each block’s **`previous_hash`**. Each peer keeps its own copy of the chain plus a **mempool** of transactions not yet in a block. **Exactly one `Transaction` per `Block`:** the proposer selects **one** tx from the mempool using a **fixed order** (e.g. by timestamp then voter key) so that, given the same mempool, every node would pick the same candidate.

Peers are connected via a **P2P protocol** (see below), which handles peer discovery, message propagation, and chain synchronization. **Transactions** and **blocks** arrive over those sockets, update the mempool, and propagate so every authority can validate and extend the same chain.

## P2P Protocol

### Tracker

The tracker is a **central TCP server** that maintains the current set of active peers in the network.

**Responsibilities:**
- Accept `REGISTER` messages from peers and add them to the network
- Accept `DEREGISTER` messages or remove peers that fail liveness checks
- Enforce heartbeat-based liveness:
  - Peers send `HEARTBEAT` every **5 seconds**
  - Peers are dropped after **15 seconds of silence**
- Broadcast updated membership via `PEER_LIST` whenever the peer set changes
- Provide the current peer list to newly joining peers so they can establish connections

---

### Peers

Each peer:
- Opens **one TCP connection to the tracker**
- Opens **one TCP connection to each other peer** in the network

**Threads per peer:**
- **Listener thread**: accepts incoming peer connections
- **Miner thread**: continuously attempts proof-of-work using transactions in the mempool
- **Heartbeat thread**: periodically sends liveness messages to the tracker

---

### Message Framing

All messages use a length-prefixed framing format:

<4-byte big-endian length><JSON payload>

The JSON payload always includes a `type` field indicating the message kind.

---

### Message Types

| Type | Fields | Description |
|------|--------|-------------|
| `REGISTER` | `peer_id`, `ip` (port inferred from socket) | Sent by a peer on startup to join the network |
| `DEREGISTER` | `peer_id` | Sent by a peer when exiting cleanly |
| `HEARTBEAT` | `peer_id` | Sent every 5s; peers removed after 15s of silence |
| `HELLO` | `protocol_version`, `peer_id`, `chain_tip_index`, `chain_tip_hash` | Initial handshake between peers; used to check compatibility and determine if synchronization is needed |
| `PEER_LIST` | `peers: [...]` | Tracker’s current view of active peers |
| `NEW_TX` | `transaction` | Broadcast of a new transaction; recipients validate, add to mempool, and re-broadcast if unseen |
| `NEW_BLOCK` | `block` | Broadcast of a newly mined block; recipients validate, extend the chain (or trigger fork handling), and re-broadcast if unseen |
| `GET_CHAIN` | `from_index` | Request for blocks starting from a given index |
| `CHAIN_RESP` | `blocks: [...]` | Response containing the requested block range |

---

### Gossip and Deduplication

Transactions and blocks are propagated using a **flooding (gossip) protocol**:
- `NEW_TX` and `NEW_BLOCK` messages are forwarded to all peers except the sender
- No acknowledgements are required (best-effort dissemination)

To prevent infinite propagation loops:
- Each peer maintains a `seen_set`
  - Transactions keyed by **transaction hash**
  - Blocks keyed by **block hash**
- On receiving a message:
  - If already seen → drop silently
  - Otherwise → validate, process, add to `seen_set`, and forward

---

### Chain Synchronization

Peers synchronize state using `HELLO`, `GET_CHAIN`, and `CHAIN_RESP`:
- During `HELLO`, peers compare `chain_tip_index` and `chain_tip_hash`
- If a peer is behind or detects a mismatch:
  - It sends `GET_CHAIN` starting from its latest known index
- The responding peer sends missing blocks via `CHAIN_RESP`

This ensures eventual consistency even after late joins, temporary partitions, or missed `NEW_BLOCK` messages.

## Block

| Field | Purpose |
|--------|---------|
| **Index** | Height; genesis is `0`, then `parent.index + 1`. |
| **Timestamp** | When the block was produced; can help order mempool picks. |
| **Transaction** | Exactly **one** vote object in this block (not a list). |
| **Previous hash** | Parent block’s hash; fixed constant for genesis. |
| **Hash** | Digest of a defined preimage **excluding** `hash` itself. |
| **Nonce** | Included in the preimage; varied during mining to produce a valid hash. |

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
| **Block** (on receive) | Correct link to parent and matching `hash`; block satisfies the mining condition; the **single** transaction is valid against state after parent; no broken invariants (e.g. still ≤ one vote per pubkey). |
| **Forks** | Pick and document a simple rule (e.g. first valid block at height, or longest valid chain). |

## Consensus: Mining (Proof of Work)

| Concept | Definition |
|--------|------------|
| **Mining** | Each node attempts to create a valid block by varying the nonce until the block hash satisfies a simple condition (e.g. leading zeros). |
| **Block creation** | Any node may mine a block. When a valid block is found, it is broadcast to all peers. |
| **Difficulty** | A fixed, low difficulty (e.g. hash starts with `"00"`) is used to keep mining feasible for the project. |
| **Forks** | If multiple nodes mine a block at a similar time, forks may occur. Nodes resolve forks using a simple rule such as adopting the longest valid chain. |
| **Miner thread** | Continuously attempts to mine a block from the mempool. When a valid block is found, it is broadcast over the network. |

## Optional Network Behavior Simulation

Peers may simulate non-ideal network behavior, such as delayed message propagation or dropped messages, to evaluate the robustness of the gossip protocol and consensus mechanism. These behaviors are optional and do not affect the core correctness of the system.


## Timeline of a Vote

### Voter Registration

We assume the user has some external form of unique identification that can be provided to an Election Authority to confirm voter eligibility. The user will generate a unique digital key, then scramble it as a token. The scrambled/blinded token is sent alongside the identification to the Election Authority. The Election Authority verifies the identification and signs the token before sending it back to the user. The user unscrambled the token and now has a signed token.

### Casting the Vote

After selecting the candidate(s), the user will create a packet with their vote, signed token, and nonce, and sign it with their private key. The packet is sent to an entry node, which performs pre-validation by checking for the correct format and a valid signature. The entry node then spreads the packet to other nodes’ mempools through the gossip protocol.

### Vote Validation

The block producer picks the vote from the mempools and does further validation. It compares the token signature with the Election Authority public key to check for validity, checks that the token has not already been used through a nullifier check, and verifies the voter's signature on the packet.

### Recording

The block is hashed and added to the chain.

## Demo Application Design

The demo application is a decentralized voting system built on top of the blockchain network. Users create signed vote transactions, which are broadcast to peers and validated before entering the mempool. Peers mine blocks containing valid vote transactions, and the resulting blockchain serves as the immutable record used to compute the final vote tally.