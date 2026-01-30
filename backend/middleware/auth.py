import os
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable

from llm_common.agents import verify_token

class TestAuthBypassMiddleware(BaseHTTPMiddleware):
    """Standardized Auth Bypass for Affordabot."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        environment = os.getenv("RAILWAY_ENVIRONMENT_NAME", "development").lower()
        # Fallback to ENVIRONMENT for local
        env_name = os.getenv("ENVIRONMENT", environment).lower()
        secret_key = os.getenv("TEST_AUTH_BYPASS_SECRET")

        # Only allow bypass in non-production environments with a configured secret
        is_bypass_env = env_name in ["dev", "staging", "development"]
        if not secret_key or not is_bypass_env:
            return await call_next(request)

        token = request.cookies.get("x-test-user")
        if not token:
            auth = request.headers.get("Authorization")
            if auth and auth.startswith("Bearer v1."):
                token = auth.split(" ")[1]

        if token:
            try:
                payload = verify_token(token, secret_key)
                
                # Attach bypass user to request state
                logger.info(f"🎭 Auth Bypass: Authenticated as {payload.get('sub')}")
                # To avoid circular import, we do a local import.
                from auth.clerk import UserProfile
                
                # For Affordabot, we create a dummy UserProfile for compatibility
                request.state.user = UserProfile(
                    id=payload.get("sub", "test_user"),
                    email=payload.get("email", payload.get("sub", "test@example.com")),
                    first_name="Test",
                    last_name="User",
                    public_metadata={"role": payload.get("role", "user")}
                )
            except ValueError as ve:
                logger.warning(f"AuthBypass: Token verification failed: {ve}")
            except Exception as e:
                logger.error(f"AuthBypass: Unexpected error: {e}")

        return await call_next(request)
