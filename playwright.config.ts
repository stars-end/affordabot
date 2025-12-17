import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './', // Look for tests in the root directory
  testMatch: /temp_playwright_test\.ts/, // Specifically match our test file
});
