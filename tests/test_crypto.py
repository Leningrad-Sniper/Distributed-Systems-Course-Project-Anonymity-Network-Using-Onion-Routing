import os
import json

from onion_routing.crypto_utils import (
    generate_x25519_keypair,
    hybrid_encrypt,
    hybrid_decrypt,
    derive_session_key_from_private_and_peer,
    sym_encrypt,
    sym_decrypt,
    encrypt_cell,
    decrypt_cell,
)


def test_hybrid_roundtrip():
    priv_a, pub_a = generate_x25519_keypair()
    priv_b, pub_b = generate_x25519_keypair()

    plaintext = b"hello hybrid"
    env = hybrid_encrypt(pub_b, plaintext)
    out = hybrid_decrypt(priv_b, env)
    assert out == plaintext


def test_derive_session_key_consistent():
    priv_a, pub_a = generate_x25519_keypair()
    priv_b, pub_b = generate_x25519_keypair()

    k_ab = derive_session_key_from_private_and_peer(priv_a, pub_b)
    k_ba = derive_session_key_from_private_and_peer(priv_b, pub_a)
    assert k_ab == k_ba


def test_sym_encrypt_decrypt():
    key = os.urandom(32)
    message = b"secret payload"
    env = sym_encrypt(key, message)
    out = sym_decrypt(key, env)
    assert out == message


def test_cell_encrypt_decrypt_compact():
    key = os.urandom(32)
    obj = {"a": 1, "b": "x"}
    enc = encrypt_cell(key, obj, None)
    dec = decrypt_cell(key, enc)
    assert dec == obj


def test_cell_encrypt_decrypt_fixed():
    key = os.urandom(32)
    obj = {"text": "small"}
    enc = encrypt_cell(key, obj, 256)
    dec = decrypt_cell(key, enc)
    assert dec == obj

import pytest
def test_cell_encryption_size_constraint():
    """Guarantee an error throws if an inner packet forces out the size boundary."""
    key = os.urandom(32)
    large_payload = {"pad": "X" * 1000}
    with pytest.raises(ValueError):
        # Enforcing a 512 byte limit should break on a 1000+ byte dict
        encrypt_cell(key, large_payload, cell_size=512)
