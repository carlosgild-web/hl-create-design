import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { samePayload } from './hooks/useChat'
import { baseRoutes, jsonResponse, makeAction, renderWithProviders, sseResponse, stubFetch, user } from './test/helpers'

afterEach(() => vi.unstubAllGlobals())

/** The assistant picks HL-HW-26-0042 (rev C next) and opens its create card. */
const assistantOpensCard = (url: string) =>
  url === '/api/chat'
    ? sseResponse([
        ['conversation', { id: 'c1' }],
        ['form_proposal', { fields: { design_number: 'HL-HW-26-0042', designer: 'C. Velazquez' } }],
        ['pending_action', { action: makeAction() }],
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

describe('samePayload', () => {
  it('ignores the formatting the backend adds, not the values', () => {
    expect(samePayload({ name: 'bead  sorter', revision: 'c' }, { name: 'Bead Sorter', revision: 'C' })).toBe(true)
    expect(samePayload({ name: 'Bead Sorter' }, { name: 'Bead Sorter', designer: 'C. Velazquez' })).toBe(false)
    expect(samePayload({ name: 'Bead Sorter', designer: '' }, { name: 'Bead Sorter' })).toBe(true)
  })
})
