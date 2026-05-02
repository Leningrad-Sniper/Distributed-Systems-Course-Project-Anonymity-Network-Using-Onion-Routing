import argparse
import asyncio
import os
import random
from typing import Any

from onion_routing.config import DEFAULT_CELL_SIZE, MIN_PATH_HOPS
from onion_routing.crypto_utils import decrypt_cell, encrypt_cell, hybrid_encrypt
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
        session_key = os.urandom(32)
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

        enc_key = hybrid_encrypt(relay["public_key"], session_key)
        # Only the entry layer is padded to fixed size; inner layers stay compact.
        current_cell_size = cell_size if idx == 0 else None
        enc_cell = encrypt_cell(session_key, plain, current_cell_size)
        inner_layer = {"enc_key": enc_key, "cell": enc_cell}

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
