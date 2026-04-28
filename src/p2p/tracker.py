from __future__ import annotations
import argparse
import logging
import socket
import threading
import time
from dataclasses import dataclass
from typing import Optional
from . import protocol
from .config import (DEFAULT_TRACKER_HOST, DEFAULT_TRACKER_PORT, PEER_TIMEOUT_S,)

log = logging.getLogger("tracker")


@dataclass
class PeerEntry:
    peer_id: str
    ip: str
    port: int
    sock: socket.socket
    last_seen: float


class Tracker:

    """
    Class for the main tracker server.
    Maintains the active peer set and pushes it out whenever membership changes, also evicts peers if they timeout.
    """

    def __init__(self, host: str = DEFAULT_TRACKER_HOST, port: int = DEFAULT_TRACKER_PORT):
        self.host = host
        self.port = port
        self._peers: dict[str, PeerEntry] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._server_sock: Optional[socket.socket] = None

    # --- Lifecycle ---

    def start(self) -> None:

        """
        Starting method, set up the sockets and set up the timeout threads, as well as the connection handling thread for each peer connection
        """

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen()
        log.info("tracker listening on %s:%d", self.host, self.port)

        threading.Thread(target = self._timeout_loop, name = "tracker-timeout", daemon = True).start()

        try:
            while not self._stop.is_set():
                try:
                    client_sock, addr = self._server_sock.accept()
                except OSError:
                    break
                threading.Thread(target = self._handle_client, args = (client_sock, addr), name = f"tracker-conn-{addr[0]}:{addr[1]}", daemon = True).start()
        finally:
            self.stop()

    def stop(self) -> None:

        """
        Stopping method, literally just setting the stop var and closing the socket
        """

        self._stop.set()
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass

    def _handle_client(self, sock: socket.socket, addr: tuple[str, int]) -> None:

        """
        Connection handling, doing the routing depending on the type of message and then following through with whichever request
        """

        peer_id: Optional[str] = None
        try:
            while not self._stop.is_set():
                msg = protocol.recv_msg(sock)
                mtype = msg.get("type")

                if mtype == protocol.REGISTER:
                    peer_id = msg["peer_id"]
                    self._on_register(peer_id, msg["ip"], int(msg["port"]), sock)
                    # On join, push the current list back to the new peer.
                    protocol.send_msg(sock, protocol.make_peer_list(self._snapshot_peers()))
                elif mtype == protocol.HEARTBEAT:
                    self._on_heartbeat(msg["peer_id"])
                elif mtype == protocol.DEREGISTER:
                    self._on_deregister(msg["peer_id"])
                    break
                else:
                    log.warning("tracker got unexpected message type=%s from %s", mtype, addr)
        except (ConnectionError, protocol.ProtocolError, OSError) as e:
            log.info("tracker conn closed (%s): %s", addr, e)
        finally:
            if peer_id is not None:
                self._on_deregister(peer_id)
            try:
                sock.close()
            except OSError:
                pass

    def _on_register(self, peer_id: str, ip: str, port: int, sock: socket.socket) -> None:

        """
        Adding peer to dict and informing everyone upon a register request
        """

        with self._lock:
            old = self._peers.get(peer_id)
            self._peers[peer_id] = PeerEntry(peer_id, ip, port, sock, time.monotonic())
            changed = old is None or (old.ip, old.port) != (ip, port)
        log.info("REGISTER %s @ %s:%d (changed=%s)", peer_id, ip, port, changed)

        if changed:
            self._broadcast_peer_list()

    def _on_heartbeat(self, peer_id: str) -> None:

        """
        Updating the last seen upon getting a heartbeat from a peer
        """

        with self._lock:
            entry = self._peers.get(peer_id)
            if entry is not None:
                entry.last_seen = time.monotonic()

    def _on_deregister(self, peer_id: str) -> None:

        """
        Removing peer from dict and informing everyone upon a deregister request
        """

        with self._lock:
            removed = self._peers.pop(peer_id, None)
        if removed is not None:
            log.info("DEREGISTER %s", peer_id)
            self._broadcast_peer_list()

    def _timeout_loop(self) -> None:

        """
        Checks if any peers' last seen is greater than timeout, if so we evict them and report it
        """

        while not self._stop.is_set():
            time.sleep(1)
            now = time.monotonic()
            evicted: list[str] = []
            with self._lock:
                for pid, entry in list(self._peers.items()):
                    if now - entry.last_seen > PEER_TIMEOUT_S:
                        self._peers.pop(pid, None)
                        evicted.append(pid)
            for pid in evicted:
                log.info("evicted stale peer %s", pid)
            if evicted:
                self._broadcast_peer_list()

    def _broadcast_peer_list(self) -> None:
        
        """
        Send the peer list to everyone
        """

        peers = [{"peer_id": p.peer_id, "ip": p.ip, "port": p.port} for p in self._peers.values()]
        msg = protocol.make_peer_list(peers)
        with self._lock:
            targets = list(self._peers.values())
        for entry in targets:
            try:
                protocol.send_msg(entry.sock, msg)
            except (OSError, protocol.ProtocolError) as e:
                log.warning("failed to push PEER_LIST to %s: %s", entry.peer_id, e)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_TRACKER_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_TRACKER_PORT)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    Tracker(args.host, args.port).start()


if __name__ == "__main__":
    main()