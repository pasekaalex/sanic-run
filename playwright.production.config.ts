import { defineConfig, devices } from '@playwright/test';

const port = 4_187;
const productionOutDir = process.env.SANIC_PRODUCTION_OUT_DIR ?? 'dist';

export default defineConfig({
  testDir: './tests/production-e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ?? '/usr/bin/chromium',
    },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `npm run preview -- --port ${port} --outDir ${productionOutDir}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
  projects: [
    {
      name: 'production-desktop-chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1_024, height: 640 } },
    },
    {
      name: 'production-mobile-chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 390, height: 844 },
        hasTouch: true,
        isMobile: true,
      },
    },
  ],
});
