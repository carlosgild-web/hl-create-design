import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { InlineMarkdown, ManualText } from './ManualText'

const NUMBERING =
  '- **New revision, same number:** you change the same design (a fix, a component change,\n' +
  '  a layout change). See [02-revisions](02-revisions.md).\n' +
  '- **New number:** the design goes to `OBSOLETE`.'

const SKIPPED =
  'The letters **I, O and Q are never used**, in capitals.\n\n' +
  '| Letter | Mistaken for |\n|---|---|\n| `I` | the digit `1` |\n| `O` | the digit `0` |\n\n' +
  'So after `H` comes `J`.'

describe('ManualText', () => {
  it('renders a list with wrapped lines, bold, code and links as text', () => {
    const { container } = render(<ManualText text={NUMBERING} />)

    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent(
      'New revision, same number: you change the same design (a fix, a component change, a layout change). See 02-revisions.',
    )
    expect(screen.getByText('New revision, same number:').tagName).toBe('STRONG')
    expect(screen.getByText('OBSOLETE').tagName).toBe('CODE')
    expect(container.textContent).not.toMatch(/\*\*|`|\]\(/)
  })

  it('renders a table without its separator row', () => {
    render(<ManualText text={SKIPPED} />)

    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Letter', 'Mistaken for'])
    expect(screen.getAllByRole('row')).toHaveLength(3)
    expect(screen.getByText('I, O and Q are never used').tagName).toBe('STRONG')
  })

  it('keeps markup in a passage as text', () => {
    render(<ManualText text={'<img src=x onerror="alert(1)"> plain'} />)

    expect(screen.getByText('<img src=x onerror="alert(1)"> plain')).toBeInTheDocument()
    expect(screen.queryByRole('img')).toBeNull()
  })

  it('renders a numbered list and keeps paragraphs apart', () => {
    const { container } = render(<ManualText text={'Two steps:\n\n1. one\n2. two'} />)

    expect(container.querySelector('ol')?.children).toHaveLength(2)
    expect(container.querySelectorAll('p')).toHaveLength(1)
  })
})

describe('InlineMarkdown in a chat answer', () => {
  it('shows **bold** and `code` without the marks', () => {
    render(
      <p>
        <InlineMarkdown text={'Confirm the card for **Bead Threader Controller**; after `H` comes `J`.'} />
      </p>,
    )
    expect(screen.getByText('Bead Threader Controller').tagName).toBe('STRONG')
    expect(screen.getByText('H').tagName).toBe('CODE')
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument()
  })
})
