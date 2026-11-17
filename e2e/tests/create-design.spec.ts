import { expect, test } from '@playwright/test'

const API = 'http://127.0.0.1:8191'
const PREVIEW = `${API}/api/designs/HW/HL-HW-26-0003/C/preview.svg`

test.describe.configure({ mode: 'serial' })

test('assistant fills the form, nothing is created until the click, then the preview shows', async ({
  page,
  request,
}) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Create Design' })).toBeVisible()
  await expect(page.getByText('No designs yet.')).toBeVisible()

  await page.getByLabel(/describe your design/i).fill('Revision C of the bead sorter vision board')
  await page.getByRole('button', { name: 'Send' }).click()

  // the form is filled and marked as the assistant's suggestion
  await expect(page.getByLabel('Design number')).toHaveValue('HL-HW-26-0003')
  await expect(page.getByLabel('Revision')).toHaveValue('C')
  await expect(page.getByLabel('Design folder')).toHaveValue('HW/HL-HW-26-0003/C')
  await expect(page.getByText('Suggested by the assistant').first()).toBeVisible()

  // SAP card from the real mock service
  const sap = page.getByRole('region', { name: 'SAP record' })
  await expect(sap.getByText('In work')).toBeVisible()
  await expect(sap.getByText('40001177')).toBeVisible()

  // the card is waiting: the model has not created anything (invariant 2)
  const confirm = page.getByRole('button', { name: 'Confirm' })
  await expect(confirm).toBeVisible()
  expect((await request.get(PREVIEW)).status()).toBe(404)

  await confirm.click()

  await expect(page.getByText('Created HL-HW-26-0003 rev C')).toBeVisible()
  const preview = page.getByRole('img', { name: /Title block of HL-HW-26-0003 rev C/ })
  await expect(preview).toBeVisible()
  await expect
    .poll(() => preview.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0))
    .toBe(true)
  expect((await request.get(PREVIEW)).status()).toBe(200)
  await expect(page.getByRole('button', { name: /HL-HW-26-0003 C/ })).toBeVisible()

})

test('a revision that SAP already knows is refused with the manual reference', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Department').selectOption('HW')
  await page.getByLabel('Design number').fill('HL-HW-26-0003')
  await page.getByLabel('Revision').fill('B')
  await page.getByLabel('Design name').fill('Bead Sorter Vision Board')
  await page.getByLabel('Designer').fill('C. Velazquez')

  await page.getByRole('button', { name: 'Create design' }).click()
  await page.getByRole('button', { name: 'Confirm' }).click()

  await expect(page.getByText('Not done')).toBeVisible()
  await expect(page.getByLabel('Revision')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByRole('alert').filter({ hasText: '[02-revisions' }).first()).toBeVisible()
})

test('reserves a number in SAP from the form and uses it', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Department').selectOption('PWR')
  await page.getByLabel('Design name').fill('Test Fixture Supply')
  await page.getByLabel('Designer').fill('C. Velazquez')

  await page.getByRole('button', { name: 'Reserve a new number' }).click()
  await page.getByRole('button', { name: 'Confirm' }).click()
  await expect(page.getByText(/Reserved HL-PWR-26-\d{4}/)).toBeVisible()

  await page.getByRole('button', { name: 'Use this number' }).click()
  await expect(page.getByLabel('Design number')).toHaveValue(/HL-PWR-26-\d{4}/)
  await expect(page.getByLabel('Revision')).toHaveValue('A')
})

test('switches to Spanish', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'ES', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Crear diseño' })).toBeVisible()
})
