import { Check } from 'lucide-react'

import type { FormField, FormValues, Validation } from '@/api/types'
import { useI18n, type MessageKey } from '@/i18n'
import { isFilled } from '@/lib/fields'
import { cn } from '@/lib/utils'

const STEPS: { key: MessageKey; fields: FormField[] }[] = [
  { key: 'step.department', fields: ['department'] },
  { key: 'step.number', fields: ['design_number'] },
  { key: 'step.revision', fields: ['revision'] },
  { key: 'step.details', fields: ['name', 'designer'] },
  { key: 'step.confirm', fields: [] },
]

type Props = { values: FormValues; validation?: Validation; created: boolean }

/**
 * Progress only: which part of the form is done (filled and without errors from the
 * validators). It never decides anything; the fields stay editable in any order.
 */
export function FormStepper({ values, validation, created }: Props) {
  const { t } = useI18n()
  const done = STEPS.map(({ fields }) =>
    fields.length === 0
      ? created
      : fields.every((f) => isFilled(f, values[f]) && !validation?.errors.some((e) => e.field === f)),
  )
  const current = done.findIndex((d) => !d)

  return (
    <ol aria-label={t('step.label')} className="flex flex-wrap items-center gap-x-1 gap-y-2 text-xs">
      {STEPS.map(({ key }, i) => (
        <li key={key} aria-current={i === current ? 'step' : undefined} className="flex items-center gap-1">
          <span
            className={cn(
              'grid size-5 shrink-0 place-items-center rounded-full border text-[0.65rem] font-semibold',
              done[i] && 'border-success bg-success text-white',
              !done[i] && i === current && 'border-primary text-primary',
              !done[i] && i !== current && 'text-muted-foreground',
            )}
          >
            {done[i] ? <Check aria-hidden className="size-3" /> : i + 1}
          </span>
          <span className={cn(i === current ? 'font-medium text-foreground' : 'text-muted-foreground')}>
            {t(key)}
            {done[i] && <span className="sr-only"> ({t('step.done')})</span>}
          </span>
          {i < STEPS.length - 1 && <span aria-hidden className="mx-1 h-px w-3 bg-border sm:w-5" />}
        </li>
      ))}
    </ol>
  )
}
