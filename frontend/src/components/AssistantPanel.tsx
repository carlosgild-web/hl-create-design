import { useEffect, useRef, useState } from 'react'
import { Loader2, MessageSquarePlus } from 'lucide-react'

import type { Action, SwitchTarget } from '@/api/types'
import type { Activity, TimelineItem } from '@/hooks/useChat'
import { ActionCard } from '@/components/ActionCard'
import { SapCard } from '@/components/SapCard'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useI18n, type MessageKey, type Translate } from '@/i18n'
import { cn } from '@/lib/utils'

type Props = {
  timeline: TimelineItem[]
  actions: Record<string, Action>
  busy: boolean
  activity?: Activity | null
  onSend: (text: string) => void
  onStop: () => void
  onNewConversation?: () => void
  onSwitch?: (to: SwitchTarget) => void
  onActionChange: (action: Action) => void
  onUseNumber: (action: Action) => void
  onShowPreview: (action: Action) => void
  stepsButton?: React.ReactNode
}

const TOOL_LABELS: Record<string, MessageKey> = {
  search_design_manual: 'activity.search_design_manual',
  validate_design_request: 'activity.validate_design_request',
  sap_get_design: 'activity.sap',
  sap_list_departments: 'activity.sap',
  check_design_folder: 'activity.check_design_folder',
  propose_form_values: 'activity.propose_form_values',
  request_reserve_number: 'activity.request_card',
  request_create_design: 'activity.request_card',
}

function activityText(activity: Activity | null | undefined, t: Translate): string {
  if (!activity || activity.kind === 'thinking') return t('chat.working')
  if (activity.kind === 'tool') return t(TOOL_LABELS[activity.name] ?? 'chat.working')
  return t('activity.rate_limited', {
    provider: activity.provider === 'groq' ? 'Groq' : activity.provider,
    seconds: Math.ceil(activity.waitS),
  })
}

export function AssistantPanel({
  timeline,
  actions,
  busy,
  activity,
  onSend,
  onStop,
  onNewConversation,
  onSwitch,
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
        <div className="flex items-center gap-1">
          {onNewConversation && timeline.length > 0 && (
            <Button size="sm" variant="ghost" onClick={onNewConversation} disabled={busy}>
              <MessageSquarePlus aria-hidden className="size-4" />
              {t('chat.new')}
            </Button>
          )}
          {stepsButton}
        </div>
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
                if (item.code === 'turn_timeout') {
                  return (
                    <div key={item.id} role="alert" className="space-y-2 rounded-lg border border-destructive/40 px-3 py-2 text-sm">
                      <p className="text-destructive">{t('chat.timeout', { seconds: item.timeoutS ?? '' })}</p>
                      {item.switchTo && item.switchTo.length > 0 && onSwitch && (
                        <div className="flex flex-wrap gap-2">
                          {item.switchTo.map((to) => (
                            <Button key={to} size="sm" variant="outline" onClick={() => onSwitch(to)}>
                              {t(to === 'ollama' ? 'chat.switch.ollama' : 'chat.switch.fake')}
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                }
                return (
                  <p key={item.id} role="alert" className="rounded-lg border border-destructive/40 px-3 py-2 text-sm text-destructive">
                    {t('chat.error', { message: item.text })}
                  </p>
                )
              case 'switched':
                return (
                  <p key={item.id} role="status" className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
                    {item.by === 'user'
                      ? t('chat.switched.user', { name: item.to === 'ollama' ? `Ollama (${item.model})` : t('chat.demo_model') })
                      : t(item.to === 'ollama' ? 'chat.switched.ollama' : 'chat.switched.fake', { model: item.model })}
                  </p>
                )
              case 'stopped':
                return (
                  <p key={item.id} role="status" className="text-center text-xs text-muted-foreground">
                    {t('chat.stopped')}
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
          {busy && (
            <p role="status" className={cn('flex items-center gap-2 text-sm text-muted-foreground')}>
              <Loader2 aria-hidden className="size-4 animate-spin" />
              {activityText(activity, t)}
            </p>
          )}
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
