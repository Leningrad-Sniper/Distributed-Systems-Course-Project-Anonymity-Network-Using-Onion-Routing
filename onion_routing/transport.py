import json
from typing import Any, Dict

from onion_routing.config import DEFAULT_CELL_SIZE

class ProtocolError(Exception):
    pass


async def send_json(writer, payload: Dict[str, Any], fix_size: int = DEFAULT_CELL_SIZE) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if fix_size > 0:
        padding_needed = fix_size - len(data) - 1 # Space for newline
        if padding_needed > 0:
            data += b" " * padding_needed
    data += b"\n"
    
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
