import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { WithRefs } from './components/ManualRef'
import { jsonResponse, renderWithProviders, stubFetch, user } from './test/helpers'

afterEach(() => vi.unstubAllGlobals())

describe('manual references (decision 0026)', () => {
  it('a citation in an answer opens its manual section', async () => {
    const calls = stubFetch((url) =>
      url === '/api/manual/en/02-revisions/skipped-letters'
        ? jsonResponse({ source: '02-revisions#skipped-letters', lang: 'en', document: '02 · Revisions', heading: 'Skipped letters', text: 'I, O, Q, S, X and Z are never used.' })
        : undefined,
    )
    renderWithProviders(<p><WithRefs text={'No: after H comes J [02‑revisions#skipped‑letters].'} /></p>)

    await user.click(screen.getByRole('button', { name: '[02-revisions#skipped-letters]' }))

    expect(await screen.findByRole('dialog', { name: 'Skipped letters' })).toHaveTextContent('I, O, Q, S, X and Z are never used.')
    expect(calls.map((c) => c.url)).toEqual(['/api/manual/en/02-revisions/skipped-letters'])
  })

  it('an unknown section says so', async () => {
    stubFetch((url) => (url.startsWith('/api/manual/') ? jsonResponse({ detail: 'No such manual section' }, 404) : undefined))
    renderWithProviders(<WithRefs text="[07-faq#nothing-here]" />)
    await user.click(screen.getByRole('button', { name: /07-faq#nothing-here/ }))
    expect(await screen.findByText('This section is not in the manual.')).toBeInTheDocument()
  })
})
