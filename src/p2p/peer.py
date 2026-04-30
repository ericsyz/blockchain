from __future__ import annotations
import argparse
import logging
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from src.blockchain import Node, transaction_id
from . import protocol
from .config import (CONNECT_TIMEOUT_S, DEFAULT_PEER_PORT, DEFAULT_TRACKER_HOST, DEFAULT_TRACKER_PORT, HEARTBEAT_INTERVAL_S, PROTOCOL_VERSION,)
from .serialization import block_to_dict, dict_to_block, dict_to_tx

log = logging.getLogger("peer")


@dataclass
class RemotePeer:

    """
    This class is basically for the peer's that each peer sees

    Note that the send_lock makes it so that writes to a socket are serialized while broadcasting can still be in parallel
    """

    peer_id: str
    ip: str
    port: int
    sock: socket.socket
    send_lock: threading.Lock = field(default_factory=threading.Lock)

class Peer:

    """Peer node info:

    Like we mentioned in the design doc, it has these threads:
    - tracker thread: maintains connection to tracker and reads PEER_LIST pushes
    - heartbeat thread: sends heartbeats
    - listener thread: accepts inbound peer connections
    - per-peer reader threads: one per outbound/inbound connection
    - miner thread: stub; for the PoW stuff

    Stuff for TODO: Block / Transaction / Mempool / Chain are not implemented here. Hooks too
    """

    def __init__(self, peer_id: Optional[str] = None, node: Optional[Node] = None,
                 listen_host: str = "127.0.0.1", listen_port: int = DEFAULT_PEER_PORT,
                 tracker_host: str = DEFAULT_TRACKER_HOST, tracker_port: int = DEFAULT_TRACKER_PORT):
        self.peer_id = peer_id or uuid.uuid4().hex[:8]

        # Local blockchain node. Wesley's `Node` is not thread-safe; we serialize
        # all calls into it through `_node_lock` since multiple threads (miner,
        # per-peer readers) can hit it concurrently.
        self.node = node if node is not None else Node(node_id=self.peer_id)
        self._node_lock = threading.Lock()

        # Listen vars are the peer's server side to be dialed from, also what we advertise to the tracker
        self.listen_host = listen_host
        self.listen_port = listen_port

        # Tracker vars are the peer's client side to talk to the tracker, really mainly just for register/deregister and heartbeat
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port

        # Flag to tell itself to kill all the threads its running
        self._stop = threading.Event()

        self._listen_sock: Optional[socket.socket] = None
        self._tracker_sock: Optional[socket.socket] = None
        self._tracker_send_lock = threading.Lock()
        self._peers: dict[str, RemotePeer] = {}
        self._peers_lock = threading.Lock()

        # Gossip w/ deduplication. TODO rn the seen_tx just keeps growing, maybe we have to cap it?? not sure if its rly in scope but we could do like a time-based
        self._seen_tx: set[str] = set()
        self._seen_block: set[str] = set()
        self._seen_lock = threading.Lock()

    def start(self) -> None:

        """
        The method to start everything up.
        
        In order of what it does:
        1. Straightforward set up for the listening socket. For the thread, it essentially opens up loop for any peer to dial in, then it calls accept() and does handshake
        2. Tracker setup, connects, then registers, and then opens the tracker thread
        3. Sets up the heartbeat and the miner thread

        """

        # Step 1
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.listen_host, self.listen_port))
        sock.listen()
        self._listen_sock = sock
        threading.Thread(target = self._accept_loop, name = "peer-listener", daemon = True).start()

        # Step 2
        sock = socket.create_connection((self.tracker_host, self.tracker_port), timeout = CONNECT_TIMEOUT_S)
        sock.settimeout(None)
        self._tracker_sock = sock
        with self._tracker_send_lock: protocol.send_msg(sock, protocol.make_register(self.peer_id, self.listen_host, self.listen_port))
        threading.Thread(target = self._tracker_reader, name = "peer-tracker-reader", daemon = True).start()

        # Step 3
        threading.Thread(target = self._heartbeat_loop, name = "peer-heartbeat", daemon = True).start()
        threading.Thread(target = self._miner_loop, name = "peer-miner", daemon = True).start()
        log.info("peer %s has been set up on %s:%d", self.peer_id, self.listen_host, self.listen_port)

    def stop(self) -> None:

        """
        The method to shut everything down.

        In order of what it does:
        1. Set the shutdown var
        2. Send the deregister signal
        3. Close the tracker, listener, and then every peer socket
        """

        self._stop.set()

        if self._tracker_sock is not None:
            try:
                with self._tracker_send_lock:
                    protocol.send_msg(self._tracker_sock, protocol.make_deregister(self.peer_id))
            except (OSError, protocol.ProtocolError):
                pass
            try:
                self._tracker_sock.close()
            except OSError:
                pass

        if self._listen_sock is not None:
            try:
                self._listen_sock.close()
            except OSError:
                pass

        with self._peers_lock:
            for p in self._peers.values():
                try:
                    p.sock.close()
                except OSError:
                    pass
            self._peers.clear()

    # --- The loops that are always up and running ---

    def _tracker_reader(self) -> None:

        """
        Listens to the tracker, literally just waits for peer list updates and then reaches out to new peers
        """

        assert self._tracker_sock is not None

        try:
            while not self._stop.is_set():
                msg = protocol.recv_msg(self._tracker_sock)

                if msg.get("type") == protocol.PEER_LIST:

                    for entry in msg.get("peers", []):
                        pid = entry["peer_id"]

                        if pid == self.peer_id:
                            continue

                        with self._peers_lock:
                            already = pid in self._peers

                        if already:
                            continue
                        
                        # Just a tie-break
                        if self.peer_id < pid:
                            threading.Thread(target = self._dial_peer, args = (pid, entry["ip"], int(entry["port"])),
                                name = f"peer-out-{pid}", daemon = True).start()
                else:
                    log.warning("unexpected tracker msg: %s", msg.get("type"))
        except (ConnectionError, protocol.ProtocolError, OSError) as e:
            if not self._stop.is_set():
                log.warning("tracker connection lost: %s", e)

    def _heartbeat_loop(self) -> None:

        while not self._stop.is_set():
            if self._tracker_sock is not None:
                try:
                    with self._tracker_send_lock:
                        protocol.send_msg(self._tracker_sock, protocol.make_heartbeat(self.peer_id))
                except (OSError, protocol.ProtocolError) as e:
                    log.warning("heartbeat send failed: %s", e)
            self._stop.wait(HEARTBEAT_INTERVAL_S)

    def _accept_loop(self) -> None:
        assert self._listen_sock is not None
        while not self._stop.is_set():
            try:
                conn, addr = self._listen_sock.accept()
            except OSError:
                return
            threading.Thread(
                target=self._inbound_handshake,
                args=(conn, addr),
                name=f"peer-in-{addr[0]}:{addr[1]}",
                daemon=True,
            ).start()

    def _inbound_handshake(self, sock: socket.socket, addr: tuple[str, int]) -> None:
        try:
            hello = protocol.recv_msg(sock)
            if hello.get("type") != protocol.HELLO:
                log.warning("inbound %s sent %s before HELLO", addr, hello.get("type"))
                sock.close()
                return
            remote_id = hello["peer_id"]
            self._send_hello(sock)
            remote = RemotePeer(remote_id, addr[0], int(hello.get("listen_port", addr[1])), sock)
            self._add_peer(remote)
            self._peer_reader(remote)
        except (ConnectionError, protocol.ProtocolError, OSError, KeyError) as e:
            log.info("inbound handshake from %s failed: %s", addr, e)
            try:
                sock.close()
            except OSError:
                pass

    def _dial_peer(self, peer_id: str, ip: str, port: int) -> None:

        """
        The actual method to dial another peer
        Sets up socket, sends hello, makes sure it recieves a good handshake response, and then adds peer to dict and opens thread

        """

        try:
            sock = socket.create_connection((ip, port), timeout=CONNECT_TIMEOUT_S)
            sock.settimeout(None)
        except OSError as e:
            log.warning("dial %s@%s:%d failed: %s", peer_id, ip, port, e)
            return
        
        try:
            self._send_hello(sock)
            hello = protocol.recv_msg(sock)
            if hello.get("type") != protocol.HELLO:
                log.warning("peer %s replied with %s, not HELLO", peer_id, hello.get("type"))
                sock.close()
                return
        except (ConnectionError, protocol.ProtocolError, OSError) as e:
            log.warning("handshake with %s failed: %s", peer_id, e)
            try:
                sock.close()
            except OSError:
                pass
            return
        
        remote = RemotePeer(peer_id, ip, port, sock)
        self._add_peer(remote)
        threading.Thread(target=self._peer_reader, args=(remote,), name=f"peer-rd-{peer_id}", daemon=True).start()

    def _send_hello(self, sock: socket.socket) -> None:
        """
        Method for simple hello
        """
        tip_idx, tip_hash = self._chain_tip()
        msg = protocol.make_hello(PROTOCOL_VERSION, self.peer_id, tip_idx, tip_hash)
        msg["listen_port"] = self.listen_port  # so inbound side learns our dial address
        protocol.send_msg(sock, msg)

    def _add_peer(self, remote: RemotePeer) -> None:

        """
        Method for adding peer, takes the lock, makes sure to replace any potential pre-existing entry (in case of dropping and reconnecting), then add new entry
        """

        with self._peers_lock:
            existing = self._peers.get(remote.peer_id)
            if existing is not None:
                try:
                    existing.sock.close()
                except OSError:
                    pass
            self._peers[remote.peer_id] = remote
        log.info("connected to peer %s @ %s:%d", remote.peer_id, remote.ip, remote.port)

    def _drop_peer(self, peer_id: str) -> None:

        """
        Method for dropping a peer, removing it from the dict and then closing the socket
        """

        with self._peers_lock:
            remote = self._peers.pop(peer_id, None)
        if remote is not None:
            try:
                remote.sock.close()
            except OSError:
                pass
            log.info("dropped peer %s", peer_id)


    def _peer_reader(self, remote: RemotePeer) -> None:

        """
        The reading loop for each peer connection
        """

        try:
            while not self._stop.is_set():
                msg = protocol.recv_msg(remote.sock)
                self._dispatch(remote, msg)
        except (ConnectionError, protocol.ProtocolError, OSError) as e:
            if not self._stop.is_set():
                log.info("peer %s disconnected: %s", remote.peer_id, e)
        finally:
            self._drop_peer(remote.peer_id)

    def _dispatch(self, sender: RemotePeer, msg: dict[str, Any]) -> None:

        """
        Method responsible for routing each type of message, whether it be for various functionalities of our blockchain system
        """

        mtype = msg.get("type")
        if mtype == protocol.NEW_TX:
            self._handle_new_tx(sender, msg["transaction"])
        elif mtype == protocol.NEW_BLOCK:
            self._handle_new_block(sender, msg["block"])
        elif mtype == protocol.GET_CHAIN:
            self._handle_get_chain(sender, int(msg["from_index"]))
        elif mtype == protocol.CHAIN_RESP:
            self._handle_chain_resp(sender, msg.get("blocks", []))
        else:
            log.warning("unexpected peer msg from %s: %s", sender.peer_id, mtype)

    ### Blockchain message handlers (wired into Wesley's Node)

    def _handle_new_tx(self, sender: RemotePeer, tx: dict[str, Any]) -> None:
        tx_hash = self._tx_hash(tx)
        with self._seen_lock:
            if tx_hash in self._seen_tx:
                return
            self._seen_tx.add(tx_hash)
        with self._node_lock:
            ok, reason = self.node.submit_transaction(dict_to_tx(tx))
        if not ok:
            log.info("rejected tx from %s: %s", sender.peer_id, reason)
            return
        self._broadcast(protocol.make_new_tx(tx), exclude=sender.peer_id)

    def _handle_new_block(self, sender: RemotePeer, block: dict[str, Any]) -> None:
        block_hash = self._block_hash(block)
        with self._seen_lock:
            if block_hash in self._seen_block:
                return
            self._seen_block.add(block_hash)
        with self._node_lock:
            ok, reason = self.node.receive_block(dict_to_block(block))
        if not ok:
            log.info("rejected block from %s: %s", sender.peer_id, reason)
            # Looks like we're behind — ask sender for the missing tail.
            if reason in ("bad index", "bad previous_hash"):
                with self._node_lock:
                    next_idx = self.node.height() + 1
                self._send(sender, protocol.make_get_chain(next_idx))
            return
        self._broadcast(protocol.make_new_block(block), exclude=sender.peer_id)

    def _handle_get_chain(self, sender: RemotePeer, from_index: int) -> None:
        with self._node_lock:
            full = self.node.export_chain_payload()
        blocks = full[from_index:] if 0 <= from_index < len(full) else []
        self._send(sender, protocol.make_chain_resp(blocks))

    def _handle_chain_resp(self, sender: RemotePeer, blocks: list[dict[str, Any]]) -> None:
        if not blocks:
            return
        decoded = [dict_to_block(b) for b in blocks]
        with self._node_lock:
            ok, reason = self.node.receive_chain(decoded)
        if not ok:
            log.info("chain replace from %s rejected: %s", sender.peer_id, reason)
            return
        # Mark every block in the new chain as seen so we don't re-process echoes.
        with self._seen_lock:
            for b in decoded:
                self._seen_block.add(b.hash)

    # --- Basic Send helpers ---

    def _send(self, remote: RemotePeer, msg: dict[str, Any]) -> None:
        try:
            with remote.send_lock:
                protocol.send_msg(remote.sock, msg)
        except (OSError, protocol.ProtocolError) as e:
            log.warning("send to %s failed: %s", remote.peer_id, e)
            self._drop_peer(remote.peer_id)

    def _broadcast(self, msg: dict[str, Any], exclude: Optional[str] = None) -> None:
        with self._peers_lock:
            targets = [p for pid, p in self._peers.items() if pid != exclude]
        for remote in targets:
            self._send(remote, msg)

    # --- Hooks into the Node class that Wesley added ---

    def _chain_tip(self) -> tuple[int, str]:
        """
        Used during the handshake, we send the HELLO w/ the chain tip index and hash to check if both peers are up-to-date
        """

        with self._node_lock:
            return (self.node.height(), self.node.blockchain.tip.hash)

    def _tx_hash(self, tx: dict[str, Any]) -> str:
        """
        The gossip deduplication id for any of the transactions
        """
        return transaction_id(dict_to_tx(tx))

    def _block_hash(self, block: dict[str, Any]) -> str:
        """
        The gossip deduplication id for any of the blocks, note that we just straight up return the block's hash
        """
        return block["hash"]

    def _miner_loop(self) -> None:
        """
        This is the actual method for mining thread:
        1. Prompt the node to mine a block, which returns a new block if success and None if the mempool is empty
        2. If there is nothing, then wait half a second
        3. If we did get a block, we mark it and then broadcast it to our peers
        
        """


        while not self._stop.is_set():
            with self._node_lock:
                mined = self.node.mine_once()
            if mined is None:
                self._stop.wait(0.5)
                continue
            # Mark our own block seen before broadcasting so echoes from peers
            # don't make us re-process it.
            with self._seen_lock:
                self._seen_block.add(mined.hash)
            log.info("mined block %d %s", mined.index, mined.hash[:12])
            self._broadcast(protocol.make_new_block(block_to_dict(mined)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--peer-id", default=None)
    ap.add_argument("--listen-host", default = "127.0.0.1")
    ap.add_argument("--listen-port", type = int, default = DEFAULT_PEER_PORT)
    ap.add_argument("--tracker-host", default = DEFAULT_TRACKER_HOST)
    ap.add_argument("--tracker-port", type = int, default = DEFAULT_TRACKER_PORT)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    peer_id = args.peer_id or uuid.uuid4().hex[:8]
    node = Node(node_id=peer_id)
    peer = Peer(peer_id=peer_id, node=node, listen_host=args.listen_host, listen_port=args.listen_port,
                tracker_host=args.tracker_host, tracker_port=args.tracker_port)
    peer.start()

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        peer.stop()

if __name__ == "__main__":
    main()
