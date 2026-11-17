import type { FormValues } from '@/api/types'

/** The folder the design would go to, shown for information (the backend decides). */
export function folderPreview({ department, design_number, revision }: FormValues) {
  return department && design_number && revision ? `${department}/${design_number}/${revision}` : ''
}
