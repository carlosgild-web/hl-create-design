import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { baseRoutes, jsonResponse, openStream, renderWithProviders, sseResponse, stubFetch, user } from './test/helpers'

afterEach(() => vi.unstubAllGlobals())

async function startGuided() {
  await user.click(screen.getByRole('button', { name: 'Guide me step by step' }))
}

describe('assistant progress (decision 0017)', () => {
  it('says what it is doing: a tool, then a rate-limit wait', async () => {
    const stream = openStream([
      ['conversation', { id: 'c1' }],
      ['run', { id: 5 }],
      ['tool_call', { id: 't1', name: 'search_design_manual', arguments: { query: 'rev' } }],
    ])
    stubFetch((url) => (url === '/api/chat' ? stream.response : undefined), ...baseRoutes)
    renderWithProviders(<App />)
    await startGuided()

    expect(await screen.findByText('Searching the Design Manual…')).toBeInTheDocument()

    stream.send([['status', { kind: 'rate_limited', wait_s: 41.2, provider: 'groq', scope: 'minute' }]])
    expect(await screen.findByText('Waiting for the Groq rate limit (about 42 s)…')).toBeInTheDocument()

    stream.send([
      ['message', { role: 'assistant', content: 'Which department?' }],
      ['done', { conversation_id: 'c1', run_id: 5, status: 'answered' }],
    ])
    stream.close()
    expect(await screen.findByText('Which department?')).toBeInTheDocument()
    expect(screen.queryByText(/Waiting for the Groq/)).not.toBeInTheDocument()
  })

  it('Stop cancels the run and says Stopped', async () => {
    const stream = openStream([
      ['conversation', { id: 'c1' }],
      ['run', { id: 6 }],
    ])
    const calls = stubFetch(
      (url) => (url === '/api/chat' ? stream.response : undefined),
      (url) => {
        if (url !== '/api/runs/6/cancel') return undefined
        stream.send([['done', { conversation_id: 'c1', run_id: 6, status: 'cancelled' }]])
        stream.close()
        return jsonResponse({ id: 6, cancelling: true })
      },
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await startGuided()

    await user.click(await screen.findByRole('button', { name: 'Stop' }))

    expect(await screen.findByText('Stopped. Nothing more was done.')).toBeInTheDocument()
    expect(calls.some((c) => c.url === '/api/runs/6/cancel' && c.init?.method === 'POST')).toBe(true)
    expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument()
  })

  it('a stuck turn offers to switch, and switching says so', async () => {
    const calls = stubFetch(
      (url) =>
        url === '/api/chat'
          ? sseResponse([
              ['conversation', { id: 'c1' }],
              ['run', { id: 7 }],
              ['error', { code: 'turn_timeout', message: 'x', timeout_s: 120, can_switch_to: ['ollama', 'fake'] }],
              ['done', { conversation_id: 'c1', run_id: 7, status: 'timeout' }],
            ])
          : undefined,
      (url) => (url === '/api/llm/switch' ? jsonResponse({ provider: 'ollama', model: 'qwen3' }) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await startGuided()

    expect(await screen.findByText(/did not answer within 120 s/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Switch to Ollama (local)' }))

    expect(await screen.findByText('From now on the assistant answers with Ollama (qwen3).')).toBeInTheDocument()
    const body = calls.find((c) => c.url === '/api/llm/switch')?.init?.body
    expect(JSON.parse(String(body))).toEqual({ to: 'ollama' })
    expect(screen.getByRole('button', { name: 'Use the demo model' })).toBeInTheDocument()
  })

  it('New conversation clears the chat and starts a new one', async () => {
    const calls = stubFetch(
      (url) =>
        url === '/api/chat'
          ? sseResponse([
              ['conversation', { id: 'c1' }],
              ['message', { role: 'assistant', content: 'Which department?' }],
              ['done', { conversation_id: 'c1', run_id: 8, status: 'answered' }],
            ])
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await startGuided()
    expect(await screen.findByText('Which department?')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'New conversation' }))

    expect(screen.queryByText('Which department?')).not.toBeInTheDocument()
    await startGuided()
    await waitFor(() => expect(calls.filter((c) => c.url === '/api/chat')).toHaveLength(2))
    const second = JSON.parse(String(calls.filter((c) => c.url === '/api/chat')[1].init?.body))
    expect(second.conversation_id).toBeNull()
  })
})
