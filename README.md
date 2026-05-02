# Anonymity Network Using Onion Routing (Backbone)

Team:
- Sudheera Y S (2023111002)
- Monosij Roy (2023111016)
- Anurag Peddi (2023101090)

This repository now contains a runnable backbone implementation of your course project, and the main run/test flow has been verified, with:
- Directory Node
- Relay Nodes (entry/middle/exit behavior emerges from position in the selected path)
- Client Proxy
- Multi-layer encryption using hybrid key exchange + symmetric AEAD
- Fixed-size entry transport cell with padding + compact inner onion layers

## 1. What Is Implemented In This Backbone

1. Relay discovery and liveness tracking
- Relays register to the Directory Node with host, port, public key, and capacity.
- Relays send heartbeats periodically.
- Directory removes stale relays after TTL expiry.

2. Weighted path selection
- Client fetches active relays.
- Client selects a multi-hop path using relay capacity as selection weight.

3. Onion construction and forwarding
- Client creates one random symmetric session key per selected relay.
- Each session key is encrypted for that relay using an ephemeral X25519-based hybrid envelope.
- Entry transport cell is fixed-size and padded; inner recursive layers use compact framing.
- Each relay decrypts exactly one layer, learns only next hop, forwards inner layer.

4. Reverse-path layered response
- Exit relay creates final response.
- Intermediate relays wrap the response in reverse layers.
- Client peels all layers to recover final payload.

5. Run and validation support
- `run_demo.ps1` starts the directory, relays, and client for a quick demo.
- `pytest -q` runs the automated crypto and cell-framing tests.
- `pytest.ini` adds the repository root to `sys.path` so the package imports cleanly during test collection.

## 2. Project Structure

```
.
├── onion_routing/
│   ├── __init__.py
│   ├── client.py
│   ├── config.py
│   ├── crypto_utils.py
│   ├── directory.py
│   ├── relay.py
│   └── transport.py
├── requirements.txt
└── README.md
```

## 3. Prerequisites

- Python 3.10+
- pip
- OS: tested for local execution (Windows PowerShell commands shown below)

## 4. Setup

From repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If execution policy blocks activation in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 5. How To Run

1) Run the unit tests:

```powershell
pytest -q
```

2) Quick demo (launches services in separate windows):

```powershell
.\run_demo.ps1
```

This opens multiple PowerShell windows: Directory, three Relay processes, and the client run. Watch the client window for the selected path and final response.

3) Manual demo (single-terminal reproducible steps):

- Start the Directory (port 9000):

```powershell
python -m onion_routing.directory --host 127.0.0.1 --port 9000
```

- Start three relays (each in its own terminal):

```powershell
python -m onion_routing.relay --relay-id relayA --host 127.0.0.1 --port 9101 --directory-host 127.0.0.1 --directory-port 9000 --capacity 5 --cell-size 16384
python -m onion_routing.relay --relay-id relayB --host 127.0.0.1 --port 9102 --directory-host 127.0.0.1 --directory-port 9000 --capacity 3 --cell-size 16384
python -m onion_routing.relay --relay-id relayC --host 127.0.0.1 --port 9103 --directory-host 127.0.0.1 --directory-port 9000 --capacity 2 --cell-size 16384
```

- Run the client (single-shot):

```powershell
python -m onion_routing.client --directory-host 127.0.0.1 --directory-port 9000 --hops 3 --destination demo://echo --message "hello from team demo"
```

4) Alternative isolated handshake demo (development configuration):

```powershell
# Directory on 9002 and relays on 9301-9303
python -m onion_routing.directory --host 127.0.0.1 --port 9002
python -m onion_routing.relay --relay-id r1 --host 127.0.0.1 --port 9301 --directory-host 127.0.0.1 --directory-port 9002 --capacity 5 --cell-size 16384
python -m onion_routing.relay --relay-id r2 --host 127.0.0.1 --port 9302 --directory-host 127.0.0.1 --directory-port 9002 --capacity 3 --cell-size 16384
python -m onion_routing.relay --relay-id r3 --host 127.0.0.1 --port 9303 --directory-host 127.0.0.1 --directory-port 9002 --capacity 2 --cell-size 16384
python -m onion_routing.client --directory-host 127.0.0.1 --directory-port 9002 --hops 3 --destination demo://echo --message "handshake test" --cell-size 16384
```

