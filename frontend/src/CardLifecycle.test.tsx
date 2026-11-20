import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { samePayload } from './hooks/useChat'
import { blockers } from './lib/fields'
import { baseRoutes, jsonResponse, makeAction, renderWithProviders, sseResponse, stubFetch, user } from './test/helpers'

afterEach(() => vi.unstubAllGlobals())

/** The assistant picks HL-HW-26-0042 (rev C next) and opens its create card. */
const assistantOpensCard = (url: string) =>
  url === '/api/chat'
    ? sseResponse([
        ['conversation', { id: 'c1' }],
        ['form_proposal', { fields: { design_number: 'HL-HW-26-0042', designer: 'C. Velazquez' } }],
        // as the real backend sends it: SAP's material and project ride along
        ['pending_action', { action: makeAction({ payload: { ...makeAction().payload, sap_material: '000000000040001234', project: 'P-26-0108' } }) }],
        ['done', { status: 'answered' }],
      ])
    : undefined

describe('confirmation cards: one live card per request', () => {
  it('Create does not open a copy of the card the assistant already opened', async () => {
    const calls = stubFetch(assistantOpensCard, ...baseRoutes)
    renderWithProviders(<App />)
    await user.click(screen.getByRole('button', { name: 'Try an example' }))
    await screen.findByRole('region', { name: 'Create this design?' })
    await waitFor(() => expect(screen.getByLabelText('Designer')).toHaveValue('C. Velazquez'))
    expect(screen.getByText(/A card for these values is waiting in the chat/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Create revision C' }))

    expect(screen.getAllByRole('region', { name: 'Create this design?' })).toHaveLength(1)
    expect(calls.some((c) => c.url === '/api/actions')).toBe(false)
  })

  it('a mode switch cancels the waiting card and leaves it without buttons', async () => {
    const calls = stubFetch(
      assistantOpensCard,
      (url) => (url === '/api/actions/a1/cancel' ? jsonResponse({ ...makeAction(), status: 'cancelled' }) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await user.click(screen.getByRole('button', { name: 'Try an example' }))
    const card = await screen.findByRole('region', { name: 'Create this design?' })
    await waitFor(() => expect(screen.getByLabelText('Designer')).toHaveValue('C. Velazquez'))

    await user.click(screen.getByRole('radio', { name: 'New design' }))
    await user.click(screen.getByRole('button', { name: 'Switch' }))

    await waitFor(() => expect(card).toHaveAttribute('data-status', 'cancelled'))
    expect(calls.some((c) => c.url === '/api/actions/a1/cancel')).toBe(true)
    expect(within(card).queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument()
    expect(within(card).getByText(/From an earlier design/)).toBeInTheDocument()
    expect(screen.getByText(/Started over/)).toBeInTheDocument()
  })
})

describe('why Create is not available', () => {
  it('a new design named Test: says the SAP number is missing and offers it next to Create', async () => {
    stubFetch(...baseRoutes)
    renderWithProviders(<App />)
    await screen.findByRole('option', { name: /^PWR/ })
    await user.selectOptions(screen.getByLabelText('Department'), 'PWR')
    await user.type(screen.getByLabelText('Design name'), 'Test')

    const create = screen.getByRole('button', { name: 'Create design' })
    expect(create).toBeDisabled()
    expect(create).toHaveAccessibleDescription('To create: fill in Designer · get a SAP number')
    expect(screen.getByRole('button', { name: 'Next: get SAP number' })).toBeDisabled()

    await user.type(screen.getByLabelText('Designer'), 'C. Velazquez')

    expect(create).toHaveAccessibleDescription('To create: get a SAP number')
    expect(screen.getByRole('button', { name: 'Next: get SAP number' })).toBeEnabled()
  })

  it('lists blockers in the order to do things', () => {
    const empty = { department: '', design_number: '', revision: 'A', name: '', designer: '', description: '' }
    expect(blockers('new', empty, 0).map((b) => b.key)).toEqual([
      'need_field',
      'need_field',
      'need_field',
      'need_sap_number',
    ])
    expect(blockers('existing', { ...empty, revision: '' }, 0).map((b) => b.key)).toEqual(['need_design', 'need_field'])
    const full = { ...empty, department: 'HW', design_number: 'HL-HW-26-0042', revision: 'C', name: 'X Board', designer: 'C. V' }
    expect(blockers('existing', full, 0)).toEqual([])
    expect(blockers('existing', full, 1)).toEqual([{ key: 'fix_errors' }])
  })
})

describe('description (optional)', () => {
  it('is not needed to create, is sent with the card, and counts its characters', async () => {
    const calls = stubFetch(
      (url) => (url === '/api/actions' ? jsonResponse(makeAction({ id: 'd1' }), 201) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await user.click(screen.getByRole('radio', { name: 'From existing design' }))
    await user.click(await screen.findByRole('option', { name: /HL-HW-26-0042/ }))
    await user.type(screen.getByLabelText('Designer'), 'C. Velazquez')
    const create = screen.getByRole('button', { name: 'Create revision C' })
    expect(create).toBeEnabled() // without a description

    await user.type(screen.getByLabelText(/Description/), 'Second source for the driver')
    expect(screen.getByText('28/60')).toBeInTheDocument()
    await user.click(create)

    await waitFor(() => expect(calls.some((c) => c.url === '/api/actions')).toBe(true))
    const sent = JSON.parse(String(calls.find((c) => c.url === '/api/actions')!.init?.body))
    expect(sent.payload.description).toBe('Second source for the driver')
  })
})

describe('samePayload', () => {
  it('ignores the formatting the backend adds, not the values', () => {
    expect(samePayload({ name: 'bead  sorter', revision: 'c' }, { name: 'Bead Sorter', revision: 'C' })).toBe(true)
    expect(samePayload({ name: 'Bead Sorter' }, { name: 'Bead Sorter', designer: 'C. Velazquez' })).toBe(false)
    expect(samePayload({ name: 'Bead Sorter', designer: '' }, { name: 'Bead Sorter' })).toBe(true)
    // an assistant card from the real backend also carries SAP's material and project (or null)
    expect(samePayload({ name: 'Bead Sorter', sap_material: '000000000040001177', project: null }, { name: 'Bead Sorter' })).toBe(true)
  })
})
