import { Download, ExternalLink, RotateCw, ScanSearch } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { previewUrl } from '@/api/client'
import type { PreviewTarget } from '@/api/types'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'

type State = 'loading' | 'ready' | 'missing' | 'error'

type Props = { target: PreviewTarget | null; onClose: () => void }

/**
 * The title block preview (decision 0018), in a dialog so it is never below the fold:
 * fit or 100%, a jump to the title block (bottom right of the sheet), Open and Download PDF.
 */
export function PreviewDialog({ target, onClose }: Props) {
  const { t } = useI18n()
  // Opened from code (a confirmed card, a recent design), not a Radix trigger: remember who
  // had the focus, and give it back on close.
  const opener = useRef<HTMLElement | null>(null)
  const open = target !== null

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      {target && (
        <DialogContent
          closeLabel={t('steps.close')}
          className="sm:h-[90vh]"
          // runs before focus moves into the dialog: the opener still has it
          onOpenAutoFocus={() => {
            opener.current = document.activeElement as HTMLElement | null
          }}
          onCloseAutoFocus={(event) => {
            if (opener.current?.isConnected) {
              event.preventDefault()
              opener.current.focus()
            }
          }}
        >
          <PreviewBody key={`${target.department}/${target.design_number}/${target.revision}`} target={target} />
        </DialogContent>
      )}
    </Dialog>
  )
}

function PreviewBody({ target }: { target: PreviewTarget }) {
  const { t } = useI18n()
  const [state, setState] = useState<State>('loading')
  const [actual, setActual] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const scroller = useRef<HTMLDivElement>(null)
  const svg = `${previewUrl(target, 'svg')}${attempt ? `?retry=${attempt}` : ''}`
  const pdf = previewUrl(target, 'pdf')
  const folder = target.folder ?? `${target.department}/${target.design_number}/${target.revision}`

  // Tell "no preview" (404) from a failure that a retry may fix.
  async function failed() {
    try {
      const response = await fetch(previewUrl(target, 'svg'))
      setState(response.status === 404 ? 'missing' : 'error')
    } catch {
      setState('error')
    }
  }

  useEffect(() => {
    if (actual && state === 'ready') scroller.current?.scrollTo?.({ left: 0, top: 0 })
  }, [actual, state])

  function titleBlock() {
    setActual(true)
    requestAnimationFrame(() => {
      const el = scroller.current
      el?.scrollTo?.({ left: el.scrollWidth, top: el.scrollHeight, behavior: 'smooth' })
    })
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>
          {target.design_number} · rev {target.revision}
          {target.name ? ` · ${target.name}` : ''}
        </DialogTitle>
        <DialogDescription>
          {target.department} · <span className="font-mono">{folder}</span>
        </DialogDescription>
      </DialogHeader>

      {state === 'ready' && (
        <div role="group" aria-label={t('preview.zoom')} className="flex flex-wrap gap-2">
          <Button size="sm" variant={actual ? 'outline' : 'secondary'} aria-pressed={!actual} onClick={() => setActual(false)}>
            {t('preview.fit')}
          </Button>
          <Button size="sm" variant={actual ? 'secondary' : 'outline'} aria-pressed={actual} onClick={() => setActual(true)}>
            100%
          </Button>
          <Button size="sm" variant="outline" onClick={titleBlock}>
            <ScanSearch aria-hidden className="size-4" />
            {t('preview.title_block')}
          </Button>
        </div>
      )}

      <div
        ref={scroller}
        className={cn('min-h-64 flex-1 rounded-lg border bg-white', actual ? 'overflow-auto' : 'overflow-hidden')}
      >
        {state === 'loading' && <div aria-hidden className="size-full min-h-64 animate-pulse bg-muted" />}
        {state === 'missing' && <p className="p-4 text-sm text-muted-foreground">{t('preview.missing')}</p>}
        {state === 'error' && (
          <div role="alert" className="flex items-center gap-3 p-4 text-sm">
            {t('preview.error')}
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setState('loading')
                setAttempt((n) => n + 1)
              }}
            >
              <RotateCw aria-hidden className="size-4" />
              {t('preview.retry')}
            </Button>
          </div>
        )}
        {(state === 'loading' || state === 'ready') && (
          <img
            src={svg}
            alt={t('preview.alt', { number: target.design_number, rev: target.revision })}
            className={cn(
              state === 'loading' && 'sr-only',
              actual ? 'max-w-none' : 'size-full object-contain',
            )}
            onLoad={() => setState('ready')}
            onError={() => void failed()}
          />
        )}
      </div>

      <DialogFooter>
        <Button size="sm" variant="outline" asChild>
          <a href={pdf} target="_blank" rel="noreferrer">
            <ExternalLink aria-hidden className="size-4" />
            {t('preview.open_pdf')}
          </a>
        </Button>
        <Button size="sm" variant="outline" asChild>
          <a href={pdf} download={`${target.design_number}_${target.revision}.pdf`}>
            <Download aria-hidden className="size-4" />
            {t('preview.download')}
          </a>
        </Button>
        <DialogClose asChild>
          <Button size="sm">{t('preview.close')}</Button>
        </DialogClose>
      </DialogFooter>
    </>
  )
}
