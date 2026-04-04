import base64
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import quote

from playwright.async_api import Page


async def _is_not_found_page(page: Page) -> bool:
    try:
        h1 = page.locator("h1.next-error-h1")
        if await h1.count() == 0:
            return False
        return await h1.first.is_visible()
    except Exception:
        return False


async def _is_authenticated(page: Page) -> bool:
    url = (page.url or "").lower()
    if "sign-in" in url or "sign-up" in url:
        return False
    if await _has_email_field(page) or await _has_password_field(page):
        return False
    if await _is_not_found_page(page):
        return False
    return True


async def _has_email_field(page: Page) -> bool:
    return (
        await page.locator(
            'input[type="email"], input[name="identifier"], input[autocomplete="email"], input[placeholder*="email" i], input[id*="identifier" i]'
        ).count()
        > 0
    )


async def _has_password_field(page: Page) -> bool:
    return (
        await page.locator(
            'input[type="password"], input[name="password"], input[autocomplete="current-password"], input[id*="password" i]'
        ).count()
        > 0
    )


async def _click_primary_continue(page: Page) -> None:
    candidates = [
        page.get_by_role("button", name=re.compile(r"(continue|sign in|next)", re.I)),
        page.locator('button[type="submit"]'),
        page.locator("button").filter(has_text=re.compile(r"(continue|sign in|next)", re.I)),
    ]

    last_error: Exception | None = None
    for button in candidates:
        try:
            if await button.count() > 0:
                await button.first.click()
                return
        except Exception as e:
            last_error = e

    if last_error:
        raise last_error
    raise RuntimeError("No suitable continue/sign-in button found")


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def build_signed_bypass_cookie(
    secret: str,
    *,
    now: int | None = None,
    ttl_seconds: int = 3600,
) -> str:
    issued_at = now if now is not None else int(time.time())
    payload = {
        "sub": "test-admin",
        "role": "admin",
        "exp": issued_at + ttl_seconds,
    }
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64url_encode(payload_json)
    message = f"v1.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"v1.{payload_b64}.{signature_b64}"


async def clerk_login(page: Page, base_url: str, output_dir: Path) -> bool:
    """
    Attempt to authenticate for Clerk-protected routes.

    Strategy:
    - If already authenticated, proceed.
    - First, try cookie-gated bypass (for Railway dev/PR verification runs).
    - Otherwise, login via email/password using `TEST_USER_EMAIL` / `TEST_USER_PASSWORD`.

    Note: Do not set global extra headers like `x-test-user` on the page context; they can
    break Clerk script loading due to cross-origin preflight restrictions.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Cookie-gated bypass (preferred for non-prod verification runs).
    # The current frontend middleware expects a signed x-test-user token on
    # dev / staging / CI-style verification hosts, so verification helpers
    # must mint the same v1 payload+HMAC format used by Playwright auth setup.
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname
        secret = os.environ.get("TEST_AUTH_BYPASS_SECRET")
        if host and secret:
            await page.context.add_cookies(
                [
                    {
                        "name": "x-test-user",
                        "value": build_signed_bypass_cookie(secret),
                        "domain": host,
                        "path": "/",
                        "secure": parsed.scheme == "https",
                        "sameSite": "Lax",
                    }
                ]
            )
    except Exception:
        # Best-effort only; fall back to normal auth below.
        pass

    # Check if already authenticated
    await page.goto(f"{base_url}/admin", wait_until="domcontentloaded", timeout=60_000)
    if await _is_authenticated(page):
        return True

    # Ensure redirect_url points at the public base URL (Clerk can sometimes derive localhost behind proxies).
    redirect_url = quote(f"{base_url}/admin", safe="")
    await page.goto(f"{base_url}/sign-in?redirect_url={redirect_url}", wait_until="domcontentloaded", timeout=60_000)

    # UI login with env credentials
    email = os.environ.get("TEST_USER_EMAIL")
    password = os.environ.get("TEST_USER_PASSWORD")
    if not email or not password:
        await page.screenshot(path=str(output_dir / "auth_missing_creds.png"), full_page=True)
        return False

    # Clerk often uses a 2-step flow: identifier -> password
    if await _has_email_field(page):
        await page.locator(
            'input[type="email"], input[name="identifier"], input[autocomplete="email"], input[placeholder*="email" i], input[id*="identifier" i]'
        ).first.fill(email)
        await _click_primary_continue(page)

    # Wait for password field to appear (or for auth to complete)
    try:
        await page.wait_for_timeout(500)
        if await _has_password_field(page):
            await page.locator(
                'input[type="password"], input[name="password"], input[autocomplete="current-password"], input[id*="password" i]'
            ).first.fill(password)
            await _click_primary_continue(page)
    except Exception:
        # Continue below with auth check + artifacts
        pass

    # Don't trust Clerk's `redirect_url` query parameter; in some proxied environments
    # it can incorrectly point at localhost. After completing sign-in, force navigation
    # back to the desired in-app route and verify auth there.
    try:
        await page.goto(f"{base_url}/admin", wait_until="domcontentloaded", timeout=60_000)
    except Exception:
        pass

    # Final check: should be on /admin (or at least not show Clerk login UI)
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=60_000)
    except Exception:
        pass

    ok = await _is_authenticated(page)
    if not ok:
        await page.screenshot(path=str(output_dir / "auth_failed.png"), full_page=True)
        (output_dir / "auth_failed.html").write_text(await page.content(), encoding="utf-8")
    return ok
