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

// These two run first: the assistant's card asks for HL-HW-26-0003 rev C, which the next test creates.
test('Create does not copy the card the assistant opened; Cancel leaves nothing behind', async ({ page, request }) => {
  await page.goto('/')
  await page.getByLabel(/describe your design/i).fill('Revision C of the bead sorter vision board')
  await page.getByRole('button', { name: 'Send' }).click()
  const cards = page.getByRole('region', { name: 'Create this design?' })
  await expect(cards).toHaveCount(1)
  await expect(page.getByText(/A card for these values is waiting in the chat/)).toBeVisible()

  await page.getByRole('button', { name: 'Create revision C' }).click()

  await expect(cards).toHaveCount(1)
  await expect(cards.getByRole('button', { name: 'Confirm' })).toBeFocused() // brought into view

  await cards.getByRole('button', { name: 'Cancel' }).click()
  await expect(cards).toContainText('Nothing was created or reserved.')
  expect((await request.get(PREVIEW)).status()).toBe(404)
})

test('a mode switch cancels the waiting card and leaves it without buttons', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel(/describe your design/i).fill('Revision C of the bead sorter vision board')
  await page.getByRole('button', { name: 'Send' }).click()
  const card = page.getByRole('region', { name: 'Create this design?' })
  await expect(card.getByRole('button', { name: 'Confirm' })).toBeVisible()

  await page.getByRole('radio', { name: 'New design' }).click()
  await page.getByRole('button', { name: 'Switch', exact: true }).click()

  await expect(card).toHaveAttribute('data-status', 'cancelled')
  await expect(card.getByRole('button')).toHaveCount(0)
  await expect(card).toContainText('From an earlier design')
  await expect(page.getByText('Started over. Waiting cards were cancelled; finished ones stay in the history.')).toBeVisible()
  await expect(page.getByLabel('Design number')).toHaveValue('')
})

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
  await expect(page.getByRole('button', { name: 'Get SAP number', exact: true })).toBeDisabled()
  await page.getByLabel('Department').selectOption('PWR')
  await page.getByLabel('Design name').fill('test fixture supply')
  await page.getByLabel('Designer').fill('C. Velazquez')
  // inline check from the real validators: the stored name is in title case
  await expect(page.getByText('Will be saved as:')).toContainText('Test Fixture Supply')

  await page.getByRole('button', { name: 'Get SAP number', exact: true }).click()
  const card = page.getByRole('region', { name: 'Reserve a new SAP number?' })
  await expect(card.getByText('PWR – Power Electronics')).toBeVisible()
  await card.getByRole('button', { name: 'Confirm' }).click()

  await expect(page.getByLabel('Design number')).toHaveValue(/HL-PWR-26-\d{4}/)
  await expect(page.getByLabel('Revision')).toHaveValue('A')
  await expect(page.getByText(/Reserved HL-PWR-26-\d{4} · rev A/).first()).toBeVisible()
  await expect(page.getByLabel('Design name')).toHaveAttribute('readonly') // SAP's name now

  await page.getByRole('button', { name: 'Create design' }).click()
  await page.getByRole('region', { name: 'Create this design?' }).getByRole('button', { name: 'Confirm' }).click()
  const number = await page.getByLabel('Design number').inputValue()
  await previewLoaded(page, number, 'A')
  await page.keyboard.press('Escape')

  // the number is used: no Undo, and no second reservation from the same values
  await expect(page.getByRole('button', { name: 'Undo' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Get SAP number', exact: true })).toBeDisabled()
})

test('a new design named Test: Create says why it waits, and a bad designer is caught inline', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Department').selectOption('EMB')
  await page.getByLabel('Design name').fill('Test')
  const create = page.getByRole('button', { name: 'Create design' })
  await expect(create).toBeDisabled()
  await expect(create).toHaveAccessibleDescription('To create: fill in Designer · get a SAP number')

  await page.getByLabel('Designer').fill('carlos')
  await expect(page.getByText(/Write the designer as one or two initials/)).toBeVisible()
  await expect(create).toHaveAccessibleDescription(/fix the errors above/)

  await page.getByLabel('Designer').fill('C. Velazquez')
  await expect(create).toHaveAccessibleDescription('To create: get a SAP number')
  await page.getByRole('button', { name: 'Next: get SAP number' }).click()
  const card = page.getByRole('region', { name: 'Reserve a new SAP number?' })
  await expect(card.getByText('EMB – Embedded Boards')).toBeVisible()
  await card.getByRole('button', { name: 'Cancel' }).click() // no number consumed
  await expect(card).toHaveAttribute('data-status', 'cancelled')
})

test('a description goes on the card and the recent list; the project downloads as a zip', async ({ page, request }) => {
  await page.goto('/')
  await page.getByRole('radio', { name: 'From existing design' }).click()
  await page.getByRole('searchbox', { name: 'Search by number or name' }).fill('polisher')
  await page.getByRole('listbox', { name: 'Designs in SAP' }).getByRole('option', { name: /HL-PWR-26-0011/ }).click()
  await expect(page.getByLabel('Revision')).toHaveValue('D') // C was created above
  await page.getByLabel('Designer').fill('C. Velazquez')
  await page.getByLabel(/Description/).fill('  Second source   for the gate driver ')

  await page.getByRole('button', { name: 'Create revision D' }).click()
  const card = page.getByRole('region', { name: 'Create this design?' })
  await expect(card).toContainText('Second source for the gate driver') // as stored
  await card.getByRole('button', { name: 'Confirm' }).click()

  const dialog = await previewLoaded(page, 'HL-PWR-26-0011', 'D')
  await expect(dialog.getByText(/HL-PWR-26-0011_D\.kicad_pro$/)).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Copy path' })).toBeVisible()
  // the e2e backend runs with KICAD_OPEN_ENABLED=false, as Docker does
  await expect(dialog.getByRole('button', { name: 'Open in KiCad' })).toHaveCount(0)
  const zip = dialog.getByRole('link', { name: 'Download project (.zip)' })
  const response = await request.get(`${API}${await zip.getAttribute('href')}`)
  expect(response.status()).toBe(200)
  expect((await response.body()).includes(Buffer.from('HL-PWR-26-0011_D/HL-PWR-26-0011_D.kicad_pro'))).toBe(true)
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: /Recent designs \(\d+\)/ }).click()
  await expect(page.getByText('Second source for the gate driver').last()).toBeVisible()

  // rev D is in SAP now (decision 0023): the list counts it, folders or not
  await page.goto('/')
  await page.getByRole('radio', { name: 'From existing design' }).click()
  await page.getByRole('searchbox', { name: 'Search by number or name' }).fill('polisher')
  const option = page.getByRole('listbox', { name: 'Designs in SAP' }).getByRole('option', { name: /HL-PWR-26-0011/ })
  await expect(option).toContainText('latest D')
  await expect(option).toContainText('→ rev E')
})

test('switches to Spanish, rule messages included', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'ES', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Crear diseño' })).toBeVisible()
  await expect(page.getByRole('radio', { name: 'Desde un diseño existente' })).toBeVisible()

  // the validators answer in English with a code; the form shows the Spanish template
  await page.getByLabel('Diseñador').fill('carlos')
  await expect(page.getByText(/Escribe el diseñador con una o dos iniciales/)).toBeVisible()
  await page.getByLabel('Nombre del diseño').fill('Prueba')
  await expect(page.getByText(/El nombre parece estar en español/)).toBeVisible()
  await expect(page.getByText(/Write the designer|The name looks Spanish/)).toHaveCount(0)
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
