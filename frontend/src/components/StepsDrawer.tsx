import { useQuery } from '@tanstack/react-query'

import { getRun } from '@/api/client'
import type { Step } from '@/hooks/useChat'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { useI18n } from '@/i18n'

/** Shows what the agent called and what it got back (invariant 6: nothing is hidden). */
export function StepsDrawer({ steps, runId }: { steps: Step[]; runId: number | null }) {
  const { t } = useI18n()
  const run = useQuery({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId as number),
    enabled: runId != null,
    retry: false,
  })

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button size="sm" variant="ghost">
          {t('steps.open')}
          {steps.length > 0 && ` (${steps.length})`}
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{t('steps.title')}</SheetTitle>
          <SheetDescription>
            {run.data
              ? t('steps.run', {
                  id: run.data.id,
                  provider: run.data.provider,
                  model: run.data.model,
                  calls: run.data.model_calls,
                  status: run.data.status,
                })
              : ''}
          </SheetDescription>
        </SheetHeader>
        <ol className="space-y-3 px-4 pb-4 text-sm">
          {steps.length === 0 && <li className="text-muted-foreground">{t('steps.empty')}</li>}
          {steps.map((step) => (
            <li key={step.id} className="rounded-lg border p-2">
              <p className="font-mono font-medium">
                {step.name}
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
