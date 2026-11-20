import { useCallback, useEffect, useRef, useState } from 'react'

import {
  FORM_FIELDS,
  type FormField,
  type FormMode,
  type FormValues,
  type Issue,
  type SapListDesign,
  type ValueSource,
} from '@/api/types'
import { isFilled } from '@/lib/fields'

export const EMPTY_FORM: FormValues = { department: '', design_number: '', revision: '', name: '', designer: '' }

/** The empty form of a mode: a new design always starts at revision A (decision 0018). */
export const emptyFor = (mode: FormMode, designer = ''): FormValues => ({
  ...EMPTY_FORM,
  revision: mode === 'new' ? 'A' : '',
  designer,
})

/** Fields the user can't type in this mode: SAP sets them (decision 0018, Q1/Q2/Q4). */
export const LOCKED: Record<FormMode, ReadonlySet<FormField>> = {
  new: new Set<FormField>(['design_number', 'revision']),
  existing: new Set<FormField>(['department', 'design_number', 'revision', 'name']),
}

export type Created = { values: FormValues; design_number: string; revision: string }
type Snapshot = { values: FormValues; source: Partial<Record<FormField, ValueSource>> }

/**
 * The form's values, where each came from and how the form is used:
 * - mode `new`: SAP issues the number (Get SAP number); the user fills department, name and
 *   designer; revision A.
 * - mode `existing`: a design picked from SAP's list sets department, number, name and the
 *   next free revision; only the designer is typed.
 * - the assistant's proposals fill empty or AI-filled fields, never a value the user typed
 *   (kept as a suggestion) and never a locked field.
 */
export function useDesignForm() {
  const [mode, setModeState] = useState<FormMode>('new')
  const [values, setValues] = useState<FormValues>(() => emptyFor('new'))
  const [source, setSource] = useState<Partial<Record<FormField, ValueSource>>>({})
  const [suggestions, setSuggestions] = useState<Partial<Record<FormField, string>>>({})
  const [errors, setErrors] = useState<Issue[]>([])
  const [created, setCreated] = useState<Created | null>(null)
  const [selected, setSelected] = useState<SapListDesign | null>(null)
  const [undo, setUndo] = useState<Record<string, Snapshot>>({}) // by reservation action id

  const state = useRef({ values, source, mode })
  useEffect(() => {
    state.current = { values, source, mode }
  }, [values, source, mode])

  /** Start over in `next` mode; the designer is the user's in both modes and stays. */
  const startOver = useCallback((next: FormMode) => {
    setModeState(next)
    setValues(emptyFor(next, state.current.values.designer))
    setSource({})
    setSuggestions({})
    setErrors([])
    setCreated(null)
    setSelected(null)
  }, [])

  /** The assistant's `propose_form_values`. */
  const propose = useCallback((fields: Partial<FormValues>) => {
    const { values: now, source: from, mode: current } = state.current
    const take: Partial<FormValues> = {}
    const suggest: Partial<FormValues> = {}
    for (const f of FORM_FIELDS) {
      const value = fields[f]
      if (typeof value !== 'string' || !value.trim() || value === now[f] || LOCKED[current].has(f)) continue
      if (!isFilled(f, now[f]) || from[f] === 'ai') take[f] = value
      else suggest[f] = value
    }
    const taken = Object.keys(take) as FormField[]
    if (taken.length) {
      setValues((v) => ({ ...v, ...take }))
      setSource((s) => ({ ...s, ...Object.fromEntries(taken.map((f) => [f, 'ai'])) }))
    }
    setSuggestions((s) => {
      const next = { ...s, ...suggest }
      for (const f of taken) delete next[f]
      return next
    })
  }, [])

  /** A design picked in the Start panel's list: SAP sets everything but the designer. */
  const selectExisting = useCallback((design: SapListDesign) => {
    setModeState('existing')
    setSelected(design)
    setValues({
      department: design.department,
      design_number: design.design_number,
      revision: design.next_free_revision,
      name: design.name,
      designer: state.current.values.designer,
    })
    setSource({ department: 'sap', design_number: 'sap', revision: 'sap', name: 'sap' })
    setSuggestions({})
    setErrors([])
    setCreated(null)
  }, [])

  /** A reservation was confirmed: fill its number from SAP; keep what was there for Undo. */
  const fillFromSap = useCallback((actionId: string, fields: Partial<FormValues>) => {
    const keys = FORM_FIELDS.filter((f) => fields[f] && fields[f] !== state.current.values[f])
    setUndo((u) => ({ ...u, [actionId]: { values: state.current.values, source: state.current.source } }))
    setValues((v) => ({ ...v, ...fields }))
    setSource((s) => ({ ...s, ...Object.fromEntries(keys.map((f) => [f, 'sap'])) }))
    setSuggestions((s) => Object.fromEntries(Object.entries(s).filter(([f]) => !keys.includes(f as FormField))))
  }, [])

  const undoFill = useCallback(
    (actionId: string) => {
      const snapshot = undo[actionId]
      if (!snapshot) return
      setValues(snapshot.values)
      setSource(snapshot.source)
      setUndo((u) => Object.fromEntries(Object.entries(u).filter(([id]) => id !== actionId)))
    },
    [undo],
  )

  /** The user types: the value is theirs now. Locked fields don't change. */
  const edit = useCallback((field: FormField, value: string) => {
    if (LOCKED[state.current.mode].has(field)) return
    setValues((v) => ({ ...v, [field]: value }))
    setSource((s) => Object.fromEntries(Object.entries(s).filter(([f]) => f !== field)))
    setSuggestions((s) => Object.fromEntries(Object.entries(s).filter(([f]) => f !== field)))
    setErrors((all) => all.filter((e) => e.field !== field))
  }, [])

  const takeSuggestion = useCallback(
    (field: FormField) => {
      const value = suggestions[field]
      if (value === undefined) return
      setValues((v) => ({ ...v, [field]: value }))
      setSource((s) => ({ ...s, [field]: 'ai' }))
      setSuggestions((s) => Object.fromEntries(Object.entries(s).filter(([f]) => f !== field)))
    },
    [suggestions],
  )

  const markCreated = useCallback((design_number: string, revision: string) => {
    setCreated({ values: state.current.values, design_number, revision })
  }, [])

  /** "New design" after a creation: the same mode as last time, empty but the designer. */
  const reset = useCallback(() => startOver(state.current.mode), [startOver])

  const sameAsCreated = created !== null && FORM_FIELDS.every((f) => created.values[f] === values[f])

  return {
    mode,
    values,
    source,
    suggestions,
    errors,
    setErrors,
    created,
    sameAsCreated,
    selected,
    canUndo: (actionId: string) => actionId in undo,
    locked: (field: FormField) => LOCKED[mode].has(field),
    startOver,
    propose,
    selectExisting,
    fillFromSap,
    undoFill,
    edit,
    takeSuggestion,
    markCreated,
    reset,
  }
}
