import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import {
  baseRoutes,
  jsonResponse,
  makeAction,
  renderWithProviders,
  sseResponse,
  stubFetch,
  user,
} from './test/helpers'

const SAP = {
  design_number: 'HL-HW-26-0042',
  department: 'HW',
  name: 'Bead Drill Controller',
  status: 'IN_WORK',
  material: '000000000040001234',
  wbs: 'P-26-0108',
  current_revision: 'B',
  block_reason: '',
  successor: '',
  revisions: ['A', 'B'],
}

afterEach(() => vi.unstubAllGlobals())

/** In the Start panel: "From existing design", pick the design, type the designer. */
async function pickExisting(number: string, designer = 'C. Velazquez') {
  await user.click(screen.getByRole('radio', { name: 'From existing design' }))
  const option = await screen.findByRole('option', { name: new RegExp(number) })
  await user.click(option)
  await waitFor(() => expect(screen.getByLabelText('Design number')).toHaveValue(number))
  await user.type(screen.getByLabelText('Designer'), designer)
}

describe('Create Design', () => {
  it('chat → filled form → SAP card → confirm → preview', async () => {
    const action = makeAction()
    const calls = stubFetch(
      (url) =>
        url === '/api/chat'
          ? sseResponse([
              ['conversation', { id: 'c1' }],
              ['tool_call', { id: 't1', name: 'sap_get_design', arguments: { design_number: SAP.design_number } }],
              ['tool_result', { id: 't1', name: 'sap_get_design', ok: true, result: { found: true, design: SAP, status_notes: [] } }],
              ['form_proposal', { fields: { department: 'HW', design_number: 'HL-HW-26-0042', revision: 'C' } }],
              ['pending_action', { action }],
              ['message', { role: 'assistant', content: 'Please confirm the card.' }],
              ['done', { conversation_id: 'c1', run_id: 7, status: 'answered' }],
            ])
          : undefined,
      (url) =>
        url === '/api/actions/a1/confirm?lang=en'
          ? jsonResponse(
              makeAction({
                status: 'confirmed',
                result: { ok: true, design_number: 'HL-HW-26-0042', revision: 'C', folder: 'HW/HL-HW-26-0042/C', pdf: true },
              }),
            )
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)

    await user.type(screen.getByLabelText(/describe your design/i), 'revision C of HL-HW-26-0042')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    // the assistant named a number SAP knows: the form switches to that existing design, visibly
    await waitFor(() => expect(screen.getByLabelText('Design number')).toHaveValue('HL-HW-26-0042'))
    expect(screen.getByText('The assistant selected HL-HW-26-0042.')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'From existing design' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByLabelText('Revision')).toHaveValue('C') // next free, from SAP
    expect(screen.getByLabelText('Design number')).toHaveAttribute('aria-readonly', 'true')
    // SAP set the locked fields: they say "From SAP", never "Suggested by the assistant". Only
    // the designer, which the card brought into the empty field, is the assistant's.
    expect(screen.getAllByText('Suggested by the assistant')).toHaveLength(1)
    expect(document.getElementById('field-designer-source')).toHaveTextContent('Suggested by the assistant')
    expect(screen.getAllByText('From SAP')).toHaveLength(4)
    expect(screen.getByLabelText('Design folder')).toHaveValue('HW/HL-HW-26-0042/C')
    // SAP card: material without leading zeros
    // one in the chat, one for the selected design in the Start panel
    const [sap] = await screen.findAllByRole('region', { name: 'SAP record' })
    expect(within(sap).getByText('40001234')).toBeInTheDocument()
    expect(within(sap).getByText('In work')).toBeInTheDocument()
    // nothing was confirmed by the stream itself
    expect(calls.some((c) => c.url.includes('/confirm'))).toBe(false)

    await user.click(await screen.findByRole('button', { name: 'Confirm' }))

    // the card and the form both say so; the form offers a new design and won't create it twice
    expect(await screen.findAllByText('Created HL-HW-26-0042 rev C')).toHaveLength(2)
    // the preview opens in a dialog
    const dialog = await screen.findByRole('dialog', { name: /HL-HW-26-0042 · rev C/ })
    const preview = within(dialog).getByRole('img', { name: /Title block of HL-HW-26-0042 rev C/ })
    expect(preview).toHaveAttribute('src', '/api/designs/HW/HL-HW-26-0042/C/preview.svg')
    fireEvent.keyDown(dialog, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    // the form offers a new design and won't create the same revision twice
    expect(screen.getByRole('button', { name: 'New design' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create revision C' })).toBeDisabled()
    // the chat request carried the language and the current form
    const chat = calls.find((c) => c.url === '/api/chat')!
    expect(JSON.parse(String(chat.init?.body))).toMatchObject({ language: 'en', conversation_id: null })
  })

  it('stops highlighting a suggested field once the user edits it', async () => {
    stubFetch(
      (url) =>
        url === '/api/chat'
          ? sseResponse([
              ['conversation', { id: 'c1' }],
              ['form_proposal', { fields: { name: 'Bead Counter' } }],
              ['done', { status: 'answered' }],
            ])
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)

    await user.click(screen.getByRole('button', { name: 'Try an example' }))
    expect(await screen.findByText('Suggested by the assistant')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Design name'), '!')

    expect(screen.queryByText('Suggested by the assistant')).not.toBeInTheDocument()
  })

  it('the form opens a card through the gate and does not create anything itself', async () => {
    const calls = stubFetch(
      (url, init) =>
        url === '/api/actions' && init?.method === 'POST' ? jsonResponse(makeAction(), 201) : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    expect(screen.getByRole('button', { name: 'Create design' })).toBeDisabled()

    await pickExisting('HL-HW-26-0042')
    await user.click(screen.getByRole('button', { name: 'Create revision C' }))

    expect(await screen.findByRole('button', { name: 'Confirm' })).toBeInTheDocument()
    const post = calls.find((c) => c.url === '/api/actions')!
    expect(JSON.parse(String(post.init?.body))).toMatchObject({
      kind: 'create_design',
      payload: { department: 'HW', design_number: 'HL-HW-26-0042', revision: 'C', name: 'Bead Drill Controller' },
    })
    expect(calls.some((c) => c.url.includes('/confirm'))).toBe(false)
  })

  it('a rule failure on confirm shows the manual reference under the field', async () => {
    const failed = makeAction({
      status: 'failed',
      result: {
        ok: false,
        error_kind: 'validation',
        message: 'The values break a rule of the Design Manual; nothing was done.',
        errors: [
          { field: 'revision', code: 'rev_reused', message: 'Revision C is already used.', ref: '02-revisions#never-reused' },
        ],
      },
    })
    stubFetch(
      (url, init) => (url === '/api/actions' && init?.method === 'POST' ? jsonResponse(makeAction(), 201) : undefined),
      (url) => (url === '/api/actions/a1/confirm?lang=en' ? jsonResponse(failed, 422) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await pickExisting('HL-HW-26-0042')
    await user.click(screen.getByRole('button', { name: 'Create revision C' }))
    await user.click(await screen.findByRole('button', { name: 'Confirm' }))

    expect(await screen.findByText('Not done')).toBeInTheDocument()
    const alerts = await screen.findAllByRole('alert')
    expect(alerts.some((a) => a.textContent?.includes('[02-revisions#never-reused]'))).toBe(true)
    expect(screen.getByLabelText('Revision')).toHaveAttribute('aria-invalid', 'true')
  })

  it('a SAP refusal on confirm reads in Spanish: our words and the SAP text (decision 0027)', async () => {
    const detail = 'El diseño HL-HW-26-0042 está en BLOCKED; no se permiten revisiones nuevas'
    const failed = makeAction({
      status: 'failed',
      result: {
        ok: false,
        error_kind: 'sap',
        message: `SAP refused: ZHL_PLM/020 ${detail}`,
        params: { sap_code: 'ZHL_PLM/020', detail },
      },
    })
    stubFetch(
      (url, init) => (url === '/api/actions' && init?.method === 'POST' ? jsonResponse(makeAction(), 201) : undefined),
      (url) => (url === '/api/actions/a1/confirm?lang=es' ? jsonResponse(failed, 502) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await pickExisting('HL-HW-26-0042')
    await user.click(screen.getByRole('button', { name: 'Create revision C' }))
    await screen.findByRole('button', { name: 'Confirm' })
    await user.click(screen.getByRole('button', { name: 'ES' }))
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(await screen.findByText(`SAP lo rechazó: ${detail} (ZHL_PLM/020)`)).toBeInTheDocument()
  })

  it('an expired card says so instead of pretending it worked', async () => {
    stubFetch(
      (url, init) => (url === '/api/actions' && init?.method === 'POST' ? jsonResponse(makeAction(), 201) : undefined),
      (url) => (url === '/api/actions/a1/confirm?lang=en' ? jsonResponse({ detail: 'expired', action: makeAction() }, 410) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await pickExisting('HL-HW-26-0042')
    await user.click(screen.getByRole('button', { name: 'Create revision C' }))
    await user.click(await screen.findByRole('button', { name: 'Confirm' }))

    expect(await screen.findByText('This card expired. Ask again.')).toBeInTheDocument()
  })

  it('switches the interface to Spanish', async () => {
    stubFetch(...baseRoutes)
    renderWithProviders(<App />)

    await user.click(screen.getByRole('button', { name: 'ES' }))

    expect(screen.getByRole('heading', { name: 'Crear diseño' })).toBeInTheDocument()
    expect(screen.getByLabelText('Nombre del diseño')).toBeInTheDocument()
  })

  it('shows an error line when the assistant is not reachable', async () => {
    stubFetch((url) => (url === '/api/chat' ? new Response('', { status: 502 }) : undefined), ...baseRoutes)
    renderWithProviders(<App />)

    await user.click(screen.getByRole('button', { name: 'Guide me step by step' }))

    expect(await screen.findByText(/Something went wrong: Chat failed: HTTP 502/)).toBeInTheDocument()
  })

  it('says so when the backend moved from Groq to Ollama mid-session', async () => {
    stubFetch(
      (url) =>
        url === '/api/chat'
          ? sseResponse([
              ['conversation', { id: 'c1' }],
              ['notice', { code: 'provider_switched', from: 'groq', to: 'ollama', model: 'qwen3', reason: 'daily' }],
              ['message', { role: 'assistant', content: 'Which department?' }],
              ['done', { conversation_id: 'c1', run_id: 8, status: 'answered' }],
            ])
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)

    await user.click(screen.getByRole('button', { name: 'Guide me step by step' }))

    expect(await screen.findByText(/continues on Ollama \(qwen3, local and slower\)/)).toBeInTheDocument()
    expect(screen.getByText(/^Groq's quota or credit is used up/)).toBeInTheDocument()
    expect(screen.getByText('Which department?')).toBeInTheDocument()
  })

  it('says so when a busy Dahl model handed over to the next one (decision 0031)', async () => {
    stubFetch(
      (url) =>
        url === '/api/chat'
          ? sseResponse([
              ['conversation', { id: 'c1' }],
              ['notice', { code: 'model_switched', provider: 'dahl', from: 'zai-org/GLM-5.3-Flash', to: 'deepseek-ai/DeepSeek-V4-Flash-0731', model: 'deepseek-ai/DeepSeek-V4-Flash-0731', reason: 'is at capacity' }],
              ['message', { role: 'assistant', content: 'Which department?' }],
              ['done', { conversation_id: 'c1', run_id: 8, status: 'answered' }],
            ])
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)

    await user.click(screen.getByRole('button', { name: 'Guide me step by step' }))

    expect(
      await screen.findByText(
        'zai-org/GLM-5.3-Flash is busy on Dahl, so the assistant continues on deepseek-ai/DeepSeek-V4-Flash-0731 for the rest of this session.',
      ),
    ).toBeInTheDocument()
  })

  it('names Dahl when its credit ran out and the session moved to Groq (decision 0029)', async () => {
    stubFetch(
      (url) =>
        url === '/api/chat'
          ? sseResponse([
              ['conversation', { id: 'c1' }],
              ['notice', { code: 'provider_switched', from: 'dahl', to: 'groq', model: 'gpt-oss', reason: 'no credit' }],
              ['message', { role: 'assistant', content: 'Which department?' }],
              ['done', { conversation_id: 'c1', run_id: 9, status: 'answered' }],
            ])
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)

    await user.click(screen.getByRole('button', { name: 'Guide me step by step' }))

    expect(
      await screen.findByText("Dahl's quota or credit is used up, so the assistant continues on Groq (gpt-oss) for the rest of this session."),
    ).toBeInTheDocument()
  })
})

describe('header: which assistant answers (decision 0025)', () => {
  it('says when the demo assistant answers, in the UI language', async () => {
    stubFetch((url) => (url === '/api/health' ? jsonResponse({ status: 'ok', llm_provider: 'demo' }) : undefined), ...baseRoutes)
    renderWithProviders(<App />)
    expect(await screen.findByText('Assistant: demo (no AI)')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'ES' }))
    expect(screen.getByText('Asistente: demostración (sin IA)')).toBeInTheDocument()
  })

  it('shows nothing for a real model', async () => {
    stubFetch((url) => (url === '/api/health' ? jsonResponse({ status: 'ok', llm_provider: 'groq' }) : undefined), ...baseRoutes)
    renderWithProviders(<App />)
    await screen.findByRole('heading', { name: 'Create Design' })
    expect(screen.queryByText('Assistant: demo (no AI)')).not.toBeInTheDocument()
  })
})
