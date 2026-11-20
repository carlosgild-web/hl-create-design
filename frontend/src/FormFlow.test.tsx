import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import type { Action } from './api/types'
import { baseRoutes, jsonResponse, makeAction, renderWithProviders, sseResponse, stubFetch, user } from './test/helpers'

afterEach(() => vi.unstubAllGlobals())

const QUIET = { ok: true, normalized: {}, errors: [], warnings: [] }

function proposal(fields: Record<string, string>) {
  return (url: string) =>
    url === '/api/chat'
      ? sseResponse([
          ['conversation', { id: 'c1' }],
          ['form_proposal', { fields }],
          ['done', { status: 'answered' }],
        ])
      : undefined
}

describe('form: inline validation (decision 0017, block B)', () => {
  it('shows a skipped revision letter right away, with its manual reference', async () => {
    const calls = stubFetch(
      (url, init) => {
        if (url !== '/api/validate') return undefined
        const { fields } = JSON.parse(String(init?.body))
        return jsonResponse(
          fields.revision === 'I'
            ? {
                ok: false,
                normalized: { revision: 'I' },
                errors: [
                  {
                    field: 'revision',
                    code: 'rev_skipped_letter',
                    message: 'I is never used as a revision letter.',
                    ref: '02-revisions#skipped-letters',
                  },
                ],
                warnings: [],
              }
            : QUIET,
        )
      },
      ...baseRoutes,
    )
    renderWithProviders(<App />)

    await user.type(screen.getByLabelText('Revision'), 'I')

    const alert = await screen.findByText(/I is never used as a revision letter/, undefined, { timeout: 2000 })
    expect(alert).toHaveTextContent('[02-revisions#skipped-letters]')
    expect(screen.getByLabelText('Revision')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Revision')).toHaveValue('I') // never replaced
    const sent = calls.filter((c) => c.url === '/api/validate').map((c) => JSON.parse(String(c.init?.body)))
    expect(sent.at(-1)).toEqual({ fields: { revision: 'I' } })
  })

  it('shows the name as it will be stored', async () => {
    stubFetch(
      (url) =>
        url === '/api/validate'
          ? jsonResponse({ ...QUIET, normalized: { name: 'Bead Sorter Vision Board' } })
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)

    await user.type(screen.getByLabelText('Design name'), 'bead sorter vision board')

    const note = await screen.findByText('Will be saved as:', undefined, { timeout: 2000 })
    expect(note).toHaveTextContent('Bead Sorter Vision Board')
  })
})

describe('form: where each value came from', () => {
  it('labels only what the assistant changed, and never overwrites what the user typed', async () => {
    stubFetch(proposal({ department: 'HW', name: 'Bead Counter', revision: 'A' }), ...baseRoutes)
    renderWithProviders(<App />)
    await screen.findByRole('option', { name: /^HW/ })
    await user.selectOptions(screen.getByLabelText('Department'), 'HW')
    await user.type(screen.getByLabelText('Revision'), 'B')

    await user.click(screen.getByRole('button', { name: 'Try an example' }))

    await waitFor(() => expect(screen.getByLabelText('Design name')).toHaveValue('Bead Counter'))
    expect(screen.getAllByText('Suggested by the assistant')).toHaveLength(1) // only the name
    expect(screen.getByLabelText('Revision')).toHaveValue('B')
    expect(screen.getByText('The assistant suggests: A')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Use it' }))

    expect(screen.getByLabelText('Revision')).toHaveValue('A')
    expect(screen.getAllByText('Suggested by the assistant')).toHaveLength(2)
  })

  it('fills a reserved number from SAP at once, and Undo puts the form back', async () => {
    const pending = makeAction({
      id: 'r1',
      kind: 'reserve_number',
      payload: { department: 'PWR', name: 'Gate Driver', designer: 'C. Velazquez' },
    })
    const confirmed: Action = {
      ...pending,
      status: 'confirmed',
      result: { ok: true, design_number: 'HL-PWR-26-0101', department: 'PWR', revision: 'A' },
    }
    stubFetch(
      (url) => (url === '/api/actions' ? jsonResponse(pending, 201) : undefined),
      (url) => (url === '/api/actions/r1/confirm' ? jsonResponse(confirmed) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await screen.findByRole('option', { name: /^PWR/ })
    await user.selectOptions(screen.getByLabelText('Department'), 'PWR')
    await user.type(screen.getByLabelText('Design name'), 'Gate Driver')
    await user.type(screen.getByLabelText('Designer'), 'C. Velazquez')
    await user.click(screen.getByRole('button', { name: 'Reserve a new number' }))

    await user.click(await screen.findByRole('button', { name: 'Confirm' }))

    await waitFor(() => expect(screen.getByLabelText('Design number')).toHaveValue('HL-PWR-26-0101'))
    expect(screen.getByLabelText('Revision')).toHaveValue('A')
    expect(screen.getAllByText('From SAP')).toHaveLength(2) // number and revision, not the department
    expect(screen.queryByText('Suggested by the assistant')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Undo' }))

    expect(screen.getByLabelText('Design number')).toHaveValue('')
    expect(screen.queryByText('From SAP')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Use this number' })).toBeInTheDocument()
  })
})

describe('confirmation card', () => {
  it('shows that it is working while Confirm waits, with translated labels', async () => {
    let finish!: (r: Response) => void
    stubFetch(
      (url) =>
        url === '/api/chat'
          ? sseResponse([
              ['conversation', { id: 'c1' }],
              ['pending_action', { action: makeAction() }],
              ['done', { status: 'answered' }],
            ])
          : undefined,
      (url) => (url === '/api/actions/a1/confirm' ? new Promise<Response>((r) => (finish = r)) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await user.click(screen.getByRole('button', { name: 'Guide me step by step' }))
    const card = await screen.findByRole('region', { name: 'Create this design?' })
    expect(within(card).getByText('Design number')).toBeInTheDocument()
    expect(within(card).getByText('HW – Hardware Design')).toBeInTheDocument()

    await user.click(within(card).getByRole('button', { name: 'Confirm' }))

    const busy = await within(card).findByRole('button', { name: 'Confirming…' })
    expect(busy).toBeDisabled()
    expect(busy).toHaveAttribute('aria-busy', 'true')
    expect(within(card).getByRole('button', { name: 'Cancel' })).toBeDisabled()

    finish(jsonResponse({ ...makeAction(), status: 'cancelled' }))
    await waitFor(() => expect(within(card).queryByRole('button', { name: 'Confirming…' })).not.toBeInTheDocument())
  })
})
