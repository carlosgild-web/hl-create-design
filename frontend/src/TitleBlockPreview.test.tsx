import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { TitleBlockPreview } from './components/TitleBlockPreview'
import { renderWithProviders } from './test/helpers'

const DEPARTMENTS = [{ code: 'HW', name: 'Hardware Design' }]
const EMPTY = { department: '', design_number: '', revision: '', name: '', designer: '', description: '' }

describe('title block preview', () => {
  it('fills the drawing sheet cells from the form and SAP', () => {
    renderWithProviders(
      <TitleBlockPreview
        values={{
          department: 'HW',
          design_number: 'HL-HW-26-0003',
          revision: 'C',
          name: 'Bead Sorter Vision Board',
          designer: 'C. Velazquez',
          description: 'Camera board for the sorter',
        }}
        source={{ design_number: 'sap', designer: 'ai' }}
        departments={DEPARTMENTS}
        sap={{ material: '00040001177', wbs: 'P-26-0097' }}
      />,
    )

    expect(screen.getByRole('figure', { name: /^The title block KiCad prints/ })).toBeInTheDocument()
    const block = screen.getByTestId('title-block')
    for (const text of [
      'Bead Sorter Vision Board',
      'Camera board for the sorter',
      'HW – Hardware Design',
      'P-26-0097',
      '40001177', // without leading zeros, as the renderer writes it
      'C. Velazquez',
      'File: HL-HW-26-0003_C.kicad_sch',
    ]) {
      expect(within(block).getByText(text)).toBeInTheDocument()
    }
    // the legend names only the sources in use
    expect(screen.getByText('SAP')).toBeInTheDocument()
    expect(screen.getByText('Suggested')).toBeInTheDocument()
  })

  it('keeps empty cells and shows no legend before anything is filled', () => {
    renderWithProviders(<TitleBlockPreview values={EMPTY} source={{}} departments={DEPARTMENTS} />)

    const block = screen.getByTestId('title-block')
    expect(within(block).getByText('Design No.')).toBeInTheDocument()
    expect(within(block).getByText('File:')).toBeInTheDocument()
    expect(screen.queryByText('SAP')).not.toBeInTheDocument()
  })
})
