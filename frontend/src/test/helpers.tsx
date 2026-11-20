import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { vi } from 'vitest'

import type { Action } from '@/api/types'
import { I18nProvider, type Lang } from '@/i18n'

export function renderWithProviders(ui: ReactElement, lang: Lang = 'en') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <I18nProvider lang={lang}>{ui}</I18nProvider>
    </QueryClientProvider>,
  )
}

export function sseBody(events: [string, unknown][]): string {
  return events.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`).join('')
}

export function sseResponse(events: [string, unknown][]): Response {
  return new Response(sseBody(events), { headers: { 'Content-Type': 'text/event-stream' } })
}

/** A chat stream that stays open: `send` more events, then `close`. For Stop and progress. */
export function openStream(first: [string, unknown][]) {
  let controller!: ReadableStreamDefaultController<Uint8Array>
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c
      c.enqueue(encoder.encode(sseBody(first)))
    },
  })
  return {
    response: new Response(body, { headers: { 'Content-Type': 'text/event-stream' } }),
    send: (events: [string, unknown][]) => controller.enqueue(encoder.encode(sseBody(events))),
    close: () => controller.close(),
  }
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function makeAction(overrides: Partial<Action> = {}): Action {
  return {
    id: 'a1',
    conversation_id: 'c1',
    kind: 'create_design',
    payload: {
      department: 'HW',
      design_number: 'HL-HW-26-0042',
      revision: 'C',
      name: 'Bead Drill Controller',
      designer: 'C. Velazquez',
    },
    status: 'pending',
    created_at: '2026-11-17T10:00:00Z',
    expires_at: '2026-11-17T10:30:00Z',
    decided_at: null,
    result: {},
    ...overrides,
  }
}

type Route = (url: string, init?: RequestInit) => Response | Promise<Response> | undefined

/** A fetch stub: the first route that answers wins; unknown URLs fail the test. */
export function stubFetch(...routes: Route[]) {
  const calls: { url: string; init?: RequestInit }[] = []
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    calls.push({ url, init })
    for (const route of routes) {
      const response = await route(url, init)
      if (response) return response
    }
    throw new Error(`Unexpected fetch ${init?.method ?? 'GET'} ${url}`)
  })
  vi.stubGlobal('fetch', fn)
  return calls
}

export const baseRoutes: Route[] = [
  (url) =>
    url === '/api/departments'
      ? jsonResponse([
          { code: 'HW', name: 'Hardware Design' },
          { code: 'PWR', name: 'Power Electronics' },
        ])
      : undefined,
  (url) => (url === '/api/designs' ? jsonResponse([]) : undefined),
  (url) =>
    url === '/api/validate' ? jsonResponse({ ok: true, normalized: {}, errors: [], warnings: [] }) : undefined,
]

/** The few user gestures the tests need, without an extra dependency. */
export const user = {
  type: async (el: HTMLElement, text: string) =>
    fireEvent.change(el, { target: { value: (el as HTMLInputElement).value + text } }),
  selectOptions: async (el: HTMLElement, value: string) =>
    fireEvent.change(el, { target: { value } }),
  click: async (el: HTMLElement) => fireEvent.click(el),
}
