export const FORM_FIELDS = ['department', 'design_number', 'revision', 'name', 'designer'] as const
export type FormField = (typeof FORM_FIELDS)[number]
export type FormValues = Record<FormField, string>

export type Department = { code: string; name: string }

export type Issue = { field: string; code: string; message: string; ref: string }

export type ActionKind = 'create_design' | 'reserve_number'
export type ActionStatus = 'pending' | 'executing' | 'confirmed' | 'failed' | 'cancelled'

export type ActionResult = {
  ok?: boolean
  cancelled?: boolean
  error_kind?: string
  message?: string
  errors?: Issue[]
  warnings?: Issue[]
  ref?: string
  design_number?: string
  department?: string
  revision?: string
  name?: string
  folder?: string
  pdf?: boolean
  sap_material?: string
  project?: string
  status?: string
}

export type Action = {
  id: string
  conversation_id: string
  kind: ActionKind
  payload: Record<string, string>
  status: ActionStatus
  created_at: string
  expires_at: string
  decided_at: string | null
  result: ActionResult
}

export type SapDesign = {
  design_number: string
  department: string
  name: string
  status: 'IN_WORK' | 'RELEASED' | 'BLOCKED' | 'OBSOLETE' | string
  material: string
  wbs: string
  current_revision: string
  block_reason: string
  successor: string
  revisions: string[]
}

export type RecentDesign = {
  design_number: string
  revision: string
  name: string
  department: string
  designer: string
  pdf: boolean
  created_at: string
}

export type PreviewTarget = { department: string; design_number: string; revision: string }

/** One server-sent event of `POST /api/chat`. */
export type ChatEvent =
  | { type: 'conversation'; data: { id: string } }
  | { type: 'thinking'; data: { content: string } }
  | { type: 'tool_call'; data: { id: string; name: string; arguments: Record<string, unknown> } }
  | {
      type: 'tool_result'
      data: { id: string; name: string; ok: boolean; result: Record<string, unknown> }
    }
  | { type: 'form_proposal'; data: { fields: Partial<FormValues> } }
  | { type: 'pending_action'; data: { action: Action } }
  | { type: 'message'; data: { role: 'assistant'; content: string } }
  | { type: 'error'; data: { message: string } }
  | {
      type: 'notice'
      data: { code: 'provider_switched'; from: string; to: string; model: string; reason: string }
    }
  | { type: 'done'; data: { conversation_id?: string; run_id?: number; status: string } }

export type RunTrace = {
  id: number
  provider: string
  model: string
  status: string
  model_calls: number
  trace: Record<string, unknown>
}
