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
        token = request.cookies.get("x-test-user")
        
        # Mandatory host check if in Railway
        host = request.headers.get("host", "")
        # Allow localhost for development tests
        is_railway_host = host.endswith(".up.railway.app") or "localhost" in host or "127.0.0.1" in host
        
        secret = os.environ.get("TEST_AUTH_BYPASS_SECRET")
        
        if is_allowed_env and token and is_railway_host and secret:
            try:
                # Local fallback implementation of v1 token verification
                payload = self._verify_v1_token(token, secret)

                if payload:
                    role = payload.get("role", "user")
                    user_id = payload.get("sub", "test_user")
                    email = payload.get("email", f"{user_id}@example.com")
                    
                    # To avoid circular import
                    from auth.clerk import UserProfile
                    
                    # Set dummy user on request state
                    request.state.user = UserProfile(
                        id=user_id,
                        email=email,
                        first_name="Test",
                        last_name=role.capitalize(),
                        public_metadata={"role": role}
                    )
            except Exception:
                # Silently fail bypass on error for security
                pass
            
        response = await call_next(request)
        return response

    def _verify_v1_token(self, token: str, secret: str) -> dict | None:
        """Local implementation of v1 token verification."""
        import hmac
        import hashlib
        import base64
        import json
        import time

        try:
            parts = token.split(".")
            if len(parts) != 3 or parts[0] != "v1":
                return None
            
            header, payload_b64, sig_b64 = parts
            msg = f"{header}.{payload_b64}"
            
            # Verify signature
            expected_sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
            expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
            
            if not hmac.compare_digest(sig_b64, expected_sig_b64):
                return None
                
            # Decode payload
            padding = "=" * (4 - len(payload_b64) % 4)
            payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode()
            payload = json.loads(payload_json)
            
            # Check expiration
            exp = payload.get("exp")
            if exp and time.time() > exp:
                return None
                
            return payload
        except Exception:
            return None
