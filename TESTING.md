# blockchain testing file

All commands below were run from the project root. I used `.venv/bin/python` to ensure it would work on other machines, not just mine

### Test 1 - blockchain unit tests

Description:
Runs the main chain tests for mining, mempool, one vote per voter, bad POW block, longest chain, tiebreak, double vote in a longer chain, and voter tallies.

Commands run:
```
.venv/bin/python -m unittest tst/test_blockchain.py -v
```

Results:
```
test_add_transaction_and_mine_one_tx_per_block (tst.test_blockchain.BlockchainTests.test_add_transaction_and_mine_one_tx_per_block) ... ok
test_duplicate_tx_rejected (tst.test_blockchain.BlockchainTests.test_duplicate_tx_rejected) ... ok
test_longer_chain_with_duplicate_voter_rejected (tst.test_blockchain.BlockchainTests.test_longer_chain_with_duplicate_voter_rejected) ... ok
test_longest_chain_adopted (tst.test_blockchain.BlockchainTests.test_longest_chain_adopted) ... ok
test_mine_once_returns_none_for_empty_mempool (tst.test_blockchain.BlockchainTests.test_mine_once_returns_none_for_empty_mempool) ... ok
test_mining_uses_deterministic_mempool_order (tst.test_blockchain.BlockchainTests.test_mining_uses_deterministic_mempool_order) ... ok
test_one_vote_per_voter_enforced (tst.test_blockchain.BlockchainTests.test_one_vote_per_voter_enforced) ... ok
test_receive_invalid_pow_block_rejected (tst.test_blockchain.BlockchainTests.test_receive_invalid_pow_block_rejected) ... ok
test_running_tally_counts_votes_by_candidate (tst.test_blockchain.BlockchainTests.test_running_tally_counts_votes_by_candidate) ... ok
test_running_tally_updates_after_longest_chain_replace (tst.test_blockchain.BlockchainTests.test_running_tally_updates_after_longest_chain_replace) ... ok
test_split_brain_tiebreak (tst.test_blockchain.BlockchainTests.test_split_brain_tiebreak) ... ok

----------------------------------------------------------------------
Ran 11 tests in 0.003s

OK
```

Explanation:
Everything passed. These tests walk through normal mining and mempool behavior, then check that bad blocks do not get in wrong proof of work, that nodes switch to a longer valid chain and that vote counts follow the chain you believe. If two chains are the same length, the code picks a winner using a rule on the tip block hash. It also refuses a longer chain that would let the same voter appear twice.

### Test 2 - integration blockchain tests

Description:
three nodes should pick the same longest branch, and a late joiner should copy the full chain

Commands run:
```
.venv/bin/python -m unittest tst/test_integration_blockchain.py -v
```

Results:
```
test_late_joiner_chain_sync (tst.test_integration_blockchain.BlockchainIntegrationTests.test_late_joiner_chain_sync) ... ok
test_three_node_eventual_convergence_after_fork (tst.test_integration_blockchain.BlockchainIntegrationTests.test_three_node_eventual_convergence_after_fork) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.001s

OK
```

Explanation:
Both passed. One test lets three nodes fork and then feeds them each other’s chains in random order until they all agree on the longest branch and the same vote tally. The other is a node that starts empty and then ingests a full chain in one go and ends up matching the other node’s tip.

### Test 3 - P2P fork test

Description:
Starts a real tracker and two peers over TCP, longer chain wins.

Commands run:
```
.venv/bin/python -m unittest tst/test_p2p.py -v
```

Results:
```
test_peer_adopts_longer_fork_over_p2p (tst.test_p2p.P2PForkTest.test_peer_adopts_longer_fork_over_p2p) ... ok

----------------------------------------------------------------------
Ran 1 test in 2.722s

OK
```

Explanation:
Passed. tne peer has a longer chain, it announces a block, and the shorter peer ends up on the same chain with matching hashes. It takes a few seconds because the test sleeps between steps so threads can catch up.

### Test 4 - Election Authority tests

Description:
Hits the real EA on `127.0.0.1:5017`. Start the EA from the project root first so it writes `ea_public_key.pem` and matches what `tst/test_ea.py` loads. Then run the tests in another terminal

Commands run (terminal 1):
```
.venv/bin/python -m src.election_authority.election_authority
```

Commands run (terminal 2):
```
.venv/bin/python -m unittest tst/test_ea.py -v
```

Results:
```
test_ea_works_after_bad_request (tst.test_ea.BlockchainTests.test_ea_works_after_bad_request) ... ok
test_receive_signed_token (tst.test_ea.BlockchainTests.test_receive_signed_token) ... ok
test_single_token_per_voter (tst.test_ea.BlockchainTests.test_single_token_per_voter) ... ok
test_token_not_validated_by_wrong_signature (tst.test_ea.BlockchainTests.test_token_not_validated_by_wrong_signature) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.010s

OK
```

Explanation:
All passed, the client gets a hex signature back and checks it with the public key in `ea_public_key.pem`. A signature that belongs to another voter’s token is rejected. The same voter cannot pull two signatures. After sending junk that is not JSON, the server still answers normally for the next valid voter.

