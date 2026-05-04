# Voting Blockchain

A way to vote using the blockchain. An election authority signs valid tokens that valid voters use to verify the votes that they then send to the peer to peer network which runs a tally of all votes. Features privacy and security considerations.

The blockchain features:

- one transaction per block
- PoW mining via nonce search (`difficulty_prefix`)
- mempool + deterministic tx ordering
- block and transaction validation
- longest-valid-chain replacement

## Requirements

You need **Python 3.10+** and library **cryptography**

```
pip install cryptography
```

## How to run
It is important to run the following commands in this exact order from the `blockchain` directory.

### 1. Start Election Authority
First, you should start the election authority by running

`python -m src.election_authority.election_authority --host <host> --port <port> --key-file <key-file>`

* host - the IP address of the election authority. default: ‘127.0.0.1’
* port - the port of the election authority. default: 5017
* key-file - the name of the file to store the private key. default: "ea_private_key.pem"

This will print a public key, keep the default private key file at the project root, and write `ea_public_key.pem` beside it. 
The peers need to be shared this public key if they are running on different machines. This is so peers never have access to the private key.
If the key file is not deleted the program will reuse the same key in subsequent runs.

### 2. Start Tracker
Next, you should start the tracker by running

`python -m src.p2p.tracker --host <host> --port <port>`
* host - the IP address of the tracker. default: ‘127.0.0.1’
* port - the port of the tracker. default: 9000

### 3. Start Peers
Next, you should start the peers by running

`python -m src.p2p.peer --peer-id <peer-id> --listen-port <listen-port> --listen-host <listen-host> --tracker-host <tracker-host> --tracker-port <tracker-port>`
* peer-id - the ID of the peer. default: None
* listen-port - the IP address of the peer. default: ‘127.0.0.1’
* listen-host - the port of the peer. default: 9100
* tracker-host - the IP address of the tracker. default: ‘127.0.0.1’
* tracker-port - the port of the tracker. default: 9000

### 4. Cast Votes
Finally, cast votes by running

`python -m src.voter_client.client <voter_id> <candidate_id> --ea-host <ea-host> --ea-port <ea-port> --peer-host <peer-host> --peer-port <peer-port>`

* voter_id - (required) the id of the voter to use, must be explicitly under `valid_voter_ids` in `election_authority.py`
* candidate_id - (required) the id of your candidate
* ea-host - the ip of the election authority. default: ‘127.0.0.1’
* ea-port - the port of the election authority. default: 5017
* peer-host - the ip of the peer to send the vote to. default: ‘127.0.0.1’
* peer-port - the port of the peer to send to vote to. default: 9100

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

python -m src.election_authority.election_authority
python -m unittest tst/test_ea.py -v

python -m unittest tst/test_integration_blockchain.py -v
python -m unittest tst/test_p2p.py -v
```