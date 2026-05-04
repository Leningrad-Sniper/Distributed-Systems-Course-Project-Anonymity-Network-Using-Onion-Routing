import pytest
import io
import asyncio
import json
from unittest.mock import AsyncMock
from onion_routing.transport import send_json, read_json

def test_send_json_exact_padding():
    """Verify that send_json correctly pads the byte length to the EXACT given size including the newline."""
    mock_writer = AsyncMock()
    from unittest.mock import MagicMock
    mock_writer.write = MagicMock()
    
    payload = {"status": "ok", "foo": "bar"}
    # Target size: 1024 bytes
    asyncio.run(send_json(mock_writer, payload, fix_size=1024))
    
    mock_writer.write.assert_called_once()
    
    # Extract what was written
    written_data = mock_writer.write.call_args[0][0]
    
    assert len(written_data) == 1024, f"Transport frame must equal exactly 1024 bytes, got {len(written_data)}"
    assert written_data.endswith(b"\n"), "Must terminate with protocol newline"
    
    # Payload is parseable if stripped
    cleaned = written_data.strip(b" \n")
    parsed = json.loads(cleaned.decode("utf-8"))
    assert parsed == payload

def test_send_json_no_padding_flag():
    """Verify that setting fix_size=0 completely ignores padding generation."""
    mock_writer = AsyncMock()
    from unittest.mock import MagicMock
    mock_writer.write = MagicMock()
    
    payload = {"short": "msg"}
    # We disable padding intentionally to test dynamic sizes
    asyncio.run(send_json(mock_writer, payload, fix_size=0))
    
    written_data = mock_writer.write.call_args[0][0]
    
    expected_data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
    
    assert written_data == expected_data, "Should exactly match stripped JSON + newline"
    assert len(written_data) < 200, "Should be tiny (no 16KB padding inserted)"
