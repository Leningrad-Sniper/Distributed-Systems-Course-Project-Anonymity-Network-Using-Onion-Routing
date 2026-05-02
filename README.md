# Anonymity Network Using Onion Routing (Backbone)

Team:
- Sudheera Y S (2023111002)
- Monosij Roy (2023111016)
- Anurag Peddi (2023101090)

This repository now contains a runnable backbone implementation of your course project with:
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

## 5. How To Run (Detailed Team Demo)

Open 5 terminals in the repository root and run the following.

Terminal 1: Start Directory Node

```powershell
python -m onion_routing.directory --host 127.0.0.1 --port 9000
```

Terminal 2: Start Relay A

```powershell
python -m onion_routing.relay --relay-id relayA --host 127.0.0.1 --port 9101 --directory-host 127.0.0.1 --directory-port 9000 --capacity 5
```

Terminal 3: Start Relay B

```powershell
python -m onion_routing.relay --relay-id relayB --host 127.0.0.1 --port 9102 --directory-host 127.0.0.1 --directory-port 9000 --capacity 3
```

Terminal 4: Start Relay C

```powershell
python -m onion_routing.relay --relay-id relayC --host 127.0.0.1 --port 9103 --directory-host 127.0.0.1 --directory-port 9000 --capacity 2
```

Terminal 5: Run Client Proxy

```powershell
python -m onion_routing.client --directory-host 127.0.0.1 --directory-port 9000 --hops 3 --destination demo://echo --message "hello from team demo"
```

Expected output from client:
- Selected relay path (3 hops)
- Final decrypted response dictionary with status and echo message

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
- Per-hop hybrid key establishment (ephemeral X25519 + HKDF + AES-GCM envelope)
- Fixed-size padded entry transport cell (inner recursive layers are compact in this backbone)
- No relay logs include payload content or IP pair mapping logic by design in code paths

Not yet implemented (recommended next milestones):
- Full circuit-level handshake protocol with explicit key-confirmation steps
- Guard/exit policy constraints and relay reputation scoring
- Cover traffic and timing obfuscation beyond fixed-size cells
- Real exit delivery to external TCP/HTTP destination (currently demo sink)
- Persistent signed relay descriptors and directory authenticity verification
- Replay protection and stronger protocol version negotiation

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