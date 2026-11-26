import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { baseRoutes, jsonResponse, renderWithProviders, stubFetch, user } from './test/helpers'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

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

describe('guided fields (decisions 0017 F and 0018)', () => {
  it('a new design: the number comes from SAP, revision A, hints before typing', () => {
    stubFetch(...baseRoutes)
    renderWithProviders(<App />)

    const number = screen.getByLabelText('Design number')
    expect(number).toHaveAttribute('aria-readonly', 'true')
    expect(number).toHaveAttribute('placeholder', 'Comes from SAP')
    expect(number).toHaveAccessibleDescription(/Get SAP number/)
    expect(screen.getByLabelText('Revision')).toHaveValue('A')
    expect(screen.getByLabelText('Revision')).toHaveAttribute('aria-readonly', 'true')
    expect(screen.getByText('Name or initials and surname, e.g. Carlos Velazquez or C. Velazquez')).toBeInTheDocument()
    expect(screen.getByLabelText('Design name')).toHaveAttribute('placeholder', 'e.g. Bead Drill Controller')
    // the old reserve buttons in the form are gone: the Start panel owns reserving
    expect(screen.queryByRole('button', { name: 'Reserve a new number' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reserve new' })).not.toBeInTheDocument()
  })

  it('typing in a locked field changes nothing', async () => {
    stubFetch(...baseRoutes)
    renderWithProviders(<App />)
    await user.type(screen.getByLabelText('Design number'), 'HL-HW-26-0042')
    expect(screen.getByLabelText('Design number')).toHaveValue('')
  })

  it('offers the last designer', async () => {
    stubFetch(recent, ...baseRoutes)
    renderWithProviders(<App />)

    const designerHint = await screen.findByText(/Last used: M. Ortega/)
    await user.click(designerHint.querySelector('button')!)

    expect(screen.getByLabelText('Designer')).toHaveValue('M. Ortega')
    expect(screen.queryByText('Suggested by the assistant')).not.toBeInTheDocument() // the user's choice
  })
})
