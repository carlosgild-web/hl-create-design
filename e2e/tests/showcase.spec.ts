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
  await page.waitForTimeout(500) // let the debounced inline check and animations settle
  await page.screenshot({ path: join(OUT, `${name}.png`) })
}

test('desktop: start, the assistant picks an existing design, confirm, preview dialog', async ({ page }) => {
  await page.setViewportSize(DESKTOP)
  await page.goto('/')
  await shot(page, 'desktop-start')

  await page.getByLabel(/describe your design/i).fill('Revision C of the bead sorter vision board')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText('The assistant selected HL-HW-26-0003.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Confirm' })).toBeVisible()
  await shot(page, 'desktop-assistant-filled')

  await page.getByRole('button', { name: 'Confirm' }).click()
  const preview = page.getByRole('dialog').getByRole('img')
  await expect.poll(() => preview.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true)
  await shot(page, 'desktop-preview-dialog')
})

test('desktop: from an existing design, the SAP list', async ({ page }) => {
  await page.setViewportSize(DESKTOP)
  await page.goto('/')
  await page.getByRole('radio', { name: 'From existing design' }).click()
  await expect(page.getByRole('option', { name: /HL-HW-24-0015/ })).toBeVisible()
  await page.getByRole('listbox').focus()
  await page.keyboard.press('ArrowDown')
  await shot(page, 'desktop-existing-list')
})

test('desktop in Spanish: a new design with an inline rule message', async ({ page }) => {
  await page.setViewportSize(DESKTOP)
  await page.goto('/')
  await page.getByRole('button', { name: 'ES', exact: true }).click()
  await page.getByLabel('Departamento').selectOption('HW')
  await page.getByLabel('Nombre del diseño').fill('placa ñandú')
  await expect(page.getByRole('alert').filter({ hasText: '[03-title-block#design-name]' })).toBeVisible()
  await shot(page, 'desktop-es-inline-check')
})

test('phone: design and assistant tabs', async ({ page }) => {
  await page.setViewportSize(PHONE)
  await page.goto('/')
  await shot(page, 'phone-design')
  const tabs = page.getByRole('tablist', { name: 'Sections' })
  await tabs.getByRole('tab', { name: /Assistant/ }).click()
  await page.getByLabel(/describe your design/i).fill('New controller board for the drilling machine, Hardware.')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByRole('region', { name: 'SAP record' })).toBeVisible()
  await shot(page, 'phone-assistant')
})
