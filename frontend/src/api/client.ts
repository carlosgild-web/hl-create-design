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

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json() as Promise<T>
}

/** `llm_provider` is the model that answers now (`demo` = the rule-based demo assistant). */
export const getHealth = () => fetch('/api/health').then((r) => json<{ llm_provider: string }>(r))

export const getDepartments = () => fetch('/api/departments').then((r) => json<Department[]>(r))

export const getRecentDesigns = () => fetch('/api/designs').then((r) => json<RecentDesign[]>(r))

export const getRun = (id: number) => fetch(`/api/runs/${id}`).then((r) => json<RunTrace>(r))

/** The designs SAP knows (read-only, for the Start panel). SAP down: the error says so. */
export async function listSapDesigns(): Promise<SapListDesign[]> {
  const response = await fetch('/api/sap/designs')
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { message?: string } | null
    throw new Error(body?.message ?? `HTTP ${response.status}`)
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
async function decide(id: string, verb: 'confirm' | 'cancel'): Promise<Decision> {
  const response = await fetch(`/api/actions/${id}/${verb}`, { method: 'POST' })
  const body = (await response.json().catch(() => null)) as
    | (Action & { action?: Action; detail?: string })
    | null
  const action = body?.action ?? (body?.id ? body : null)
  if (!action) throw new Error(`HTTP ${response.status}`)
  return { action, http: response.status }
}

export type Decision = { action: Action; http: number }
export const confirmAction = (id: string) => decide(id, 'confirm')
export const cancelAction = (id: string) => decide(id, 'cancel')

const designBase = (t: PreviewTarget) => `/api/designs/${t.department}/${t.design_number}/${t.revision}`

export const previewUrl = (t: PreviewTarget, format: 'pdf' | 'svg') => `${designBase(t)}/preview.${format}`

/** The revision folder as a zip (works everywhere, also in Docker). */
export const projectZipUrl = (t: PreviewTarget) => `${designBase(t)}/project.zip`

export type DesignFiles = { folder: string; project_file: string; can_open: boolean }

export const getDesignFiles = (t: PreviewTarget) => fetch(`${designBase(t)}/files`).then((r) => json<DesignFiles>(r))

/** Start KiCad with the project on the backend's machine (local mode; decision 0019). */
export const openInKicad = (t: PreviewTarget) =>
  fetch(`${designBase(t)}/open`, { method: 'POST' }).then((r) => json<{ ok: boolean }>(r))
