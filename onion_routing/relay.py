import argparse
import asyncio
import time

from onion_routing.config import DEFAULT_CELL_SIZE, HEARTBEAT_INTERVAL_SECONDS
from onion_routing.crypto_utils import (
    b64e,
    decrypt_cell,
    encrypt_cell,
    generate_x25519_keypair,
    hybrid_decrypt,
)
from onion_routing.crypto_utils import (
    derive_session_key_from_private_and_peer,
    sym_encrypt,
    sym_decrypt,
)
import base64
from onion_routing.transport import read_json, send_json


class RelayNode:
    def __init__(
        self,
        relay_id: str,
        host: str,
        port: int,
        directory_host: str,
        directory_port: int,
        capacity: int,
        cell_size: int,
    ) -> None:
        self.relay_id = relay_id
        self.host = host
        self.port = port
        self.directory_host = directory_host
        self.directory_port = directory_port
        self.capacity = capacity
        self.cell_size = cell_size
        self.private_key, self.public_key_b64 = generate_x25519_keypair()
        self.sessions: dict[str, bytes] = {}

    async def register(self) -> None:
        reader, writer = await asyncio.open_connection(self.directory_host, self.directory_port)
        await send_json(
            writer,
            {
                "type": "register_relay",
                "relay_id": self.relay_id,
                "host": self.host,
                "port": self.port,
                "public_key": self.public_key_b64,
                "capacity": self.capacity,
            },
        )
        response = await read_json(reader)
        writer.close()
        await writer.wait_closed()
        if response.get("type") != "register_ok":
            raise RuntimeError(f"register failed: {response}")
        print(f"[{self.relay_id}] registered with directory")

    async def heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            try:
                reader, writer = await asyncio.open_connection(self.directory_host, self.directory_port)
                await send_json(
                    writer,
                    {
                        "type": "heartbeat",
                        "relay_id": self.relay_id,
                        "ts": time.time(),
                    },
                )
                _ = await read_json(reader)
                writer.close()
                await writer.wait_closed()
            except Exception as exc:  # noqa: BLE001
                print(f"[{self.relay_id}] heartbeat failed: {exc}")

    async def _forward(self, next_hop: dict, inner_layer: dict) -> dict:
        reader, writer = await asyncio.open_connection(next_hop["host"], int(next_hop["port"]))
        await send_json(writer, {"type": "onion_cell", "layer": inner_layer})
        response = await read_json(reader)
        writer.close()
        await writer.wait_closed()
        return response

    async def _handle_handshake_init(self, msg: dict, writer) -> None:
        ephemeral_pub = msg.get("ephemeral_pub")
        client_nonce = msg.get("client_nonce")
        if not ephemeral_pub or not client_nonce:
            await send_json(writer, {"type": "error", "message": "missing handshake fields"})
            return
        session_key = derive_session_key_from_private_and_peer(self.private_key, ephemeral_pub)
        # store under handshake id = ephemeral_pub
        handshake_id = ephemeral_pub
        self.sessions[handshake_id] = session_key

        # decode nonce from base64 then confirm by encrypting raw nonce
        try:
            raw_nonce = base64.b64decode(client_nonce.encode("ascii"))
        except Exception:
            await send_json(writer, {"type": "error", "message": "invalid nonce encoding"})
            return

        enc = sym_encrypt(session_key, raw_nonce)
        await send_json(writer, {"type": "handshake_response", "enc_confirm": enc, "handshake_id": handshake_id})

    async def _handle_handshake_finish(self, msg: dict, writer) -> None:
        handshake_id = msg.get("handshake_id")
        enc_finish = msg.get("enc_finish")
        if not handshake_id or not enc_finish:
            await send_json(writer, {"type": "error", "message": "missing finish fields"})
            return
        session_key = self.sessions.get(handshake_id)
        if not session_key:
            await send_json(writer, {"type": "error", "message": "unknown handshake id"})
            return
        try:
            plaintext = sym_decrypt(session_key, enc_finish)
            if plaintext.decode("utf-8") != "client_confirm":
                await send_json(writer, {"type": "error", "message": "handshake verification failed"})
                return
            await send_json(writer, {"type": "handshake_ok", "handshake_id": handshake_id})
        except Exception as exc:  # noqa: BLE001
            await send_json(writer, {"type": "error", "message": f"handshake decrypt failed: {exc}"})
            return

    def _handle_exit_payload(self, payload: dict) -> dict:
        destination = payload.get("destination", "demo://echo")
        message = payload.get("message", "")
        return {
            "status": "ok",
            "relay": self.relay_id,
            "destination": destination,
            "echo": message,
            "note": "Exit relay delivered payload to demo sink",
        }

    async def _process_layer(self, layer: dict) -> dict:
        # support legacy 'enc_key' envelope or handshake-based session ids
        if "enc_key" in layer:
            session_key = hybrid_decrypt(self.private_key, layer["enc_key"])
        elif "handshake_id" in layer:
            session_key = self.sessions.get(layer["handshake_id"])
            if session_key is None:
                raise RuntimeError("unknown handshake id")
        else:
            raise RuntimeError("no session key info in layer")

        inner = decrypt_cell(session_key, layer["cell"])

        if inner.get("next_hop"):
            next_response = await self._forward(inner["next_hop"], inner["inner_layer"])
            wrapped_plain = {"payload": next_response}
        else:
            exit_result = self._handle_exit_payload(inner["exit_payload"])
            wrapped_plain = exit_result

        wrapped_cell = encrypt_cell(session_key, wrapped_plain, None)
        return {"type": "onion_response", "cell": wrapped_cell}

    async def handle_client(self, reader, writer) -> None:
        peer = writer.get_extra_info("peername")
        try:
            msg = await read_json(reader)
            mtype = msg.get("type")
            if mtype == "onion_cell":
                response = await self._process_layer(msg["layer"])
                await send_json(writer, response)
            elif mtype == "handshake_init":
                await self._handle_handshake_init(msg, writer)
            elif mtype == "handshake_finish":
                await self._handle_handshake_finish(msg, writer)
            else:
                await send_json(writer, {"type": "error", "message": f"unknown message type {mtype}"})
        except Exception as exc:  # noqa: BLE001
            await send_json(writer, {"type": "error", "message": f"relay error: {exc}"})
            print(f"[{self.relay_id}] error with {peer}: {exc}")
        finally:
            writer.close()
            await writer.wait_closed()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Onion routing relay")
    parser.add_argument("--relay-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--directory-host", default="127.0.0.1")
    parser.add_argument("--directory-port", type=int, default=9000)
    parser.add_argument("--capacity", type=int, default=1)
    parser.add_argument("--cell-size", type=int, default=DEFAULT_CELL_SIZE)
    args = parser.parse_args()

    relay = RelayNode(
        relay_id=args.relay_id,
        host=args.host,
        port=args.port,
        directory_host=args.directory_host,
        directory_port=args.directory_port,
        capacity=args.capacity,
        cell_size=args.cell_size,
    )

    await relay.register()
    asyncio.create_task(relay.heartbeat_loop())

    server = await asyncio.start_server(relay.handle_client, args.host, args.port)
    print(f"[{args.relay_id}] listening on {args.host}:{args.port}")
    print(f"[{args.relay_id}] public_key={relay.public_key_b64}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
