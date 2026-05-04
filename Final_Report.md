# Final Report: Anonymity Network via Onion Routing

**Team 🙈🙉🙊:**
- Sudheera Y S (2023111002)
- Monosij Roy (2023111016)
- Anurag Peddi (2023101090)

## 1. Introduction and Architectural Overview

As outlined in our initial project proposal, our objective was to design and implement a distributed anonymity network utilizing the principles of Onion Routing. Standard Internet protocols inadvertently expose the source and destination IP metadata, permitting traffic analysis. By implementing this network, we successfully obfuscate the communication link between a sender and receiver to prevent generalized surveillance and node-level metadata exposure. 

The architecture consists of three primary fully asynchronous Python modules utilizing the `asyncio` framework:
1. **Directory Node (`directory.py`)**: A centralized coordination service. It accepts cryptographic registrations from active relays, enforces authenticity via HMAC signatures, tracks operational heartbeat telemetry, and distributes this network layout to clients.
2. **Relay Nodes (`relay.py`)**: The intermediate servers responsible for masking network hops. They accept incoming connections, decrypt their specific designated layer of the "onion" using a derived symmetric session key, and subsequently forward the stripped payload to either the next relay or the ultimate exit destination.
3. **Client Proxy (`client.py`)**: The user-facing software. It coordinates with the Directory Node, performs capacity-weighted path selection to pick an Entry, Middle, and Exit node, performs individual cryptographic handshakes to establish session keys, and constructs the recursive onion-encrypted payload.

---

## 2. Protocol Design & System Logic

### Payload Construction (The Onion)
The core design relies on strict encapsulation. To send a message, the Client Proxy constructs nested layers of encryption.
- **Layer 1 (The Core)**: The raw payload and the external destination IP/Port. Encrypted symmetrically exclusively for the **Exit Node**.
- **Layer 2**: Encrypted for the **Middle Node**. Contains Layer 1 and the location of the Exit node.
- **Layer 3**: Encrypted for the **Entry Node**. Contains Layer 2 and the location of the Middle node.

When traversing the network, no single relay possesses the full mapping. The Entry node knows the Client but not the destination. The Exit node knows the payload/destination but not the Client. The Middle node only knows the adjoining relays. 

### Load Balancing & Path Selection
We fulfilled the proposal's requirement to implement "weighted routing and basic load distribution."
Load balancing operates entirely dynamically during the Client's path selection phase (`client.py` -> `weighted_path_selection`):
1. **Relay Capacities**: When relays boot up, they declare an arbitrary available throughput/resource metric (`capacity`). This is securely registered to the Directory Node.
2. **Weighted Random Selection**: The Client requests these metrics and utilizes a randomly weighted selection algorithm (using `random.choices(pool, weights=...)`).
3. **Distribution**: Relays with a declared capacity of `5` are mathematically five times more likely to be selected into a circuit than a relay with a capacity of `1`. This efficiently distributes network traffic away from congested or weak relays transparently, naturally load-balancing the ecosystem without centralized bottlenecks.
4. **Exit Delegation**: The algorithm respects relay limitations by ensuring the final hop explicitly permits Exit Traffic via the `--is-exit` flag constraint.

---

## 3. Cryptographic Handshake Process

To ensure robust and forward-secret communications mentioned in the proposal's multi-layered encryption requirements, we implemented an **Elliptic Curve Diffie-Hellman (ECDH) Key Exchange**.

**The Handshake:**
1. **Directory Fetch**: The Client already possesses the Relay's public key from the Directory Node.
2. **Ephemeral Initialization**: The Client temporarily generates its own one-time-use `X25519` keypair. It sends the `ephemeral_public_key` and a randomly generated challenge `nonce` to the relay.
3. **Key Derivation (Shared Secret)**: Both the Client (using its private ephemeral key + the Relay's public key) and the Relay (using its private key + the Client's ephemeral public key) utilize elliptic curve mathematics to independently compute the exact same mathematical "shared secret."
4. **HKDF & AES-GCM**: To guarantee perfect cryptographic properties, this shared secret is run through a Hash-based Key Derivation Function (`HKDF` with `SHA256`) to derive a pure 256-bit symmetric session key. This key initializes the `AES-GCM` algorithm used for the remainder of the session layer wrapping.
5. **Confirmation**: The relay encrypts the original challenge `nonce` using the newly derived `AES-GCM` session key and sends it back. If the Client gracefully decrypts it and the nonce matches, the handshake is mutually validated. 

