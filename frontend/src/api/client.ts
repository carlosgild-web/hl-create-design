import type {
  Action,
  ActionKind,
  Department,
  RecentDesign,
  RunTrace,
  PreviewTarget,
  SapListDesign,
  SwitchTarget,
  Validation,
} from './types'
import type { Lang } from '@/i18n/messages'

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json() as Promise<T>
}

/** `llm_provider` is the model that answers now (`demo` = the rule-based demo assistant). */
export const getHealth = () => fetch('/api/health').then((r) => json<{ llm_provider: string }>(r))

/** One indexed Design Manual passage (`GET /api/manual/{lang}/{document}/{anchor}`). */
export const getManualPassage = (lang: string, source: string) => {
  const [document, anchor] = source.split('#')
  return fetch(`/api/manual/${lang}/${encodeURIComponent(document)}/${encodeURIComponent(anchor)}`).then((r) =>
    json<{ source: string; lang: string; document: string; heading: string; text: string }>(r),
  )
}

export const getDepartments = () => fetch('/api/departments').then((r) => json<Department[]>(r))

export const getRecentDesigns = () => fetch('/api/designs').then((r) => json<RecentDesign[]>(r))

export const getRun = (id: number) => fetch(`/api/runs/${id}`).then((r) => json<RunTrace>(r))

/** A SAP failure with its code (`sap_unavailable`, `sap_error`) and params, for the UI's text. */
export class SapRequestError extends Error {
  readonly code?: string
  readonly params?: Record<string, string>

  constructor(message: string, code?: string, params?: Record<string, string>) {
    super(message)
    this.code = code
    this.params = params
  }
}

/**
 * The designs SAP knows (read-only, for the Start panel). SAP down: the error says so.
 * `lang` asks SAP for its own texts in the UI language (decision 0027).
 */
export async function listSapDesigns(lang: Lang = 'en'): Promise<SapListDesign[]> {
  const response = await fetch(`/api/sap/designs?lang=${lang}`)
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { message?: string; code?: string; params?: Record<string, string> }
      | null
    throw new SapRequestError(body?.message ?? `HTTP ${response.status}`, body?.code, body?.params)
  }
  return response.json() as Promise<SapListDesign[]>
}

/** The form's inline check (read-only; the validators decide, invariant 1). */
export const validateFields = (fields: Record<string, string>, signal?: AbortSignal) =>
  fetch('/api/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fields }),
    signal,
  }).then((r) => json<Validation>(r))

/** The Stop button: the run ends as `cancelled` and the stream sends `done`. */
export const cancelRun = (id: number) =>
  fetch(`/api/runs/${id}/cancel`, { method: 'POST' }).then((r) => r.ok)

/** After a stuck turn: answer with Ollama or the demo model from now on. */
export const switchProvider = (to: SwitchTarget) =>
  fetch('/api/llm/switch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ to }),
  }).then((r) => json<{ provider: string; model: string }>(r))

/** The form opens a confirmation card; nothing happens until `confirmAction`. */
export const proposeAction = (
  kind: ActionKind,
  payload: Record<string, string>,
  conversationId: string | null,
) =>
  fetch('/api/actions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind, payload, conversation_id: conversationId }),
  }).then((r) => json<Action>(r))

/**
 * Confirm or cancel. The backend answers with the action even when it did not happen
 * (409 already decided, 410 expired, 422 rule, 502 SAP, 500 export), so those bodies
 * are returned with their HTTP status, not thrown.
 */
async function decide(id: string, verb: 'confirm' | 'cancel', lang?: Lang): Promise<Decision> {
  const query = lang ? `?lang=${lang}` : ''
  const response = await fetch(`/api/actions/${id}/${verb}${query}`, { method: 'POST' })
  const body = (await response.json().catch(() => null)) as
    | (Action & { action?: Action; detail?: string })
    | null
  const action = body?.action ?? (body?.id ? body : null)
  if (!action) throw new Error(`HTTP ${response.status}`)
  return { action, http: response.status }
}

export type Decision = { action: Action; http: number }
/** `lang`: SAP's refusal text comes in the UI language (decision 0027). */
export const confirmAction = (id: string, lang: Lang = 'en') => decide(id, 'confirm', lang)
export const cancelAction = (id: string) => decide(id, 'cancel')

const designBase = (t: PreviewTarget) => `/api/designs/${t.department}/${t.design_number}/${t.revision}`

/** Which drawing a preview or an Open shows: the schematic, or the board (decision 0033). */
export type DrawingView = 'schematic' | 'pcb'

export const previewUrl = (t: PreviewTarget, format: 'pdf' | 'svg', view: DrawingView = 'schematic') =>
  `${designBase(t)}/${view === 'pcb' ? 'pcb' : 'preview'}.${format}`

/** The revision folder as a zip (works everywhere, also in Docker). */
export const projectZipUrl = (t: PreviewTarget) => `${designBase(t)}/project.zip`

export type DesignFiles = {
  folder: string
  project_file: string
  can_open: boolean
  /** Designs made before decision 0033 have no board: no Open PCB and no PCB view. */
  can_open_pcb?: boolean
  has_pcb_preview?: boolean
}

export const getDesignFiles = (t: PreviewTarget) => fetch(`${designBase(t)}/files`).then((r) => json<DesignFiles>(r))

/** Start KiCad's schematic or PCB editor on the backend's machine (local mode; 0019, 0033). */
export const openInKicad = (t: PreviewTarget, view: DrawingView = 'schematic') =>
  fetch(`${designBase(t)}/open${view === 'pcb' ? '?target=pcb' : ''}`, { method: 'POST' }).then((r) =>
    json<{ ok: boolean }>(r),
  )
