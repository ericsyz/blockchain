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
