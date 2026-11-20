import { Collapsible } from 'radix-ui'
import { ChevronDown, FilePlus2, Files, RotateCw, Search, Sparkles } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState } from 'react'

import type { Action, Department, FormMode, Issue, PreviewTarget, SapListDesign } from '@/api/types'
import { RecentDesigns } from '@/components/RecentDesigns'
import { SapCard } from '@/components/SapCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useI18n, type MessageKey } from '@/i18n'
import { departmentName } from '@/lib/fields'
import { STATUS_STYLE } from '@/lib/status'
import { cn } from '@/lib/utils'

type DesignList = {
  data?: SapListDesign[]
  isLoading: boolean
  error: Error | null
  refetch: () => void
}

type Props = {
  mode: FormMode
  /** Values that a mode switch would clear. */
  dirty: boolean
  onModeChange: (mode: FormMode) => void
  departments: Department[]
  // new design
  canReserve: boolean
  busy: boolean
  onReserve: () => void
  reservation: Action | null
  canUndoReservation: boolean
  onUndoReservation: () => void
  // from an existing design
  designs: DesignList
  selected: SapListDesign | null
  onSelect: (design: SapListDesign) => void
  onChangeDesign: () => void
  statusNotes: Issue[]
  aiSelected: string | null
  // recent designs
  showRecent: boolean
  recentCount?: number
  onPreview: (target: PreviewTarget) => void
  /** Medium screens: the list in a shorter scroll box. */
  compact?: boolean
}

const SEARCH_DEBOUNCE_MS = 250

/**
 * Where a design starts (decision 0018): a NEW design gets its number from SAP; a design
 * picked FROM SAP's list gets a new revision. The panel only reads SAP and opens the same
 * confirmation cards as before: nothing happens without the user's click (invariant 2).
 */
export function StartPanel(props: Props) {
  const { t } = useI18n()
  const { mode, dirty, onModeChange } = props
  const [pending, setPending] = useState<FormMode | null>(null)

  function choose(next: FormMode) {
    if (next === mode) return
    if (dirty) setPending(next)
    else onModeChange(next)
  }

  return (
    <Card className="flex h-full min-h-0 flex-col">
      <CardHeader className="gap-3">
        <CardTitle className="font-heading text-[0.95rem] font-semibold">{t('start.title')}</CardTitle>
        <div role="radiogroup" aria-label={t('start.mode_label')} className="grid gap-2">
          {(['new', 'existing'] as const).map((m) => {
            const on = mode === m
            const Icon = m === 'new' ? FilePlus2 : Files
            return (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={on}
                aria-labelledby={`mode-${m}-title`}
                aria-describedby={`mode-${m}-help`}
                onClick={() => choose(m)}
                className={cn(
                  'flex items-start gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
                  on
                    ? 'border-primary bg-hl-cobalt-soft dark:bg-hl-cobalt/20'
                    : 'border-border hover:border-primary/40 hover:bg-muted/60',
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    'mt-0.5 grid size-7 shrink-0 place-items-center rounded-md',
                    on ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground',
                  )}
                >
                  <Icon className="size-4" />
                </span>
                <span className="min-w-0">
                  <span id={`mode-${m}-title`} className={cn('block text-sm font-medium', on && 'text-primary dark:text-foreground')}>
                    {t(m === 'new' ? 'start.mode_new' : 'start.mode_existing')}
                  </span>
                  <span id={`mode-${m}-help`} className="block text-xs text-muted-foreground">
                    {t(m === 'new' ? 'start.mode_new_help' : 'start.mode_existing_help')}
                  </span>
                </span>
              </button>
            )
          })}
        </div>
        {pending && (
          <div role="alertdialog" aria-label={t('start.switch')} className="space-y-2 rounded-lg border p-2 text-sm">
            <p>{t(pending === 'new' ? 'start.switch_confirm_new' : 'start.switch_confirm_existing')}</p>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => {
                  onModeChange(pending)
                  setPending(null)
                }}
              >
                {t('start.switch')}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setPending(null)}>
                {t('start.keep')}
              </Button>
            </div>
          </div>
        )}
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
        {mode === 'new' ? <NewDesign {...props} /> : <FromExisting {...props} />}
        {props.showRecent && (
          <Collapsible.Root className="mt-auto border-t pt-2">
            <Collapsible.Trigger className="group flex w-full items-center justify-between rounded-md py-1 text-sm font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
              {t('recent.count', { count: props.recentCount ?? 0 })}
              <ChevronDown aria-hidden className="size-4 transition-transform group-data-[state=open]:rotate-180" />
            </Collapsible.Trigger>
            <Collapsible.Content className="pt-1">
              <RecentDesigns bare onPreview={props.onPreview} />
            </Collapsible.Content>
          </Collapsible.Root>
        )}
      </CardContent>
    </Card>
  )
}

