import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { getDepartments, proposeAction } from '@/api/client'
import { FORM_FIELDS, type Action, type PreviewTarget } from '@/api/types'
import { AssistantPanel } from '@/components/AssistantPanel'
import { DesignForm } from '@/components/DesignForm'
import { Header } from '@/components/Header'
import { PreviewPane } from '@/components/PreviewPane'
import { RecentDesigns } from '@/components/RecentDesigns'
import { StepsDrawer } from '@/components/StepsDrawer'
import { useChat } from '@/hooks/useChat'
import { useDesignForm } from '@/hooks/useDesignForm'
import { useValidation } from '@/hooks/useValidation'
import { useI18n } from '@/i18n'

export default function CreateDesignPage() {
  const { lang } = useI18n()
  const queryClient = useQueryClient()
  const departments = useQuery({ queryKey: ['departments'], queryFn: getDepartments, retry: false })

  const form = useDesignForm()
  const validation = useValidation(form.values)
  const [preview, setPreview] = useState<PreviewTarget | null>(null)
  const [opening, setOpening] = useState(false)
  const previewRef = useRef<HTMLDivElement>(null)

  const valuesRef = useRef(form.values)
  useEffect(() => {
    valuesRef.current = form.values
  }, [form.values])

  const chat = useChat({
    language: lang,
    getForm: () => Object.fromEntries(FORM_FIELDS.filter((f) => valuesRef.current[f]).map((f) => [f, valuesRef.current[f]])),
    onFormProposal: form.propose,
  })

  async function openCard(kind: 'create_design' | 'reserve_number') {
    setOpening(true)
    try {
      const v = form.values
      const payload = Object.fromEntries(
        FORM_FIELDS.filter((f) => v[f].trim() && (kind === 'create_design' || (f !== 'design_number' && f !== 'revision'))).map(
          (f) => [f, v[f].trim()],
        ),
      )
      chat.addAction(await proposeAction(kind, payload, chat.conversationId))
    } finally {
      setOpening(false)
    }
  }

  function onActionChange(action: Action) {
    const before = chat.actions[action.id]?.status
    chat.putAction(action)
    form.setErrors(action.status === 'failed' ? (action.result.errors ?? []) : [])
    if (action.status !== 'confirmed' || before === 'confirmed') return
    void queryClient.invalidateQueries({ queryKey: ['recent-designs'] })
    const { design_number, revision } = action.result
    if (action.kind === 'reserve_number' && design_number) {
      // The number comes from SAP: fill it at once (the card offers Undo).
      form.fillFromSap(action.id, { design_number, revision: revision ?? 'A', department: action.result.department ?? action.payload.department })
    }
    if (action.kind === 'create_design') {
      if (design_number && revision) form.markCreated(design_number, revision)
      showPreview(action)
    }
  }

  function show(target: PreviewTarget) {
    setPreview(target)
    // The preview can be below the fold (one column on small screens).
    requestAnimationFrame(() => previewRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' }))
  }

  function showPreview(action: Action) {
    const { design_number, revision } = action.result
    const department = action.payload.department
    if (design_number && revision && department) show({ department, design_number, revision })
  }

  function useNumber(action: Action) {
    const { design_number, revision, department } = action.result
    form.fillFromSap(action.id, { design_number, revision: revision ?? 'A', department: department ?? action.payload.department })
  }

  return (
    <div className="min-h-svh bg-background">
      <Header />
      {/* pb-20: the floating demo-guide pill (bottom left) never covers the last card */}
      <main className="mx-auto grid max-w-7xl gap-4 px-4 pb-20 lg:grid-cols-2">
        <div className="space-y-4">
          <DesignForm
            values={form.values}
            source={form.source}
            suggestions={form.suggestions}
            errors={form.errors}
            validation={validation}
            created={form.created}
            sameAsCreated={form.sameAsCreated}
            departments={departments.data ?? []}
            busy={opening}
            onChange={form.edit}
            onTakeSuggestion={form.takeSuggestion}
            onReserve={() => void openCard('reserve_number')}
            onCreate={() => void openCard('create_design')}
            onNewDesign={form.reset}
          />
          <RecentDesigns selected={preview} onSelect={show} />
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
            onUndoNumber={(action) => form.undoFill(action.id)}
            canUndoNumber={(action) => form.canUndo(action.id)}
            onShowPreview={showPreview}
            departments={departments.data ?? []}
            stepsButton={<StepsDrawer steps={chat.steps} runId={chat.runId} />}
          />
          <div ref={previewRef}>
            <PreviewPane target={preview} />
          </div>
        </div>
      </main>
    </div>
  )
}
