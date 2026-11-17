import type {
  Action,
  ActionKind,
  Department,
  RecentDesign,
  RunTrace,
  PreviewTarget,
} from './types'

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json() as Promise<T>
}

export const getDepartments = () => fetch('/api/departments').then((r) => json<Department[]>(r))

export const getRecentDesigns = () => fetch('/api/designs').then((r) => json<RecentDesign[]>(r))

export const getRun = (id: number) => fetch(`/api/runs/${id}`).then((r) => json<RunTrace>(r))

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

export const previewUrl = (t: PreviewTarget, format: 'pdf' | 'svg') =>
  `/api/designs/${t.department}/${t.design_number}/${t.revision}/preview.${format}`