function NewDesign({ canReserve, busy, onReserve, reservation, canUndoReservation, onUndoReservation }: Props) {
  const { t } = useI18n()
  const result = reservation?.result
  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted-foreground">{t('start.new_help')}</p>
      <div>
        <Button className="w-full" disabled={!canReserve || busy} aria-describedby={canReserve ? undefined : 'start-needs'} onClick={onReserve}>
          <Sparkles aria-hidden className="size-4" />
          {t('start.get_sap_number')}
        </Button>
        {!canReserve && (
          <p id="start-needs" className="mt-1 text-xs text-muted-foreground">
            {t('start.needs_fields')}
          </p>
        )}
      </div>
      {result?.design_number && (
        <div role="status" className="space-y-1 rounded-lg border border-hl-sea/50 bg-hl-sea/10 p-2 text-xs">
          <p className="font-medium text-hl-sea-ink dark:text-hl-sea">
            {t('start.reserved', { number: result.design_number, rev: result.revision ?? 'A' })}
          </p>
          {(result.sap_material || result.project) && (
            <p className="tabular-nums text-muted-foreground">
              {[result.sap_material?.replace(/^0+/, ''), result.project].filter(Boolean).join(' · ')}
            </p>
          )}
          {canUndoReservation && (
            <Button size="xs" variant="outline" onClick={onUndoReservation}>
              {t('action.undo')}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

function FromExisting({
  designs,
  selected,
  onSelect,
  onChangeDesign,
  statusNotes,
  aiSelected,
  departments,
  compact,
}: Props) {
  const { t, lang } = useI18n()
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [dept, setDept] = useState('ALL')
  const [active, setActive] = useState<string | null>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const listId = useId()

  useEffect(() => {
    const timer = setTimeout(() => setQuery(text.trim().toLowerCase()), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [text])

  const rows = useMemo(
    () =>
      (designs.data ?? []).filter(
        (d) =>
          (dept === 'ALL' || d.department === dept) &&
          (!query || d.design_number.toLowerCase().includes(query) || d.name.toLowerCase().includes(query)),
      ),
    [designs.data, dept, query],
  )
  const byNumber = useMemo(() => new Map((designs.data ?? []).map((d) => [d.design_number, d])), [designs.data])
  const activeIndex = rows.findIndex((r) => r.design_number === active)
  const optionId = (number: string) => `${listId}-${number}`

  function pick(design: SapListDesign) {
    setActive(design.design_number)
    if (design.selectable) onSelect(design)
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (!rows.length) return
    const move = (index: number) => {
      const next = rows[Math.max(0, Math.min(rows.length - 1, index))]
      setActive(next.design_number)
      document.getElementById(optionId(next.design_number))?.scrollIntoView?.({ block: 'nearest' })
    }
    if (event.key === 'ArrowDown') move(activeIndex + 1)
    else if (event.key === 'ArrowUp') move(activeIndex <= 0 ? 0 : activeIndex - 1)
    else if (event.key === 'Home') move(0)
    else if (event.key === 'End') move(rows.length - 1)
    else if ((event.key === 'Enter' || event.key === ' ') && activeIndex >= 0) pick(rows[activeIndex])
    else return
    event.preventDefault()
  }

  if (selected) {
    return (
      <div className="space-y-2 text-sm">
        {aiSelected === selected.design_number && (
          <p role="status" className="flex items-center gap-1.5 text-xs text-hl-amber-ink dark:text-hl-amber">
            <Sparkles aria-hidden className="size-3.5" />
            {t('start.ai_selected', { number: selected.design_number })}
          </p>
        )}
        <SapCard design={selected} notes={statusNotes.map((n) => ({ message: n.message, ref: n.ref }))} />
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            onChangeDesign()
            requestAnimationFrame(() => listRef.current?.focus())
          }}
        >
          {t('start.change_design')}
        </Button>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 text-sm">
      <div className="relative">
        <Search aria-hidden className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          aria-label={t('start.search')}
          placeholder={t('start.search')}
          className="pl-8"
          value={text}
          maxLength={40}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      <div role="group" aria-label={t('start.filter_label')} className="flex flex-wrap gap-1">
        {['ALL', ...departments.map((d) => d.code)].map((code) => {
          const d = departments.find((x) => x.code === code)
          return (
            <Button
              key={code}
              size="xs"
              variant={dept === code ? 'default' : 'outline'}
              aria-pressed={dept === code}
              title={d ? departmentName(d, lang) : undefined}
              onClick={() => setDept(code)}
            >
              {code === 'ALL' ? t('start.filter_all') : code}
            </Button>
          )
        })}
      </div>

      {designs.isLoading && <p className="text-muted-foreground">{t('start.loading')}</p>}
      {designs.error && (
        <div role="alert" className="space-y-2 rounded-lg border border-destructive/40 p-2 text-destructive">
          <p>{designs.error.message}</p>
          <Button size="xs" variant="outline" onClick={() => designs.refetch()}>
            <RotateCw aria-hidden />
            {t('start.retry')}
          </Button>
        </div>
      )}
      {designs.data && rows.length === 0 && <p className="text-muted-foreground">{t('start.no_match')}</p>}
      {rows.length > 0 && (
        <ul
          ref={listRef}
          role="listbox"
          tabIndex={0}
          aria-label={t('start.list_label')}
          aria-activedescendant={activeIndex >= 0 ? optionId(rows[activeIndex].design_number) : undefined}
          onKeyDown={onKeyDown}
          onFocus={() => !active && rows[0] && setActive(rows[0].design_number)}
          className={cn(
            'min-h-0 flex-1 divide-y overflow-y-auto rounded-lg border outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
            compact && 'max-h-64',
          )}
        >
          {rows.map((d) => {
            const successor = d.successor ? byNumber.get(d.successor) : undefined
            return (
              <li
                key={d.design_number}
                id={optionId(d.design_number)}
                role="option"
                aria-selected={false}
                aria-disabled={!d.selectable}
                onClick={() => pick(d)}
                className={cn(
                  'cursor-pointer border-l-2 border-transparent px-2 py-1.5',
                  d.design_number === active && 'border-hl-cobalt bg-hl-cobalt-soft dark:bg-hl-cobalt/20',
                  !d.selectable && 'cursor-not-allowed opacity-70',
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="tabular-nums text-xs">{d.design_number}</span>
                  <Badge variant="secondary" className={STATUS_STYLE[d.status]}>
                    {t(`status.${d.status}` as MessageKey)}
                  </Badge>
                </div>
                <p className="truncate">{d.name}</p>
                <p className="text-xs text-muted-foreground">
                  {d.department} · {t('start.latest', { rev: d.current_revision || '–' })}
                  {d.selectable && <span className="ml-1 font-medium text-foreground">{t('start.next_rev', { rev: d.next_free_revision })}</span>}
                </p>
                {!d.selectable && d.block_reason && <p className="text-xs text-destructive">{d.block_reason}</p>}
                {successor && (
                  <Button
                    size="xs"
                    variant="link"
                    className="h-auto p-0"
                    onClick={(e) => {
                      e.stopPropagation()
                      pick(successor)
                    }}
                  >
                    {t('start.use_successor', { number: successor.design_number })}
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
