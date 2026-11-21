import { fireEvent, screen, waitFor, within } from '@testing-library/react'
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
  it('shows a rule error right away, with its manual reference', async () => {
    const calls = stubFetch(
      (url, init) => {
        if (url !== '/api/validate') return undefined
        const { fields } = JSON.parse(String(init?.body))
        return jsonResponse(
          fields.name === 'Bead Ünit'
            ? {
                ok: false,
                normalized: { name: 'Bead Ünit' },
                errors: [
                  {
                    field: 'name',
                    code: 'name_characters',
                    message: 'The design name may contain only letters A-Z, digits, spaces and - _ .',
                    ref: '03-title-block#design-name',
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

    await user.type(screen.getByLabelText('Design name'), 'Bead Ünit')

    const alert = await screen.findByText(/may contain only letters/, undefined, { timeout: 2000 })
    expect(alert).toHaveTextContent('[03-title-block#design-name]')
    expect(screen.getByLabelText('Design name')).toHaveAttribute('aria-invalid', 'true')
    const sent = calls.filter((c) => c.url === '/api/validate').map((c) => JSON.parse(String(c.init?.body)))
    // a new design starts at revision A; the name is what the user typed
    expect(sent.at(-1)).toEqual({ fields: { revision: 'A', name: 'Bead Ünit' } })
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
  it('labels only what the assistant changed, never overwrites the user, never touches locked fields', async () => {
    stubFetch(proposal({ department: 'HW', name: 'Bead Counter', revision: 'B', design_number: 'HL-HW-26-0777' }), ...baseRoutes)
    renderWithProviders(<App />)
    await user.type(screen.getByLabelText('Design name'), 'My Board')

    await user.click(screen.getByRole('button', { name: 'Try an example' }))

    await waitFor(() => expect(screen.getByLabelText('Department')).toHaveValue('HW'))
    expect(screen.getAllByText('Suggested by the assistant')).toHaveLength(1) // only the department
    expect(screen.getByLabelText('Design name')).toHaveValue('My Board')
    expect(screen.getByText('The assistant suggests: Bead Counter')).toBeInTheDocument()
    // a new design: the number comes only from SAP, the revision is A
    expect(screen.getByLabelText('Design number')).toHaveValue('')
    expect(screen.getByLabelText('Revision')).toHaveValue('A')

    await user.click(screen.getByRole('button', { name: 'Use it' }))

    expect(screen.getByLabelText('Design name')).toHaveValue('Bead Counter')
    expect(screen.getAllByText('Suggested by the assistant')).toHaveLength(2)
  })

  it('Get SAP number fills the number from SAP, and Undo puts the form back', async () => {
    const pending = makeAction({
      id: 'r1',
      kind: 'reserve_number',
      payload: { department: 'PWR', name: 'Gate Driver', designer: 'C. Velazquez' },
    })
    const confirmed: Action = {
      ...pending,
      status: 'confirmed',
      result: { ok: true, design_number: 'HL-PWR-26-0101', department: 'PWR', revision: 'A', sap_material: '000000000040009001', project: 'P-26-0112' },
    }
    const calls = stubFetch(
      (url) => (url === '/api/actions' ? jsonResponse(pending, 201) : undefined),
      (url) => (url === '/api/actions/r1/confirm' ? jsonResponse(confirmed) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    const get = screen.getByRole('button', { name: 'Get SAP number' })
    expect(get).toBeDisabled()
    expect(screen.getByText('Fill in Department, Design name and Designer first.')).toBeInTheDocument()
    await screen.findByRole('option', { name: /^PWR/ })
    await user.selectOptions(screen.getByLabelText('Department'), 'PWR')
    await user.type(screen.getByLabelText('Design name'), 'Gate Driver')
    await user.type(screen.getByLabelText('Designer'), 'C. Velazquez')
    await user.click(screen.getByRole('button', { name: 'Get SAP number' }))

    await user.click(await screen.findByRole('button', { name: 'Confirm' }))

    await waitFor(() => expect(screen.getByLabelText('Design number')).toHaveValue('HL-PWR-26-0101'))
    expect(screen.getByLabelText('Revision')).toHaveValue('A')
    expect(screen.getAllByText('From SAP')).toHaveLength(1) // the number (A was already there)
    const summary = screen.getByText('Reserved HL-PWR-26-0101 · rev A').closest('[role="status"]') as HTMLElement
    expect(within(summary).getByText('40009001 · P-26-0112')).toBeInTheDocument()
    expect(JSON.parse(String(calls.find((c) => c.url === '/api/actions')!.init?.body)).kind).toBe('reserve_number')

    // SAP issued the number for this department and name: they lock (decision 0023)
    expect(screen.getByLabelText('Design name')).toHaveAttribute('readonly')
    expect(screen.getByLabelText('Department')).toHaveAttribute('readonly')
    expect(screen.getByLabelText('Designer')).not.toHaveAttribute('readonly')

    await user.click(within(summary).getByRole('button', { name: 'Undo' }))

    expect(screen.getByLabelText('Design number')).toHaveValue('')
    expect(screen.queryByText('From SAP')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Design name')).not.toHaveAttribute('readonly')
  })

  it('a Create click while the check runs waits for it instead of being lost', async () => {
    const opened: unknown[] = []
    stubFetch(
      (url, init) => {
        if (url === '/api/actions') {
          opened.push(JSON.parse(String(init?.body)))
          return jsonResponse(makeAction({ id: 'q1' }), 201)
        }
        if (url !== '/api/validate') return undefined
        const { fields } = JSON.parse(String(init?.body))
        return jsonResponse(
          fields.designer === 'carlos'
            ? {
                ok: false,
                normalized: {},
                errors: [{ field: 'designer', code: 'designer_format', message: 'Bad designer.', ref: '03-title-block#designer' }],
                warnings: [],
              }
            : QUIET,
        )
      },
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await user.click(screen.getByRole('radio', { name: 'From existing design' }))
    await user.click(await screen.findByRole('option', { name: /HL-HW-26-0042/ }))
    await user.type(screen.getByLabelText('Designer'), 'carlos')
    await screen.findByText(/Write the designer as one or two initials/, undefined, { timeout: 2000 })

    fireEvent.change(screen.getByLabelText('Designer'), { target: { value: 'C. Velazquez' } })
    // the last answer still has the error, but the click is kept
    await user.click(screen.getByRole('button', { name: 'Create revision C' }))
    expect(screen.getByRole('button', { name: 'Checking…' })).toBeInTheDocument()

    await waitFor(() => expect(opened).toHaveLength(1), { timeout: 2000 })
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
