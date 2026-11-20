import { useCallback, useRef, useState } from 'react'

import { cancelRun, switchProvider } from '@/api/client'
import { streamChat } from '@/api/sse'
import type { Action, ChatEvent, FormValues, SapDesign, SwitchTarget } from '@/api/types'
import type { Lang } from '@/i18n'

export type TimelineItem =
  | { id: number; kind: 'user'; text: string }
  | { id: number; kind: 'assistant'; text: string }
  | { id: number; kind: 'error'; text: string; code?: string; timeoutS?: number; switchTo?: SwitchTarget[] }
  | { id: number; kind: 'switched'; to: string; model: string; by: 'quota' | 'user' }
  | { id: number; kind: 'stopped' }
  | { id: number; kind: 'sap'; design: SapDesign; notes: { message: string; ref: string }[] }
  | { id: number; kind: 'action'; actionId: string }

export type Step = { id: string; name: string; arguments?: Record<string, unknown>; ok?: boolean; result?: unknown }

/** What the assistant is doing right now, shown instead of a bare "Thinking…". */
export type Activity =
  | { kind: 'thinking' }
  | { kind: 'tool'; name: string }
  | { kind: 'rate_limited'; waitS: number; provider: string }

type Options = {
  language: Lang
  getForm: () => Partial<FormValues>
  onFormProposal: (fields: Partial<FormValues>) => void
}

/** After Stop, wait this long for the backend's `done` before dropping the stream. */
const STOP_GRACE_MS = 3000

/**
 * The assistant conversation: streams one turn at a time and keeps the timeline, the
 * confirmation cards (by action id), the agent steps of the latest turn and what the
 * assistant is doing while it works.
 */
export function useChat({ language, getForm, onFormProposal }: Options) {
  const [timeline, setTimeline] = useState<TimelineItem[]>([])
  const [actions, setActions] = useState<Record<string, Action>>({})
  const [steps, setSteps] = useState<Step[]>([])
  const [busy, setBusy] = useState(false)
  const [activity, setActivity] = useState<Activity | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [runId, setRunId] = useState<number | null>(null)
  const nextId = useRef(1)
  const abort = useRef<AbortController | null>(null)
  const conversation = useRef<string | null>(null)
  const currentRun = useRef<number | null>(null)
  const stopping = useRef(false)

  const push = useCallback((item: DistributiveOmit<TimelineItem, 'id'>) => {
    setTimeline((items) => [...items, { ...item, id: nextId.current++ } as TimelineItem])
  }, [])

  const setConversation = useCallback((id: string) => {
    conversation.current = id
    setConversationId(id)
  }, [])

  const putAction = useCallback((action: Action) => {
    setActions((all) => ({ ...all, [action.id]: action }))
  }, [])

  /** A card opened outside the chat stream (the form's buttons). */
  const addAction = useCallback(
    (action: Action) => {
      setConversation(action.conversation_id)
      putAction(action)
      push({ kind: 'action', actionId: action.id })
    },
    [push, putAction, setConversation],
  )

  const handle = useCallback(
    (event: ChatEvent) => {
      switch (event.type) {
        case 'conversation':
          setConversation(event.data.id)
          break
        case 'run':
          currentRun.current = event.data.id
          setRunId(event.data.id)
          break
        case 'thinking':
          break
        case 'status':
          if (event.data.kind === 'rate_limited') {
            setActivity({ kind: 'rate_limited', waitS: event.data.wait_s, provider: event.data.provider })
          }
          break
        case 'tool_call':
          setActivity({ kind: 'tool', name: event.data.name })
          setSteps((s) => [...s, { id: event.data.id, name: event.data.name, arguments: event.data.arguments }])
          break
        case 'tool_result': {
          setActivity({ kind: 'thinking' })
          setSteps((s) =>
            s.map((x) => (x.id === event.data.id ? { ...x, ok: event.data.ok, result: event.data.result } : x)),
          )
          const result = event.data.result as {
            found?: boolean
            design?: SapDesign
            status_notes?: { message: string; ref: string }[]
          }
          if (event.data.name === 'sap_get_design' && result.found && result.design) {
            push({ kind: 'sap', design: result.design, notes: result.status_notes ?? [] })
          }
          break
        }
        case 'form_proposal':
          onFormProposal(event.data.fields)
          break
        case 'pending_action':
          putAction(event.data.action)
          push({ kind: 'action', actionId: event.data.action.id })
          break
        case 'message':
          push({ kind: 'assistant', text: event.data.content })
          break
        case 'error':
          push({
            kind: 'error',
            text: event.data.message,
            code: event.data.code,
            timeoutS: event.data.timeout_s,
            switchTo: event.data.can_switch_to,
          })
          break
        case 'notice':
          if (event.data.code === 'provider_switched') {
            push({ kind: 'switched', to: event.data.to, model: event.data.model, by: 'quota' })
          }
          break
        case 'done':
          if (event.data.run_id != null) setRunId(event.data.run_id)
          break
      }
    },
    [onFormProposal, push, putAction, setConversation],
  )

  const send = useCallback(
    async (text: string) => {
      const message = text.trim()
      if (!message || busy) return
      push({ kind: 'user', text: message })
      setSteps([])
      setBusy(true)
      setActivity({ kind: 'thinking' })
      stopping.current = false
      currentRun.current = null
      const controller = new AbortController()
      abort.current = controller
      try {
        for await (const event of streamChat(
          { message, conversation_id: conversation.current, language, form: getForm() as Record<string, string> },
          controller.signal,
        )) {
          handle(event)
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          push({ kind: 'error', text: error instanceof Error ? error.message : String(error) })
        }
      } finally {
        if (stopping.current) push({ kind: 'stopped' })
        stopping.current = false
        setBusy(false)
        setActivity(null)
        abort.current = null
      }
    },
    [busy, getForm, handle, language, push],
  )

  /** Stop: the backend ends the run as `cancelled` (no card opens after this) and the
   * stream finishes; if it does not within a few seconds, the stream is dropped. */
  const stop = useCallback(async () => {
    if (stopping.current || !abort.current) return
    stopping.current = true
    const controller = abort.current
    const run = currentRun.current
    const cancelled = run != null ? await cancelRun(run).catch(() => false) : false
    if (!cancelled) controller.abort()
    else setTimeout(() => controller.abort(), STOP_GRACE_MS)
  }, [])

  /** Start over: a new conversation (the form keeps its values). */
  const reset = useCallback(() => {
    if (busy) return
    conversation.current = null
    currentRun.current = null
    setConversationId(null)
    setRunId(null)
    setTimeline([])
    setActions({})
    setSteps([])
  }, [busy])

  /** The user's choice after a stuck turn. */
  const switchTo = useCallback(
    async (to: SwitchTarget) => {
      try {
        const now = await switchProvider(to)
        push({ kind: 'switched', to: now.provider, model: now.model, by: 'user' })
      } catch (error) {
        push({ kind: 'error', text: error instanceof Error ? error.message : String(error) })
      }
    },
    [push],
  )

  return {
    timeline,
    actions,
    steps,
    busy,
    activity,
    conversationId,
    runId,
    send,
    stop,
    reset,
    switchTo,
    addAction,
    putAction,
  }
}

type DistributiveOmit<T, K extends keyof never> = T extends unknown ? Omit<T, K> : never
