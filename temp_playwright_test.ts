import { test, expect } from '@playwright/test';

test('verify UI changes for ScrapeManager and AnalysisLab', async ({ page }) => {
  // Increase the overall test timeout
  test.setTimeout(120000);

  console.log('Navigating to admin page: http://localhost:3000/admin');
  await page.goto('http://localhost:3000/admin');

  console.log('Waiting for main heading to be visible...');
  await expect(page.getByRole('heading', { name: 'Admin Dashboard' })).toBeVisible({ timeout: 30000 });
  console.log('Admin Dashboard heading is visible.');

  // Handle potential toast notifications that might interfere with clicks
  const toast = page.locator('[data-sonner-toast]');
  if (await toast.count() > 0) {
    console.log('Toast notification detected. Waiting for it to disappear.');
    await expect(toast.first()).not.toBeVisible({ timeout: 20000 });
    console.log('Toast notification is gone.');
  } else {
    console.log('No toast notification detected.');
  }

  const scrapingTab = page.getByRole('tab', { name: 'Scraping' });
  console.log('Waiting for the "Scraping" tab...');
  await expect(scrapingTab).toBeVisible({ timeout: 15000 });
  console.log('Scraping tab is visible. Clicking the tab.');
  await scrapingTab.click();

  // Take a screenshot to debug the state of the scraping page
  await page.screenshot({ path: '/home/jules/verification/debug_scraping_tab.png' });
  console.log('Screenshot of the Scraping tab taken for debugging.');

  console.log('Waiting for the "View Asset" link to appear...');
  // Assuming there's at least one row in the table. We'll look for the first one.
  const viewAssetLink = page.getByRole('link', { name: 'View Asset' }).first();
  await expect(viewAssetLink).toBeVisible({ timeout: 15000 });
  console.log('"View Asset" link is visible.');

  await page.screenshot({ path: '/home/jules/verification/scrape-manager-view-asset.png' });
  console.log('Screenshot of ScrapeManager taken.');

  // Navigate to the Analysis tab
  const analysisTab = page.getByRole('tab', { name: 'Analysis' });
  console.log('Waiting for the "Analysis" tab...');
  await expect(analysisTab).toBeVisible({ timeout: 15000 });
  console.log('Analysis tab is visible. Clicking the tab.');
  await analysisTab.click();

  console.log('Waiting for the "View Result" button to appear...');
  const viewResultButton = page.getByRole('button', { name: 'View Result' }).first();
  await expect(viewResultButton).toBeVisible({ timeout: 15000 });
  console.log('"View Result" button is visible. Clicking the button.');
  await viewResultButton.click();

  console.log('Waiting for the modal with heading "Analysis Result" to appear...');
  const modalHeading = page.getByRole('heading', { name: 'Analysis Result' });
  await expect(modalHeading).toBeVisible({ timeout: 15000 });
  console.log('Modal is visible.');

  await page.screenshot({ path: '/home/jules/verification/analysis-lab-view-result.png' });
  console.log('Screenshot of AnalysisLab modal taken.');
});
