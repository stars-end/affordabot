import { test, expect } from '@playwright/test';
import { readFileSync } from 'fs';
import { resolve } from 'path';

/**
 * Preserved admin routes — visual regression for affordabot admin Prism GUI.
 *
 * Uses the signed-cookie auth bypass matching middleware's contract.
 * Most admin pages degrade gracefully to demo/fallback states when API
 * calls fail, providing stable screenshot targets without complex mocking.
 */
import { test as adminTest } from './auth-setup';

const legislationFixture = JSON.parse(
  readFileSync(resolve(__dirname, 'fixtures/legislation-california.json'), 'utf-8')
);

// Mock the legislation API for the admin overview (it embeds SummaryDashboard)
async function mockLegislationAPI(page) {
  await page.route('**/legislation/**', async (route) => {
    await route.fulfill({ json: legislationFixture });
  });
}

adminTest.describe('Preserved Admin Routes', () => {
  // --- Main admin dashboard ---
  adminTest('admin — preserved visual baseline', async ({ adminPage }) => {
    await mockLegislationAPI(adminPage);

    await adminPage.goto('/admin');
    await expect(adminPage.locator('h1', { hasText: 'Admin Dashboard' })).toBeVisible();
    await expect(adminPage.locator('text=System Pipeline & Logs')).toBeVisible();
    await expect(adminPage.locator('text=System Online').first()).toBeVisible();

    // Wait for tab components to render
    await adminPage.waitForTimeout(500);

    await expect(adminPage).toHaveScreenshot('admin-dashboard.png', {
      maxDiffPixelRatio: 0.005,
      fullPage: true,
    });
  });

  // --- Admin sub-routes ---

  adminTest('admin/audits/trace — preserved visual baseline', async ({ adminPage }) => {
    // Mock the pipeline-runs API to return empty list
    await adminPage.route('**/api/admin/pipeline-runs**', async (route) => {
      await route.fulfill({ json: [] });
    });

    await adminPage.goto('/admin/audits/trace');
    await expect(adminPage.locator('h1', { hasText: 'Audit Trace' })).toBeVisible();
    await expect(adminPage.locator('text=View pipeline runs and debug LLM analysis steps')).toBeVisible();

    // Page shows "No Pipeline Runs Found" when API returns empty
    await expect(adminPage.locator('text=No Pipeline Runs Found')).toBeVisible();

    await expect(adminPage).toHaveScreenshot('admin-audits-trace.png', {
      maxDiffPixelRatio: 0.005,
      fullPage: true,
    });
  });

  adminTest('admin/discovery — preserved visual baseline', async ({ adminPage }) => {
    await adminPage.goto('/admin/discovery');
    await expect(adminPage.locator('h1', { hasText: 'Discovery Queue' })).toBeVisible();
    await expect(adminPage.locator('text=Discover new sources')).toBeVisible();

    // Demo cards render when no results
    await expect(adminPage.locator('text=City Council Meeting Minutes')).toBeVisible();

    await expect(adminPage).toHaveScreenshot('admin-discovery.png', {
      maxDiffPixelRatio: 0.005,
      fullPage: true,
    });
  });

  adminTest('admin/jurisdiction/test-jurisdiction — preserved visual baseline', async ({ adminPage }) => {
    // Mock the admin service for jurisdiction dashboard
    await adminPage.route('**/api/admin/jurisdiction/**', async (route) => {
      await route.fulfill({
        json: {
          jurisdiction: 'Test City',
          pipeline_status: 'healthy',
          last_scrape: '2025-03-10T14:30:00Z',
          total_raw_scrapes: 42,
          processed_scrapes: 38,
          total_bills: 15,
          active_alerts: [],
        },
      });
    });
    await adminPage.route('**/api/admin/scrape-history**', async (route) => {
      await route.fulfill({ json: [] });
    });

    await adminPage.goto('/admin/jurisdiction/test-jurisdiction');
    await expect(adminPage.locator('h1', { hasText: 'Test City' })).toBeVisible();
    await expect(adminPage.locator('text=HEALTHY')).toBeVisible();

    await expect(adminPage).toHaveScreenshot('admin-jurisdiction-detail.png', {
      maxDiffPixelRatio: 0.005,
      fullPage: true,
    });
  });

  adminTest('admin/prompts — preserved visual baseline', async ({ adminPage }) => {
    // Mock the prompt service — return empty to trigger demo prompts
    await adminPage.route('**/api/admin/prompts**', async (route) => {
      await route.fulfill({ json: [] });
    });

    await adminPage.goto('/admin/prompts');
    await expect(adminPage.locator('h1', { hasText: 'Prompt Editor' })).toBeVisible();
    await expect(adminPage.locator('text=Manage LLM system prompts')).toBeVisible();

    // Demo prompts should render
    await expect(adminPage.locator('text=impact_analysis')).toBeVisible();

    await expect(adminPage).toHaveScreenshot('admin-prompts.png', {
      maxDiffPixelRatio: 0.005,
      fullPage: true,
    });
  });

  adminTest('admin/reviews — preserved visual baseline', async ({ adminPage }) => {
    // Mock the reviews API — return empty to trigger demo reviews
    await adminPage.route('**/api/admin/reviews**', async (route) => {
      await route.fulfill({ json: [] });
    });

    await adminPage.goto('/admin/reviews');
    await expect(adminPage.locator('h1', { hasText: 'Review Queue' })).toBeVisible();
    await expect(adminPage.locator('text=Review LLM-suggested improvements')).toBeVisible();

    // Demo reviews should render
    await expect(adminPage.locator('text=Template Improvement').first()).toBeVisible();

    await expect(adminPage).toHaveScreenshot('admin-reviews.png', {
      maxDiffPixelRatio: 0.005,
      fullPage: true,
    });
  });

  adminTest('admin/sources — preserved visual baseline', async ({ adminPage }) => {
    // Mock the admin service for sources — return empty to trigger demo data
    await adminPage.route('**/api/admin/sources**', async (route) => {
      await route.fulfill({ json: [] });
    });

    await adminPage.goto('/admin/sources');
    await expect(adminPage.locator('h1', { hasText: 'Source Management' })).toBeVisible();
    await expect(adminPage.locator('text=Manage legislative document sources')).toBeVisible();

    // Demo table should render
    await expect(adminPage.locator('text=HR-5501.pdf')).toBeVisible();

    await expect(adminPage).toHaveScreenshot('admin-sources.png', {
      maxDiffPixelRatio: 0.005,
      fullPage: true,
    });
  });
});
