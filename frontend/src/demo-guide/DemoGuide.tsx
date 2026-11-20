import { BookOpen, Compass, X } from 'lucide-react'
import { useCallback, useState, useSyncExternalStore } from 'react'

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'

import { guide as defaultGuide, type Bi, type GuideConfig } from './guide.config'

type Mode = 'open' | 'pill'

const listeners = new Set<() => void>()
let fallback: Mode = 'open' // used only when localStorage is unavailable

function readMode(key: string): Mode {
  try {
    return localStorage.getItem(key) === 'pill' ? 'pill' : 'open'
  } catch {
    return fallback
  }
}

function writeMode(key: string, mode: Mode) {
  fallback = mode
  try {
    localStorage.setItem(key, mode)
  } catch {
    /* not remembered across visits; still changes this one */
  }
  listeners.forEach((notify) => notify())
}

function useGuideMode(key: string): [Mode, (mode: Mode) => void] {
  const subscribe = useCallback(
    (notify: () => void) => {
      listeners.add(notify)
      const onStorage = (event: StorageEvent) => event.key === key && notify()
      window.addEventListener('storage', onStorage)
      return () => {
        listeners.delete(notify)
        window.removeEventListener('storage', onStorage)
      }
    },
    [key],
  )
  const mode = useSyncExternalStore(subscribe, () => readMode(key))
  return [mode, (next) => writeMode(key, next)]
}

// Neutral on purpose: the guide is about the project, so it never wears the demo's brand colors.
const FRAME = 'border-dashed border-zinc-600 bg-zinc-900 text-zinc-100'

export function DemoGuide({ config = defaultGuide }: { config?: GuideConfig }) {
  const { lang } = useI18n()
  const text = (value: Bi) => value[lang]
  const [mode, setMode] = useGuideMode(config.storageKey)
  const [panelOpen, setPanelOpen] = useState(false)
  const reopen = useCallback(() => {
    setMode('open')
    setPanelOpen(true)
  }, [setMode])

  return (
    <>
      {mode === 'open' && (
        <div role="region" aria-label={text(config.pill)} className={cn(FRAME, 'border-b')}>
          <div className="mx-auto flex max-w-7xl items-start gap-3 px-4 py-2.5 text-xs">
            <Compass className="mt-0.5 size-4 shrink-0 text-zinc-400 max-sm:hidden" aria-hidden />
            <div className="min-w-0 flex-1 space-y-1">
              <p className="font-mono text-[0.65rem] tracking-[0.12em] text-zinc-400 uppercase">
                {text(config.tag)}
              </p>
              <p className="text-zinc-200">{text(config.banner)}</p>
            </div>
            <button
              type="button"
              onClick={() => setPanelOpen(true)}
              className="shrink-0 rounded-md border border-zinc-600 px-2.5 py-1 font-semibold text-zinc-100 transition-colors hover:bg-white/10"
            >
              {text(config.how)}
            </button>
            <button
              type="button"
              onClick={() => setMode('pill')}
              title={text(config.hide)}
              aria-label={text(config.hide)}
              className="grid size-7 shrink-0 place-items-center rounded-md text-zinc-400 hover:bg-white/10 hover:text-white"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>
      )}

      {mode === 'pill' && (
        <button
          type="button"
          onClick={reopen}
          className={cn(
            FRAME,
            'fixed bottom-4 left-4 z-40 flex items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-semibold shadow-lg hover:bg-zinc-800',
          )}
        >
          <Compass className="size-4 text-zinc-400" aria-hidden /> {text(config.pill)}
        </button>
      )}

      <Sheet open={panelOpen} onOpenChange={setPanelOpen}>
        <SheetContent side="right" className="overflow-y-auto font-sans sm:max-w-md">
          <SheetHeader>
            <p className="font-mono text-[0.65rem] tracking-[0.12em] text-muted-foreground uppercase">
              {text(config.tag)}
            </p>
            <SheetTitle>{text(config.how)}</SheetTitle>
            <SheetDescription>{text(config.panel.lede)}</SheetDescription>
          </SheetHeader>
          <div className="space-y-6 px-4 text-sm leading-relaxed">
            <section>
              <h3 className="font-semibold">{text(config.panel.whatTitle)}</h3>
              <p className="mt-1 text-muted-foreground">{text(config.panel.what)}</p>
            </section>
            <section>
              <h3 className="font-semibold">{text(config.panel.pathTitle)}</h3>
              <ol className="mt-2 space-y-2">
                {config.panel.steps.map((step, index) => (
                  <li key={step.title.en} className="flex gap-3 rounded-md border p-3">
                    <span className="grid size-6 shrink-0 place-items-center rounded-full bg-zinc-900 text-xs font-semibold text-white">
                      {index + 1}
                    </span>
                    <div>
                      <p className="font-medium">{text(step.title)}</p>
                      <p className="text-muted-foreground">{text(step.body)}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
            <section>
              <h3 className="font-semibold">{text(config.panel.tryTitle)}</h3>
              <ul className="mt-2 list-disc space-y-1.5 pl-5 text-muted-foreground">
                {config.panel.tries.map((item) => (
                  <li key={item.en}>{text(item)}</li>
                ))}
              </ul>
            </section>
          </div>
          <SheetFooter>
            <a
              href={config.repoUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground hover:underline"
            >
              <BookOpen className="size-4" aria-hidden /> {text(config.panel.repo)}
            </a>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
  )
}
