import { defineConfig } from '@playwright/test';

import baseConfig from './playwright.config';

export default defineConfig(baseConfig, {
  testDir: './tests/legacy-e2e',
});
