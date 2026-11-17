import { FORM_FIELDS, type Department, type FormField, type FormValues, type Issue } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useI18n, type MessageKey } from '@/i18n'
import { folderPreview } from '@/lib/folder'
import { cn } from '@/lib/utils'

const LABELS: Record<FormField, MessageKey> = {
  department: 'form.department',
  design_number: 'form.design_number',
  revision: 'form.revision',
  name: 'form.name',
  designer: 'form.designer',
}

type Props = {
  values: FormValues
  proposed: ReadonlySet<FormField>
  errors: Issue[]
  departments: Department[]
  busy: boolean
  onChange: (field: FormField, value: string) => void
  onReserve: () => void
  onCreate: () => void
}

const fieldClass =
  'h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive dark:bg-input/30'

export function DesignForm({
  values,
  proposed,
  errors,
  departments,
  busy,
  onChange,
  onReserve,
  onCreate,
}: Props) {
  const { t } = useI18n()
  const folder = folderPreview(values)
  const canReserve = Boolean(values.department && values.name && values.designer)
  const canCreate = FORM_FIELDS.every((f) => values[f].trim())

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-heading text-lg">{t('form.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (canCreate) onCreate()
          }}
        >
          {FORM_FIELDS.map((field) => {
            const fieldErrors = errors.filter((e) => e.field === field)
            const suggested = proposed.has(field)
            const id = `field-${field}`
            return (
              <div key={field} className="grid gap-1.5">
                <Label htmlFor={id}>
                  {t(LABELS[field])}
                </Label>
                {field === 'department' ? (
                  <select
                    id={id}
                    className={cn(fieldClass, suggested && 'ring-2 ring-amber-400')}
                    value={values.department}
                    aria-invalid={fieldErrors.length > 0}
                    aria-describedby={suggested ? `${id}-suggested` : undefined}
                    onChange={(e) => onChange(field, e.target.value)}
                  >
                    <option value="">{t('form.department.placeholder')}</option>
                    {departments.map((d) => (
                      <option key={d.code} value={d.code}>
                        {d.code} – {d.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    id={id}
                    value={values[field]}
                    className={cn(suggested && 'ring-2 ring-amber-400')}
                    aria-invalid={fieldErrors.length > 0}
                    aria-describedby={suggested ? `${id}-suggested` : undefined}
                    autoComplete="off"
                    onChange={(e) => onChange(field, e.target.value)}
                  />
                )}
                {suggested && (
                  <p id={`${id}-suggested`} className="text-xs text-amber-700 dark:text-amber-400">
                    {t('form.suggested')}
                  </p>
                )}
                {fieldErrors.map((e) => (
                  <p key={e.code} role="alert" className="text-xs text-destructive">
                    {e.message} <span className="text-muted-foreground">[{e.ref}]</span>
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
          <p className="text-xs text-muted-foreground">{t('form.hint')}</p>
        </form>
      </CardContent>
    </Card>
  )
}
