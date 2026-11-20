import type { Department, FormField } from '@/api/types'
import type { MessageKey } from '@/i18n'

/** The form field labels, also used on the confirmation cards. */
export const FIELD_LABELS: Record<FormField, MessageKey> = {
  department: 'form.department',
  design_number: 'form.design_number',
  revision: 'form.revision',
  name: 'form.name',
  designer: 'form.designer',
}

/** The department in the UI language: SAP's Spanish name in ES, else the English one. */
export function departmentName(d: Department, lang: string): string {
  return lang === 'es' && d.name_es ? d.name_es : d.name
}
