import { fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { baseRoutes, jsonResponse, makeAction, renderWithProviders, sseResponse, stubFetch, user } from './test/helpers'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

/** Radix tabs switch on mouse-down (a plain click does not). */
const pick = (tab: HTMLElement) => fireEvent.mouseDown(tab, { button: 0, ctrlKey: false })

/** A phone: `(min-width: 1024px)` does not match. */
function phone() {
  vi.stubGlobal(
    'matchMedia',
    (query: string) =>
      ({ matches: false, media: query, addEventListener: () => {}, removeEventListener: () => {} }) as unknown as MediaQueryList,
  )
}

const cardStream = (url: string) =>
  url === '/api/chat'
    ? sseResponse([
        ['conversation', { id: 'c1' }],
        ['pending_action', { action: makeAction() }],
        ['message', { role: 'assistant', content: 'Please confirm.' }],
        ['done', { status: 'answered' }],
      ])
    : undefined

const RECENT = (url: string) =>
  url === '/api/designs'
    ? jsonResponse([
        {
          design_number: 'HL-HW-26-0042',
          revision: 'C',
          name: 'Bead Drill Controller',
          department: 'HW',
          designer: 'C. Velazquez',
          pdf: true,
          created_at: '2026-11-17T10:00:00Z',
        },
      ])
    : undefined

describe('layout (decisions 0017 D and 0018)', () => {
  it('on a phone: Design | Assistant | Recent, the chat opens when you send, a badge counts cards', async () => {
    phone()
    stubFetch(cardStream, ...baseRoutes)
    renderWithProviders(<App />)

    const tabs = screen.getByRole('tablist', { name: 'Sections' })
    expect(within(tabs).getAllByRole('tab').map((t) => t.textContent)).toEqual(['Design', 'Assistant', 'Recent designs'])
    expect(within(tabs).getByRole('tab', { name: 'Design' })).toHaveAttribute('aria-selected', 'true')
    // the Design tab: the Start panel's choice, then the form
    expect(screen.getByRole('radiogroup', { name: 'What do you want to create?' })).toBeInTheDocument()

    pick(within(tabs).getByRole('tab', { name: /Assistant/ }))
    await user.click(screen.getByRole('button', { name: 'Guide me step by step' }))
    expect(await screen.findByText('Please confirm.')).toBeInTheDocument()

    pick(within(tabs).getByRole('tab', { name: 'Design' }))
    expect(within(tabs).getByRole('tab', { name: /Assistant/ })).toHaveAttribute('aria-selected', 'false')
    expect(within(tabs).getByLabelText('1 card(s) waiting for you')).toBeInTheDocument()
  })

  it('on a desktop: Start panel with the recent designs, which open the preview dialog', async () => {
    stubFetch(RECENT, ...baseRoutes)
    renderWithProviders(<App />)
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()

    await user.click(await screen.findByRole('button', { name: 'Recent designs (1)' }))
    await user.click(await screen.findByRole('button', { name: 'Preview HL-HW-26-0042 rev C' }))

    const dialog = await screen.findByRole('dialog', { name: /HL-HW-26-0042 · rev C · Bead Drill Controller/ })
    expect(within(dialog).getByRole('img', { name: /Title block of HL-HW-26-0042 rev C/ })).toBeInTheDocument()
  })
})
