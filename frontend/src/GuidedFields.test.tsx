import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { baseRoutes, jsonResponse, renderWithProviders, stubFetch, user } from './test/helpers'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

/** `/api/validate` like the backend: the prefix for a department, the next free revision. */
function validateLikeTheBackend(sent: Record<string, string>[]) {
  return (url: string, init?: RequestInit) => {
    if (url !== '/api/validate') return undefined
    const { fields } = JSON.parse(String(init?.body)) as { fields: Record<string, string> }
    sent.push(fields)
    const suggest: Record<string, string> = {}
    if (fields.department) suggest.design_number_prefix = `HL-${fields.department}-26-`
    if (fields.design_number === 'HL-HW-26-0042') suggest.revision = 'C'
    return jsonResponse({ ok: true, normalized: {}, errors: [], warnings: [], suggest })
  }
}

const recent = (url: string) =>
  url === '/api/designs'
    ? jsonResponse([
        {
          design_number: 'HL-HW-26-0003',
          revision: 'C',
          name: 'Bead Sorter Vision Board',
          department: 'HW',
          designer: 'M. Ortega',
          pdf: true,
          created_at: '2026-11-17T10:00:00Z',
        },
      ])
    : undefined

describe('guided fields (decision 0017, block F)', () => {
  it('says what each field expects before anything is typed', () => {
    stubFetch(...baseRoutes)
    renderWithProviders(<App />)

    expect(screen.getByText(/Format HL-<DEPT>-<YY>-NNNN, e.g. HL-HW-26-0042/)).toBeInTheDocument()
    expect(screen.getByText(/One letter, e.g. A for a new design/)).toBeInTheDocument()
    expect(screen.getByText('Initial and surname, e.g. C. Velazquez')).toBeInTheDocument()
    expect(screen.getByLabelText('Design number')).toHaveAttribute('placeholder', 'HL-HW-26-0042')
    expect(screen.getByLabelText('Design number')).toHaveAccessibleDescription(/Format HL-/)
  })

  it('picking a department pre-fills the number prefix, which is not checked as a value', async () => {
    const sent: Record<string, string>[] = []
    stubFetch(validateLikeTheBackend(sent), ...baseRoutes)
    renderWithProviders(<App />)
    await screen.findByRole('option', { name: /^HW/ })

    await user.selectOptions(screen.getByLabelText('Department'), 'HW')

    await waitFor(() => expect(screen.getByLabelText('Design number')).toHaveValue('HL-HW-26-'), { timeout: 2000 })
    expect(screen.getByText(/Type the 4-digit sequence after HL-HW-26-/)).toBeInTheDocument()
    expect(screen.getByLabelText('Design folder')).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Create design' })).toBeDisabled()
    // the bare prefix never went to the validators as a design number
    expect(sent.every((f) => !('design_number' in f))).toBe(true)

    await user.type(screen.getByLabelText('Design number'), '00')
    expect(screen.getByText('2 more digits')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Design number'), '42')
    expect(screen.getByText(/Format OK/)).toBeInTheDocument()
  })

  it('offers the next free revision and the last designer', async () => {
    stubFetch(validateLikeTheBackend([]), recent, ...baseRoutes)
    renderWithProviders(<App />)

    const designerHint = await screen.findByText(/Last used: M. Ortega/)
    await user.click(designerHint.querySelector('button')!)
    expect(screen.getByLabelText('Designer')).toHaveValue('M. Ortega')
    expect(screen.queryByText('Suggested by the assistant')).not.toBeInTheDocument() // the user's choice

    await screen.findByRole('option', { name: /^HW/ })
    await user.selectOptions(screen.getByLabelText('Department'), 'HW')
    await waitFor(() => expect(screen.getByLabelText('Design number')).toHaveValue('HL-HW-26-'), { timeout: 2000 })
    await user.type(screen.getByLabelText('Design number'), '0042')

    const next = await screen.findByText(/Next free revision: C/, undefined, { timeout: 2000 })
    await user.click(next.querySelector('button')!)
    expect(screen.getByLabelText('Revision')).toHaveValue('C')
  })

  it('has a Reserve shortcut next to the number, enabled once the card can be filled', async () => {
    stubFetch(validateLikeTheBackend([]), ...baseRoutes)
    renderWithProviders(<App />)
    const shortcut = screen.getByRole('button', { name: 'Reserve new' })
    expect(shortcut).toBeDisabled()
    expect(shortcut).toHaveAttribute('title', 'Fill in the department, the name and the designer first.')

    await screen.findByRole('option', { name: /^HW/ })
    await user.selectOptions(screen.getByLabelText('Department'), 'HW')
    await user.type(screen.getByLabelText('Design name'), 'Gate Driver')
    await user.type(screen.getByLabelText('Designer'), 'C. Velazquez')

    expect(screen.getByRole('button', { name: 'Reserve new' })).toBeEnabled()
  })
})
