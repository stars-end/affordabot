from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import os

class TestAuthBypassMiddleware(BaseHTTPMiddleware):
    """
    Middleware to bypass Clerk authentication for verification runners.
    Requires 'x-test-user' cookie and RAILWAY_ENVIRONMENT_NAME in {dev, staging}.
    """
    async def dispatch(self, request: Request, call_next):
        # SECURITY: Strictly skip in production or if bypass cookie is missing
        env_name = os.environ.get("RAILWAY_ENVIRONMENT_NAME")
        is_allowed_env = env_name in {"dev", "staging"}
        test_user = request.cookies.get("x-test-user")
        
        # Mandatory host check if in Railway
        host = request.headers.get("host", "")
        is_railway_host = host.endswith(".up.railway.app") or "localhost" in host or "127.0.0.1" in host
        
        if is_allowed_env and test_user and is_railway_host:
            # Map role based on cookie value
            role = "admin" if test_user == "admin" else "user"
            
            # To avoid circular import
            from auth.clerk import UserProfile
            
            # Set dummy user on request state
            request.state.user = UserProfile(
                id=f"test_{test_user}",
                email=f"{test_user}@example.com",
                first_name="Test",
                last_name=test_user.capitalize(),
                public_metadata={"role": role}
            )
            
        response = await call_next(request)
        return response
