import { describe, expect, it } from 'vitest'

import { issueText } from './issues'

const skipped = {
  code: 'rev_skipped_letter',
  message: 'The letters I, O, Q, S, X and Z are never used (I in "I"). The next free revision is J.',
  params: { letters: 'I', value: 'I', expected: 'J' },
}

describe('issueText', () => {
  it('renders the code in the UI language with its params', () => {
    expect(issueText('es', skipped)).toBe(
      'Las letras I, O, Q, S, X y Z no se usan nunca (I en «I»). La siguiente revisión libre es J.',
    )
    expect(issueText('en', skipped)).toContain('The next free revision is J.')
  })

  it('uses the variant template when the params name one', () => {
    const blocked = {
      code: 'status_blocked',
      message: 'english',
      params: { variant: 'reason', reason: 'Field returns' },
    }
    expect(issueText('es', blocked)).toContain('Motivo en SAP: Field returns.')
    expect(issueText('es', { code: 'status_blocked', message: 'english' })).not.toContain('Motivo')
  })

  it('falls back to the English message for an unknown code or a missing code', () => {
    expect(issueText('es', { code: 'something_new', message: 'Plain English.' })).toBe('Plain English.')
    expect(issueText('es', { message: 'No code.' })).toBe('No code.')
  })
})

describe('normalizeRefs', () => {
  it('turns unicode dashes and spaced brackets into the manual form', async () => {
    const { normalizeRefs } = await import('./issues')
    expect(normalizeRefs('see [02‑revisions#skipped‑letters] and [ 07-faq # assistant ]')).toBe(
      'see [02-revisions#skipped-letters] and [07-faq#assistant]',
    )
  })
})
