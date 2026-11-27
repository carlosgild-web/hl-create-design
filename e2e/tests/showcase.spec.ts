/**
 * Screenshots and the GIF for the README (docs/showcase/), on the scripted model, so they
 * always show the same flow. Skipped in normal runs (`npx playwright test`). Run on demand:
 *
 *   cd e2e && npm run showcase        # the screenshots
 *   cd e2e && npm run showcase:gif    # the GIF, alone, on fresh servers
 *
 * Set E2E_REAL_KICAD=1 and KICAD_CLI so the preview is the real KiCad output, and
 * E2E_BROWSER_CHANNEL=msedge to use the installed Edge. The GIF needs ffmpeg on PATH.
 * The project file's local path is blurred in every image (decision 0037).
 */
import { spawnSync } from 'node:child_process'
import { rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type BrowserContext, type Page } from '@playwright/test'

const HERE = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(HERE, '..', '..', 'docs', 'showcase')
const TMP = resolve(HERE, '..', '.tmp')
const DESKTOP = { width: 1440, height: 900 }
const PHONE = { width: 375, height: 812 }

const ON_DEMAND = process.env.SHOWCASE || process.env.npm_lifecycle_event?.startsWith('showcase')
test.skip(!ON_DEMAND, 'run with npm run showcase or showcase:gif (or SHOWCASE=1)')
test.describe.configure({ mode: 'serial' })

// The preview dialog shows the project file's absolute path on this machine: blur it, as the
// video does (video/record.spec.ts), so no local path reaches an image.
async function blurLocalPaths(context: BrowserContext) {
  await context.addInitScript(() => {
    document.addEventListener('DOMContentLoaded', () => {
      const style = document.createElement('style')
      style.textContent = 'code[title] { filter: blur(7px); }'
      document.head.append(style)
    })
  })
}
test.beforeEach(({ context }) => blurLocalPaths(context))

async function shot(page: Page, name: string) {
  await page.waitForTimeout(500) // let the debounced inline check and animations settle
  await page.screenshot({ path: join(OUT, `${name}.png`) })
}

// First: the script proposes revision C, which the next test creates.
test('phone: design and assistant tabs', async ({ page }) => {
  await page.setViewportSize(PHONE)
  await page.goto('/')
  await shot(page, 'phone-design')
  const tabs = page.getByRole('tablist', { name: 'Sections' })
  await tabs.getByRole('tab', { name: /Assistant/ }).click()
  await page.getByLabel(/describe your design/i).fill('Revision C of the bead sorter vision board')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByRole('region', { name: 'SAP record' })).toBeVisible()
  await shot(page, 'phone-assistant')
})

test('desktop: start, the assistant picks an existing design, confirm, preview dialog', async ({ page }) => {
  test.setTimeout(120_000)
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
  await expect.poll(() => preview.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0), { timeout: 60_000 }).toBe(true)
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

test('desktop: a question about the rules, answered with a manual reference', async ({ page }) => {
  await page.setViewportSize(DESKTOP)
  await page.goto('/')
  await page.getByLabel(/describe your design/i).fill('When do I need a new revision instead of a new design number?')
  await page.getByRole('button', { name: 'Send' }).click()
  const ref = page.getByRole('button', { name: '[01-design-numbering#new-number-or-revision]' })
  await expect(ref).toBeVisible()
  await shot(page, 'desktop-manual-answer')

  await ref.click()
  await expect(page.getByRole('dialog').getByText(/can replace the old one/)).toBeVisible()
  await shot(page, 'desktop-manual-passage')
})

/** The portfolio GIF spec (standard section 2): 10 fps, 960 px wide, 96 colours. */
function toGif(webm: string, gif: string, startS: number, endS: number) {
  const filters =
    'fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];' +
    '[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle'
  const run = spawnSync(
    'ffmpeg',
    ['-y', '-loglevel', 'error', '-ss', startS.toFixed(2), '-to', endS.toFixed(2), '-i', webm, '-vf', filters, '-loop', '0', gif],
    { timeout: 120_000, encoding: 'utf8' },
  )
  if (run.error || run.status !== 0) {
    console.warn(`showcase: no GIF (${run.error?.message ?? run.stderr.trim()}); the WebM stays at ${webm}`)
    return false
  }
  return true
}

/**
 * The README GIF: the same flow as the first desktop test, recorded at a reading pace and
 * turned into docs/showcase/demo.gif. It creates revision C, as that test does, so it runs
 * alone on fresh servers: `npm run showcase:gif` (`npm run showcase` leaves it out).
 */
test('desktop: recorded demo for the README GIF @gif', async ({ browser }) => {
  test.setTimeout(180_000) // the real KiCad export takes a while
  const size = { width: 1280, height: 800 }
  const context = await browser.newContext({ viewport: size, recordVideo: { dir: join(TMP, 'video'), size } })
  await blurLocalPaths(context)
  const page = await context.newPage()
  const t0 = Date.now()
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Create Design' })).toBeVisible()
  const startS = (Date.now() - t0) / 1000
  await page.waitForTimeout(1500)

  const input = page.getByLabel(/describe your design/i)
  await input.click()
  await input.pressSequentially('Revision C of the bead sorter vision board', { delay: 40 })
  await page.waitForTimeout(400)
  await page.getByRole('button', { name: 'Send' }).click()
  const confirm = page.getByRole('button', { name: 'Confirm' })
  await expect(confirm).toBeVisible()
  await page.waitForTimeout(3500) // the filled form and the title block

  await confirm.hover()
  await page.waitForTimeout(600)
  await confirm.click()
  const preview = page.getByRole('dialog').getByRole('img')
  await expect.poll(() => preview.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0), { timeout: 60_000 }).toBe(true)
  await page.waitForTimeout(2500)
  await page.getByRole('dialog').getByRole('button', { name: 'Title block' }).click()
  await page.waitForTimeout(3500)

  // The board has the same title block (decision 0033): switch to it and zoom in again.
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'PCB', exact: true }).hover()
  await page.waitForTimeout(500)
  await dialog.getByRole('button', { name: 'PCB', exact: true }).click()
  const board = dialog.getByRole('img', { name: /PCB title block/ })
  await expect.poll(() => board.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0), { timeout: 30_000 }).toBe(true)
  await page.waitForTimeout(2000)
  await dialog.getByRole('button', { name: 'Title block' }).click()
  await page.waitForTimeout(3500)
  const endS = (Date.now() - t0) / 1000

  const video = page.video()
  await context.close()
  const webm = join(TMP, 'demo.webm')
  await video?.saveAs(webm)
  if (toGif(webm, join(OUT, 'demo.gif'), startS, endS)) rmSync(webm)
})
