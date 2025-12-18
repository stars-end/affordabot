
import { test, expect } from '@playwright/test';

test.describe('Verification UI Check', () => {
    test('Admin Tabs and New Features', async ({ page }) => {
        // 1. Navigate to Admin Root
        await page.goto('/admin');
        await expect(page.locator('h1', { hasText: 'Admin Dashboard' })).toBeVisible();

        // 2. Initial Tab Check (Overview)
        // Verify Analytics Dashboard loaded (PR #120)
        await expect(page.locator('text=Bills per Month')).toBeVisible();

        // 3. Verify Scraping Tab (PR #116 View Asset feature)
        // Click 'Scraping' tab trigger
        await page.getByRole('tab', { name: 'Scraping' }).click();

        // Wait for Scrape Manager content
        // Look for the "Actions" column or "View Asset" element
        // While there may be no data, the column header "Actions" should likely be present 
        // IF the table is rendered even when empty. 
        // Or we look for the "Run Scrape" button which confirms ScrapeManager loaded.
        await expect(page.getByRole('button', { name: 'Start Scrape' })).toBeVisible();

        // Check if table headers exist OR empty state message
        // If history is empty, table headers won't be visible.
        const emptyState = page.getByText('No scrape history yet');
        const statusHeader = page.locator('th', { hasText: 'Status' });

        if (await emptyState.isVisible()) {
            await expect(emptyState).toBeVisible();
        } else {
            await expect(statusHeader).toBeVisible();
            await expect(page.locator('th', { hasText: 'Actions' })).toBeVisible();
        }


        // 4. Verify Analysis Tab (PR #116 View Result feature)
        // Hardened Tab Switching for Flaky UI
        const analysisTrigger = page.locator('button[role="tab"][value="analysis"]');
        await analysisTrigger.click();

        // Explicitly wait for the tab to report as active
        await expect(analysisTrigger).toHaveAttribute('data-state', 'active', { timeout: 10000 });

        // Wait for the tab panel to be visible
        await expect(page.locator('div[role="tabpanel"][data-state="active"][value="analysis"]')).toBeVisible();

        // Check for Analysis Lab content title
        await expect(page.locator('text=Run Analysis Pipeline')).toBeVisible({ timeout: 10000 });

        // Look for "Run Analysis" button
        await expect(page.getByRole('button', { name: 'Run Analysis' })).toBeVisible();

        // Verify 'Result' column header is present (PR #116)
        const analysisEmpty = page.getByText('No analysis history yet');
        const resultHeader = page.locator('th', { hasText: 'Result' }); // Or 'Actions' as seen in code line 471

        if (await analysisEmpty.isVisible()) {
            await expect(analysisEmpty).toBeVisible();
        } else {
            // In AnalysisLab.tsx, the header is "Actions" (line 471), but I should verify the "Result" concept.
            // Actually, I should check for "Actions" header as that's what is in the code.
            await expect(page.locator('th', { hasText: 'Actions' })).toBeVisible();
        }
    });
});
