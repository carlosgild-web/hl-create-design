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

describe('layout (decision 0017, block D)', () => {
  it('on a phone: tabs, the chat opens when you send, and a badge counts waiting cards', async () => {
    phone()
    stubFetch(cardStream, ...baseRoutes)
    renderWithProviders(<App />)

    const tabs = screen.getByRole('tablist', { name: 'Sections' })
    expect(within(tabs).getByRole('tab', { name: 'Form' })).toHaveAttribute('aria-selected', 'true')

    pick(within(tabs).getByRole('tab', { name: /Assistant/ }))
    await user.click(screen.getByRole('button', { name: 'Guide me step by step' }))
    expect(await screen.findByText('Please confirm.')).toBeInTheDocument()

    // back to the form: the Assistant tab shows that a card waits
    pick(within(tabs).getByRole('tab', { name: 'Form' }))
    expect(within(tabs).getByRole('tab', { name: /Assistant/ })).toHaveAttribute('aria-selected', 'false')
    expect(within(tabs).getByLabelText('1 card(s) waiting for you')).toBeInTheDocument()
  })

  it('on a desktop: preview and recent designs share tabs next to the form', async () => {
    stubFetch(
      (url) =>
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
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    const tabs = screen.getByRole('tablist', { name: 'Preview or recent designs' })
    expect(within(tabs).getByRole('tab', { name: 'Recent designs' })).toHaveAttribute('aria-selected', 'true')

    await user.click(await screen.findByRole('button', { name: /HL-HW-26-0042 C/ }))

    expect(within(tabs).getByRole('tab', { name: 'Preview' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByRole('img', { name: /Title block of HL-HW-26-0042 rev C/ })).toBeInTheDocument()
  })
})
