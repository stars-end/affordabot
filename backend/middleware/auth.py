from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import os

class TestAuthBypassMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # We need to make sure this only runs for /admin routes
        if "/admin" in request.url.path and os.environ.get("ENVIRONMENT") != "production":
            if request.cookies.get("x-test-user") == "admin":
                # To avoid circular import, we do a local import.
                from auth.clerk import UserProfile
                
                # Set a dummy user on the request state
                request.state.user = UserProfile(
                    id="test_admin",
                    email="test@example.com",
                    first_name="Test",
                    last_name="Admin",
                    public_metadata={"role": "admin"}
                )
        
        response = await call_next(request)
        return response
