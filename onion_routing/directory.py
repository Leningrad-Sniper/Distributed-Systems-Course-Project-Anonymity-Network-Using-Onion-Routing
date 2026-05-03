import argparse
import asyncio
import time
from dataclasses import dataclass, asdict

from onion_routing.config import RELAY_TTL_SECONDS
from onion_routing.transport import ProtocolError, read_json, send_json


@dataclass
class RelayInfo:
    relay_id: str
    host: str
    port: int
    public_key: str
    capacity: int
    is_exit: bool
    last_seen: float

class DirectoryNode:
    def __init__(self) -> None:
        self.relays: dict[str, RelayInfo] = {}

    def _cleanup_relays(self) -> None:
        now = time.time()
        stale_ids = [
            relay_id
            for relay_id, relay in self.relays.items()
            if now - relay.last_seen > RELAY_TTL_SECONDS
        ]
        for relay_id in stale_ids:
            self.relays.pop(relay_id, None)

    def _register_or_update(self, msg: dict) -> None:
        relay = RelayInfo(
            relay_id=msg["relay_id"],
            host=msg["host"],
            port=int(msg["port"]),
            public_key=msg["public_key"],
            capacity=max(1, int(msg.get("capacity", 1))),
            is_exit=bool(msg.get("is_exit", False)),
            last_seen=time.time(),
        )
        self.relays[relay.relay_id] = relay

    def _heartbeat(self, relay_id: str) -> bool:
        if relay_id not in self.relays:
            return False
        self.relays[relay_id].last_seen = time.time()
        return True

    async def handle_client(self, reader, writer) -> None:
        peer = writer.get_extra_info("peername")
        try:
            msg = await read_json(reader)
            msg_type = msg.get("type")

            if msg_type == "register_relay":
                print(f"[directory] Registering relay: {msg.get('relay_id')} from {peer}")
                if "signature" not in msg:
                    print(f"[directory] Dropping unauthenticated registration from {peer}")
                    await send_json(writer, {"type": "error", "message": "unauthenticated relay"})
                else:
                    import hashlib
                    import hmac
                    expected_payload = f"{msg['relay_id']}:{msg['host']}:{msg['port']}:{msg['capacity']}".encode("utf-8")
                    expected_signature = hmac.new(b"directory_shared_secret", expected_payload, hashlib.sha256).hexdigest()
                    if hmac.compare_digest(expected_signature, msg["signature"]):
                        self._register_or_update(msg)
                        await send_json(writer, {"type": "register_ok"})
                    else:
                        print(f"[directory] Signature validation failed for {peer}")
                        await send_json(writer, {"type": "error", "message": "invalid signature"})

            elif msg_type == "heartbeat":
                ok = self._heartbeat(msg.get("relay_id", ""))
                await send_json(writer, {"type": "heartbeat_ok", "known": ok})

            elif msg_type == "get_relays":
                print(f"[directory] Client requested relay list from {peer}")
                self._cleanup_relays()
                relay_list = [asdict(relay) for relay in self.relays.values()]
                await send_json(writer, {"type": "relay_list", "relays": relay_list})

            else:
                await send_json(
                    writer,
                    {"type": "error", "message": f"Unknown message type: {msg_type}"},
                )

        except ProtocolError as exc:
            await send_json(writer, {"type": "error", "message": str(exc)})
        except Exception as exc:  # noqa: BLE001
            await send_json(writer, {"type": "error", "message": f"Directory error: {exc}"})
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"[directory] handled request from {peer}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Onion routing directory node")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()

    node = DirectoryNode()
    server = await asyncio.start_server(node.handle_client, args.host, args.port)
    print(f"[directory] listening on {args.host}:{args.port}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
