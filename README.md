# Anonymity Network Using Onion Routing

Team 🙈🙉🙊:
- Sudheera Y S (2023111002)
- Monosij Roy (2023111016)
- Anurag Peddi (2023101090)

## Features Implemented
1. **Directory Node & Authenticity**: Tracks active relays, their keys, capacities, and liveness. Enforces cryptographic HMAC signatures to prevent relay spoofing/hijacking.
2. **Relay Nodes (Guard/Exit Constraints)**: Emerge as entry, middle, or exit nodes based on their position. Exit constraints are strictly enforced; only nodes explicitly opting in (`--is-exit`) are used for external routing.
3. **Client Proxy**: Fetches the active relay list, performs dynamically weighted path selection (>= 3 hops) balancing load towards higher-capacity relays, and routes the messages.
4. **Multi-layered Encryption (Forward Secrecy)**: 
   - Establishes unique session keys per hop via an X25519-based single-pass handshake securely generating shared secrets via HKDF.
   - Transmits securely wrapped onion cells using AES-GCM for layered symmetric encryption.
5. **Traffic Analysis Resistance (Padding & Jitter)**: 
   - **Uniform Padding**: Transport layer pads **every** JSON payload to a uniform `DEFAULT_CELL_SIZE` (16KB) regardless of inner payload, explicitly defeating volume-based traffic analysis.
   - **Timing Obfuscation**: Artificial random micro-delays (jitter) are injected at decryption stages to thwart deterministic flow-timing correlation perfectly.
6. **Replay Protection**: Cryptographic caching of single-use `nonce` variables permanently defeats replay injection attacks across active sessions.
7. **Logging & Auditing**: Relay nodes log operational health telemetry (`uptime`, `memory usage`, `CPU usage`) decoupling identifiers from `.log` monitoring files without tracking IPs or payloads.
8. **Real TCP Exit Routing**: Onion exit nodes can proxy actual TCP payloads outward to external network hosts or cleanly fallback to local simulation sinks.

## Project Structure
```
.
├── .env                # Global configuration properties
├── driver.py           # OS-agnostic python driver to start the whole demo seamlessly
├── onion_routing/
│   ├── __init__.py     
│   ├── client.py       # Client logic: path selection, onion building
│   ├── config.py       # Parses .env and default configurations
│   ├── crypto_utils.py # Shared primitives: X25519, HKDF, AES-GCM
│   ├── directory.py    # Directory logic: HMAC validation & heartbeats
│   ├── relay.py        # Generic relay, exit routing, jitter, replay caches
│   └── transport.py    # JSON-based socket communication with explicit 16KB padding
├── requirements.txt    # Project dependencies
├── tests/              # Pytest crypto + unit coverage
├── README.md           # Project documentation
└── Final_Report.md     # Final Report
```

## Prerequisites
- Python 3.10+
- pip

## Quick Start (Setup)

Create your virtual environment, activate it, and install required libraries.
The required dependencies (`cryptography`, `psutil`, `python-dotenv`, `pytest`) are included in `requirements.txt`.

**On Windows:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**On Linux/macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Running the Automated Network Driver
To make running the multi-node network OS-agnostic and easy to operate, we have created a single powerful execution controller: `driver.py`.

**1. Internal Demo Sink Proxy (Default):**
```bash
python driver.py --hops 3 --num-relays 3 --message "Secret payload via onion network"
```

**2. Real TCP External Exit Routing:**
```bash
python driver.py --hops 3 --num-relays 3 --dest-host "www.google.com" --dest-port 80 --message "GET / HTTP/1.0`r`nHost: www.google.com`r`nConnection: close`r`n`r`n"
```

The driver automatically:
1. Spawns the Directory Node.
2. Spawns multiple Relay Nodes (assigning varying ports, dynamic capacities, and explicit Exit flags natively).
3. Executes the Client script which selects a full resilient route (Entry -> Middle -> Exit) and transmits the onion packet.
4. Automatically tears down nodes upon completion executing gracefully to generate logs in the `logs/` folder.

You can individually inspect `logs/relayX.log` or `logs/directory.log` to view decentralized metrics totally devoid of identifying metadata.

## Running Nodes Manually (Advanced)
If you prefer running nodes in separate terminals:

1) **Start the Directory Node:**
```bash
python -m onion_routing.directory --host 127.0.0.1 --port 9000
```
2) **Start Relay Nodes:** (In separate terminals. Note the `--is-exit` flag on final relays!)
```bash
python -m onion_routing.relay --relay-id relayA --port 9101 --capacity 5
python -m onion_routing.relay --relay-id relayB --port 9102 --capacity 3
python -m onion_routing.relay --relay-id relayC --port 9103 --capacity 2 --is-exit
```
3) **Run the Client Proxy:** (With or without the outer exit destination hosts)
```bash
python -m onion_routing.client --hops 3 --destination "demo://echo" --message "hello manual network" --dest-host "example.com" --dest-port 80
```

## Configuration (`.env`)
The code reads constants directly from the `.env` settings file dynamically. You can configure:
- `DEFAULT_CELL_SIZE`: Base padded transit network uniform sizing mapping. Set to `16384` bytes tightly.
- `HEARTBEAT_INTERVAL_SECONDS`: TTL heartbeat intervals securely syncing Directory configurations.
- `RELAY_TTL_SECONDS`: Timeout threshold offline purge periods.
- `MIN_PATH_HOPS`: Client-mandated minimum depth chain.
- `JITTER_MIN` / `JITTER_MAX`: Sub-second float bounds enforcing mathematical padding delay variants.

## Running Tests
Run the comprehensive `pytest` test suite covering cryptographic primitives and framing features.
```bash
python -m pytest tests
```

## Deliverables
1. **Source Code**: Provided fully under `onion_routing/`. All required components are heavily structured and loosely coupled for simple maintenance.
2. **Demonstration**: Run `driver.py` to seamlessly demonstrate establishing an anonymous connection through directory, 3 relay nodes, completing successfully end-to-end to an external server or internal sink logic.
3. **Final Report**: Added `Final_Report.md` exhaustively outlining every protection scheme alongside code documentation.
