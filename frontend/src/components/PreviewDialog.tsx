import { useQuery } from '@tanstack/react-query'
import {
  AppWindow,
  Check,
  CircuitBoard,
  Copy,
  Download,
  ExternalLink,
  FileText,
  FolderArchive,
  Info,
  Loader2,
  RotateCw,
  ScanSearch,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { type DrawingView, getDesignFiles, getKicadStatus, openInKicad, previewUrl, projectZipUrl } from '@/api/client'
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
 * Since decision 0033 the board has the same title block: a Schematic | PCB switch picks
 * which drawing the preview and the PDF links show, and Open PCB starts the PCB editor.
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

type Opening = { view: DrawingView; status: 'busy' | 'done' } | { view: DrawingView; status: Error } | null

function PreviewBody({ target }: { target: PreviewTarget }) {
  const { t } = useI18n()
  const [view, setView] = useState<DrawingView>('schematic')
  const [state, setState] = useState<State>('loading')
  const [actual, setActual] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const scroller = useRef<HTMLDivElement>(null)
  const svg = `${previewUrl(target, 'svg', view)}${attempt ? `?retry=${attempt}` : ''}`
  const pdf = previewUrl(target, 'pdf', view)
  const pdfName = `${target.design_number}_${target.revision}${view === 'pcb' ? '_pcb' : ''}.pdf`
  const folder = target.folder ?? `${target.department}/${target.design_number}/${target.revision}`
  const files = useQuery({ queryKey: ['design-files', target], queryFn: () => getDesignFiles(target), retry: false })
  const kicad = useQuery({ queryKey: ['kicad'], queryFn: getKicadStatus, retry: false, staleTime: 60_000 })
  const [opening, setOpening] = useState<Opening>(null)
  const busy = opening?.status === 'busy'

  async function open(which: DrawingView) {
    setOpening({ view: which, status: 'busy' })
    try {
      await openInKicad(target, which)
      setOpening({ view: which, status: 'done' })
    } catch (error) {
      setOpening({ view: which, status: error instanceof Error ? error : new Error(String(error)) })
    }
  }

  function show(next: DrawingView) {
    if (next === view) return
    setView(next)
    setState('loading')
    setActual(false)
    setAttempt(0)
  }

  // Tell "no preview" (404) from a failure that a retry may fix.
  async function failed() {
    try {
      const response = await fetch(previewUrl(target, 'svg', view))
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

      {kicad.data && !kicad.data.found && <KicadMissing url={kicad.data.download_url} />}

      {files.data?.has_pcb_preview && (
        <div role="group" aria-label={t('preview.drawing')} className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={view === 'schematic' ? 'secondary' : 'outline'}
            aria-pressed={view === 'schematic'}
            onClick={() => show('schematic')}
          >
            <FileText aria-hidden className="size-4" />
            {t('preview.schematic')}
          </Button>
          <Button size="sm" variant={view === 'pcb' ? 'secondary' : 'outline'} aria-pressed={view === 'pcb'} onClick={() => show('pcb')}>
            <CircuitBoard aria-hidden className="size-4" />
            {t('preview.pcb')}
          </Button>
        </div>
      )}

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
            key={view}
            src={svg}
            alt={t(view === 'pcb' ? 'preview.alt_pcb' : 'preview.alt', {
              number: target.design_number,
              rev: target.revision,
            })}
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
          <OpenButton
            busy={busy}
            starting={busy && opening?.view === 'schematic'}
            label={t('preview.open_kicad')}
            onClick={() => void open('schematic')}
          />
        )}
        {files.data?.can_open_pcb && (
          <OpenButton
            busy={busy}
            starting={busy && opening?.view === 'pcb'}
            label={t('preview.open_pcb')}
            icon={CircuitBoard}
            variant="outline"
            onClick={() => void open('pcb')}
          />
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
          <a href={pdf} download={pdfName}>
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
      {opening?.status === 'done' && (
        <p role="status" className="text-xs text-muted-foreground">
          {t(opening.view === 'pcb' ? 'preview.opened_pcb' : 'preview.opened')}
        </p>
      )}
      {opening?.status instanceof Error && (
        <p role="alert" className="text-xs text-destructive">
          {t('preview.open_failed', { message: opening.status.message })}
        </p>
      )}
    </>
  )
}

/** KiCad 9 is not on this computer (decision 0035): say what that leaves out and where to
 * get it, instead of hiding the preview and the Open buttons without a word. */
function KicadMissing({ url }: { url: string }) {
  const { t } = useI18n()
  return (
    <div role="note" aria-label={t('kicad.missing_title')} className="flex gap-2 rounded-lg border bg-muted/50 px-3 py-2 text-xs">
      <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      <div className="space-y-1">
        <p className="font-medium">{t('kicad.missing_title')}</p>
        <p className="text-muted-foreground">{t('kicad.missing_body')}</p>
        <a href={url} target="_blank" rel="noreferrer" className="font-medium text-primary underline-offset-2 hover:underline">
          {t('kicad.download')}
        </a>
      </div>
    </div>
  )
}

type OpenButtonProps = {
  busy: boolean
  starting: boolean
  label: string
  icon?: LucideIcon
  variant?: 'default' | 'outline'
  onClick: () => void
}

/** Open in KiCad / Open PCB: one start at a time; the one starting shows the spinner. */
function OpenButton({ busy, starting, label, icon: Icon = AppWindow, variant = 'default', onClick }: OpenButtonProps) {
  const { t } = useI18n()
  return (
    <Button size="sm" variant={variant} disabled={busy} aria-busy={starting} onClick={onClick}>
      {starting ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <Icon aria-hidden className="size-4" />}
      {starting ? t('preview.opening') : label}
    </Button>
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
