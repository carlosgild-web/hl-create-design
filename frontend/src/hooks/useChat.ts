import { useCallback, useRef, useState } from 'react'

import { streamChat } from '@/api/sse'
import type { Action, ChatEvent, FormValues, SapDesign } from '@/api/types'
import type { Lang } from '@/i18n'

export type TimelineItem =
  | { id: number; kind: 'user'; text: string }
  | { id: number; kind: 'assistant'; text: string }
  | { id: number; kind: 'error'; text: string }
  | { id: number; kind: 'switched'; to: string; model: string }
  | { id: number; kind: 'sap'; design: SapDesign; notes: { message: string; ref: string }[] }
  | { id: number; kind: 'action'; actionId: string }

export type Step = { id: string; name: string; arguments?: Record<string, unknown>; ok?: boolean; result?: unknown }

type Options = {
  language: Lang
  getForm: () => Partial<FormValues>
  onFormProposal: (fields: Partial<FormValues>) => void
}

/**
 * The assistant conversation: streams one turn at a time and keeps the timeline, the
 * confirmation cards (by action id) and the agent steps of the latest turn.
 */
export function useChat({ language, getForm, onFormProposal }: Options) {
  const [timeline, setTimeline] = useState<TimelineItem[]>([])
  const [actions, setActions] = useState<Record<string, Action>>({})
  const [steps, setSteps] = useState<Step[]>([])
  const [busy, setBusy] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [runId, setRunId] = useState<number | null>(null)
  const nextId = useRef(1)
  const abort = useRef<AbortController | null>(null)
  const conversation = useRef<string | null>(null)

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
        case 'thinking':
          break
        case 'tool_call':
          setSteps((s) => [...s, { id: event.data.id, name: event.data.name, arguments: event.data.arguments }])
          break
        case 'tool_result': {
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
          push({ kind: 'error', text: event.data.message })
          break
        case 'notice':
          if (event.data.code === 'provider_switched') {
            push({ kind: 'switched', to: event.data.to, model: event.data.model })
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
        setBusy(false)
        abort.current = null
      }
    },
    [busy, getForm, handle, language, push],
  )

  const stop = useCallback(() => abort.current?.abort(), [])

  return { timeline, actions, steps, busy, conversationId, runId, send, stop, addAction, putAction }
}

type DistributiveOmit<T, K extends keyof never> = T extends unknown ? Omit<T, K> : never
