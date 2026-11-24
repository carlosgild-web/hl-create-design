import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { baseRoutes, jsonResponse, renderWithProviders, stubFetch, user } from './test/helpers'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

async function existingMode() {
  await user.click(screen.getByRole('radio', { name: 'From existing design' }))
  return screen.findByRole('listbox', { name: 'Designs in SAP' })
}

describe('Start panel (decision 0018)', () => {
  it('lists SAP designs with status, latest and next free revision', async () => {
    stubFetch(...baseRoutes)
    renderWithProviders(<App />)
    const list = await existingMode()

    const drill = within(list).getByRole('option', { name: /HL-HW-26-0042/ })
    expect(drill).toHaveTextContent('Bead Drill Controller')
    expect(drill).toHaveTextContent('In work')
    expect(drill).toHaveTextContent('latest B')
    expect(drill).toHaveTextContent('→ rev C')
    expect(drill).toHaveAttribute('aria-disabled', 'false')
  })

  it('BLOCKED and OBSOLETE designs are disabled, with the reason; OBSOLETE offers its successor', async () => {
    stubFetch(...baseRoutes)
    renderWithProviders(<App />)
    const list = await existingMode()

    const blocked = within(list).getByRole('option', { name: /HL-HW-24-0003/ })
    expect(blocked).toHaveAttribute('aria-disabled', 'true')
    expect(blocked).toHaveTextContent('Supplier part discontinued')
    await user.click(blocked)
    expect(screen.getByLabelText('Design number')).toHaveValue('') // not selected

    const obsolete = within(list).getByRole('option', { name: /HL-EMB-23-0002/ })
    await user.click(within(obsolete).getByRole('button', { name: 'Use successor HL-EMB-25-0011' }))

    await waitFor(() => expect(screen.getByLabelText('Design number')).toHaveValue('HL-EMB-25-0011'))
    expect(screen.getByLabelText('Design name')).toHaveValue('Sensor Hub II')
  })

  it('search and department chips filter the list; arrow keys and Enter pick a design', async () => {
    stubFetch(...baseRoutes)
    renderWithProviders(<App />)
    const list = await existingMode()

    await user.click(screen.getByRole('button', { name: 'HW' }))
    expect(within(list).getAllByRole('option').map((o) => o.id.split('-').slice(-4).join('-'))).toEqual([
      'HL-HW-24-0003',
      'HL-HW-26-0042',
    ])
    await user.click(screen.getByRole('button', { name: 'All' }))
    await user.type(screen.getByRole('searchbox', { name: 'Search by number or name' }), 'drill')
    await waitFor(() => expect(within(list).getAllByRole('option')).toHaveLength(1))

    fireEvent.focus(list)
    fireEvent.keyDown(list, { key: 'Enter' })

    await waitFor(() => expect(screen.getByLabelText('Design number')).toHaveValue('HL-HW-26-0042'))
    // department, number, name and revision are SAP's and locked; only the designer is typed
    for (const label of ['Department', 'Design number', 'Design name', 'Revision']) {
      expect(screen.getByLabelText(label)).toHaveAttribute('aria-readonly', 'true')
    }
    expect(screen.getByLabelText('Design name')).toHaveValue('Bead Drill Controller')
    expect(screen.getByLabelText('Revision')).toHaveValue('C')
    expect(screen.getByLabelText('Designer')).not.toHaveAttribute('aria-readonly')
    expect(screen.getByRole('button', { name: 'Create revision C' })).toBeInTheDocument()
    // the selected design's SAP card, and a way back to the list
    const card = within(screen.getByRole('radiogroup').closest('[data-slot="card"]') as HTMLElement)
    expect(card.getByRole('region', { name: 'SAP record' })).toHaveTextContent('40001234')
    await user.click(card.getByRole('button', { name: 'Change design' }))
    expect(await screen.findByRole('listbox')).toBeInTheDocument()
    expect(screen.getByLabelText('Design number')).toHaveValue('')
  })

  it('switching modes with values asks first and keeps the designer', async () => {
    stubFetch(...baseRoutes)
    renderWithProviders(<App />)
    await user.type(screen.getByLabelText('Design name'), 'Gate Driver')
    await user.type(screen.getByLabelText('Designer'), 'C. Velazquez')

    await user.click(screen.getByRole('radio', { name: 'From existing design' }))
    const ask = screen.getByRole('alertdialog')
    expect(ask).toHaveTextContent('The values you entered are cleared.')
    await user.click(within(ask).getByRole('button', { name: 'Keep' }))
    expect(screen.getByRole('radio', { name: 'New design' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByLabelText('Design name')).toHaveValue('Gate Driver')

    await user.click(screen.getByRole('radio', { name: 'From existing design' }))
    await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Switch' }))

    expect(screen.getByRole('radio', { name: 'From existing design' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByLabelText('Design name')).toHaveValue('')
    expect(screen.getByLabelText('Designer')).toHaveValue('C. Velazquez')
  })

  it('SAP down: says so, with Retry', async () => {
    let down = true
    stubFetch(
      (url) =>
        url === '/api/sap/designs?lang=en' && down
          ? jsonResponse(
              {
                code: 'sap_unavailable',
                message: 'SAP is not available right now (SAP system is in maintenance). ...',
                params: { sap_code: 'ZHL_GW/003', detail: 'SAP system is in maintenance; try again later' },
              },
              503,
            )
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await user.click(screen.getByRole('radio', { name: 'From existing design' }))

    expect(
      await screen.findByText(
        'SAP is not available right now (SAP system is in maintenance; try again later). Nothing was checked in SAP; try again later.',
      ),
    ).toBeInTheDocument()
    down = false
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('listbox')).toBeInTheDocument()
  })
})
