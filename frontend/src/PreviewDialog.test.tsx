import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { PreviewDialog } from './components/PreviewDialog'
import App from './App'
import { baseRoutes, jsonResponse, renderWithProviders, stubFetch, user } from './test/helpers'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

const TARGET = { department: 'HW', design_number: 'HL-HW-26-0042', revision: 'C', name: 'Bead Drill Controller' }

describe('preview dialog (decision 0018)', () => {
  it('shows the header, the image, Open and Download PDF', () => {
    stubFetch(...baseRoutes)
    renderWithProviders(<PreviewDialog target={TARGET} onClose={() => {}} />)

    const dialog = screen.getByRole('dialog', { name: 'HL-HW-26-0042 · rev C · Bead Drill Controller' })
    expect(dialog).toHaveAccessibleDescription(/HW · HW\/HL-HW-26-0042\/C/)
    expect(within(dialog).getByRole('img', { name: /Title block of HL-HW-26-0042 rev C/ })).toHaveAttribute(
      'src',
      '/api/designs/HW/HL-HW-26-0042/C/preview.svg',
    )
    const download = within(dialog).getByRole('link', { name: 'Download PDF' })
    expect(download).toHaveAttribute('href', '/api/designs/HW/HL-HW-26-0042/C/preview.pdf')
    expect(download).toHaveAttribute('download', 'HL-HW-26-0042_C.pdf')
    expect(within(dialog).getByRole('link', { name: 'Open PDF' })).toHaveAttribute('target', '_blank')
  })

  it('a missing preview says so (404)', async () => {
    stubFetch((url) => (url.endsWith('preview.svg') ? new Response('', { status: 404 }) : undefined), ...baseRoutes)
    renderWithProviders(<PreviewDialog target={TARGET} onClose={() => {}} />)

    fireEvent.error(screen.getByRole('img'))

    expect(await screen.findByText('No preview for this design.')).toBeInTheDocument()
  })

  it('another failure offers Retry', async () => {
    stubFetch((url) => (url.endsWith('preview.svg') ? new Response('', { status: 500 }) : undefined), ...baseRoutes)
    renderWithProviders(<PreviewDialog target={TARGET} onClose={() => {}} />)

    fireEvent.error(screen.getByRole('img'))
    await user.click(await screen.findByRole('button', { name: 'Retry' }))

    expect(screen.getByRole('img')).toHaveAttribute('src', '/api/designs/HW/HL-HW-26-0042/C/preview.svg?retry=1')
  })

  it('Esc closes it and focus returns to the button that opened it', async () => {
    stubFetch(
      (url) =>
        url === '/api/designs'
          ? jsonResponse([{ ...TARGET, designer: 'C. Velazquez', pdf: true, created_at: '2026-11-17T10:00:00Z' }])
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<App />)
    await user.click(await screen.findByRole('button', { name: 'Recent designs (1)' }))
    const opener = await screen.findByRole('button', { name: 'Preview HL-HW-26-0042 rev C' })
    opener.focus()
    await user.click(opener)

    const dialog = await screen.findByRole('dialog')
    fireEvent.keyDown(dialog, { key: 'Escape' })

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(opener).toHaveFocus())
  })
})
