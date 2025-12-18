import pytest
from fastapi.security import HTTPAuthorizationCredentials
from auth.clerk import ClerkAuth

@pytest.mark.asyncio
async def test_auth_bypass_enabled(monkeypatch):
    """Verify bypass works when env var is set."""
    monkeypatch.setenv("ENABLE_TEST_AUTH_BYPASS", "true")
    verifier = ClerkAuth()
    
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="TEST_TOKEN_ADMIN")
    user = await verifier(creds)
    
    assert user.id == "test_admin"
    assert user.public_metadata["role"] == "admin"

@pytest.mark.asyncio
async def test_auth_bypass_disabled(monkeypatch):
    """Verify bypass ignored when env var is NOT true."""
    monkeypatch.setenv("ENABLE_TEST_AUTH_BYPASS", "false")
    # Need to set JWKS path to avoid init warning/error or ensure it doesn't crash
    # But ClerkAuth init is robust.
    verifier = ClerkAuth()
    
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="TEST_TOKEN_ADMIN")
    
    # wrapper to catch the 500 or 401 depending on config
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await verifier(creds)
