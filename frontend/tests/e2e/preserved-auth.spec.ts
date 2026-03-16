import { test, expect } from '@playwright/test';

/**
 * Preserved auth routes — smoke tests only.
 *
 * These Clerk-hosted pages are NOT part of the pixel-perfect baseline set.
 * We verify they render without fatal runtime errors and show expected shells.
 * Exact visual appearance depends on Clerk's hosted component styling.
 *
 * In CI mode (placeholder Clerk keys), ClerkProvider is not mounted so
 * Clerk components cannot render. We skip these tests in CI mode since
 * they can only be validated with real Clerk credentials.
 *
 * The build already verifies that auth route pages compile correctly.
 * Production verification requires real Clerk keys.
 */

const isCI = process.env.NEXT_PUBLIC_TEST_AUTH_BYPASS === 'true'
  && (process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? '').includes('placeholder');

test.describe('Preserved Auth Routes', () => {
  // Auth pages require ClerkProvider which is not mounted in CI mode.
  // Skip in CI; these are verified by build compilation and real-key testing.
  test.skip(isCI, 'Auth routes skipped in CI mode (ClerkProvider not mounted)');

  test('sign-in — renders without fatal errors', async ({ page }) => {
    const errors: string[] = [];

    page.on('pageerror', (err) => {
      errors.push(err.message);
    });
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto('/sign-in');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).toBeVisible();
    expect(errors).toHaveLength(0);
  });

  test('sign-up — renders without fatal errors', async ({ page }) => {
    const errors: string[] = [];

    page.on('pageerror', (err) => {
      errors.push(err.message);
    });
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto('/sign-up');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).toBeVisible();
    expect(errors).toHaveLength(0);
  });
});
