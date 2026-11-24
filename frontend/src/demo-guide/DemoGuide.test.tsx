import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders, user } from '@/test/helpers'

import { DemoGuide } from './DemoGuide'
import { guide } from './guide.config'

describe('DemoGuide', () => {
  it('shows the banner and opens the panel with the path and things to try', async () => {
    renderWithProviders(<DemoGuide />)

    expect(screen.getByText(guide.banner.en)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: guide.how.en }))

    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText(guide.panel.steps[1].title.en)).toBeInTheDocument()
    expect(within(panel).getByText(guide.panel.tries[0].en)).toBeInTheDocument()
    expect(within(panel).getByRole('link', { name: guide.panel.repo.en })).toHaveAttribute(
      'href',
      guide.repoUrl,
    )
  })

  it('closes the panel with Escape', async () => {
    renderWithProviders(<DemoGuide />)
    await user.click(screen.getByRole('button', { name: guide.how.en }))
    const panel = await screen.findByRole('dialog')

    fireEvent.keyDown(panel, { key: 'Escape' })

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('hides to a pill, remembers it, and the pill brings the guide back', async () => {
    const first = renderWithProviders(<DemoGuide />)
    await user.click(screen.getByRole('button', { name: guide.hide.en }))

    expect(screen.queryByText(guide.banner.en)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: guide.pill.en })).toBeInTheDocument()
    expect(localStorage.getItem(guide.storageKey)).toBe('pill')

    first.unmount()
    renderWithProviders(<DemoGuide />) // a reload: still a pill
    expect(screen.queryByText(guide.banner.en)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: guide.pill.en }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(localStorage.getItem(guide.storageKey)).toBe('open')
  })

  it('speaks Spanish', () => {
    renderWithProviders(<DemoGuide />, 'es')

    expect(screen.getByText(guide.banner.es)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: guide.how.es })).toBeInTheDocument()
  })
})
