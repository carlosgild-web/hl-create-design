/**
 * Screenshots for the README (docs/showcase/), on the scripted model, so they always show
 * the same flow. Skipped in normal runs. Run on demand:
 *
 *   cd e2e && SHOWCASE=1 E2E_BROWSER_CHANNEL=msedge npx playwright test tests/showcase.spec.ts
 */
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type Page } from '@playwright/test'

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', 'docs', 'showcase')
const DESKTOP = { width: 1440, height: 900 }
const PHONE = { width: 375, height: 812 }

test.skip(!process.env.SHOWCASE, 'set SHOWCASE=1 to write the screenshots')
test.describe.configure({ mode: 'serial' })

async function shot(page: Page, name: string) {
  await page.waitForTimeout(400) // let the debounced inline check and animations settle
  await page.screenshot({ path: join(OUT, `${name}.png`) })
}

async function askAssistant(page: Page) {
  await page.getByLabel(/describe your design/i).fill('Revision C of the bead sorter vision board')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByRole('region', { name: 'SAP record' })).toBeVisible()
  await expect(page.getByLabel('Design number')).toHaveValue('HL-HW-26-0003')
}

test('desktop: the assistant fills the form, SAP card, confirmation card, then the preview', async ({ page }) => {
  await page.setViewportSize(DESKTOP)
  await page.goto('/')
  await shot(page, 'desktop-start')

  await askAssistant(page)
  await expect(page.getByRole('button', { name: 'Confirm' })).toBeVisible()
  await shot(page, 'desktop-assistant-filled')

  await page.getByRole('button', { name: 'Confirm' }).click()
  const preview = page.getByRole('img', { name: /Title block of HL-HW-26-0003 rev C/ })
  await expect
    .poll(() => preview.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0))
    .toBe(true)
  await preview.scrollIntoViewIfNeeded()
  await shot(page, 'desktop-created-preview')
})

test('desktop in Spanish, with an inline rule message', async ({ page }) => {
  await page.setViewportSize(DESKTOP)
  await page.goto('/')
  await page.getByRole('button', { name: 'ES', exact: true }).click()
  await page.getByLabel('Departamento').selectOption('HW')
  await page.getByLabel('Revisión').fill('I')
  await page.getByLabel('Nombre del diseño').fill('placa controladora taladro')
  await expect(page.getByRole('alert').filter({ hasText: '[02-revisions#skipped-letters]' })).toBeVisible()
  await shot(page, 'desktop-es-inline-check')
})

test('phone: form and assistant tabs', async ({ page }) => {
  await page.setViewportSize(PHONE)
  await page.goto('/')
  const tabs = page.getByRole('tablist', { name: 'Sections' })
  await tabs.getByRole('tab', { name: /Assistant/ }).click()
  await page.getByLabel(/describe your design/i).fill('New controller board for the drilling machine, Hardware.')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByRole('region', { name: 'SAP record' })).toBeVisible()
  await shot(page, 'phone-assistant')

  await tabs.getByRole('tab', { name: 'Form' }).click()
  await shot(page, 'phone-form')
})
