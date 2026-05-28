import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  timeout: 120000,
  use: {
    baseURL: process.env.FRONTEND_URL || 'https://neomi-pipeline-ui-643234238822.europe-west1.run.app',
    headless: true,
    viewport: { width: 1440, height: 900 },
    screenshot: 'on',
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  },
  reporter: [['html', { outputFolder: 'playwright-report' }], ['list']],
})
