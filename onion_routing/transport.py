import json
from typing import Any, Dict


class ProtocolError(Exception):
    pass


async def send_json(writer, payload: Dict[str, Any]) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
    writer.write(data)
    await writer.drain()


async def read_json(reader) -> Dict[str, Any]:
    raw = await reader.readline()
    if not raw:
        raise ProtocolError("Connection closed")

    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ProtocolError("Invalid JSON payload") from exc
