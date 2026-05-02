import argparse
import asyncio
import os
import random
from typing import Any
import base64

from cryptography.hazmat.primitives import serialization

from onion_routing.config import DEFAULT_CELL_SIZE, MIN_PATH_HOPS
from onion_routing.crypto_utils import decrypt_cell, encrypt_cell, hybrid_encrypt
from onion_routing.crypto_utils import (
    decrypt_cell,
    encrypt_cell,
    hybrid_encrypt,
    derive_session_key_from_private_and_peer,
    sym_encrypt,
    sym_decrypt,
    b64e,
)
from cryptography.hazmat.primitives.asymmetric import x25519
from onion_routing.transport import read_json, send_json


async def fetch_relays(directory_host: str, directory_port: int) -> list[dict[str, Any]]:
    reader, writer = await asyncio.open_connection(directory_host, directory_port)
    await send_json(writer, {"type": "get_relays"})
    response = await read_json(reader)
    writer.close()
    await writer.wait_closed()

    if response.get("type") != "relay_list":
        raise RuntimeError(f"unexpected directory response: {response}")
    return response["relays"]


async def perform_handshake(relay: dict) -> tuple[bytes, str]:
    """Perform X25519 single-pass handshake with relay and confirm session key.

    Returns: (session_key_bytes, handshake_id)
    """
    host = relay["host"]
    port = int(relay["port"])
    relay_pub = relay["public_key"]

    # generate ephemeral key
    eph_priv = x25519.X25519PrivateKey.generate()
    eph_pub = eph_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw if False else serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    # use b64 representation
    eph_pub_b64 = b64e(eph_pub)

    # derive expected session key locally
    session_key = derive_session_key_from_private_and_peer(eph_priv, relay_pub)

    # client nonce
    client_nonce = os.urandom(16)

    reader, writer = await asyncio.open_connection(host, port)
    await send_json(writer, {"type": "handshake_init", "ephemeral_pub": eph_pub_b64, "client_nonce": base64.b64encode(client_nonce).decode("ascii")})
    resp = await read_json(reader)
    writer.close()
    await writer.wait_closed()

    if resp.get("type") != "handshake_response":
        raise RuntimeError(f"handshake init failed: {resp}")

    enc_confirm = resp.get("enc_confirm")
    handshake_id = resp.get("handshake_id")
    if not enc_confirm or not handshake_id:
        raise RuntimeError("invalid handshake response")

    # verify relay knowledge of the derived key
    try:
        confirm_plain = sym_decrypt(session_key, enc_confirm)
    except Exception as exc:
        raise RuntimeError(f"handshake decrypt failed: {exc}")

    if confirm_plain != client_nonce:
        raise RuntimeError("handshake confirmation mismatch")

    # send finish
    reader, writer = await asyncio.open_connection(host, port)
    enc_finish = sym_encrypt(session_key, b"client_confirm")
    await send_json(writer, {"type": "handshake_finish", "handshake_id": handshake_id, "enc_finish": enc_finish})
    finish_resp = await read_json(reader)
    writer.close()
    await writer.wait_closed()

    if finish_resp.get("type") != "handshake_ok":
        raise RuntimeError(f"handshake finish failed: {finish_resp}")

    return session_key, handshake_id


def weighted_path_selection(relays: list[dict[str, Any]], hops: int) -> list[dict[str, Any]]:
    if len(relays) < hops:
        raise RuntimeError(f"Need at least {hops} active relays, found {len(relays)}")

    pool = relays[:]
    selected = []
    for _ in range(hops):
        weights = [max(1, int(relay.get("capacity", 1))) for relay in pool]
        chosen = random.choices(pool, weights=weights, k=1)[0]
        selected.append(chosen)
        pool = [relay for relay in pool if relay["relay_id"] != chosen["relay_id"]]
    return selected


def build_onion(
    path: list[dict[str, Any]],
    destination: str,
    message: str,
    cell_size: int,
) -> tuple[dict, dict[str, bytes]]:
    session_keys: dict[str, bytes] = {}
    inner_layer = None

    for idx in range(len(path) - 1, -1, -1):
        relay = path[idx]
        relay_id = relay["relay_id"]
        # use session key established during handshake
        session_key = relay.get("session_key")
        if not session_key:
            raise RuntimeError(f"no session key for relay {relay_id}")
        session_keys[relay_id] = session_key

        if idx == len(path) - 1:
            plain = {
                "next_hop": None,
                "exit_payload": {
                    "destination": destination,
                    "message": message,
                },
            }
        else:
            next_hop = path[idx + 1]
            plain = {
                "next_hop": {"host": next_hop["host"], "port": next_hop["port"]},
                "inner_layer": inner_layer,
            }

        # Each layer references an already-established handshake id.
        handshake_id = relay.get("handshake_id")
        if not handshake_id:
            raise RuntimeError(f"missing handshake id for relay {relay['relay_id']}")
        current_cell_size = cell_size if idx == 0 else None
        enc_cell = encrypt_cell(session_keys[relay["relay_id"]], plain, current_cell_size)
        inner_layer = {"handshake_id": handshake_id, "cell": enc_cell}

    return inner_layer, session_keys


def peel_response(response: dict, path: list[dict[str, Any]], session_keys: dict[str, bytes]) -> dict:
    current = response
    for idx, relay in enumerate(path):
        relay_id = relay["relay_id"]
        decrypted = decrypt_cell(session_keys[relay_id], current["cell"])

        if idx == len(path) - 1:
            return decrypted
        current = decrypted["payload"]

    raise RuntimeError("failed to peel onion response")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Onion routing client proxy")
    parser.add_argument("--directory-host", default="127.0.0.1")
    parser.add_argument("--directory-port", type=int, default=9000)
    parser.add_argument("--hops", type=int, default=MIN_PATH_HOPS)
    parser.add_argument("--destination", default="demo://echo")
    parser.add_argument("--message", default="hello from onion client")
    parser.add_argument("--cell-size", type=int, default=DEFAULT_CELL_SIZE)
    args = parser.parse_args()

    relays = await fetch_relays(args.directory_host, args.directory_port)
    path = weighted_path_selection(relays, args.hops)

    # Perform explicit handshake with each relay in chosen path
    for relay in path:
        session_key, handshake_id = await perform_handshake(relay)
        relay["handshake_id"] = handshake_id
        # store session key by relay id for onion builder
        relay["session_key"] = session_key

    print("[client] selected path:")
    for relay in path:
        print(f"  - {relay['relay_id']} ({relay['host']}:{relay['port']}, cap={relay['capacity']})")

    onion_layer, session_keys = build_onion(path, args.destination, args.message, args.cell_size)

    entry = path[0]
    reader, writer = await asyncio.open_connection(entry["host"], int(entry["port"]))
    await send_json(writer, {"type": "onion_cell", "layer": onion_layer})
    response = await read_json(reader)
    writer.close()
    await writer.wait_closed()

    if response.get("type") == "error":
        raise RuntimeError(f"entry relay error: {response}")
    if response.get("type") != "onion_response":
        raise RuntimeError(f"unexpected response from entry relay: {response}")

    final = peel_response(response, path, session_keys)
    print("[client] final response:")
    print(final)


if __name__ == "__main__":
    asyncio.run(main())
