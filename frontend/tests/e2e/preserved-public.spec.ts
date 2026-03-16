import { test, expect } from '@playwright/test';
import { readFileSync } from 'fs';
import { resolve } from 'path';

/**
 * Preserved public routes — visual regression for affordabot Prism GUI.
 *
 * These routes are publicly accessible (no auth required).
 * API calls are intercepted with fixture data for stable screenshots.
 */

const legislationFixture = JSON.parse(
  readFileSync(resolve(__dirname, 'fixtures/legislation-california.json'), 'utf-8')
);

const billDetailFixture = JSON.parse(
  readFileSync(resolve(__dirname, 'fixtures/bill-detail.json'), 'utf-8')
);

// Intercept the direct backend API calls (api.ts uses API_BASE_URL, not Next.js rewrites)
async function mockLegislationAPI(page, jurisdiction: string) {
  await page.route('**/legislation/**', async (route) => {
    const url = route.request().url();
    // Return legislation list for the jurisdiction
    if (url.includes(`/legislation/${jurisdiction}`) && !url.includes('/legislation/')) {
      await route.fulfill({ json: legislationFixture });
    } else {
      await route.continue();
    }
  });
}

async function mockBillAPI(page, jurisdiction: string, billNumber: string) {
  await page.route(`**/legislation/${jurisdiction}/${billNumber}**`, async (route) => {
    await route.fulfill({ json: billDetailFixture });
  });
}

test.describe('Preserved Public Routes', () => {
  // --- Redirect contract ---
  test.describe('Redirect: / redirects to /dashboard/california', () => {
    test('homepage redirects to dashboard/california', async ({ page }) => {
      const response = await page.goto('/');
      expect(response?.status()).toBeLessThan(400);
      expect(page.url()).toContain('/dashboard/california');
    });
  });

  // --- Dashboard routes ---
  test.describe('Dashboard Routes', () => {
    test('dashboard/california — preserved visual baseline', async ({ page }) => {
      await mockLegislationAPI(page, 'california');

      await page.goto('/dashboard/california');
      await expect(page.locator('h1', { hasText: 'California State Dashboard' })).toBeVisible();
      await expect(page.locator('text=Real-time affordability impact analysis')).toBeVisible();
      await expect(page.locator('text=System Online').first()).toBeVisible();
      await expect(page.locator('text=Export Analysis')).toBeVisible();

      // Wait for data to render
      await page.waitForTimeout(500);

      await expect(page).toHaveScreenshot('dashboard-california.png', {
        maxDiffPixelRatio: 0.005,
        fullPage: true,
      });
    });

    test('dashboard/santa-clara-county — preserved visual baseline', async ({ page }) => {
      await mockLegislationAPI(page, 'santa-clara-county');

      await page.goto('/dashboard/santa-clara-county');
      await expect(page.locator('h1', { hasText: 'Santa Clara County Dashboard' })).toBeVisible();
      await expect(page.locator('text=System Online').first()).toBeVisible();

      await page.waitForTimeout(500);
      await expect(page).toHaveScreenshot('dashboard-santa-clara-county.png', {
        maxDiffPixelRatio: 0.005,
        fullPage: true,
      });
    });

    test('dashboard/san-jose — preserved visual baseline', async ({ page }) => {
      await mockLegislationAPI(page, 'san-jose');

      await page.goto('/dashboard/san-jose');
      await expect(page.locator('h1', { hasText: 'San Jose City Dashboard' })).toBeVisible();
      await expect(page.locator('text=System Online').first()).toBeVisible();

      await page.waitForTimeout(500);
      await expect(page).toHaveScreenshot('dashboard-san-jose.png', {
        maxDiffPixelRatio: 0.005,
        fullPage: true,
      });
    });

    test('dashboard/saratoga — preserved visual baseline', async ({ page }) => {
      await mockLegislationAPI(page, 'saratoga');

      await page.goto('/dashboard/saratoga');
      await expect(page.locator('h1', { hasText: 'Saratoga City Dashboard' })).toBeVisible();
      await expect(page.locator('text=System Online').first()).toBeVisible();

      await page.waitForTimeout(500);
      await expect(page).toHaveScreenshot('dashboard-saratoga.png', {
        maxDiffPixelRatio: 0.005,
        fullPage: true,
      });
    });

    test('dashboard/[jurisdiction] — generic jurisdiction route smoke', async ({ page }) => {
      await mockLegislationAPI(page, 'saratoga');

      await page.goto('/dashboard/saratoga');
      // Verify breadcrumb and Prism shell
      await expect(page.locator('text=MAIN DASHBOARD')).toBeVisible();
      await expect(page.locator('text=SARATOGA_ANALYSIS_V1')).toBeVisible();
    });
  });

  // --- Bill detail route ---
  test.describe('Bill Detail Route', () => {
    test('bill/california/AB-1234 — preserved visual baseline', async ({ page }) => {
      await mockBillAPI(page, 'california', 'AB-1234');

      await page.goto('/bill/california/AB-1234');
      await expect(page.locator('h1', { hasText: 'Housing Affordability Act' })).toBeVisible();
      await expect(page.locator('text=california').first()).toBeVisible();

      await page.waitForTimeout(500);
      await expect(page).toHaveScreenshot('bill-california-ab1234.png', {
        maxDiffPixelRatio: 0.005,
        fullPage: true,
      });
    });
  });

  // --- Search route ---
  test.describe('Search Route', () => {
    test('search — preserved visual baseline (empty state)', async ({ page }) => {
      await page.goto('/search');
      await expect(page.locator('h1', { hasText: 'Search Legislation' })).toBeVisible();
      await expect(page.locator('text=Find bills and their economic impact analysis')).toBeVisible();
      await expect(page.locator('input[placeholder*="Search for bills"]')).toBeVisible();

      await expect(page).toHaveScreenshot('search-empty.png', {
        maxDiffPixelRatio: 0.005,
        fullPage: true,
      });
    });
  });
});
