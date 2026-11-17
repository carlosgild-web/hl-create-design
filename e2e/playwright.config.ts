import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig } from '@playwright/test'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const tmp = join(here, '.tmp')
const isWindows = process.platform === 'win32'

/** The service's venv Python when it exists (local runs); `python` in CI. */
function python(service: string) {
  const venv = join(root, service, '.venv', isWindows ? 'Scripts/python.exe' : 'bin/python')
  return existsSync(venv) ? `"${venv}"` : 'python'
}

// Own ports, so a running dev stack is never touched or reused.
const SAP = 8190
const API = 8191
const WEB = 5190

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${WEB}`,
    trace: 'retain-on-failure',
    // Locally the installed Edge or Chrome runs the tests; CI installs Chromium.
    channel: process.env.E2E_BROWSER_CHANNEL || undefined,
  },
  webServer: [
    {
      command: `node "${join(here, 'reset.mjs')}" "${join(tmp, 'sap')}" && ${python('sap-mock')} -m uvicorn app.main:app --host 127.0.0.1 --port ${SAP}`,
      cwd: join(root, 'sap-mock'),
      url: `http://127.0.0.1:${SAP}/health`,
      env: { DATA_DIR: join(tmp, 'sap'), SAP_TODAY: '2026-11-17' },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `${python('backend')} "${join(here, 'harness.py')}"`,
      cwd: join(root, 'backend'),
      url: `http://127.0.0.1:${API}/api/health`,
      env: {
        E2E_DATA_DIR: join(tmp, 'backend'),
        E2E_PORT: String(API),
        SAP_BASE_URL: `http://127.0.0.1:${SAP}`,
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${WEB} --strictPort`,
      cwd: join(root, 'frontend'),
      url: `http://127.0.0.1:${WEB}`,
      env: { API_TARGET: `http://127.0.0.1:${API}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
