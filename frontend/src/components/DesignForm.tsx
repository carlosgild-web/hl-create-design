import { CheckCircle2, Lock, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type * as React from 'react'

import {
  DESCRIPTION_MAX,
  REQUIRED_FIELDS,
  type Department,
  type FormField,
  type FormMode,
  type FormValues,
  type Issue,
  type Validation,
  type ValueSource,
} from '@/api/types'
import { FormStepper } from '@/components/FormStepper'
import { TitleBlockPreview } from '@/components/TitleBlockPreview'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { Created } from '@/hooks/useDesignForm'
import { useI18n } from '@/i18n'
import { blockers, departmentName, FIELD_LABELS, FIELD_PLACEHOLDERS, isFilled } from '@/lib/fields'
import { folderPreview } from '@/lib/folder'
import { issueText } from '@/lib/issues'
import { cn } from '@/lib/utils'

type Props = {
  mode: FormMode
  /** Fields SAP sets in this mode: shown read-only (decision 0018). */
  locked: (field: FormField) => boolean
  values: FormValues
  source: Partial<Record<FormField, ValueSource>>
  suggestions: Partial<Record<FormField, string>>
  errors: Issue[]
  validation?: Validation
  /** The inline check for the current values hasn't answered yet (debounce or request). */
  checking?: boolean
  created: Created | null
  sameAsCreated: boolean
  departments: Department[]
  /** The designer of the most recent design, offered for an empty Designer field. */
  lastDesigner?: string
  busy: boolean
  /** A card for exactly these values is waiting in the chat: Create shows it. */
  cardWaiting?: boolean
  /** New design without a number: Get SAP number next to Create. */
  canReserve?: boolean
  onReserve?: () => void
  onChange: (field: FormField, value: string) => void
  onTakeSuggestion: (field: FormField) => void
  onCreate: () => void
  onNewDesign: () => void
  className?: string
}

const fieldClass =
  'h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive dark:bg-input/30'

/** Two columns: Department | Design number, Revision | Designer, then name and description across. */
const LAYOUT: FormField[] = ['department', 'design_number', 'revision', 'designer', 'name', 'description']
const WIDE: ReadonlySet<FormField> = new Set(['name', 'description'])

const RING: Record<ValueSource, string> = { ai: 'ring-2 ring-hl-amber', sap: 'ring-2 ring-hl-sea' }

/** Errors of the latest check for this field, plus those of a refused card, once each. */
function issuesFor(field: FormField, errors: Issue[], validation?: Validation) {
  const seen = new Set<string>()
  const errorList = [...(validation?.errors ?? []), ...errors].filter(
    (e) => e.field === field && !seen.has(e.code) && seen.add(e.code),
  )
  const warnings = (validation?.warnings ?? []).filter((w) => w.field === field)
  return { errorList, warnings }
}

export function DesignForm({
  mode,
  locked,
  values,
  source,
  suggestions,
  errors,
  validation,
  created,
  sameAsCreated,
  departments,
  lastDesigner,
  busy,
  cardWaiting = false,
  canReserve = false,
  onReserve,
  onChange,
  onTakeSuggestion,
  onCreate,
  onNewDesign,
  className,
  checking = false,
}: Props) {
  const { t, lang } = useI18n()
  const folder = folderPreview(values)
  const todo = blockers(mode, values, validation?.errors.length ?? 0)
  const canCreate = REQUIRED_FIELDS.every((f) => isFilled(f, values[f])) && !sameAsCreated && todo.length === 0
  // While the check runs, the last result may be out of date: a click is kept and runs once
  // the answer says the values are valid (finding 13), instead of being lost.
  const mayCreateAfterCheck =
    checking && REQUIRED_FIELDS.every((f) => isFilled(f, values[f])) && !sameAsCreated && blockers(mode, values, 0).length === 0
  const valuesKey = JSON.stringify(values)
  const [queuedFor, setQueuedFor] = useState<string | null>(null) // the values a click waits for
  const fired = useRef<string | null>(null)
  const queued = queuedFor === valuesKey && checking
  useEffect(() => {
    if (queuedFor !== valuesKey || checking || fired.current === queuedFor) return
    fired.current = queuedFor // once per click; an edit in between drops the click
    if (canCreate) onCreate()
  }, [queuedFor, valuesKey, checking, canCreate, onCreate])
  const requestCreate = () => {
    if (checking && mayCreateAfterCheck) {
      fired.current = null
      setQueuedFor(valuesKey)
    } else if (canCreate) onCreate()
  }
  const needsNumber = mode === 'new' && !isFilled('design_number', values.design_number)
  const todoText = todo
    .map((b) =>
      b.key === 'need_field' ? t('block.need_field', { field: t(FIELD_LABELS[b.field]) }) : t(`block.${b.key}`),
    )
    .join(' · ')
  const normalizedName = validation?.normalized.name

  const departmentLabel = (code: string) => {
    const d = departments.find((x) => x.code === code)
    return d ? `${code} – ${departmentName(d, lang)}` : code
  }

  const takeButton = (field: FormField, value: string) => (
    <Button type="button" size="xs" variant="outline" onClick={() => onChange(field, value)}>
      {t('form.use_suggestion')}
    </Button>
  )

  /** The line under a field before (or while) it is typed: format, examples, values to
   * pick. Errors from the validators replace nothing; they show below it. */
  function guidance(field: FormField): React.ReactNode {
    const value = values[field]
    const filled = isFilled(field, value)
    if (field === 'design_number') return mode === 'new' && !filled ? t('hint.number_new') : null
    if (field === 'revision') return mode === 'new' ? t('hint.revision_new') : null
    if (field === 'designer' && !filled) {
      return lastDesigner ? (
        <>
          {t('form.last_designer', { name: lastDesigner })} {takeButton('designer', lastDesigner)}
        </>
      ) : (
        t('hint.designer')
      )
    }
    if (field === 'description') {
      return (
        <>
          <span className="flex-1">{t('hint.description')}</span>
          <span aria-hidden className="tabular-nums">
            {value.length}/{DESCRIPTION_MAX}
          </span>
        </>
      )
    }
    if (field === 'name' && !locked('name')) {
      if (!filled) return t('hint.name')
      if (normalizedName && normalizedName !== value.trim()) {
        return (
          <>
            {t('form.saved_as')} <span className="font-medium text-foreground">{normalizedName}</span>
          </>
        )
      }
    }
    return null
  }

  return (
    <Card className={className}>
      <CardHeader className="gap-3">
        <CardTitle className="font-heading text-[0.95rem] font-semibold">{t('form.title')}</CardTitle>
        <FormStepper mode={mode} values={values} validation={validation} created={sameAsCreated} />
      </CardHeader>
      <CardContent>
        {created && (
          <div role="status" className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm">
            <p className="flex items-center gap-2 font-medium text-success">
              <CheckCircle2 aria-hidden className="size-4" />
              {t('form.created', { number: created.design_number, rev: created.revision })}
            </p>
            <Button type="button" size="sm" variant="outline" onClick={onNewDesign}>
              {t('form.new_design')}
            </Button>
          </div>
        )}
        <form
          className="grid gap-x-4 gap-y-3 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault()
            requestCreate()
          }}
        >
          {LAYOUT.map((field) => {
            const { errorList, warnings } = issuesFor(field, errors, validation)
            const from = source[field]
            const suggestion = suggestions[field]
            const id = `field-${field}`
            const readOnly = locked(field)
            const hint = guidance(field)
            const notes = [
              from && `${id}-source`,
              hint && `${id}-hint`,
              errorList.length > 0 && `${id}-errors`,
            ]
              .filter(Boolean)
              .join(' ')
            const common = {
              id,
              'aria-invalid': errorList.length > 0,
              'aria-describedby': notes || undefined,
              className: cn(from && !readOnly && RING[from]),
            }
            const lockedClass = 'bg-muted pr-8 text-foreground/80 focus-visible:ring-ring/30'
            return (
              <div key={field} className={cn('grid content-start gap-1', WIDE.has(field) && 'sm:col-span-2')}>
                <Label htmlFor={id}>
                  {t(FIELD_LABELS[field])}
                  {field === 'description' && (
                    <span className="font-normal text-muted-foreground">{t('form.optional')}</span>
                  )}
                </Label>
                {readOnly ? (
                  // Set by SAP in this mode: still focusable for screen readers, not editable.
                  <div className="relative">
                    <Input
                      {...common}
                      readOnly
                      aria-readonly
                      className={cn(common.className, lockedClass)}
                      value={field === 'department' ? departmentLabel(values.department) : values[field]}
                      placeholder={field === 'design_number' ? t('form.from_sap_pending') : undefined}
                    />
                    <Lock aria-hidden className="absolute top-1/2 right-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
                  </div>
                ) : field === 'department' ? (
                  <select
                    {...common}
                    className={cn(fieldClass, common.className)}
                    value={values.department}
                    onChange={(e) => onChange(field, e.target.value)}
                  >
                    <option value="">{t('form.department.placeholder')}</option>
                    {departments.map((d) => (
                      <option key={d.code} value={d.code}>
                        {d.code} – {departmentName(d, lang)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    {...common}
                    value={values[field]}
                    placeholder={FIELD_PLACEHOLDERS[field]}
                    maxLength={field === 'description' ? DESCRIPTION_MAX : undefined}
                    autoComplete="off"
                    onChange={(e) => onChange(field, e.target.value)}
                  />
                )}
                {hint && (
                  <div id={`${id}-hint`} className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                    {hint}
                  </div>
                )}
                {from && (
                  <p
                    id={`${id}-source`}
                    title={readOnly ? t('form.locked') : undefined}
                    className={cn('text-xs', from === 'ai' ? 'text-hl-amber-ink dark:text-hl-amber' : 'text-hl-sea-ink dark:text-hl-sea')}
                  >
                    {t(from === 'ai' ? 'form.suggested' : 'form.from_sap')}
                  </p>
                )}
                {suggestion !== undefined && (
                  <p className="flex flex-wrap items-center gap-2 text-xs text-hl-amber-ink dark:text-hl-amber">
                    {t('form.assistant_suggests', { value: suggestion })}
                    <Button type="button" size="xs" variant="outline" onClick={() => onTakeSuggestion(field)}>
                      {t('form.use_suggestion')}
                    </Button>
                  </p>
                )}
                <div id={`${id}-errors`}>
                  {errorList.map((e) => (
                    <p key={e.code} role="alert" className="text-xs text-destructive">
                      {issueText(lang, e)} <span className="text-muted-foreground">[{e.ref}]</span>
                    </p>
                  ))}
                </div>
                {warnings.map((w) => (
                  <p key={w.code} className="text-xs text-foreground/80">
                    <span aria-hidden>⚠ </span>
                    {issueText(lang, w)} <span className="text-muted-foreground">[{w.ref}]</span>
                  </p>
                ))}
              </div>
            )
          })}

          <div className="flex items-center gap-2 text-xs text-muted-foreground sm:col-span-2">
            <Label htmlFor="field-folder" className="text-xs font-normal text-muted-foreground after:-ml-1.5 after:content-[':']">{t('form.folder')}</Label>
            <Input
              id="field-folder"
              readOnly
              tabIndex={-1}
              value={folder}
              placeholder="–"
              className="h-6 flex-1 border-0 bg-transparent px-0 text-xs tabular-nums shadow-none focus-visible:ring-0"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:col-span-2">
            {needsNumber && onReserve && (
              // The next step where the user is looking: the same reservation card as the Start panel.
              <Button type="button" variant="secondary" disabled={!canReserve || busy} onClick={onReserve}>
                <Sparkles aria-hidden className="size-4" />
                {t('form.next_sap_number')}
              </Button>
            )}
            <Button
              type="submit"
              disabled={!(canCreate || mayCreateAfterCheck) || busy || queued}
              aria-busy={queued}
              aria-describedby="create-hint"
            >
              {queued
                ? t('form.checking')
                : mode === 'existing' && values.revision
                  ? t('form.create_revision', { rev: values.revision })
                  : t('form.create')}
            </Button>
            <p id="create-hint" className="min-w-48 flex-1 text-xs text-muted-foreground">
              {sameAsCreated ? (
                t('form.already_created')
              ) : cardWaiting ? (
                t('form.card_waiting')
              ) : todo.length > 0 ? (
                <>
                  <span className="font-medium text-foreground">{t('block.prefix')}</span> {todoText}
                </>
              ) : (
                t('form.hint')
              )}
            </p>
          </div>
        </form>
        <div className="mt-6 border-t pt-4">
          <TitleBlockPreview
            // the name as it will be saved (the validators normalize it), not as typed
            values={normalizedName ? { ...values, name: normalizedName } : values}
            source={source}
            departments={departments}
            sap={validation?.sap}
          />
        </div>
      </CardContent>
    </Card>
  )
}