This approach guarantees **Forward Secrecy**. Because the Client's keys are purely ephemeral and discarded post-session, a future compromise of the Relay's private key cannot retroactively decrypt past intercepted traffic payloads.

---

## 4. Defeating Traffic Analysis

As required by the proposal, our implementation deploys critical, specialized defenses against passive traffic volume analysis and timing correlation:

1. **Strict Uniform Cell Padding (`transport.py`)**: 
   Standard metadata inspection allows attackers to profile connections purely by analyzing TCP packet sizes (e.g., matching a 4KB incoming packet with a 4KB outgoing packet). To thwart this, **every** JSON cell transmitted across a socket undergoes deterministic artificial padding. Before hitting the wire, the payload is buffered with empty byte spaces until it is exactly `16,384 bytes` (16 Kilobytes). All network traffic traversing the simulated network appears as identical 16KB blocks regardless of how deeply nested the onion currently is.
2. **Timing Obfuscation Jitter (`relay.py`)**:
   Advanced timing attacks correlate the exact millisecond a packet arrives at an entry node with the millisecond it exits a relay. Our implementation introduces intentional randomized variable micro-delays (`JITTER_MIN` to `JITTER_MAX`) at every decryption phase to drastically muddy timing correlations.
3. **Replay Protection**:
   Relays cryptographically maintain an internally cached subset of verified initial nonces (`self.seen_nonces`). If an attacker intercepts an encrypted 16KB cell and attempts to aggressively re-feed it to a relay (Replay Attack), the relay immediately drops it.

---

## 5. Auditing and Verification

We fulfilled the requirement ensuring standard relay performance auditing without compromising anonymization standards:
* **Decoupled Telemetry**: Using Python's `logging` and system `psutil` libraries, `relay.py` pipes constant telemetry (Uptime, System Memory %, CPU cycle %, active session counts) directly into disjointed local log files (e.g., `logs/relayX.log`).
* **Privacy Enforcement**: At no point in the codebase are raw internal payloads or prior Client IP architectures logged to stdout or files during standard execution cycles. The operator receives health assurances strictly via the decoupled telemetry metrics.

## 6. Demonstration

To cleanly operate the simulated backbone across Windows or Unix operating systems, the project includes an automated deployment script:
```bash
python driver.py --hops 3 --num-relays 3 --message "Secret payload verification" --dest-host "example.com" --dest-port 80
```
This single command reliably simulates an entire network start loop encompassing Directory node generation, variable-capacity authenticating Relays, automated Client execution, and correct graceful teardown while verifying terminal decryption integrity.

## 7. Performance Metrics

To evaluate the operational efficiency and the overhead introduced by the anonymity protections (multi-layered encryption, symmetric cell padding, and deliberate micro-delays), we measured the end-to-end latency for a standard 3-hop circuit (Entry -> Middle -> Exit).

**Test Configuration:**
- Circuit Depth: 3 Hops
- Encryption: X25519 Handshake + AES-GCM symmetric cell encryption
- Cell Padding: Uniform 16KB (`DEFAULT_CELL_SIZE = 16384`)
- Timing Obfuscation: Randomized per-hop jitter (`JITTER_MIN = 0.01s`, `JITTER_MAX = 0.1s`)
- Environment: Localhost (simulated network)

**Latency Results (5 sequential runs):**
- Individual execution times: `0.364s, 0.502s, 0.618s, 0.311s, 0.328s`
- **Average end-to-end latency: 0.424 seconds**

**Analysis:**
The performance metrics demonstrate that the network achieves high anonymity and traffic obfuscation without unacceptable latency penalties. The 0.424s average latency comprises roughly 0.16s of intentional randomized jitter (averaging ~0.055s per hop across 3 hops) combined with the overhead of performing 3 asynchronous X25519 handshakes and transmitting padded 16KB frames. This throughput proves the feasibility of the system design and validates the balance between robust anonymity operations and practical latency limits.