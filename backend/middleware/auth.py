from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import os
from loguru import logger
from llm_common.agents import verify_token

class TestAuthBypassMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow bypass for /admin routes in non-production environments
        # Requires RAILWAY_ENVIRONMENT_NAME in {dev, staging} OR ENVIRONMENT in {development}
        env_name = os.getenv("RAILWAY_ENVIRONMENT_NAME") or os.getenv("ENVIRONMENT")
        secret = os.getenv("TEST_AUTH_BYPASS_SECRET")
        is_bypass_env = env_name in ["dev", "staging", "development"]

        if is_bypass_env and secret:
            token = request.cookies.get("x-test-user")
            if token:
                # Validate signed token with llm-common utility
                payload = verify_token(token, secret)
                if payload:
                    logger.info(f"🎭 Auth Bypass: Authenticated as {payload.get('sub')} ({payload.get('role')})")
                    # To avoid circular import, we do a local import.
                    from auth.clerk import UserProfile
                    
                    # Set a dummy user on the request state
                    request.state.user = UserProfile(
                        id=payload.get("sub", "test_user"),
                        email=payload.get("email", "test@example.com"),
                        first_name="Bypass",
                        last_name="User",
                        public_metadata={"role": payload.get("role", "user")}
                    )
        
        response = await call_next(request)
        return response
