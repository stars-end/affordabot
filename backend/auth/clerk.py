"""Clerk authentication helpers with optional local JWKS overrides."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel
import logging

# Use standard logging instead of structured_logging for now to minimize dependencies
logger = logging.getLogger("backend.auth.clerk")

class UserProfile(BaseModel):
    """Subset of Clerk user information required by the backend."""

    id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    clerk_metadata: Optional[Dict[str, Any]] = None
    public_metadata: Optional[Dict[str, Any]] = None
    private_metadata: Optional[Dict[str, Any]] = None


class ClerkAuth:
    """Reusable FastAPI dependency that validates Clerk-issued JWTs."""

    def __init__(self) -> None:
        self.jwks_url = os.getenv("CLERK_JWKS_URL")
        self.issuer = os.getenv("CLERK_JWT_ISSUER")
        test_jwks_path = os.getenv("CLERK_TEST_JWKS_PATH")
        test_issuer = os.getenv("CLERK_TEST_ISSUER")

        # Always validate that we have either test setup OR production setup
        if not test_jwks_path and (not self.jwks_url or not self.issuer):
            # Log warning but don't crash init if envs are missing (fails at runtime)
            logger.warning("Clerk JWKS URL and Issuer must be set in environment for Auth to work.")

        if test_jwks_path:
            jwks_file = Path(test_jwks_path)
            if not jwks_file.exists():
                raise ValueError(
                    f"CLERK_TEST_JWKS_PATH provided but file not found: {jwks_file}"
                )

            with jwks_file.open("r", encoding="utf-8") as fh:
                jwks_data = json.load(fh)

            self.jwks_client = self._create_test_jwks_client(jwks_data)
            self.issuer = test_issuer or self.issuer
        elif self.jwks_url:
            self.jwks_client = PyJWKClient(self.jwks_url)
        else:
            self.jwks_client = None

        self.bearer = HTTPBearer()

    async def __call__(
        self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
    ) -> UserProfile:
        if not self.jwks_client:
             raise HTTPException(
                status_code=500, detail="Clerk Authentication not configured (Missing Envs)"
            )

        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(
                credentials.credentials
            )

            payload = jwt.decode(
                credentials.credentials,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                options={"verify_aud": False},
            )

            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=401, detail="Invalid claims: 'sub' missing."
                )

            logger.info(f"Token validated for user: {user_id}")
            
            return UserProfile(
                id=user_id,
                email=payload.get("email"),
                first_name=payload.get("first_name"),
                last_name=payload.get("last_name"),
                public_metadata=payload.get("public_metadata", {}),
                private_metadata=payload.get("private_metadata", {}),
                clerk_metadata=payload.get("metadata", {}),
            )

        except Exception as exc:
            logger.error(f"Authentication failed: {exc}")
            raise HTTPException(status_code=401, detail=f"Authentication failed: {exc}")

    def _create_test_jwks_client(self, jwks_data: dict):
        """Create a simple JWKS client for test data that mimics PyJWKClient interface."""

        class TestJWKSClient:
            def __init__(self, jwks_data):
                self.jwks_data = jwks_data
                self.keys = {key["kid"]: key for key in jwks_data.get("keys", [])}

            def get_signing_key_from_jwt(self, token):
                try:
                    header = jwt.get_unverified_header(token)
                    kid = header.get("kid")

                    if not kid or kid not in self.keys:
                        raise ValueError(f"Key ID {kid} not found")

                    key_data = self.keys[kid]

                    class TestSigningKey:
                        def __init__(self, key_data):
                            try:
                                from jwt.algorithms import RSAAlgorithm
                                self.key = RSAAlgorithm.from_jwk(json.dumps(key_data))
                            except ImportError:
                                self.key = key_data
                            self.key_data = key_data

                    return TestSigningKey(key_data)

                except Exception as e:
                    raise ValueError(f"Failed to get signing key: {e}")

        return TestJWKSClient(jwks_data)


clerk_auth = ClerkAuth()


async def require_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> UserProfile:
    """Ensure the current JWT represents an admin user."""
    
    # 1. Validate Token via ClerkAuth logic manually (reuse logic or instance)
    # We call the instance to get the profile
    # Note: Dependency injection usually handles this, but since we want to extend logic...
    user_profile = await clerk_auth(credentials)

    # 2. Check Admin Role/Allowlist
    # Logic: Role OR UserID Match OR Domain Match
    
    # Check Role
    # Access raw payload workaround since UserProfile might strict type
    # For now, let's rely on standard metadata if possible, or assume Auth checks pass
    # But we need specific admin check.
    
    # Let's decode properly again or store in profile?
    # Simpler: Just re-decode strictly for claims check or trust the profile?
    # We trust profile.
    
    # CLERK METADATA CHECK (Role)
    # Clerk stores public metadata in `public_metadata`
    role = user_profile.public_metadata.get("role")
    if role == "admin":
        return user_profile

    # USER ID ALLOWLIST
    user_id = user_profile.id
    admin_user_ids_str = os.getenv("ADMIN_USER_IDS", "")
    if admin_user_ids_str:
        ids = [x.strip() for x in admin_user_ids_str.split(",") if x.strip()]
        if user_id in ids:
            return user_profile

    # DOMAIN ALLOWLIST
    email = user_profile.email
    admin_domains_str = os.getenv("ADMIN_EMAIL_DOMAINS", "")
    if email and admin_domains_str:
        domains = [x.strip() for x in admin_domains_str.split(",") if x.strip()]
        user_domain = email.split("@")[-1].lower()
        if user_domain in domains:
            return user_profile

    logger.warning(f"Admin Access Denied for user {user_id} ({email})")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
    )
