import os
import re
from pathlib import Path
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


async def clerk_login(page: Page, base_url: str, output_dir: Path) -> bool:
    """
    Attempt to authenticate for Clerk-protected routes.

    Strategy:
    - If already authenticated, proceed.
    - Otherwise, login via email/password using `TEST_USER_EMAIL` / `TEST_USER_PASSWORD`.

    Note: Do not set global extra headers like `x-test-user` on the page context; they can
    break Clerk script loading due to cross-origin preflight restrictions.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if already authenticated
    await page.goto(f"{base_url}/admin", wait_until="networkidle", timeout=60_000)
    if await _is_authenticated(page):
        return True

    # Ensure redirect_url points at the public base URL (Clerk can sometimes derive localhost behind proxies).
    redirect_url = quote(f"{base_url}/admin", safe="")
    await page.goto(f"{base_url}/sign-in?redirect_url={redirect_url}", wait_until="networkidle", timeout=60_000)

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
        await page.goto(f"{base_url}/admin", wait_until="networkidle", timeout=60_000)
    except Exception:
        pass

    # Final check: should be on /admin (or at least not show Clerk login UI)
    try:
        await page.wait_for_load_state("networkidle", timeout=60_000)
    except Exception:
        pass

    ok = await _is_authenticated(page)
    if not ok:
        await page.screenshot(path=str(output_dir / "auth_failed.png"), full_page=True)
        (output_dir / "auth_failed.html").write_text(await page.content(), encoding="utf-8")
    return ok