### Test 5 - Resilience tests

Description:
More tests to show how our blockchain is resilient to invalid transactions and modifications made to blocks

Commands run:
```
.venv/bin/python -m unittest tst/test_resilience.py -v
```

Results:
```
test_tampered_block (tst.test_resilience.ResilienceTests.test_tampered_block) ... ok
test_bad_previous_hash (tst.test_resilience.ResilienceTests.test_bad_previous_hash) ... ok
test_bad_index (tst.test_resilience.ResilienceTests.test_bad_index) ... ok
test_bad_genesis (tst.test_resilience.ResilienceTests.test_bad_genesis) ... ok
test_invalid_signature (tst.test_resilience.ResilienceTests.test_invalid_signature) ... ok

----------------------------------------------------------------------
Ran 5 tests in 0.001s

OK
```

Explanation:
All passed. These are small checks that the node refuses blocks where the data was edited but the hash was left alone, blocks that do not point at the real parent, and blocks with the wrong height. The mempool also refuses a transaction when the signature checker always says no. replacing the chain with a fake genesis hash is rejected to

### Test 6 - Manual output (EA + tracker + three peers + four voters)

Description:
Ran EA on 5017, tracker on 9000, three peers on 9100–9102, four voter clients with different candidates. Note, if you run all peers too close together their dial threads and HELLOs can race. So I started a couple seconds between each peer, and left a few seconds between each client so gossip can catch up

Commands run (each in own terminal)
```
.venv/bin/python -m src.election_authority.election_authority
.venv/bin/python -m src.p2p.tracker
.venv/bin/python -m src.p2p.peer --peer-id peer9100 --listen-port 9100

.venv/bin/python -m src.p2p.peer --peer-id peer9101 --listen-port 9101

.venv/bin/python -m src.p2p.peer --peer-id peer9102 --listen-port 9102

.venv/bin/python -m src.voter_client.client voter_1 Alice --peer-port 9100

.venv/bin/python -m src.voter_client.client voter_2 Bob --peer-port 9100
.venv/bin/python -m src.voter_client.client voter_3 Carol --peer-port 9100
.venv/bin/python -m src.voter_client.client voter_4 Dave --peer-port 9100
```

Results (EA):
```
[*] Loading existing EA key from ea_private_key.pem...

--- COPY THIS PUBLIC KEY INTO YOUR NODE/CLIENT SCRIPTS ---
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArG27kDfpLbn+8oLaLAki
n2aqhurO3NHxvDWm0kQvdhe5x9BeItvCDsFPuEfgFCL+XKDEjIqcKq/AlIt6vCev
Yb/sWHQig+bV9mP2sXHjkPNN8kF/mxejsj6WpFCa6no1wBsf6fVFY+k2zZrKO32g
mnEo1xK5A7nRVYK0pGuoPA9BnbFEhvy2PLjMxVwiVZXbr9y+GfVazIvVkWULheBm
IIf1eVTpZV0E1YuiigtagzLBNDhnuZKatoLuC/zoR8Xpk930Qlfth/nkRvjSQh4v
Rv5jevaAwGMkuYeNji8WXoRdS31Gqx+IGwXpdEnZ0xTev729mvj7bTWq1Q3JN6J0
5QIDAQAB
-----END PUBLIC KEY-----

-----------------------------------------------------------

[*] EA Server listening on 127.0.0.1:5017
Received request from voter_1
Signed token for voter_1
Received request from voter_2
Signed token for voter_2
Received request from voter_3
Signed token for voter_3
Received request from voter_4
Signed token for voter_4
```

Results tracker:
```
2026-05-02 23:02:06,820 tracker INFO tracker listening on 127.0.0.1:9000
2026-05-02 23:02:07,660 tracker INFO REGISTER peer9100 @ 127.0.0.1:9100 (changed=True)
2026-05-02 23:02:09,655 tracker INFO REGISTER peer9101 @ 127.0.0.1:9101 (changed=True)
2026-05-02 23:02:11,669 tracker INFO REGISTER peer9102 @ 127.0.0.1:9102 (changed=True)
```

Results (`voter_1` -> Alice):
```
Requesting signature from EA for voter_1...
Obtained EA Signature
Casting vote to Peer at 127.0.0.1:9100...
Vote successfully broadcast to the P2P network!
```

Results (`voter_2` -> Bob):
```
Requesting signature from EA for voter_2...
Obtained EA Signature
Casting vote to Peer at 127.0.0.1:9100...
Vote successfully broadcast to the P2P network!
```

Results (`voter_3` -> Carol):
```
Requesting signature from EA for voter_3...
Obtained EA Signature
Casting vote to Peer at 127.0.0.1:9100...
Vote successfully broadcast to the P2P network!
```

Results (`voter_4` -> Dave):
```
Requesting signature from EA for voter_4...
Obtained EA Signature
Casting vote to Peer at 127.0.0.1:9100...
Vote successfully broadcast to the P2P network!
```

