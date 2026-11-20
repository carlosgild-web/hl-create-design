import type { Department, FormField, FormValues } from '@/api/types'
import type { MessageKey } from '@/i18n'

/** The form field labels, also used on the confirmation cards. */
export const FIELD_LABELS: Record<FormField, MessageKey> = {
  department: 'form.department',
  design_number: 'form.design_number',
  revision: 'form.revision',
  name: 'form.name',
  designer: 'form.designer',
}

/** What each field expects, shown before anything is typed. */
export const FIELD_HINTS: Partial<Record<FormField, MessageKey>> = {
  design_number: 'hint.design_number',
  revision: 'hint.revision',
  name: 'hint.name',
  designer: 'hint.designer',
}

export const FIELD_PLACEHOLDERS: Partial<Record<FormField, string>> = {
  design_number: 'HL-HW-26-0042',
  revision: 'A',
  name: 'Bead Drill Controller',
  designer: 'C. Velazquez',
}

/** The department in the UI language: SAP's Spanish name in ES, else the English one. */
export function departmentName(d: Department, lang: string): string {
  return lang === 'es' && d.name_es ? d.name_es : d.name
}

// The design number format (01-design-numbering#format). Used only for typing hints:
// the backend's validators decide.
const PREFIX_ONLY = /^HL-[A-Z]{2,3}-\d{2}-$/
const PARTIAL = /^HL-[A-Z]{2,3}-\d{2}-(\d{0,4})$/
const FULL = /^HL-(HW|PWR|EMB|TFX)-\d{2}-\d{4}$/

/** `HL-HW-26-`: pre-filled from the department, nothing typed yet. */
export const isPrefixOnly = (value: string) => PREFIX_ONLY.test(value.trim())

/** A field counts as filled when it has a real value (a bare number prefix does not). */
export const isFilled = (field: FormField, value: string) =>
  Boolean(value.trim()) && !(field === 'design_number' && isPrefixOnly(value))

/** The values to check, store or send: without a bare number prefix. */
export function filledValues(values: FormValues): Partial<FormValues> {
  return Object.fromEntries(
    (Object.keys(values) as FormField[]).filter((f) => isFilled(f, values[f])).map((f) => [f, values[f]]),
  )
}

/** While typing a design number: how many digits are still missing, or done. */
export function numberProgress(value: string): { missing: number } | { complete: true } | null {
  const v = value.trim().toUpperCase()
  if (FULL.test(v)) return { complete: true }
  const partial = PARTIAL.exec(v)
  return partial ? { missing: 4 - partial[1].length } : null
}
