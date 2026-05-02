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
        session_key = hybrid_decrypt(self.private_key, layer["enc_key"])
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
            if msg.get("type") != "onion_cell":
                await send_json(writer, {"type": "error", "message": "expected onion_cell"})
            else:
                response = await self._process_layer(msg["layer"])
                await send_json(writer, response)
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