Results peer9100:
```
2026-05-02 23:02:07,660 peer INFO peer peer9100 has been set up on 127.0.0.1:9100
2026-05-02 23:02:09,656 peer INFO connected to peer peer9101 @ 127.0.0.1:9101
2026-05-02 23:02:11,670 peer INFO connected to peer peer9102 @ 127.0.0.1:9102
2026-05-02 23:02:19,677 peer INFO connected to peer VOTER_CLIENT @ 127.0.0.1:58467
2026-05-02 23:02:19,724 peer INFO accepted block from peer9102, running tally={'Alice': 1}
2026-05-02 23:02:24,682 peer INFO peer VOTER_CLIENT disconnected: [Errno 54] Connection reset by peer
2026-05-02 23:02:24,682 peer INFO dropped peer VOTER_CLIENT
2026-05-02 23:02:27,765 peer INFO connected to peer VOTER_CLIENT @ 127.0.0.1:58471
2026-05-02 23:02:27,781 peer INFO accepted block from peer9102, running tally={'Alice': 1, 'Bob': 1}
2026-05-02 23:02:32,770 peer INFO peer VOTER_CLIENT disconnected: [Errno 54] Connection reset by peer
2026-05-02 23:02:32,771 peer INFO dropped peer VOTER_CLIENT
2026-05-02 23:02:35,848 peer INFO connected to peer VOTER_CLIENT @ 127.0.0.1:58473
2026-05-02 23:02:35,871 peer INFO accepted block from peer9101, running tally={'Alice': 1, 'Bob': 1, 'Carol': 1}
2026-05-02 23:02:40,853 peer INFO peer VOTER_CLIENT disconnected: [Errno 54] Connection reset by peer
2026-05-02 23:02:40,853 peer INFO dropped peer VOTER_CLIENT
2026-05-02 23:02:43,930 peer INFO connected to peer VOTER_CLIENT @ 127.0.0.1:58477
2026-05-02 23:02:43,934 peer INFO accepted block from peer9101, running tally={'Alice': 1, 'Bob': 1, 'Carol': 1, 'Dave': 1}
2026-05-02 23:02:48,933 peer INFO peer VOTER_CLIENT disconnected: [Errno 54] Connection reset by peer
2026-05-02 23:02:48,933 peer INFO dropped peer VOTER_CLIENT
2026-05-02 23:03:04,030 peer WARNING tracker connection lost: peer closed connection
```

Results peer9101:
```
2026-05-02 23:02:09,655 peer INFO peer peer9101 has been set up on 127.0.0.1:9101
2026-05-02 23:02:09,656 peer INFO connected to peer peer9100 @ 127.0.0.1:9100
2026-05-02 23:02:11,670 peer INFO connected to peer peer9102 @ 127.0.0.1:9102
2026-05-02 23:02:19,724 peer INFO accepted block from peer9102, running tally={'Alice': 1}
2026-05-02 23:02:27,782 peer INFO accepted block from peer9102, running tally={'Alice': 1, 'Bob': 1}
2026-05-02 23:02:35,871 peer INFO mined block 3 00b1f1e5b78c running tally={'Alice': 1, 'Bob': 1, 'Carol': 1}
2026-05-02 23:02:43,934 peer INFO mined block 4 00e413b8b387 running tally={'Alice': 1, 'Bob': 1, 'Carol': 1, 'Dave': 1}
2026-05-02 23:03:04,030 peer WARNING tracker connection lost: peer closed connection
2026-05-02 23:03:04,056 peer INFO peer peer9100 disconnected: peer closed connection
2026-05-02 23:03:04,056 peer INFO dropped peer peer9100
```

Results peer9102:
```
2026-05-02 23:02:11,669 peer INFO peer peer9102 has been set up on 127.0.0.1:9102
2026-05-02 23:02:11,670 peer INFO connected to peer peer9100 @ 127.0.0.1:9100
2026-05-02 23:02:11,670 peer INFO connected to peer peer9101 @ 127.0.0.1:9101
2026-05-02 23:02:19,723 peer INFO mined block 1 004855432ff5 running tally={'Alice': 1}
2026-05-02 23:02:27,781 peer INFO mined block 2 003796c80983 running tally={'Alice': 1, 'Bob': 1}
2026-05-02 23:02:35,871 peer INFO accepted block from peer9101, running tally={'Alice': 1, 'Bob': 1, 'Carol': 1}
2026-05-02 23:02:43,934 peer INFO accepted block from peer9101, running tally={'Alice': 1, 'Bob': 1, 'Carol': 1, 'Dave': 1}
2026-05-02 23:03:04,030 peer WARNING tracker connection lost: peer closed connection
2026-05-02 23:03:04,055 peer INFO peer peer9100 disconnected: peer closed connection
2026-05-02 23:03:04,056 peer INFO dropped peer peer9100
2026-05-02 23:03:04,080 peer INFO peer peer9101 disconnected: peer closed connection
2026-05-02 23:03:04,080 peer INFO dropped peer peer9101
```

Explanation:
all three peers stay connected, `peer9102` mined blocks 1–2, `peer9101` mined 3–4, `peer9100` accepted those blocks from peers whoever won the race and the tally on every log matches the same four candidates. Who mines which block is nondeterministic
