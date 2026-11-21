import { defineConfig } from '@playwright/test'

/**
 * The recorder drives the app that is already running (start.cmd); it never starts or stops
 * it. The page is the 1920x1080 stage, which hosts the real app in an iframe.
 */
export default defineConfig({
  testDir: '.',
  testMatch: 'record.spec.ts',
  outputDir: 'out/test-results',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 20 * 60_000,
  reporter: [['list']],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8000',
    channel: process.env.VIDEO_BROWSER_CHANNEL || 'msedge',
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    colorScheme: 'light',
    locale: 'en-US',
  },
})
