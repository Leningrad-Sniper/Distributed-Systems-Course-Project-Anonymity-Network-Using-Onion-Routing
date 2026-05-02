import base64
import json
import os
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def generate_x25519_keypair() -> tuple[x25519.X25519PrivateKey, str]:
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_key, b64e(public_key)


def _derive_key(shared_secret: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"onion-routing-handshake",
    )
    return hkdf.derive(shared_secret)


def hybrid_encrypt(peer_public_key_b64: str, plaintext: bytes) -> Dict[str, str]:
    peer_public_key = x25519.X25519PublicKey.from_public_bytes(b64d(peer_public_key_b64))
    ephemeral_private = x25519.X25519PrivateKey.generate()
    ephemeral_public = ephemeral_private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    shared_secret = ephemeral_private.exchange(peer_public_key)
    aes_key = _derive_key(shared_secret)

    nonce = os.urandom(12)
    ciphertext = AESGCM(aes_key).encrypt(nonce, plaintext, None)
    return {
        "ephemeral_pub": b64e(ephemeral_public),
        "nonce": b64e(nonce),
        "ciphertext": b64e(ciphertext),
    }


def hybrid_decrypt(private_key: x25519.X25519PrivateKey, envelope: Dict[str, str]) -> bytes:
    ephemeral_public = x25519.X25519PublicKey.from_public_bytes(b64d(envelope["ephemeral_pub"]))
    shared_secret = private_key.exchange(ephemeral_public)
    aes_key = _derive_key(shared_secret)
    return AESGCM(aes_key).decrypt(
        b64d(envelope["nonce"]),
        b64d(envelope["ciphertext"]),
        None,
    )


def encrypt_cell(
    session_key: bytes,
    payload_obj: Dict[str, Any],
    cell_size: Optional[int] = None,
) -> Dict[str, str]:
    payload_raw = json.dumps(payload_obj, separators=(",", ":")).encode("utf-8")

    length_prefix = len(payload_raw).to_bytes(4, "big")
    if cell_size is not None:
        if len(payload_raw) > cell_size - 4:
            raise ValueError(
                f"Payload too large for fixed-size cell. Max={cell_size - 4}, got={len(payload_raw)}"
            )
        padding = os.urandom(cell_size - 4 - len(payload_raw))
        framed = length_prefix + payload_raw + padding
    else:
        framed = length_prefix + payload_raw

    nonce = os.urandom(12)
    ciphertext = AESGCM(session_key).encrypt(nonce, framed, None)
    return {"nonce": b64e(nonce), "ciphertext": b64e(ciphertext)}


def decrypt_cell(session_key: bytes, encrypted_cell: Dict[str, str]) -> Dict[str, Any]:
    framed = AESGCM(session_key).decrypt(
        b64d(encrypted_cell["nonce"]),
        b64d(encrypted_cell["ciphertext"]),
        None,
    )
    payload_len = int.from_bytes(framed[:4], "big")
    payload_raw = framed[4 : 4 + payload_len]
    return json.loads(payload_raw.decode("utf-8"))
