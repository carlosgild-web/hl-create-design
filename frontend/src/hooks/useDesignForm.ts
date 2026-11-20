import { useCallback, useEffect, useRef, useState } from 'react'

import { FORM_FIELDS, type FormField, type FormValues, type Issue, type ValueSource } from '@/api/types'

export const EMPTY_FORM: FormValues = { department: '', design_number: '', revision: '', name: '', designer: '' }

export type Created = { values: FormValues; design_number: string; revision: string }
type Snapshot = { values: FormValues; source: Partial<Record<FormField, ValueSource>> }

/**
 * The form's values and where each came from (decision 0017, block B):
 * - the assistant's proposals fill empty fields or fields it filled before, marked 'ai';
 *   a value the user typed (or SAP gave) is never overwritten: the proposal is kept as a
 *   suggestion the user can take;
 * - SAP values (a reserved number) are marked 'sap'; values the user typed have no mark.
 */
export function useDesignForm() {
  const [values, setValues] = useState<FormValues>(EMPTY_FORM)
  const [source, setSource] = useState<Partial<Record<FormField, ValueSource>>>({})
  const [suggestions, setSuggestions] = useState<Partial<Record<FormField, string>>>({})
  const [errors, setErrors] = useState<Issue[]>([])
  const [created, setCreated] = useState<Created | null>(null)
  const [undo, setUndo] = useState<Record<string, Snapshot>>({}) // by reservation action id

  const state = useRef({ values, source })
  useEffect(() => {
    state.current = { values, source }
  }, [values, source])

  /** The assistant's `propose_form_values`. */
  const propose = useCallback((fields: Partial<FormValues>) => {
    const { values: now, source: from } = state.current
    const take: Partial<FormValues> = {}
    const suggest: Partial<FormValues> = {}
    for (const f of FORM_FIELDS) {
      const value = fields[f]
      if (typeof value !== 'string' || !value.trim() || value === now[f]) continue
      if (!now[f].trim() || from[f] === 'ai') take[f] = value
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

  /** The user types: the value is theirs now. */
  const edit = useCallback((field: FormField, value: string) => {
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

  /** "New design": an empty form, nothing marked. */
  const reset = useCallback(() => {
    setValues(EMPTY_FORM)
    setSource({})
    setSuggestions({})
    setErrors([])
    setCreated(null)
  }, [])

  const sameAsCreated = created !== null && FORM_FIELDS.every((f) => created.values[f] === values[f])

  return {
    values,
    source,
    suggestions,
    errors,
    setErrors,
    created,
    sameAsCreated,
    canUndo: (actionId: string) => actionId in undo,
    propose,
    fillFromSap,
    undoFill,
    edit,
    takeSuggestion,
    markCreated,
    reset,
  }
}
