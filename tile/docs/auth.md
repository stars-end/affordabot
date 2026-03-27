# AffordaBot Authentication

Authentication is handled via Clerk JWT tokens. Located in `backend/auth/clerk.py`.

## Import

```python
from auth.clerk import require_admin_user, clerk_auth, ClerkAuth, UserProfile
from fastapi import Depends
```

## Models

### UserProfile

Subset of Clerk user information extracted from JWT claims.

```python { .api }
class UserProfile(BaseModel):
    id: str                                        # Clerk user ID (sub claim)
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    clerk_metadata: Optional[Dict[str, Any]] = None    # "metadata" JWT claim
    public_metadata: Optional[Dict[str, Any]] = None   # "public_metadata" JWT claim
    private_metadata: Optional[Dict[str, Any]] = None  # "private_metadata" JWT claim
```

## ClerkAuth

FastAPI dependency class that validates Clerk-issued JWTs using RS256.

```python { .api }
class ClerkAuth:
    def __init__(self) -> None:
        # Reads: CLERK_JWKS_URL, CLERK_JWT_ISSUER
        # Optional test override: CLERK_TEST_JWKS_PATH, CLERK_TEST_ISSUER
        ...

    async def __call__(
        self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
    ) -> UserProfile:
        # Validates token, returns UserProfile
        # Raises: HTTPException(401) on invalid token
        # Test bypass: if ENABLE_TEST_AUTH_BYPASS=true and token == "TEST_TOKEN_ADMIN"
        #   returns UserProfile(id="test_admin", public_metadata={"role": "admin"})
        ...
```

**Module-level instance:** `clerk_auth = ClerkAuth()`

## require_admin_user

FastAPI dependency that validates JWT and enforces admin privileges. Used as the `dependencies` parameter on admin routers.

```python { .api }
async def require_admin_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> UserProfile:
    # Priority order:
    # 1. request.state.user (middleware-injected, must have public_metadata.role == "admin")
    # 2. JWT validation via ClerkAuth
    # 3. Admin check: role == "admin" in public_metadata
    #               OR user.id in ADMIN_USER_IDS (env, comma-separated)
    #               OR email domain in ADMIN_EMAIL_DOMAINS (env, comma-separated)
    # Raises:
    #   HTTPException(401) — not authenticated
    #   HTTPException(403) — authenticated but not admin
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CLERK_JWKS_URL` | Clerk JWKS URL for JWT validation (production) |
| `CLERK_JWT_ISSUER` | Clerk JWT issuer (production) |
| `CLERK_TEST_JWKS_PATH` | Path to local JWKS JSON file (testing) |
| `CLERK_TEST_ISSUER` | JWT issuer for test JWKS (testing) |
| `ENABLE_TEST_AUTH_BYPASS` | Set to `"true"` to enable test bypass with `TEST_TOKEN_ADMIN` token |
| `ADMIN_USER_IDS` | Comma-separated Clerk user IDs with admin access |
| `ADMIN_EMAIL_DOMAINS` | Comma-separated email domains with admin access |

## Usage Examples

```python
from fastapi import APIRouter, Depends
from auth.clerk import require_admin_user, UserProfile

# Protect an entire router
router = APIRouter(
    prefix="/api/admin",
    dependencies=[Depends(require_admin_user)]
)

# Or protect individual routes
@router.get("/protected")
async def my_endpoint(user: UserProfile = Depends(require_admin_user)):
    return {"user_id": user.id, "email": user.email}
```

```python
# Test auth bypass (requires ENABLE_TEST_AUTH_BYPASS=true)
import httpx

response = httpx.get(
    "http://localhost:8000/api/admin/stats",
    headers={"Authorization": "Bearer TEST_TOKEN_ADMIN"}
)
```

## TestAuthBypassMiddleware

**Location:** `backend/middleware/auth.py`

ASGI middleware that pre-populates `request.state.user` from a signed `x-test-user` cookie when running in non-production Railway environments.

```python { .api }
class TestAuthBypassMiddleware(BaseHTTPMiddleware):
    # Only active when ALL conditions are met:
    # 1. RAILWAY_ENVIRONMENT_NAME env is "dev" or "staging"
    # 2. Request has "x-test-user" cookie containing a v1-signed token
    # 3. TEST_AUTH_BYPASS_SECRET env is set
    # 4. Request host ends with .up.railway.app, or is localhost/127.0.0.1
    #
    # Token format: "v1.<base64_payload>.<hmac_sha256_sig>"
    # Payload fields: sub (user_id), role, email, exp (expiry timestamp)
    #
    # On successful verification, sets request.state.user = UserProfile(
    #   id=payload["sub"],
    #   email=payload["email"],
    #   public_metadata={"role": payload["role"]}
    # )
    # This UserProfile is then consumed by require_admin_user.
    ...
```

**Environment variables for TestAuthBypassMiddleware:**

| Variable | Description |
|----------|-------------|
| `RAILWAY_ENVIRONMENT_NAME` | Must be `"dev"` or `"staging"` to activate |
| `TEST_AUTH_BYPASS_SECRET` | HMAC-SHA256 secret for signing test tokens |
