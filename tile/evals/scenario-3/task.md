# Authenticated Cron Trigger Endpoints

Implement authenticated cron job trigger endpoints that verify a shared secret via multiple header strategies before executing background script jobs.

## Capabilities

### Cron authentication and script execution

- A cron secret verification function accepts a request and returns `True` when the `Authorization: Bearer <secret>` header matches the configured secret [@test](./tests/test_cron_bearer.py)
- The same function also accepts the secret via an `X-Cron-Secret` header [@test](./tests/test_cron_x_header.py)
- A Prime-style `X-PR-CRON-SECRET` header is also accepted as a valid credential [@test](./tests/test_cron_pr_header.py)
- When no matching header is present, or when `CRON_SECRET` environment variable is not set, the function returns `False` [@test](./tests/test_cron_no_auth.py)

## Implementation

[@generates](./src/cron_auth.py)

## API

```python { #api }
from fastapi import Request

def verify_cron_auth(request: Request, cron_secret: str | None) -> bool:
    """
    Verify cron authentication from the request.

    Accepts the secret from:
    - Authorization: Bearer <secret>
    - X-Cron-Secret: <secret>
    - X-PR-CRON-SECRET: <secret>

    Returns False if cron_secret is None or no matching header is present.
    """
    ...
```

## Dependencies { .dependencies }

### affordabot { .dependency }

Provides the multi-header cron authentication pattern used by `/cron/discovery`, `/cron/daily-scrape`, `/cron/rag-spiders`, and `/cron/universal-harvester` endpoints.

[@satisfied-by](affordabot)
