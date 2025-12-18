#!/usr/bin/env python3
"""
Generate a test RSA keypair and JWKS file for local ClerAuth integration testing.
Usage: python3 scripts/gen_test_keys.py
"""

import json
import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
from jwt.algorithms import RSAAlgorithm

KEYS_DIR = Path(__file__).parent.parent / "backend/tests/keys"
PRIVATE_KEY_PATH = KEYS_DIR / "private_key.pem"
JWKS_PATH = KEYS_DIR / "jwks.json"

def generate_keys():
    print(f"Generating keys in {KEYS_DIR}...")
    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Generate RSA Key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # 2. Save Private Key (PEM)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    with open(PRIVATE_KEY_PATH, "wb") as f:
        f.write(pem)
    print(f"✅ Saved private key to {PRIVATE_KEY_PATH}")

    # 3. Create JWKS from Public Key
    # We use PyJWT/RSAAlgorithm/jwk logic to get standard params (n, e)
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Simple hack: use jwt.algorithms to get the JWK dict
    # But standard library support is tricky without extra deps like `jwcrypto`.
    # PyJWT `RSAAlgorithm` can load JWK, but generating it efficiently...
    
    # Let's do manual JWK construction for minimal deps (just cryptography)
    numbers = public_key.public_numbers()
    
    def int_to_b64(val):
        import base64
        # Convert int to bytes, then base64url encode
        # standard is big-endian
        byte_len = (val.bit_length() + 7) // 8
        bytes_val = val.to_bytes(byte_len, 'big')
        return base64.urlsafe_b64encode(bytes_val).decode('utf-8').rstrip('=')

    jwk = {
        "kty": "RSA",
        "alg": "RS256",
        "use": "sig",
        "kid": "test-key-1",
        "n": int_to_b64(numbers.n),
        "e": int_to_b64(numbers.e)
    }
    
    jwks = {"keys": [jwk]}
    
    with open(JWKS_PATH, "w") as f:
        json.dump(jwks, f, indent=2)
    print(f"✅ Saved JWKS to {JWKS_PATH}")

if __name__ == "__main__":
    generate_keys()
