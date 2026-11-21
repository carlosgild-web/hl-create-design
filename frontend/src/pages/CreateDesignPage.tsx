import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import { getDepartments, getRecentDesigns, listSapDesigns, proposeAction } from '@/api/client'
import { FORM_FIELDS, type Action, type ActionKind, type FormMode, type FormValues, type PreviewTarget } from '@/api/types'
import { AssistantPanel } from '@/components/AssistantPanel'
import { DesignForm } from '@/components/DesignForm'
import { Header } from '@/components/Header'
import { PreviewDialog } from '@/components/PreviewDialog'
import { RecentDesigns } from '@/components/RecentDesigns'
import { StartPanel } from '@/components/StartPanel'
import { StepsDrawer } from '@/components/StepsDrawer'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { samePayload, useChat } from '@/hooks/useChat'
import { useDesignForm } from '@/hooks/useDesignForm'
import { DESKTOP, WIDE, useMediaQuery } from '@/hooks/useMediaQuery'
import { useValidation } from '@/hooks/useValidation'
import { useI18n } from '@/i18n'
import { blockers, filledValues, isFilled } from '@/lib/fields'

export default function CreateDesignPage() {
  const { lang, t } = useI18n()
  const queryClient = useQueryClient()
  const departments = useQuery({ queryKey: ['departments'], queryFn: getDepartments, retry: false })
  const recentDesigns = useQuery({ queryKey: ['recent-designs'], queryFn: getRecentDesigns, retry: false })
  const sapDesigns = useQuery({ queryKey: ['sap-designs'], queryFn: listSapDesigns, retry: false })

  const form = useDesignForm()
  const { validation, checking } = useValidation(form.values)
  const lastDesigner = recentDesigns.data?.[0]?.designer
  const [preview, setPreview] = useState<PreviewTarget | null>(null)
  const [opening, setOpening] = useState(false)
  const [reservation, setReservation] = useState<Action | null>(null)
  const [aiSelected, setAiSelected] = useState<string | null>(null)
  const desktop = useMediaQuery(DESKTOP)
  const wide = useMediaQuery(WIDE)
  const [mobileTab, setMobileTab] = useState<MobileTab>('design')

  const formRef = useRef({ values: form.values, mode: form.mode })
  useEffect(() => {
    formRef.current = { values: form.values, mode: form.mode }
  }, [form.values, form.mode])

  // The assistant names a number SAP knows: show it as that existing design, never silently.
  const sapRef = useRef(sapDesigns.data)
  useEffect(() => {
    sapRef.current = sapDesigns.data
  }, [sapDesigns.data])
  const { propose, selectExisting } = form
  const onFormProposal = useCallback(
    async (fields: Partial<FormValues>) => {
      if (fields.design_number) {
        // the list may still be loading when the assistant answers fast
        const list =
          sapRef.current ??
          (await queryClient
            .fetchQuery({ queryKey: ['sap-designs'], queryFn: listSapDesigns })
            .catch(() => undefined))
        const known = list?.find((d) => d.design_number === fields.design_number)
        if (known && known.selectable && formRef.current.values.design_number !== known.design_number) {
          selectExisting(known)
          setAiSelected(known.design_number)
          // SAP set these just now; the rest of the proposal (the designer) still applies
          const { designer } = fields
          if (designer) propose({ designer })
          return
        }
      }
      propose(fields)
    },
    [propose, queryClient, selectExisting],
  )

  const chat = useChat({
    language: lang,
    // the assistant sees the mode with the values (decision 0018), as data (invariant 7)
    getForm: () => ({ ...(filledValues(formRef.current.values) as Record<string, string>), mode: formRef.current.mode }),
    onFormProposal,
  })

  function cardPayload(kind: ActionKind) {
    const v = form.values
    return Object.fromEntries(
      FORM_FIELDS.filter(
        (f) =>
          isFilled(f, v[f]) &&
          (kind === 'create_design' || (f !== 'design_number' && f !== 'revision' && f !== 'description')),
      ).map((f) => [f, v[f].trim()]),
    )
  }

  /** Bring a card into view and put the focus on its Confirm button. */
  function showCard(id: string) {
    setMobileTab('assistant')
    requestAnimationFrame(() => {
      const card = document.querySelector<HTMLElement>(`[data-action-id="${id}"]`)
      card?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
      card?.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true })
    })
  }

  async function openCard(kind: ActionKind) {
    const payload = cardPayload(kind)
    // The same request is already waiting (the assistant opened it, or a second click):
    // show that card instead of a copy.
    const waiting = chat.waitingCard(kind, payload)
    if (waiting) {
      showCard(waiting.id)
      return
    }
    setOpening(true)
    try {
      const action = await proposeAction(kind, payload, chat.conversationId)
      chat.addAction(action)
      showCard(action.id)
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
      // The number comes from SAP: fill it at once (the card and the panel offer Undo).
      form.fillFromSap(action.id, {
        design_number,
        revision: revision ?? 'A',
        department: action.result.department ?? action.payload.department,
      })
      setReservation(action)
      void queryClient.invalidateQueries({ queryKey: ['sap-designs'] })
    }
    if (action.kind === 'create_design') {
      if (design_number && revision) form.markCreated(design_number, revision)
      showPreview(action)
      void queryClient.invalidateQueries({ queryKey: ['sap-designs'] }) // next free revision moved on
    }
  }

  function showPreview(action: Action) {
    const { design_number, revision, folder, name } = action.result
    const department = action.payload.department
    if (design_number && revision && department) {
      setPreview({ department, design_number, revision, folder, name: name ?? action.payload.name })
    }
  }

  function useNumber(action: Action) {
    const { design_number, revision, department } = action.result
    form.fillFromSap(action.id, { design_number, revision: revision ?? 'A', department: department ?? action.payload.department })
    setReservation(action)
  }

  function changeMode(mode: FormMode) {
    form.startOver(mode)
    chat.retire()
    setReservation(null)
    setAiSelected(null)
  }

  const v = form.values
  const dirty =
    form.mode === 'existing'
      ? form.selected !== null
      : Boolean(v.department || v.name.trim() || isFilled('design_number', v.design_number))
  // After a create, a new number only after "New design" (no second reservation from the same values).
  const canReserve =
    Boolean(v.department.trim() && v.name.trim() && v.designer.trim()) && !v.design_number && form.created === null
  const statusNotes =[...(validation?.errors ?? []), ...(validation?.warnings ?? [])].filter((i) => i.field === 'status')

  const startPanel = (
    <StartPanel
      mode={form.mode}
      dirty={dirty}
      onModeChange={changeMode}
      departments={departments.data ?? []}
      canReserve={canReserve}
      missingFields={blockers('new', v, 0).flatMap((b) => (b.key === 'need_field' ? [b.field] : []))}
      busy={opening}
      onReserve={() => void openCard('reserve_number')}
      reservation={form.mode === 'new' && v.design_number ? reservation : null}
      canUndoReservation={reservation ? form.canUndo(reservation.id) : false}
      onUndoReservation={() => {
        if (reservation) form.undoFill(reservation.id)
        setReservation(null)
      }}
      designs={sapDesigns}
      selected={form.selected}
      onSelect={(design) => {
        form.selectExisting(design)
        setAiSelected(null)
      }}
      onChangeDesign={() => changeMode('existing')}
      statusNotes={statusNotes}
      aiSelected={aiSelected}
      showRecent={desktop}
      recentCount={recentDesigns.data?.length}
      onPreview={setPreview}
      compact={desktop && !wide}
    />
  )
  const designForm = (
    <DesignForm
      mode={form.mode}
      locked={form.locked}
      values={form.values}
      source={form.source}
      suggestions={form.suggestions}
      errors={form.errors}
      validation={validation}
      checking={checking}
      created={form.created}
      sameAsCreated={form.sameAsCreated}
      departments={departments.data ?? []}
      lastDesigner={lastDesigner}
      busy={opening}
      onChange={form.edit}
      onTakeSuggestion={form.takeSuggestion}
      onCreate={() => void openCard('create_design')}
      cardWaiting={Object.values(chat.actions).some(
        (a) => a.status === 'pending' && a.kind === 'create_design' && samePayload(a.payload, cardPayload('create_design')),
      )}
      canReserve={canReserve}
      onReserve={() => void openCard('reserve_number')}
      // the wide layout: as tall as the other two columns (less the room kept for the guide pill)
      className={desktop && wide ? 'min-h-[calc(100%-3.5rem)]' : undefined}
      onNewDesign={() => {
        form.reset()
        chat.retire()
        setReservation(null)
        setAiSelected(null)
      }}
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
      epoch={chat.epoch}
      departments={departments.data ?? []}
      stepsButton={<StepsDrawer steps={chat.steps} runId={chat.runId} />}
    />
  )
  const dialog = <PreviewDialog target={preview} onClose={() => setPreview(null)} />
  const waitingCards = Object.values(chat.actions).filter((a) => a.status === 'pending').length

  if (desktop) {
    // One screen, no page scroll: each column scrolls inside (decision 0018).
    return (
      <div className="flex h-svh min-h-[40rem] flex-col overflow-hidden bg-background">
        <Header />
        {wide ? (
          <main className="mx-auto grid min-h-0 w-full max-w-[110rem] flex-1 grid-cols-[minmax(20rem,1.6fr)_minmax(17rem,1fr)_minmax(28rem,2.2fr)] gap-4 px-4 pb-4">
            <div className="min-h-0">{assistant}</div>
            <div className="min-h-0">{startPanel}</div>
            <div className="min-h-0 overflow-y-auto pb-14">{designForm}</div>
          </main>
        ) : (
          <main className="mx-auto grid min-h-0 w-full flex-1 grid-cols-[minmax(20rem,2fr)_3fr] gap-4 px-4 pb-4">
            <div className="min-h-0">{assistant}</div>
            <div className="flex min-h-0 flex-col gap-3 overflow-y-auto pb-14">
              <div className="shrink-0">{startPanel}</div>
              <div className="shrink-0">{designForm}</div>
            </div>
          </main>
        )}
        {dialog}
      </div>
    )
  }

  return (
    <div className="min-h-svh bg-background">
      <Header />
      {/* pb-20: the floating demo-guide pill (bottom left) never covers the last card */}
      <main className="mx-auto max-w-7xl px-4 pb-20">
        <Tabs value={mobileTab} onValueChange={(value) => setMobileTab(value as MobileTab)}>
          <TabsList aria-label={t('layout.sections')} className="sticky top-0 z-10">
            <TabsTrigger value="design">{t('layout.design')}</TabsTrigger>
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
            <TabsTrigger value="recent">{t('recent.title')}</TabsTrigger>
          </TabsList>
          <TabsContent value="design" forceMount className="space-y-4 data-[state=inactive]:hidden">
            {startPanel}
            {designForm}
          </TabsContent>
          <TabsContent
            value="assistant"
            forceMount
            className="h-[calc(100svh-11.5rem)] min-h-96 data-[state=inactive]:hidden"
          >
            {assistant}
          </TabsContent>
          <TabsContent value="recent">
            <RecentDesigns onPreview={setPreview} />
          </TabsContent>
        </Tabs>
      </main>
      {dialog}
    </div>
  )
}

type MobileTab = 'design' | 'assistant' | 'recent'
