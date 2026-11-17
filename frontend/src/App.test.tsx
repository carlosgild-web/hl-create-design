import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  )
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the title and the backend status from /api/health', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: 'ok', version: '0.1.0', llm_provider: 'fake' })),
      ),
    )

    renderApp()

    expect(screen.getByRole('heading', { name: 'Create Design' })).toBeInTheDocument()
    expect(await screen.findByText('ok (v0.1.0, LLM: fake)')).toBeInTheDocument()
  })

  it('says when the backend is not reachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 502 })))

    renderApp()

    expect(await screen.findByText('not reachable')).toBeInTheDocument()
  })
})
