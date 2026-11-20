import { useState } from 'react'
import { Loader2 } from 'lucide-react'

import { cancelAction, confirmAction } from '@/api/client'
import { FORM_FIELDS, type Action, type Department } from '@/api/types'
import { departmentName, FIELD_LABELS } from '@/lib/fields'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'

type Props = {
  action: Action
  /** From before the form started over: shown for the record, no buttons that change the form. */
  stale?: boolean
  departments?: Department[]
  onChange: (action: Action) => void
  onUseNumber: (action: Action) => void
  onUndoNumber?: (action: Action) => void
  canUndoNumber?: (action: Action) => boolean
  onShowPreview: (action: Action) => void
}

/**
 * The confirmation gate in the UI (invariant 2): the only way to reserve a number or
 * create files is this card's Confirm button.
 */
export function ActionCard({ action, stale = false, departments = [], onChange, onUseNumber, onUndoNumber, canUndoNumber, onShowPreview }: Props) {
  const { t, lang } = useI18n()
  const [busy, setBusy] = useState<'confirm' | 'cancel' | null>(null)
  const [failure, setFailure] = useState('')

  async function decide(verb: 'confirm' | 'cancel') {
    setBusy(verb)
    setFailure('')
    try {
      const { action: next, http } = await (verb === 'confirm' ? confirmAction : cancelAction)(action.id)
      onChange(next)
      if (http === 410) setFailure(t('action.expired'))
      else if (http === 409 && next.status !== 'failed') setFailure(t('action.already'))
    } catch (error) {
      setFailure(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(null)
    }
  }

  const { status, result } = action
  const pending = status === 'pending'
  const shown = FORM_FIELDS.filter((k) => action.payload[k])
  const display = (k: (typeof FORM_FIELDS)[number]) => {
    const value = action.payload[k]
    const dept = k === 'department' ? departments.find((d) => d.code === value) : undefined
    return dept ? `${value} – ${departmentName(dept, lang)}` : value
  }
  const filled = canUndoNumber?.(action) ?? false

  return (
    <section
      aria-label={t(action.kind === 'create_design' ? 'action.create_design' : 'action.reserve_number')}
      className={cn(
        'rounded-lg border-2 bg-card p-3 text-sm',
        pending && !stale ? 'border-primary/50' : 'border-border',
        stale && 'opacity-75',
      )}
      data-status={status}
      data-action-id={action.id}
    >
      <p className="font-medium">
        {t(action.kind === 'create_design' ? 'action.create_design' : 'action.reserve_number')}
      </p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
        {shown.map((k) => (
          <div key={k} className="contents">
            <dt className="text-muted-foreground">{t(FIELD_LABELS[k])}</dt>
            <dd className="break-words font-mono">{display(k)}</dd>
          </div>
        ))}
      </dl>

      {pending && !stale && (
        <div className="mt-3 flex gap-2">
          <Button size="sm" disabled={busy !== null} aria-busy={busy === 'confirm'} onClick={() => decide('confirm')}>
            {busy === 'confirm' && <Loader2 aria-hidden className="size-4 animate-spin" />}
            {busy === 'confirm' ? t('action.confirming') : t('action.confirm')}
          </Button>
          <Button size="sm" variant="outline" disabled={busy !== null} aria-busy={busy === 'cancel'} onClick={() => decide('cancel')}>
            {busy === 'cancel' && <Loader2 aria-hidden className="size-4 animate-spin" />}
            {t('action.cancel')}
          </Button>
        </div>
      )}
      {status === 'executing' && <p className="mt-3 text-muted-foreground">{t('action.executing')}</p>}
      {status === 'cancelled' && (
        <p className="mt-3 text-muted-foreground">
          {t('action.cancelled')}. {t('action.nothing')}
        </p>
      )}

      {status === 'confirmed' && (
        <div className="mt-3 space-y-2">
          <p className="font-medium text-hl-sea-ink dark:text-hl-sea">
            {action.kind === 'reserve_number'
              ? t('action.reserved', { number: result.design_number ?? '' })
              : t('action.created', { number: result.design_number ?? '', rev: result.revision ?? '' })}
          </p>
          {result.folder && (
            <p className="text-xs text-muted-foreground">
              {t('action.folder')}: <span className="font-mono">{result.folder}</span>
            </p>
          )}
          {result.warnings?.map((w) => (
            <p key={w.code} className="text-xs text-foreground/80">
                    <span aria-hidden>⚠ </span>
              {w.message} [{w.ref}]
            </p>
          ))}
          {action.kind === 'reserve_number' ? (
            stale ? null : filled && onUndoNumber ? (
              <p className="flex flex-wrap items-center gap-2 text-xs text-hl-sea-ink dark:text-hl-sea">
                {t('action.number_filled')}
                <Button size="xs" variant="outline" onClick={() => onUndoNumber(action)}>
                  {t('action.undo')}
                </Button>
              </p>
            ) : (
              <Button size="sm" variant="outline" onClick={() => onUseNumber(action)}>
                {t('action.use_number')}
              </Button>
            )
          ) : (
            result.pdf && (
              <Button size="sm" variant="outline" onClick={() => onShowPreview(action)}>
                {t('action.show_preview')}
              </Button>
            )
          )}
        </div>
      )}

      {status === 'failed' && (
        <div className="mt-3 space-y-1" role="alert">
          <p className="font-medium text-destructive">{t('action.failed')}</p>
          {result.message && <p>{result.message}</p>}
          {result.errors?.map((e) => (
            <p key={e.code + e.field} className="text-xs">
              {e.message} <span className="text-muted-foreground">[{e.ref}]</span>
            </p>
          ))}
          {result.ref && <p className="text-xs text-muted-foreground">[{result.ref}]</p>}
        </div>
      )}
      {stale && <p className="mt-2 text-xs text-muted-foreground">{t('action.stale')}</p>}
      {failure && (
        <p role="alert" className="mt-2 text-xs text-destructive">
          {failure}
        </p>
      )}
    </section>
  )
}
