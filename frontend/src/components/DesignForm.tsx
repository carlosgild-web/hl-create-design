import { CheckCircle2 } from 'lucide-react'

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
import { departmentName, FIELD_LABELS } from '@/lib/fields'
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
  busy: boolean
  onChange: (field: FormField, value: string) => void
  onTakeSuggestion: (field: FormField) => void
  onReserve: () => void
  onCreate: () => void
  onNewDesign: () => void
}

const fieldClass =
  'h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive dark:bg-input/30'

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
  busy,
  onChange,
  onTakeSuggestion,
  onReserve,
  onCreate,
  onNewDesign,
}: Props) {
  const { t, lang } = useI18n()
  const folder = folderPreview(values)
  const canReserve = Boolean(values.department.trim() && values.name.trim() && values.designer.trim())
  const canCreate = FORM_FIELDS.every((f) => values[f].trim()) && !sameAsCreated
  const normalizedName = validation?.normalized.name

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
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (canCreate) onCreate()
          }}
        >
          {FORM_FIELDS.map((field) => {
            const { errorList, warnings } = issuesFor(field, errors, validation)
            const from = source[field]
            const suggestion = suggestions[field]
            const id = `field-${field}`
            const notes = [from && `${id}-source`, errorList.length > 0 && `${id}-errors`].filter(Boolean).join(' ')
            const common = {
              id,
              'aria-invalid': errorList.length > 0,
              'aria-describedby': notes || undefined,
              className: cn(from && RING[from]),
            }
            return (
              <div key={field} className="grid gap-1.5">
                <Label htmlFor={id}>{t(FIELD_LABELS[field])}</Label>
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
                  <Input {...common} value={values[field]} autoComplete="off" onChange={(e) => onChange(field, e.target.value)} />
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
                {field === 'name' && normalizedName && normalizedName !== values.name.trim() && (
                  <p className="text-xs text-muted-foreground">
                    {t('form.saved_as')} <span className="font-medium text-foreground">{normalizedName}</span>
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

          <div className="grid gap-1.5">
            <Label htmlFor="field-folder">{t('form.folder')}</Label>
            <Input id="field-folder" readOnly value={folder} className="bg-muted font-mono" />
          </div>

          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" disabled={!canReserve || busy} onClick={onReserve}>
              {t('form.reserve')}
            </Button>
            <Button type="submit" disabled={!canCreate || busy}>
              {t('form.create')}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">{sameAsCreated ? t('form.already_created') : t('form.hint')}</p>
        </form>
      </CardContent>
    </Card>
  )
}
