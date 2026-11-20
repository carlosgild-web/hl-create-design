import { CheckCircle2 } from 'lucide-react'
import type * as React from 'react'

import {
  FORM_FIELDS,
  type Department,
  type FormField,
  type FormValues,
  type Issue,
  type Validation,
  type ValueSource,
} from '@/api/types'
import { FormStepper } from '@/components/FormStepper'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { Created } from '@/hooks/useDesignForm'
import { useI18n } from '@/i18n'
import { departmentName, FIELD_LABELS, FIELD_PLACEHOLDERS, isFilled, isPrefixOnly, numberProgress } from '@/lib/fields'
import { folderPreview } from '@/lib/folder'
import { cn } from '@/lib/utils'

type Props = {
  values: FormValues
  source: Partial<Record<FormField, ValueSource>>
  suggestions: Partial<Record<FormField, string>>
  errors: Issue[]
  validation?: Validation
  created: Created | null
  sameAsCreated: boolean
  departments: Department[]
  /** The designer of the most recent design, offered for an empty Designer field. */
  lastDesigner?: string
  busy: boolean
  onChange: (field: FormField, value: string) => void
  onTakeSuggestion: (field: FormField) => void
  onReserve: () => void
  onCreate: () => void
  onNewDesign: () => void
}

const fieldClass =
  'h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive dark:bg-input/30'

/** Two columns: Department | Design number, Revision | Designer, then the name across. */
const LAYOUT: FormField[] = ['department', 'design_number', 'revision', 'designer', 'name']

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
  onChange,
  onTakeSuggestion,
  onReserve,
  onCreate,
  onNewDesign,
}: Props) {
  const { t, tn, lang } = useI18n()
  const folder = folderPreview(values)
  const canReserve = Boolean(values.department.trim() && values.name.trim() && values.designer.trim())
  const canCreate = FORM_FIELDS.every((f) => isFilled(f, values[f])) && !sameAsCreated
  const normalizedName = validation?.normalized.name
  const nextRevision = validation?.suggest?.revision

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
    if (field === 'design_number') {
      const progress = numberProgress(value)
      if (!value.trim()) return t('hint.design_number')
      if (isPrefixOnly(value)) return t('hint.number_digits', { prefix: value.trim() })
      if (progress && 'missing' in progress) return tn('hint.number_missing', progress.missing)
      if (progress && 'complete' in progress && !source.design_number) return `✓ ${t('hint.number_ok')}`
      return null
    }
    if (field === 'revision' && !filled) {
      return nextRevision ? (
        <>
          {t('form.next_free', { rev: nextRevision })} {takeButton('revision', nextRevision)}
        </>
      ) : (
        t('hint.revision')
      )
    }
    if (field === 'designer' && !filled) {
      return lastDesigner ? (
        <>
          {t('form.last_designer', { name: lastDesigner })} {takeButton('designer', lastDesigner)}
        </>
      ) : (
        t('hint.designer')
      )
    }
    if (field === 'name') {
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
    <Card>
      <CardHeader className="gap-3">
        <CardTitle className="font-heading text-lg">{t('form.title')}</CardTitle>
        <FormStepper values={values} validation={validation} created={sameAsCreated} />
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
            if (canCreate) onCreate()
          }}
        >
          {LAYOUT.map((field) => {
            const { errorList, warnings } = issuesFor(field, errors, validation)
            const from = source[field]
            const suggestion = suggestions[field]
            const id = `field-${field}`
            const empty = !isFilled(field, values[field])
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
              className: cn(from && RING[from]),
            }
            return (
              <div key={field} className={cn('grid content-start gap-1', field === 'name' && 'sm:col-span-2')}>
                <div className="flex items-center justify-between gap-2">
                  <Label htmlFor={id}>{t(FIELD_LABELS[field])}</Label>
                  {field === 'design_number' && empty && (
                    // A new design gets its number from SAP: right where the number goes.
                    <Button
                      type="button"
                      size="xs"
                      variant="link"
                      className="h-auto p-0"
                      disabled={!canReserve || busy}
                      title={canReserve ? undefined : t('form.reserve_needs')}
                      onClick={onReserve}
                    >
                      {t('form.reserve_short')}
                    </Button>
                  )}
                </div>
                {field === 'department' ? (
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
                      {e.message} <span className="text-muted-foreground">[{e.ref}]</span>
                    </p>
                  ))}
                </div>
                {warnings.map((w) => (
                  <p key={w.code} className="text-xs text-foreground/80">
                    <span aria-hidden>⚠ </span>
                    {w.message} <span className="text-muted-foreground">[{w.ref}]</span>
                  </p>
                ))}
              </div>
            )
          })}

          <div className="flex items-center gap-2 text-xs text-muted-foreground sm:col-span-2">
            <Label htmlFor="field-folder" className="text-xs font-normal text-muted-foreground after:content-[':']">
              {t('form.folder')}
            </Label>
            <Input
              id="field-folder"
              readOnly
              tabIndex={-1}
              value={folder}
              placeholder="–"
              className="h-6 flex-1 border-0 bg-transparent px-0 font-mono text-xs shadow-none focus-visible:ring-0"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:col-span-2">
            <Button type="button" variant="outline" disabled={!canReserve || busy} onClick={onReserve}>
              {t('form.reserve')}
            </Button>
            <Button type="submit" disabled={!canCreate || busy}>
              {t('form.create')}
            </Button>
            <p className="min-w-48 flex-1 text-xs text-muted-foreground">
              {sameAsCreated ? t('form.already_created') : t('form.hint')}
            </p>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
