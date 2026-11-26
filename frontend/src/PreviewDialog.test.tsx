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

  it('opens the project in KiCad, offers the zip and the path to copy (decision 0019)', async () => {
    const PRO = 'C:\\designs\\HW\\HL-HW-26-0042\\C\\HL-HW-26-0042_C.kicad_pro'
    const calls = stubFetch(
      (url) =>
        url.endsWith('/files') ? jsonResponse({ folder: 'C:\\designs', project_file: PRO, can_open: true }) : undefined,
      (url, init) => (url.endsWith('/open') && init?.method === 'POST' ? jsonResponse({ ok: true }) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<PreviewDialog target={TARGET} onClose={() => {}} />)
    const dialog = screen.getByRole('dialog')

    expect(await within(dialog).findByText(PRO)).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Copy path' })).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: 'Download project (.zip)' })).toHaveAttribute(
      'href',
      '/api/designs/HW/HL-HW-26-0042/C/project.zip',
    )

    await user.click(within(dialog).getByRole('button', { name: 'Open in KiCad' }))

    expect(await within(dialog).findByText(/schematic editor is opening with the design/)).toBeInTheDocument()
    expect(calls.some((c) => c.url === '/api/designs/HW/HL-HW-26-0042/C/open')).toBe(true)
  })

  it('no Open in KiCad where the server cannot start it (Docker)', async () => {
    stubFetch(
      (url) => (url.endsWith('/files') ? jsonResponse({ folder: '/data', project_file: '/data/x.kicad_pro', can_open: false }) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<PreviewDialog target={TARGET} onClose={() => {}} />)

    expect(await screen.findByText('/data/x.kicad_pro')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Open in KiCad' })).not.toBeInTheDocument()
  })

  it('switches to the PCB view, with its own image and PDF (decision 0033)', async () => {
    stubFetch(
      (url) =>
        url.endsWith('/files')
          ? jsonResponse({ folder: '/d', project_file: '/d/x.kicad_pro', can_open: false, has_pcb_preview: true })
          : undefined,
      ...baseRoutes,
    )
    renderWithProviders(<PreviewDialog target={TARGET} onClose={() => {}} />)
    const dialog = screen.getByRole('dialog')

    await user.click(await within(dialog).findByRole('button', { name: 'PCB' }))

    expect(within(dialog).getByRole('button', { name: 'PCB' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(dialog).getByRole('img', { name: /PCB title block of HL-HW-26-0042 rev C/ })).toHaveAttribute(
      'src',
      '/api/designs/HW/HL-HW-26-0042/C/pcb.svg',
    )
    const download = within(dialog).getByRole('link', { name: 'Download PDF' })
    expect(download).toHaveAttribute('href', '/api/designs/HW/HL-HW-26-0042/C/pcb.pdf')
    expect(download).toHaveAttribute('download', 'HL-HW-26-0042_C_pcb.pdf')

    await user.click(within(dialog).getByRole('button', { name: 'Schematic' }))
    expect(within(dialog).getByRole('img')).toHaveAttribute('src', '/api/designs/HW/HL-HW-26-0042/C/preview.svg')
  })

  it('no PCB switch for a design without a board', async () => {
    stubFetch(
      (url) => (url.endsWith('/files') ? jsonResponse({ folder: '/d', project_file: '/d/x.kicad_pro', can_open: true }) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<PreviewDialog target={TARGET} onClose={() => {}} />)

    expect(await screen.findByRole('button', { name: 'Open in KiCad' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'PCB' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Open PCB' })).not.toBeInTheDocument()
  })

  it('Open PCB starts the PCB editor', async () => {
    const calls = stubFetch(
      (url) =>
        url.endsWith('/files')
          ? jsonResponse({ folder: '/d', project_file: '/d/x.kicad_pro', can_open: true, can_open_pcb: true })
          : undefined,
      (url, init) => (url.includes('/open') && init?.method === 'POST' ? jsonResponse({ ok: true }) : undefined),
      ...baseRoutes,
    )
    renderWithProviders(<PreviewDialog target={TARGET} onClose={() => {}} />)

    await user.click(await screen.findByRole('button', { name: 'Open PCB' }))

    expect(await screen.findByText(/PCB editor is opening with the board/)).toBeInTheDocument()
    expect(calls.some((c) => c.url === '/api/designs/HW/HL-HW-26-0042/C/open?target=pcb')).toBe(true)
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