Example expected client output:

```
[client] selected path:
  - relayB (127.0.0.1:9102, cap=3)
  - relayA (127.0.0.1:9101, cap=5)
  - relayC (127.0.0.1:9103, cap=2)
[client] final response:
{'status': 'ok', 'relay': 'relayC', 'destination': 'demo://echo', 'echo': 'hello from team demo', 'note': 'Exit relay delivered payload to demo sink'}
```

Notes and troubleshooting:
- Unit tests are under the `tests/` directory and validate the cryptographic primitives and cell framing.
- If a port is already in use, change the port numbers (for example use 9201/9202/9203) and restart.
- `run_demo.ps1` launches services in separate windows and does not auto-terminate them; close the windows when finished.

Optionally, a single-terminal orchestrator script can be added to start services as background processes and tear them down automatically after the client completes.

## 6. Command Reference

Directory Node:

```powershell
python -m onion_routing.directory [--host 127.0.0.1] [--port 9000]
```

Relay Node:

```powershell
python -m onion_routing.relay --relay-id <id> --port <port> [--host 127.0.0.1] [--directory-host 127.0.0.1] [--directory-port 9000] [--capacity 1] [--cell-size 16384]
```

Client Proxy:

```powershell
python -m onion_routing.client [--directory-host 127.0.0.1] [--directory-port 9000] [--hops 3] [--destination demo://echo] [--message "text"] [--cell-size 16384]
```

## 7. Security Notes (Current Backbone vs Final Goal)
Implemented now:
- Per-hop hybrid key establishment (ephemeral X25519 + HKDF + AES-GCM envelope).
- Per-hop handshake with explicit key-confirmation steps (client↔relay three-step handshake; confirmations are encrypted and verified).
- Fixed-size padded entry transport cell combined with compact inner onion layers (avoids exponential padding growth).
- No relay-side logging of payload contents or IP-pair mappings in current code paths.
- Unit tests covering crypto primitives and cell framing; `pytest.ini` ensures tests import the package during collection.

Remaining work / recommended next milestones:
- Circuit-level enhancements (session continuity, stronger handshake coverage, and replay protection).
- Guard/exit policy constraints and relay reputation scoring.
- Cover traffic, batching, and timing obfuscation beyond fixed-size cells.
- Real exit delivery to external TCP/HTTP/TCP destinations (current demo uses an internal sink).
- Persistent signed relay descriptors and directory authenticity verification.
- Stronger protocol version negotiation and downgrade protections.
- Additional unit tests (handshake negative cases, relay error handling) and a single-terminal orchestrator to automate demo startup/teardown.

## 8. Troubleshooting

1. Client says not enough relays:
- Ensure at least `--hops` relay processes are running and registered.

2. Port already in use:
- Change relay port values (for example 9201, 9202, 9203) and restart.

3. Import/module error:
- Run commands from repository root.
- Confirm virtual environment is activated.

4. Heartbeat/directory errors:
- Verify directory host/port are consistent across all relays and client.

## 9. Suggested Team Work Split For Next Iterations

1. Member A: Circuit handshake hardening + replay protection.
2. Member B: Directory authenticity, relay descriptors, and weighted-routing improvements.
3. Member C: Exit delivery adapters (TCP/HTTP) + measurement scripts + performance section.

## 10. Quick Demo Script (Optional Manual Sequence)

Run in order:
1. Start directory.
2. Start at least 3 relays.
3. Run client with `--hops 3`.
4. Observe selected path and final decrypted response.

This baseline is intentionally modular so you can incrementally evolve it into your final report-grade implementation.



