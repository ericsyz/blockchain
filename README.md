# blockchain

Minimal blockchain implementation for the assignment, with:

- one transaction per block
- PoW mining via nonce search (`difficulty_prefix`)
- mempool + deterministic tx ordering
- block and transaction validation
- longest-valid-chain replacement

## Project layout

- `src/blockchain/models.py`: `Transaction`, `Block`
- `src/blockchain/core.py`: chain state, validation, mining, longest-chain logic
- `src/blockchain/node.py`: node wrapper with `submit_transaction`, `mine_once`, `receive_block`, `receive_chain`
- `tst/test_blockchain.py`: unit tests

## How to run
It is important to run the following commands in this exact order from the `blockchain` directory.

### 1. Start Election Authority
First, you should start the election authority by running

`python -m src.election_authority.election_authority --host <host> --port <port> --key-file <key-file>`

host - the IP address of the election authority. default: ‘127.0.0.1’
port - the port of the election authority. default: 5000
key-file - the name of the file to store the private key. default: "ea_private_key.pem"

This will print a public key, keep the default private key file at the project root.
If the key file is not deleted the program will reuse the same key in subsequent runs.

### 2. Start Tracker
Next, you should start the tracker by running

`python -m src.p2p.tracker --host <host> --port <port>`
host - the IP address of the tracker. default: ‘127.0.0.1’
port - the port of the tracker. default: 9000

### 3. Start Peers
Next, you should start the peers by running

`python -m src.p2p.peer --peer-id <peer-id> --listen-port <listen-port> --listen-host <listen-host> --tracker-host <tracker-host> --tracker-port <tracker-port>`
peer-id - the ID of the peer. default: None
listen-port - the IP address of the peer. default: ‘127.0.0.1’
listen-host - the port of the peer. default: 9100
tracker-host - the IP address of the tracker. default: ‘127.0.0.1’
tracker-port - the port of the tracker. default: 9000

### 4. Cast Votes
Finally, cast votes by running

`python -m src.voter_client.client <voter_id> <candidate_id> --ea-host <ea-host> --ea-port <ea-port> --peer-host <peer-host> --peer-port <peer-port>`
voter_id - (required) the id of the voter to use, must be explicitly under `valid_voter_ids` in `election_authority.py`
candidate_id - (required) the id of your candidate
ea-host - the ip of the election authority. default: ‘127.0.0.1’
ea-port - the port of the election authority. default: 5000
peer-host - the ip of the peer to send the vote to. default: ‘127.0.0.1’
peer-port - the port of the peer to send to vote to. default: 9100

### Commands used for testing:
```
python -m src.election_authority.election_authority
python -m src.p2p.tracker
python -m src.p2p.peer --listen-port 9100
python -m src.p2p.peer --listen-port 9101
python -m src.p2p.peer --listen-port 9102
python -m src.voter_client.client voter_1 Alice
python -m src.voter_client.client voter_2 Alice
```

## Run tests

```bash
python -m unittest tst/test_blockchain.py -v
```

## Quick usage example

```python
from src.blockchain import Node, Transaction
import time

node = Node("n1", difficulty_prefix="00")
tx = Transaction(
    voter_public_key="alice",
    timestamp=time.time(),
    candidate_id="candidate_1",
    signature="sig:alice",
)

ok, reason = node.submit_transaction(tx)
if ok:
    block = node.mine_once()
    print("mined:", block is not None, "height:", node.height())
```

Note: signature verification is currently pluggable; default verifier only checks non-empty key/signature fields. Replace with real cryptographic verification as you wire the Election Authority flow.
