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

const sapDesign = (over: Record<string, unknown>) => ({
  department: 'HW',
  material: '000000000040001234',
  wbs: 'P-26-0108',
  block_reason: '',
  successor: '',
  selectable: true,
  ...over,
})

/** `GET /api/sap/designs` like the backend with the fake SAP of the backend tests. */
export const SAP_DESIGNS = [
  sapDesign({ design_number: 'HL-EMB-23-0002', department: 'EMB', name: 'Sensor Hub', status: 'OBSOLETE', revisions: ['A'], current_revision: 'A', next_free_revision: 'B', successor: 'HL-EMB-25-0011', selectable: false }),
  sapDesign({ design_number: 'HL-EMB-25-0011', department: 'EMB', name: 'Sensor Hub II', status: 'RELEASED', revisions: ['A'], current_revision: 'A', next_free_revision: 'B' }),
  sapDesign({ design_number: 'HL-HW-24-0003', name: 'Old Led Panel', status: 'BLOCKED', revisions: ['A', 'B'], current_revision: 'B', next_free_revision: 'C', block_reason: 'Supplier part discontinued', selectable: false }),
  sapDesign({ design_number: 'HL-HW-26-0042', name: 'Bead Drill Controller', status: 'IN_WORK', revisions: ['A', 'B'], current_revision: 'B', next_free_revision: 'C' }),
]

export const baseRoutes: Route[] = [
  (url) => (url === '/api/sap/designs' ? jsonResponse(SAP_DESIGNS) : undefined),
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
