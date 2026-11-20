import { expect, test, type Page } from '@playwright/test'

const API = 'http://127.0.0.1:8191'
const PREVIEW = `${API}/api/designs/HW/HL-HW-26-0003/C/preview.svg`

test.describe.configure({ mode: 'serial' })

async function previewLoaded(page: Page, number: string, rev: string) {
  const dialog = page.getByRole('dialog', { name: new RegExp(`${number} · rev ${rev}`) })
  const img = dialog.getByRole('img', { name: new RegExp(`Title block of ${number} rev ${rev}`) })
  await expect(img).toBeVisible()
  await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0)).toBe(true)
  return dialog
}

test('the assistant names an existing design: nothing is created until the click, then the preview dialog', async ({
  page,
  request,
}) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Create Design' })).toBeVisible()

  await page.getByLabel(/describe your design/i).fill('Revision C of the bead sorter vision board')
  await page.getByRole('button', { name: 'Send' }).click()

  // a number SAP knows: the form switches to that existing design, and says who picked it
  await expect(page.getByText('The assistant selected HL-HW-26-0003.')).toBeVisible()
  await expect(page.getByRole('radio', { name: 'From existing design' })).toHaveAttribute('aria-checked', 'true')
  await expect(page.getByLabel('Design number')).toHaveValue('HL-HW-26-0003')
  await expect(page.getByLabel('Revision')).toHaveValue('C')
  await expect(page.getByLabel('Design name')).toHaveAttribute('aria-readonly', 'true')
  await expect(page.getByLabel('Design folder')).toHaveValue('HW/HL-HW-26-0003/C')

  // the card is waiting: the model has not created anything (invariant 2)
  const confirm = page.getByRole('button', { name: 'Confirm' })
  await expect(confirm).toBeVisible()
  expect((await request.get(PREVIEW)).status()).toBe(404)

  await confirm.click()

  const dialog = await previewLoaded(page, 'HL-HW-26-0003', 'C')
  await expect(dialog.getByRole('link', { name: 'Download PDF' })).toBeVisible()
  expect((await request.get(PREVIEW)).status()).toBe(200)
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()

  await expect(page.getByText('Created HL-HW-26-0003 rev C').first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create revision C' })).toBeDisabled()
  await page.getByRole('button', { name: /Recent designs \(\d+\)/ }).click()
  await expect(page.getByRole('button', { name: 'Preview HL-HW-26-0003 rev C' })).toBeVisible()
})

test('from an existing design: pick it, SAP sets the rest, create the next revision', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('radio', { name: 'From existing design' }).click()
  const list = page.getByRole('listbox', { name: 'Designs in SAP' })
  await page.getByRole('searchbox', { name: 'Search by number or name' }).fill('polisher')
  await list.getByRole('option', { name: /HL-PWR-26-0011/ }).click()

  await expect(page.getByLabel('Design name')).toHaveValue('Polisher Motor Inverter')
  await expect(page.getByLabel('Design name')).toHaveAttribute('aria-readonly', 'true')
  await expect(page.getByLabel('Revision')).toHaveValue('C') // SAP has A and B
  await page.getByLabel('Designer').fill('C. Velazquez')

  await page.getByRole('button', { name: 'Create revision C' }).click()
  await page.getByRole('region', { name: 'Create this design?' }).getByRole('button', { name: 'Confirm' }).click()

  await previewLoaded(page, 'HL-PWR-26-0011', 'C')
})

test('a BLOCKED design is listed but cannot be picked, and says why', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('radio', { name: 'From existing design' }).click()
  const blocked = page.getByRole('option', { name: /HL-HW-24-0015/ })
  await expect(blocked).toHaveAttribute('aria-disabled', 'true')
  await expect(blocked).toContainText('Quality hold')
  await blocked.click({ force: true }) // aria-disabled: Playwright would wait forever
  await expect(page.getByLabel('Design number')).toHaveValue('')
})

