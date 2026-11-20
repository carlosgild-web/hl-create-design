import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { getDepartments, getRecentDesigns, proposeAction } from '@/api/client'
import { FORM_FIELDS, type Action, type PreviewTarget } from '@/api/types'
import { AssistantPanel } from '@/components/AssistantPanel'
import { DesignForm } from '@/components/DesignForm'
import { Header } from '@/components/Header'
import { PreviewPane } from '@/components/PreviewPane'
import { RecentDesigns } from '@/components/RecentDesigns'
import { StepsDrawer } from '@/components/StepsDrawer'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useChat } from '@/hooks/useChat'
import { useDesignForm } from '@/hooks/useDesignForm'
import { DESKTOP, useMediaQuery } from '@/hooks/useMediaQuery'
import { useValidation } from '@/hooks/useValidation'
import { useI18n } from '@/i18n'
import { filledValues, isFilled } from '@/lib/fields'

export default function CreateDesignPage() {
  const { lang, t } = useI18n()
  const queryClient = useQueryClient()
  const departments = useQuery({ queryKey: ['departments'], queryFn: getDepartments, retry: false })

  const form = useDesignForm()
  const validation = useValidation(form.values)
  const recentDesigns = useQuery({ queryKey: ['recent-designs'], queryFn: getRecentDesigns, retry: false })
  const lastDesigner = recentDesigns.data?.[0]?.designer

  // Picking a department pre-fills its number prefix (HL-HW-26-), from the backend's rules.
  const prefix = validation?.suggest?.design_number_prefix
  const prefillNumber = form.prefillNumber
  useEffect(() => {
    if (prefix && form.values.department && prefix.includes(`-${form.values.department}-`)) prefillNumber(prefix)
  }, [prefix, form.values.department, prefillNumber])
  const [preview, setPreview] = useState<PreviewTarget | null>(null)
  const [opening, setOpening] = useState(false)
  const previewRef = useRef<HTMLDivElement>(null)
  const desktop = useMediaQuery(DESKTOP)
  const [sideTab, setSideTab] = useState<SideTab>('recent')
  const [mobileTab, setMobileTab] = useState<MobileTab>('form')

  const valuesRef = useRef(form.values)
  useEffect(() => {
    valuesRef.current = form.values
  }, [form.values])

  const chat = useChat({
    language: lang,
    getForm: () => filledValues(valuesRef.current) as Record<string, string>,
    onFormProposal: form.propose,
  })

  async function openCard(kind: 'create_design' | 'reserve_number') {
    setOpening(true)
    try {
      const v = form.values
      const payload = Object.fromEntries(
        FORM_FIELDS.filter((f) => isFilled(f, v[f]) && (kind === 'create_design' || (f !== 'design_number' && f !== 'revision'))).map(
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
    setSideTab('preview')
    setMobileTab('preview')
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

  const designForm = (
    <DesignForm
      values={form.values}
      source={form.source}
      suggestions={form.suggestions}
      errors={form.errors}
      validation={validation}
      created={form.created}
      sameAsCreated={form.sameAsCreated}
      departments={departments.data ?? []}
      lastDesigner={lastDesigner}
      busy={opening}
      onChange={form.edit}
      onTakeSuggestion={form.takeSuggestion}
      onReserve={() => void openCard('reserve_number')}
      onCreate={() => void openCard('create_design')}
      onNewDesign={form.reset}
    />
  )
  const assistant = (
    <AssistantPanel
      timeline={chat.timeline}
      actions={chat.actions}
      busy={chat.busy}
      activity={chat.activity}
      onSend={(text) => {
        setMobileTab('assistant')
        void chat.send(text)
      }}
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
  )
  const previewPane = (
    <div ref={previewRef}>
      <PreviewPane target={preview} />
    </div>
  )
  const recent = <RecentDesigns selected={preview} onSelect={show} />
  const waitingCards = Object.values(chat.actions).filter((a) => a.status === 'pending').length

  if (desktop) {
    // One screen, no page scroll: the chat (left) and the side tabs scroll inside.
    return (
      <div className="flex h-svh min-h-[40rem] flex-col overflow-hidden bg-background">
        <Header />
        <main className="mx-auto grid min-h-0 w-full max-w-[100rem] flex-1 grid-cols-[minmax(22rem,2fr)_3fr] gap-4 px-4 pb-4">
          <div className="min-h-0">{assistant}</div>
          <div className="flex min-h-0 flex-col gap-3">
            <div className="shrink-0">{designForm}</div>
            <Tabs value={sideTab} onValueChange={(v) => setSideTab(v as SideTab)} className="min-h-0 flex-1 gap-2">
              <TabsList aria-label={t('layout.side')} className="shrink-0">
                <TabsTrigger value="preview">{t('preview.title')}</TabsTrigger>
                <TabsTrigger value="recent">{t('recent.title')}</TabsTrigger>
              </TabsList>
              {/* pb-14: room for the demo-guide pill, which floats bottom right here */}
              <TabsContent value="preview" className="min-h-0 flex-1 overflow-y-auto pb-14">
                {previewPane}
              </TabsContent>
              <TabsContent value="recent" className="min-h-0 flex-1 overflow-y-auto pb-14">
                {recent}
              </TabsContent>
            </Tabs>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-svh bg-background">
      <Header />
      {/* pb-20: the floating demo-guide pill (bottom left) never covers the last card */}
      {(
        <main className="mx-auto max-w-7xl px-4 pb-20">
          <Tabs value={mobileTab} onValueChange={(v) => setMobileTab(v as MobileTab)}>
            <TabsList aria-label={t('layout.sections')} className="sticky top-0 z-10">
              <TabsTrigger value="form">{t('layout.form')}</TabsTrigger>
              <TabsTrigger value="assistant">
                {t('chat.title')}
                {waitingCards > 0 && mobileTab !== 'assistant' && (
                  <span
                    aria-label={t('layout.waiting', { count: waitingCards })}
                    className="grid size-4 place-items-center rounded-full bg-primary text-[0.6rem] text-primary-foreground"
                  >
                    {waitingCards}
                  </span>
                )}
              </TabsTrigger>
              <TabsTrigger value="preview">{t('preview.title')}</TabsTrigger>
            </TabsList>
            <TabsContent value="form" forceMount className="data-[state=inactive]:hidden">
              {designForm}
            </TabsContent>
            <TabsContent value="assistant" forceMount className="h-[calc(100svh-9rem)] min-h-96 data-[state=inactive]:hidden">
              {assistant}
            </TabsContent>
            <TabsContent value="preview" className="space-y-4">
              {previewPane}
              {recent}
            </TabsContent>
          </Tabs>
        </main>
      )}
    </div>
  )
}

type SideTab = 'preview' | 'recent'
type MobileTab = 'form' | 'assistant' | 'preview'
