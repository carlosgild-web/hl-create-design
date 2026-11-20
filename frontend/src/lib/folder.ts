import type { FormValues } from '@/api/types'
import { isPrefixOnly } from '@/lib/fields'

/** The folder the design would go to, shown for information (the backend decides). */
export function folderPreview({ department, design_number, revision }: FormValues) {
  return department && design_number && !isPrefixOnly(design_number) && revision
    ? `${department}/${design_number}/${revision}`
    : ''
}
