import { useState } from 'react'

import { cancelAction, confirmAction } from '@/api/client'
import type { Action } from '@/api/types'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n'

type Props = {
  action: Action
  onChange: (action: Action) => void
  onUseNumber: (action: Action) => void
  onShowPreview: (action: Action) => void
}

const SHOWN = ['department', 'design_number', 'revision', 'name', 'designer'] as const

/**
 * The confirmation gate in the UI (invariant 2): the only way to reserve a number or
 * create files is this card's Confirm button.
 */
export function ActionCard({ action, onChange, onUseNumber, onShowPreview }: Props) {
  const { t } = useI18n()
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState('')

  async function decide(verb: typeof confirmAction) {
    setBusy(true)
    setFailure('')
    try {
      const { action: next, http } = await verb(action.id)
      onChange(next)
      if (http === 410) setFailure(t('action.expired'))
      else if (http === 409 && next.status !== 'failed') setFailure(t('action.already'))
    } catch (error) {
      setFailure(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }

  const { status, result } = action
  const pending = status === 'pending'
  const shown = SHOWN.filter((k) => action.payload[k])

  return (
    <section
      aria-label={t(action.kind === 'create_design' ? 'action.create_design' : 'action.reserve_number')}
      className="rounded-lg border-2 border-hl-amber bg-card p-3 text-sm"
      data-status={status}
    >
      <p className="font-medium">
        {t(action.kind === 'create_design' ? 'action.create_design' : 'action.reserve_number')}
      </p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
        {shown.map((k) => (
          <div key={k} className="contents">
            <dt className="text-muted-foreground">{k.replace('_', ' ')}</dt>
            <dd className="break-words font-mono">{action.payload[k]}</dd>
          </div>
        ))}
      </dl>

      {pending && (
        <div className="mt-3 flex gap-2">
          <Button size="sm" disabled={busy} onClick={() => decide(confirmAction)}>
            {t('action.confirm')}
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => decide(cancelAction)}>
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
            <p key={w.code} className="text-xs text-hl-amber-ink dark:text-hl-amber">
              {w.message} [{w.ref}]
            </p>
          ))}
          {action.kind === 'reserve_number' ? (
            <Button size="sm" variant="outline" onClick={() => onUseNumber(action)}>
              {t('action.use_number')}
            </Button>
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
      {failure && (
        <p role="alert" className="mt-2 text-xs text-destructive">
          {failure}
        </p>
      )}
    </section>
  )
}
