import { test as base, Page } from '@playwright/test';

/**
 * Generate a signed bypass cookie matching the middleware contract in
 * frontend/src/middleware.ts. The middleware expects:
 *   - Cookie name: x-test-user
 *   - Value format: v1.{base64url_payload}.{base64url_signature}
 *   - HMAC-SHA-256 using TEST_AUTH_BYPASS_SECRET
 *   - Only active when RAILWAY_ENVIRONMENT_NAME is 'dev' or 'staging'
 *
 * We implement the signing inline using Web Crypto API (same approach as
 * the middleware itself) so no external dependency is needed.
 */
async function generateSignedBypassCookie(): Promise<string> {
  const secret = process.env.TEST_AUTH_BYPASS_SECRET || 'ci-test-secret-for-playwright-only';

  const payload = JSON.stringify({
    sub: 'test-admin',
    role: 'admin',
    exp: Math.floor(Date.now() / 1000) + 3600, // 1 hour from now
  });

  const encoder = new TextEncoder();

  // Base64url encode payload
  const payloadB64 = btoa(payload)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');

  // Create HMAC key
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  // Sign the message
  const msg = `v1.${payloadB64}`;
  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(msg));

  // Base64url encode signature
  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(sig)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');

  return `v1.${payloadB64}.${sigB64}`;
}

/**
 * Extended test fixture that provides authenticated page context for
 * admin routes. Sets a signed x-test-user cookie before each navigation.
 */
export const test = base.extend({
  /** Page with admin bypass cookie set */
  adminPage: async ({ page }, use) => {
    const token = await generateSignedBypassCookie();
    await page.context().addCookies([
      {
        name: 'x-test-user',
        value: token,
        path: '/',
        domain: 'localhost',
      },
    ]);
    await use(page);
  },
});
