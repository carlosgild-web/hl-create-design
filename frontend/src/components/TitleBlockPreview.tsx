import { useState } from 'react'
import type * as React from 'react'

import type { Department, FormField, FormValues, ValueSource } from '@/api/types'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'

type Props = {
  values: FormValues
  source: Partial<Record<FormField, ValueSource>>
  departments: Department[]
  /** SAP's record for the number, from `/api/validate` (material and WBS). */
  sap?: { material: string; wbs: string }
}

const TINT: Record<ValueSource, string> = {
  sap: 'text-hl-sea-ink dark:text-hl-sea',
  ai: 'text-hl-amber-ink dark:text-hl-amber',
}

/**
 * A drawn copy of `kicad/template/hl_title_block.kicad_wks`: the same cells, labels and
 * proportions (columns 50 / 45 / 45 / 40 mm), filled from the form as it changes. The
 * labels stay in English because the drawing sheet prints them in English. Display only:
 * the files are written by the backend renderer after Confirm (invariant 2).
 */
export function TitleBlockPreview({ values, source, departments, sap }: Props) {
  const { t } = useI18n()
  // the issue date the renderer writes: today, local time (YYYY-MM-DD)
  const [today] = useState(() => new Date().toLocaleDateString('sv-SE'))
  const dept = departments.find((d) => d.code === values.department)
  const number = values.design_number.trim()
  const rev = values.revision.trim()
  const stem = number && rev ? `${number}_${rev}` : ''
  const material = sap?.material.replace(/^0+/, '') ?? ''
  const used = new Set(Object.values(source))

  const tint = (field: FormField) => {
    const from = source[field]
    return from ? TINT[from] : undefined
  }

  return (
    <figure className="space-y-2" aria-labelledby="title-block-caption">
      {/* plain text cells, read in order: label then value */}
      <div
        data-testid="title-block"
        className="grid grid-cols-[50fr_45fr_45fr_40fr] grid-rows-[minmax(4.5rem,auto)_minmax(2.75rem,auto)_minmax(2.75rem,auto)_auto] overflow-hidden rounded-sm border-2 border-foreground/70 bg-white text-foreground dark:bg-card [&>*]:border-foreground/35"
      >
        {/* company block: rows 1-2 of the first column */}
        <div className="row-span-2 flex flex-col items-center justify-center gap-1 border-r border-b px-2 py-2 text-center">
          <img src="/favicon.svg" alt="" className="size-7 rounded-sm" />
          <p className="text-[0.7rem] leading-tight font-semibold">Hilda &amp; Luna Beadworks</p>
          <p className="text-[0.6rem] leading-tight text-muted-foreground">Electronics Engineering</p>
        </div>
        <Cell label="Title" className="col-span-2 border-r border-b">
          <Value value={values.name.trim()} className={cn('text-lg leading-tight font-semibold', tint('name'))} />
          {values.description.trim() && (
            <p className={cn('mt-0.5 truncate text-xs italic', tint('description'))}>{values.description.trim()}</p>
          )}
        </Cell>
        <Cell label="Design No." className="border-b">
          <Value value={number} className={cn('text-sm leading-tight font-semibold tracking-tight tabular-nums sm:whitespace-nowrap', tint('design_number'))} />
        </Cell>

        <Cell label="Department" className="border-r border-b">
          <Value value={dept ? `${dept.code} – ${dept.name}` : values.department} className={cn('text-xs', tint('department'))} />
        </Cell>
        <Cell label="Project (WBS)" className="border-r border-b">
          <Value value={sap?.wbs ?? ''} className="text-xs tabular-nums text-hl-sea-ink dark:text-hl-sea" />
        </Cell>
        <Cell label="Rev" className="border-b">
          <Value value={rev} className={cn('text-center text-2xl leading-none font-semibold', tint('revision'))} />
        </Cell>

        <Cell label="SAP material" className="border-r border-b">
          <Value value={material} className="text-xs tabular-nums text-hl-sea-ink dark:text-hl-sea" />
        </Cell>
        <Cell label="Designer" className="border-r border-b">
          <Value value={values.designer.trim()} className={cn('text-xs', tint('designer'))} />
        </Cell>
        <Cell label="Date" className="border-r border-b">
          <Value value={today} className="text-[0.68rem] whitespace-nowrap tabular-nums sm:text-xs" />
        </Cell>
        <Cell label="Sheet" className="border-b">
          <Value value="1 / 1" className="text-xs tabular-nums" />
        </Cell>

        <p className="col-span-2 truncate px-1.5 py-0.5 text-[0.6rem] text-muted-foreground">
          File: {stem ? `${stem}.kicad_sch` : ''}
        </p>
        <p className="px-1.5 py-0.5 text-[0.6rem] text-muted-foreground">Size: A4</p>
        <p className="px-1.5 py-0.5 text-[0.6rem] text-muted-foreground">KiCad 9.0</p>
      </div>
      <figcaption id="title-block-caption" className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="mr-auto">{t('tb.caption')}</span>
        {used.has('sap') && <Key className="bg-hl-sea">{t('tb.key_sap')}</Key>}
        {used.has('ai') && <Key className="bg-hl-amber">{t('tb.key_ai')}</Key>}
      </figcaption>
    </figure>
  )
}

function Cell({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={cn('flex min-w-0 flex-col px-1.5 pt-0.5 pb-1', className)}>
      <span className="text-[0.6rem] leading-tight text-muted-foreground">{label}</span>
      <div className="flex min-w-0 flex-1 flex-col justify-center">{children}</div>
    </div>
  )
}

/** An empty cell keeps its height with a faint rule where the value will go. */
function Value({ value, className }: { value: string; className?: string }) {
  if (!value) return <span aria-hidden className="mt-2 block h-px w-3/5 border-b border-dashed border-foreground/25" />
  return <p className={cn('break-words', className)}>{value}</p>
}

function Key({ className, children }: { className: string; children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-1.5">
      <span aria-hidden className={cn('size-2 rounded-full', className)} />
      {children}
    </span>
  )
}
