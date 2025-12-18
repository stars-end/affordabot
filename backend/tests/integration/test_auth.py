import pytest
import jwt
import time
from pathlib import Path
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

# Import the class/logic we are testing
# We import ClerkAuth class to instantiate a fresh one with our env vars
from auth.clerk import ClerkAuth, UserProfile

KEYS_DIR = Path(__file__).parent.parent / "keys"
PRIVATE_KEY_PATH = KEYS_DIR / "private_key.pem"
JWKS_PATH = KEYS_DIR / "jwks.json"

@pytest.fixture
def private_key():
    with open(PRIVATE_KEY_PATH, "r") as f:
        return f.read()

@pytest.fixture
def auth_verifier(monkeypatch):
    """
    Sets up a ClerkAuth instance pointed at local JWKS.
    """
    monkeypatch.setenv("CLERK_TEST_JWKS_PATH", str(JWKS_PATH))
    monkeypatch.setenv("CLERK_TEST_ISSUER", "test-issuer")
    # Determine the test issuer
    
    # Re-instantiate to pick up env vars
    verifier = ClerkAuth()
    return verifier

def generate_token(private_key, sub="user_123", role="admin", issuer="test-issuer", exp_seconds=300):
    payload = {
        "sub": sub,
        "iss": issuer,
        "exp": int(time.time()) + exp_seconds,
        "iat": int(time.time()),
        "email": "test@example.com",
        "public_metadata": {"role": role}
    }
    
    # Sign with RS256 using the generated private key
    # We need to include 'kid' in header to match JWKS
    headers = {"kid": "test-key-1"}
    
    token = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
    return token

@pytest.mark.asyncio
async def test_valid_token_verification(auth_verifier, private_key):
    """
    Verify that a token signed by our local private key is accepted by ClerkAuth
    configured with the corresponding JWKS.
    """
    token = generate_token(private_key)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    
    user_profile = await auth_verifier(creds)
    
    assert isinstance(user_profile, UserProfile)
    assert user_profile.id == "user_123"
    assert user_profile.public_metadata["role"] == "admin"

@pytest.mark.asyncio
async def test_invalid_signature(auth_verifier):
    """
    Verify signature validation fails if we sign with a different key 
    (or just garbage data).
    """
    # Just generate a new random key that isn't in JWKS
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    
    other_key = rsa.generate_private_key(65537, 2048)
    other_pem = other_key.private_bytes(
        encoding=serialization.Encoding.PEM, 
        format=serialization.PrivateFormat.PKCS8, 
        encryption_algorithm=serialization.NoEncryption()
    )
    
    token = generate_token(other_pem) # Signed by wrong key
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    
    with pytest.raises(HTTPException) as exc:
        await auth_verifier(creds)
    
    assert exc.value.status_code == 401
    assert "Authentication failed" in exc.value.detail or "Signature verification failed" in str(exc.value.detail)

@pytest.mark.asyncio
async def test_expired_token(auth_verifier, private_key):
    """Verify expired tokens are rejected."""
    token = generate_token(private_key, exp_seconds=-10) # Expired 10s ago
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    
    with pytest.raises(HTTPException) as exc:
        await auth_verifier(creds)
        
    assert exc.value.status_code == 401
    assert "Signature has expired" in str(exc.value.detail)
