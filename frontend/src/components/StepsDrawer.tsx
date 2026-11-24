import { useQuery } from '@tanstack/react-query'

import { getRun } from '@/api/client'
import type { Step } from '@/hooks/useChat'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { useI18n, type MessageKey } from '@/i18n'

/** Shows what the agent called and what it got back (invariant 6: nothing is hidden). */
const STATUS_KEYS: Record<string, MessageKey> = {
  running: 'run.status.running',
  answered: 'run.status.answered',
  limit: 'run.status.limit',
  error: 'run.status.error',
  cancelled: 'run.status.cancelled',
  timeout: 'run.status.timeout',
}

export function StepsDrawer({ steps, runId }: { steps: Step[]; runId: number | null }) {
  const { t, tn } = useI18n()
  const run = useQuery({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId as number),
    enabled: runId != null,
    retry: false,
  })
  const answeredWithoutTools = steps.length === 0 && run.data != null && run.data.model_calls > 0

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button size="sm" variant="ghost">
          {t('steps.open')}
          {steps.length > 0 && ` (${steps.length})`}
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg" closeLabel={t('steps.close')}>
        <SheetHeader className="pr-12">
          <SheetTitle>{t('steps.title')}</SheetTitle>
          <SheetDescription>
            {run.data
              ? t('steps.run', {
                  id: run.data.id,
                  provider: run.data.provider,
                  model: run.data.model,
                  calls: tn('steps.calls', run.data.model_calls),
                  status: STATUS_KEYS[run.data.status] ? t(STATUS_KEYS[run.data.status]) : run.data.status,
                })
              : ''}
          </SheetDescription>
        </SheetHeader>
        <ol className="space-y-3 px-4 pb-4 text-sm">
          {steps.length === 0 && (
            <li className="text-muted-foreground">{t(answeredWithoutTools ? 'steps.no_tools' : 'steps.empty')}</li>
          )}
          {steps.map((step) => (
            <li key={step.id} className="rounded-lg border p-2">
              <p className="tabular-nums font-medium">
                {step.name}
                {step.auto && <span className="ml-2 text-xs font-normal text-muted-foreground">{t('steps.auto')}</span>}
                {step.ok === false && <span className="ml-2 text-destructive">✕</span>}
              </p>
              <pre className="mt-1 overflow-x-auto text-xs text-muted-foreground">
                {JSON.stringify(step.arguments ?? {}, null, 1)}
              </pre>
              {step.result !== undefined && (
                <details className="mt-1">
                  <summary className="cursor-pointer text-xs">{t('steps.result')}</summary>
                  <pre className="mt-1 max-h-60 overflow-auto text-xs">{JSON.stringify(step.result, null, 1)}</pre>
                </details>
              )}
            </li>
          ))}
        </ol>
      </SheetContent>
    </Sheet>
  )
}
