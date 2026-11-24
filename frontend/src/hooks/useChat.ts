import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useRef, useState } from 'react'

import { cancelAction, cancelRun, switchProvider } from '@/api/client'
import { streamChat } from '@/api/sse'
import { FORM_FIELDS, type Action, type ChatEvent, type FormValues, type Issue, type SapDesign, type SwitchTarget } from '@/api/types'
import type { Lang } from '@/i18n'

export type TimelineItem =
  | { id: number; kind: 'user'; text: string }
  | { id: number; kind: 'assistant'; text: string }
  | { id: number; kind: 'error'; text: string; code?: string; timeoutS?: number; switchTo?: SwitchTarget[] }
  | { id: number; kind: 'switched'; from?: string; to: string; model: string; by: 'quota' | 'user' | 'busy'; provider?: string }
  | { id: number; kind: 'stopped' }
  | { id: number; kind: 'sap'; design: SapDesign; notes: Issue[] }
  | { id: number; kind: 'action'; actionId: string; epoch: number }
  | { id: number; kind: 'divider'; cancelled: boolean }

/** One tool call in Agent steps. `auto`: Create Design searched the manual itself (decision 0024). */
export type Step = { id: string; name: string; arguments?: Record<string, unknown>; ok?: boolean; result?: unknown; auto?: boolean }

/** What the assistant is doing right now, shown instead of a bare "Thinking…". */
export type Activity =
  | { kind: 'thinking' }
  | { kind: 'tool'; name: string }
  | { kind: 'rate_limited'; waitS: number; provider: string }

type Options = {
  language: Lang
  getForm: () => Record<string, string> // form values plus `mode`, sent as data
  onFormProposal: (fields: Partial<FormValues>) => void
}

/** After Stop, wait this long for the backend's `done` before dropping the stream. */
const STOP_GRACE_MS = 3000

// Payload values are not always strings (an assistant card can carry null SAP fields).
const loose = (value: unknown) =>
  String(value ?? '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase()

/** The same request as a card's payload: the form's fields, give or take the formatting
 * the backend adds (`bead sorter` is stored as `Bead Sorter`). What the assistant's card
 * adds from SAP (material, project) is not something the form asks for. */
export function samePayload(a: Record<string, unknown>, b: Record<string, unknown>) {
  return FORM_FIELDS.every((k) => loose(a[k]) === loose(b[k]))
}

/**
 * The assistant conversation: streams one turn at a time and keeps the timeline, the
 * confirmation cards (by action id), the agent steps of the latest turn and what the
 * assistant is doing while it works.
 */
export function useChat({ language, getForm, onFormProposal }: Options) {
  const queryClient = useQueryClient()
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

  const [epoch, setEpoch] = useState(0)
  const epochRef = useRef(0)
  const actionsRef = useRef<Record<string, Action>>({})

  const putAction = useCallback((action: Action) => {
    actionsRef.current = { ...actionsRef.current, [action.id]: action }
    setActions((all) => ({ ...all, [action.id]: action }))
  }, [])

  /** Cancel waiting cards (a cancel never has a side effect: invariant 2 holds). */
  const cancelWaiting = useCallback(
    async (keep: (action: Action) => boolean) => {
      const waiting = Object.values(actionsRef.current).filter((a) => a.status === 'pending' && !keep(a))
      await Promise.all(
        waiting.map((a) =>
          cancelAction(a.id)
            .then(({ action }) => putAction(action))
            .catch(() => putAction({ ...a, status: 'cancelled' })),
        ),
      )
    },
    [putAction],
  )

  /** The waiting card of this kind that already asks for this, if any. */
  const waitingCard = useCallback(
    (kind: Action['kind'], payload: Record<string, string>) =>
      Object.values(actionsRef.current).find(
        (a) => a.status === 'pending' && a.kind === kind && samePayload(a.payload, payload),
      ) ?? null,
    [],
  )

  /** One live card per kind: a new card replaces (cancels) an older waiting one. */
  const openCard = useCallback(
    (action: Action) => {
      void cancelWaiting((a) => a.kind !== action.kind || a.id === action.id)
      putAction(action)
      push({ kind: 'action', actionId: action.id, epoch: epochRef.current })
    },
    [cancelWaiting, push, putAction],
  )

  /** A card opened outside the chat stream (the form's buttons). */
  const addAction = useCallback(
    (action: Action) => {
      setConversation(action.conversation_id)
      openCard(action)
    },
    [openCard, setConversation],
  )

  /** The form started over (mode switch, New design): waiting cards are cancelled and the
   * earlier ones lose their buttons, so none of them can change the new form. */
  const retire = useCallback(() => {
    const cards = Object.values(actionsRef.current)
    const cancelled = cards.some((a) => a.status === 'pending')
    void cancelWaiting(() => false)
    epochRef.current += 1
    setEpoch(epochRef.current)
    // Say "cancelled" only when a card was waiting; finished cards stay in the history.
    if (cards.length > 0) push({ kind: 'divider', cancelled })
  }, [cancelWaiting, push])

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
          setSteps((s) => [...s, { id: event.data.id, name: event.data.name, arguments: event.data.arguments, auto: event.data.auto }])
          break
        case 'tool_result': {
          setActivity({ kind: 'thinking' })
          setSteps((s) =>
            s.map((x) => (x.id === event.data.id ? { ...x, ok: event.data.ok, result: event.data.result } : x)),
          )
          const result = event.data.result as {
            found?: boolean
            design?: SapDesign
            status_notes?: Issue[]
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
          openCard(event.data.action)
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
            push({ kind: 'switched', from: event.data.from, to: event.data.to, model: event.data.model, by: 'quota' })
            void queryClient.invalidateQueries({ queryKey: ['health'] })
          } else if (event.data.code === 'model_switched') {
            push({ kind: 'switched', from: event.data.from, to: event.data.to, model: event.data.model, by: 'busy', provider: event.data.provider })
          }
          break
        case 'done':
          if (event.data.run_id != null) setRunId(event.data.run_id)
          break
      }
    },
    [onFormProposal, openCard, push, queryClient, setConversation],
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
          { message, conversation_id: conversation.current, language, form: getForm() },
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
    actionsRef.current = {}
    setActions({})
    setSteps([])
  }, [busy])

  /** The user's choice after a stuck turn. */
  const switchTo = useCallback(
    async (to: SwitchTarget) => {
      try {
        const now = await switchProvider(to)
        push({ kind: 'switched', to: now.provider, model: now.model, by: 'user' })
        void queryClient.invalidateQueries({ queryKey: ['health'] }) // the header's model badge
      } catch (error) {
        push({ kind: 'error', text: error instanceof Error ? error.message : String(error) })
      }
    },
    [push, queryClient],
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
    waitingCard,
    retire,
    epoch,
  }
}

type DistributiveOmit<T, K extends keyof never> = T extends unknown ? Omit<T, K> : never
