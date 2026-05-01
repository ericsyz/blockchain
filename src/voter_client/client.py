import argparse
import socket
import json
import struct
import time
import secrets

PROTOCOL_VERSION = 1

def send_p2p_msg(sock, msg):
    """Formats message with 4-byte length prefix as required by your protocol.py"""
    payload = json.dumps(msg, separators=(",", ":"), sort_keys=True).encode("utf-8")
    header = struct.pack(">I", len(payload))
    sock.sendall(header + payload)

def cast_vote(voter_id, candidate_id, ea_host='127.0.0.1', ea_port=5000, peer_host='127.0.0.1', peer_port=9100):
    # Generate a unique token
    token = secrets.token_hex(16)
    
    print(f"Requesting signature from EA for {voter_id}...")
    
    # Connect to Election Authority to get signature
    try:
        ea_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ea_sock.connect((ea_host, ea_port))
        
        # EA expects "voter_id" and "token"
        ea_request = {"voter_id": voter_id, "token": token}
        ea_sock.sendall(json.dumps(ea_request).encode('utf-8'))
        
        # Receive the hex signature
        ea_signature = ea_sock.recv(4096).decode('utf-8')
        ea_sock.close()
        
        if not ea_signature:
            print("Failed to obtain signature from EA.")
            return
        print("Obtained EA Signature")
        
    except Exception as e:
        print(f"EA Connection Error: {e}")
        return

    # Construct the Transaction (NEW_TX)
    transaction = {
        "voter_public_key": token,
        "timestamp": time.time(),
        "candidate_id": candidate_id,
        "signature": ea_signature,
    }
    
    # Send to a Peer Entry Node
    print(f"Casting vote to Peer at {peer_host}:{peer_port}...")
    try:
        peer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_sock.connect((peer_host, peer_port))
        
        # Peer nodes expect a HELLO handshake first
        hello_msg = {
            "type": "HELLO",
            "protocol_version": PROTOCOL_VERSION,
            "peer_id": "VOTER_CLIENT",
            "chain_tip_index": 0,
            "chain_tip_hash": "0"
        }
        send_p2p_msg(peer_sock, hello_msg)
        
        # Send the NEW_TX message
        vote_msg = {
            "type": "NEW_TX",
            "transaction": transaction
        }
        send_p2p_msg(peer_sock, vote_msg)

        # Wait to ensure your vote is received before closing connection
        time.sleep(5)
        
        print("Vote successfully broadcast to the P2P network!")
        peer_sock.close()
        
    except Exception as e:
        print(f"Peer Connection Error: {e}")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("voter_id")
    ap.add_argument("candidate_id")
    ap.add_argument("--ea-host", default = "127.0.0.1")
    ap.add_argument("--ea-port", type = int, default = 5000)
    ap.add_argument("--peer-host", default = "127.0.0.1")
    ap.add_argument("--peer-port", type = int, default = 9100)
    args = ap.parse_args()

    cast_vote(
        voter_id=args.voter_id,
        candidate_id=args.candidate_id,
        ea_host=args.ea_host,
        ea_port=args.ea_port, 
        peer_host=args.peer_host,
        peer_port=args.peer_port,
    )

if __name__ == "__main__":
    main()
