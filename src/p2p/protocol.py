from __future__ import annotations
import json
import socket
import struct
from typing import Any
from .config import LENGTH_PREFIX_BYTES, MAX_MSG_BYTES

REGISTER = "REGISTER"
DEREGISTER = "DEREGISTER"
HEARTBEAT = "HEARTBEAT"
PEER_LIST = "PEER_LIST"
HELLO = "HELLO"
NEW_TX = "NEW_TX"
NEW_BLOCK = "NEW_BLOCK"
GET_CHAIN = "GET_CHAIN"
CHAIN_RESP = "CHAIN_RESP"


class ProtocolError(Exception):
    pass

def _recv_exact(sock: socket.socket, n: int) -> bytes:

    """
    Basic recieve method to get exactly n bytes from the socket
    """

    buffer = bytearray()
    while len(buffer) < n:
        chunk = sock.recv(n - len(buffer))
        if not chunk:
            raise ConnectionError("peer closed connection")
        buffer.extend(chunk)
    return bytes(buffer)


def send_msg(sock: socket.socket, msg: dict[str, Any]) -> None:

    """
    Method to send message
    """

    payload = json.dumps(msg, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(payload) > MAX_MSG_BYTES:
        raise ProtocolError(f"message too large: {len(payload)} bytes")
    sock.sendall(struct.pack(">I", len(payload)) + payload)


def recv_msg(sock: socket.socket) -> dict[str, Any]:

    """
    Method to recieve message
    """

    header = _recv_exact(sock, LENGTH_PREFIX_BYTES)
    (length,) = struct.unpack(">I", header)
    if length == 0 or length > MAX_MSG_BYTES:
        raise ProtocolError(f"bad frame length: {length}")
    payload = _recv_exact(sock, length)
    msg = json.loads(payload.decode("utf-8"))
    if not isinstance(msg, dict) or "type" not in msg:
        raise ProtocolError("malformed message: missing 'type'")
    return msg


# Message constructors

def make_register(peer_id: str, ip: str, port: int) -> dict[str, Any]:
    return {"type": REGISTER, "peer_id": peer_id, "ip": ip, "port": port}

def make_deregister(peer_id: str) -> dict[str, Any]:
    return {"type": DEREGISTER, "peer_id": peer_id}

def make_heartbeat(peer_id: str) -> dict[str, Any]:
    return {"type": HEARTBEAT, "peer_id": peer_id}

def make_peer_list(peers: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": PEER_LIST, "peers": peers}

def make_hello(protocol_version: int, peer_id: str, chain_tip_index: int, chain_tip_hash: str,) -> dict[str, Any]:
    return {"type": HELLO, "protocol_version": protocol_version, "peer_id": peer_id, "chain_tip_index": chain_tip_index, "chain_tip_hash": chain_tip_hash}

def make_new_tx(transaction: dict[str, Any]) -> dict[str, Any]:
    return {"type": NEW_TX, "transaction": transaction}

def make_new_block(block: dict[str, Any]) -> dict[str, Any]:
    return {"type": NEW_BLOCK, "block": block}

def make_get_chain(from_index: int) -> dict[str, Any]:
    return {"type": GET_CHAIN, "from_index": from_index}

def make_chain_resp(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": CHAIN_RESP, "blocks": blocks}