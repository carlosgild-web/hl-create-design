import { useEffect, useRef, useState } from 'react'

import type { Action } from '@/api/types'
import type { TimelineItem } from '@/hooks/useChat'
import { ActionCard } from '@/components/ActionCard'
import { SapCard } from '@/components/SapCard'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'

type Props = {
  timeline: TimelineItem[]
  actions: Record<string, Action>
  busy: boolean
  onSend: (text: string) => void
  onStop: () => void
  onActionChange: (action: Action) => void
  onUseNumber: (action: Action) => void
  onShowPreview: (action: Action) => void
  stepsButton?: React.ReactNode
}

export function AssistantPanel({
  timeline,
  actions,
  busy,
  onSend,
  onStop,
  onActionChange,
  onUseNumber,
  onShowPreview,
  stepsButton,
}: Props) {
  const { t } = useI18n()
  const [draft, setDraft] = useState('')
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end' })
  }, [timeline, busy])

  function submit(text: string) {
    if (!text.trim() || busy) return
    onSend(text)
    setDraft('')
  }

  return (
    <Card className="flex h-full min-h-96 flex-col">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="font-heading text-lg">{t('chat.title')}</CardTitle>
        {stepsButton}
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
        <div className="flex-1 space-y-3 overflow-y-auto pr-1" aria-live="polite">
          {timeline.length === 0 && (
            <div className="space-y-3 text-sm text-muted-foreground">
              <p>{t('chat.empty')}</p>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => submit(t('chat.guided.message'))}>
                  {t('chat.guided')}
                </Button>
                <Button size="sm" variant="outline" onClick={() => submit(t('chat.example.message'))}>
                  {t('chat.example')}
                </Button>
              </div>
            </div>
          )}
          {timeline.map((item) => {
            switch (item.kind) {
              case 'user':
                return (
                  <p key={item.id} className="ml-8 rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
                    {item.text}
                  </p>
                )
              case 'assistant':
                return (
                  <p key={item.id} className="mr-8 whitespace-pre-wrap rounded-lg bg-muted px-3 py-2 text-sm">
                    {item.text}
                  </p>
                )
              case 'error':
                return (
                  <p key={item.id} role="alert" className="rounded-lg border border-destructive/40 px-3 py-2 text-sm text-destructive">
                    {t('chat.error', { message: item.text })}
                  </p>
                )
              case 'sap':
                return <SapCard key={item.id} design={item.design} notes={item.notes} />
              case 'action': {
                const action = actions[item.actionId]
                return action ? (
                  <ActionCard
                    key={item.id}
                    action={action}
                    onChange={onActionChange}
                    onUseNumber={onUseNumber}
                    onShowPreview={onShowPreview}
                  />
                ) : null
              }
            }
          })}
          {busy && <p className={cn('text-sm text-muted-foreground')}>{t('chat.working')}</p>}
          <div ref={end} />
        </div>

        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            submit(draft)
          }}
        >
          <Input
            aria-label={t('chat.placeholder')}
            placeholder={t('chat.placeholder')}
            value={draft}
            maxLength={2000}
            onChange={(e) => setDraft(e.target.value)}
          />
          {busy ? (
            <Button type="button" variant="outline" onClick={onStop}>
              {t('chat.stop')}
            </Button>
          ) : (
            <Button type="submit" disabled={!draft.trim()}>
              {t('chat.send')}
            </Button>
          )}
        </form>
      </CardContent>
    </Card>
  )
}