test('a new design: Get SAP number fills the number at once, then create it', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Get SAP number' })).toBeDisabled()
  await page.getByLabel('Department').selectOption('PWR')
  await page.getByLabel('Design name').fill('test fixture supply')
  await page.getByLabel('Designer').fill('C. Velazquez')
  // inline check from the real validators: the stored name is in title case
  await expect(page.getByText('Will be saved as:')).toContainText('Test Fixture Supply')

  await page.getByRole('button', { name: 'Get SAP number' }).click()
  const card = page.getByRole('region', { name: 'Reserve a new SAP number?' })
  await expect(card.getByText('PWR – Power Electronics')).toBeVisible()
  await card.getByRole('button', { name: 'Confirm' }).click()

  await expect(page.getByLabel('Design number')).toHaveValue(/HL-PWR-26-\d{4}/)
  await expect(page.getByLabel('Revision')).toHaveValue('A')
  await expect(page.getByText(/Reserved HL-PWR-26-\d{4} · rev A/).first()).toBeVisible()

  await page.getByRole('button', { name: 'Create design' }).click()
  await page.getByRole('region', { name: 'Create this design?' }).getByRole('button', { name: 'Confirm' }).click()
  const number = await page.getByLabel('Design number').inputValue()
  await previewLoaded(page, number, 'A')
})

test('switches to Spanish', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'ES', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Crear diseño' })).toBeVisible()
  await expect(page.getByRole('radio', { name: 'Desde un diseño existente' })).toBeVisible()
})

test('on a phone: one-line guide banner, Design | Assistant | Recent, the chat in view', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  const banner = page.getByRole('region', { name: 'Demo guide' })
  expect((await banner.boundingBox())!.height).toBeLessThan(60)

  const tabs = page.getByRole('tablist', { name: 'Sections' })
  await expect(tabs.getByRole('tab', { name: 'Design', exact: true })).toHaveAttribute('aria-selected', 'true')
  await tabs.getByRole('tab', { name: /Assistant/ }).click()
  await page.getByLabel(/describe your design/i).fill('Revision C of the bead sorter vision board')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByRole('region', { name: 'SAP record' })).toBeVisible()
  await expect(page.getByLabel(/describe your design/i)).toBeInViewport()

  await tabs.getByRole('tab', { name: 'Design', exact: true }).click()
  await expect(page.getByLabel('Design number')).toHaveValue('HL-HW-26-0003')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

for (const size of [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 1100, height: 800 },
]) {
  test(`desktop ${size.width}x${size.height}: one screen, chat left, preview fully visible`, async ({ page }) => {
    await page.setViewportSize(size)
    await page.goto('/')
    await page.getByLabel(/describe your design/i).fill('Revision C of the bead sorter vision board')
    await page.getByRole('button', { name: 'Send' }).click()
    await expect(page.getByLabel('Design number')).toHaveValue('HL-HW-26-0003')

    expect(await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight)).toBe(true)
    const input = page.getByLabel(/describe your design/i)
    await expect(input).toBeInViewport()
    const chat = (await input.boundingBox())!
    const start = (await page.getByRole('radiogroup', { name: 'What do you want to create?' }).boundingBox())!
    const form = (await page.getByLabel('Designer').boundingBox())!
    expect(chat.x).toBeLessThan(start.x)
    if (size.width >= 1280) expect(start.x).toBeLessThan(form.x) // three columns
    else expect(start.y).toBeLessThan(form.y) // panel above the form

    // a created design's preview (from the first test) opens fully inside the viewport
    await page.getByRole('button', { name: /Recent designs \(\d+\)/ }).click()
    await page.getByRole('button', { name: 'Preview HL-HW-26-0003 rev C' }).click()
    const dialog = await previewLoaded(page, 'HL-HW-26-0003', 'C')
    const box = (await dialog.boundingBox())!
    expect(box.y).toBeGreaterThanOrEqual(0)
    expect(box.y + box.height).toBeLessThanOrEqual(size.height)
    expect(box.x + box.width).toBeLessThanOrEqual(size.width)
  })
}
