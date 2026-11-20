import { useQuery } from '@tanstack/react-query'
import { AppWindow, Check, Copy, Download, ExternalLink, FolderArchive, Loader2, RotateCw, ScanSearch } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { getDesignFiles, openInKicad, previewUrl, projectZipUrl } from '@/api/client'
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
  const files = useQuery({ queryKey: ['design-files', target], queryFn: () => getDesignFiles(target), retry: false })
  const [opening, setOpening] = useState<'idle' | 'busy' | 'done' | Error>('idle')

  async function open() {
    setOpening('busy')
    try {
      await openInKicad(target)
      setOpening('done')
    } catch (error) {
      setOpening(error instanceof Error ? error : new Error(String(error)))
    }
  }

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
          {target.department} · <span className="tabular-nums">{folder}</span>
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

      <ProjectFile target={target} />

      <DialogFooter className="flex-wrap">
        {files.data?.can_open && (
          <Button size="sm" disabled={opening === 'busy'} aria-busy={opening === 'busy'} onClick={() => void open()}>
            {opening === 'busy' ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <AppWindow aria-hidden className="size-4" />}
            {opening === 'busy' ? t('preview.opening') : t('preview.open_kicad')}
          </Button>
        )}
        <Button size="sm" variant="outline" asChild>
          <a href={projectZipUrl(target)} download={`${target.design_number}_${target.revision}.zip`}>
            <FolderArchive aria-hidden className="size-4" />
            {t('preview.download_zip')}
          </a>
        </Button>
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
          <Button size="sm" variant={files.data?.can_open ? 'outline' : 'default'}>
            {t('preview.close')}
          </Button>
        </DialogClose>
      </DialogFooter>
      {opening === 'done' && (
        <p role="status" className="text-xs text-muted-foreground">
          {t('preview.opened')}
        </p>
      )}
      {opening instanceof Error && (
        <p role="alert" className="text-xs text-destructive">
          {t('preview.open_failed', { message: opening.message })}
        </p>
      )}
    </>
  )
}

/** Where the project is, to open it by hand: the full path and a Copy button. */
function ProjectFile({ target }: { target: PreviewTarget }) {
  const { t } = useI18n()
  const files = useQuery({ queryKey: ['design-files', target], queryFn: () => getDesignFiles(target), retry: false })
  const [copied, setCopied] = useState(false)
  if (!files.data) return null
  const path = files.data.project_file

  async function copy() {
    try {
      await navigator.clipboard.writeText(path)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false) // no clipboard (http, old browser): the path is selectable
    }
  }

  return (
    <div className="space-y-1 rounded-lg border bg-muted/40 px-3 py-2 text-xs">
      <p className="font-medium">{t('preview.project_file')}</p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate tabular-nums select-all" title={path}>
          {path}
        </code>
        <Button size="xs" variant="outline" onClick={() => void copy()}>
          {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
          {copied ? t('preview.copied') : t('preview.copy')}
        </Button>
      </div>
      <p className="text-muted-foreground">{t('preview.how_to_open')}</p>
    </div>
  )
}
