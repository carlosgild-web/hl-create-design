import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useRef, useState } from 'react'

import { getDepartments, proposeAction } from '@/api/client'
import {
  FORM_FIELDS,
  type Action,
  type FormField,
  type FormValues,
  type Issue,
  type PreviewTarget,
} from '@/api/types'
import { AssistantPanel } from '@/components/AssistantPanel'
import { DesignForm } from '@/components/DesignForm'
import { Header } from '@/components/Header'
import { PreviewPane } from '@/components/PreviewPane'
import { RecentDesigns } from '@/components/RecentDesigns'
import { StepsDrawer } from '@/components/StepsDrawer'
import { useChat } from '@/hooks/useChat'
import { useI18n } from '@/i18n'

const EMPTY: FormValues = { department: '', design_number: '', revision: '', name: '', designer: '' }

export default function CreateDesignPage() {
  const { lang } = useI18n()
  const queryClient = useQueryClient()
  const departments = useQuery({ queryKey: ['departments'], queryFn: getDepartments, retry: false })

  const [values, setValues] = useState<FormValues>(EMPTY)
  const [proposed, setProposed] = useState<ReadonlySet<FormField>>(new Set())
  const [errors, setErrors] = useState<Issue[]>([])
  const [preview, setPreview] = useState<PreviewTarget | null>(null)
  const [opening, setOpening] = useState(false)

  const valuesRef = useRef(values)
  valuesRef.current = values

  const fill = useCallback((fields: Partial<FormValues>) => {
    const known = FORM_FIELDS.filter((f) => typeof fields[f] === 'string' && fields[f] !== '')
    setValues((v) => ({ ...v, ...Object.fromEntries(known.map((f) => [f, fields[f]])) }))
    setProposed((p) => new Set([...p, ...known]))
  }, [])

  const chat = useChat({
    language: lang,
    getForm: () => Object.fromEntries(FORM_FIELDS.filter((f) => valuesRef.current[f]).map((f) => [f, valuesRef.current[f]])),
    onFormProposal: fill,
  })

  function edit(field: FormField, value: string) {
    setValues((v) => ({ ...v, [field]: value }))
    // Once the user touches a suggested field it is theirs: no more highlight.
    setProposed((p) => {
      if (!p.has(field)) return p
      const next = new Set(p)
      next.delete(field)
      return next
    })
    setErrors((all) => all.filter((e) => e.field !== field))
  }

  async function openCard(kind: 'create_design' | 'reserve_number') {
    setOpening(true)
    try {
      const payload = Object.fromEntries(
        FORM_FIELDS.filter((f) => values[f].trim() && (kind === 'create_design' || f !== 'design_number' && f !== 'revision')).map((f) => [f, values[f].trim()]),
      )
      chat.addAction(await proposeAction(kind, payload, chat.conversationId))
    } finally {
      setOpening(false)
    }
  }

  function onActionChange(action: Action) {
    chat.putAction(action)
    setErrors(action.status === 'failed' ? (action.result.errors ?? []) : [])
    if (action.status === 'confirmed') {
      void queryClient.invalidateQueries({ queryKey: ['recent-designs'] })
      if (action.kind === 'create_design') showPreview(action)
    }
  }

  function showPreview(action: Action) {
    const { design_number, revision } = action.result
    const department = action.payload.department
    if (design_number && revision && department) {
      setPreview({ department, design_number, revision })
    }
  }

  function useNumber(action: Action) {
    const { design_number, revision, department } = action.result
    fill({ design_number, revision: revision ?? 'A', department })
  }

  return (
    <div className="min-h-svh bg-background">
      <Header />
      <main className="mx-auto grid max-w-7xl gap-4 px-4 pb-8 lg:grid-cols-2">
        <div className="space-y-4">
          <DesignForm
            values={values}
            proposed={proposed}
            errors={errors}
            departments={departments.data ?? []}
            busy={opening}
            onChange={edit}
            onReserve={() => void openCard('reserve_number')}
            onCreate={() => void openCard('create_design')}
          />
          <RecentDesigns onSelect={setPreview} />
        </div>
        <div className="space-y-4">
          <AssistantPanel
            timeline={chat.timeline}
            actions={chat.actions}
            busy={chat.busy}
            activity={chat.activity}
            onSend={(text) => void chat.send(text)}
            onStop={() => void chat.stop()}
            onNewConversation={chat.reset}
            onSwitch={(to) => void chat.switchTo(to)}
            onActionChange={onActionChange}
            onUseNumber={useNumber}
            onShowPreview={showPreview}
            stepsButton={<StepsDrawer steps={chat.steps} runId={chat.runId} />}
          />
          <PreviewPane target={preview} />
        </div>
      </main>
    </div>
  )
}
