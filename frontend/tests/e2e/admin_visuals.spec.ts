
import { test, expect } from '@playwright/test';

test.describe('Admin Dashboard Visuals', () => {
  test('should match the snapshot of the analytics dashboard', async ({ page }) => {
    // Navigate to the admin page
    await page.goto('/admin');

    // Wait for the main heading to be visible
    await expect(page.locator('h1', { hasText: 'Admin Dashboard' })).toBeVisible();

    // Wait for the "Bills per Month" chart to be visible, which indicates the dashboard has loaded
    await expect(page.locator('text=Bills per Month')).toBeVisible();

    // Add a short delay to ensure all animations have completed
    await page.waitForTimeout(1000); // 1 second delay

    // Take a full-page screenshot and compare it to the baseline
    await expect(page).toHaveScreenshot();
  });
});
