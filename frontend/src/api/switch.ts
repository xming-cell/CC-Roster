import type { FileObservation } from './client'
import { requestJson } from './client'
import type { BindingView, ModelEntry } from './profiles'

export type SwitchDocumentFormat = 'json' | 'toml' | 'key_value'
export type SwitchFileAction = 'created' | 'updated' | 'unchanged'
export type SwitchChangeAction = 'set' | 'remove'

export type SwitchBlockerCode =
  | 'PROTOCOL_MISMATCH'
  | 'MODEL_UNKNOWN'
  | 'SECRET_MISSING'
  | 'SECRET_STORE_ERROR'
  | 'PARSE_ERROR'
  | 'UNSUPPORTED_VERSION'
  | 'UNSAFE_WRITE'
  | 'PERMISSION_DENIED'
  | 'FILE_NOT_WRITABLE'
  | 'DIRECTORY_NOT_WRITABLE'
  | 'ENV_KEY_CONFLICT'

export type SwitchWarningCode =
  | 'PROFILE_SECRET_EMPTY'
  | 'NO_MODELS'
  | 'MODEL_SHADOWED'
  | 'OAUTH_AUTH_PRESENT'

export interface SwitchBlocker {
  code: SwitchBlockerCode
  message: string
  path: string | null
}

export interface SwitchWarning {
  code: SwitchWarningCode
  message: string
}

export interface SwitchChange {
  path: string
  field: string
  action: SwitchChangeAction
  before: string | null
  after: string | null
}

export interface SwitchFilePreview {
  path: string
  format: SwitchDocumentFormat
  action: SwitchFileAction
  before_sha256: string | null
  after_sha256: string
  before_size: number
  after_size: number
  changes: SwitchChange[]
}

export interface SwitchPreviewResponse {
  tool_id: string
  profile_id: string
  model: string | null
  available_models: ModelEntry[]
  files: SwitchFilePreview[]
  blockers: SwitchBlocker[]
  warnings: SwitchWarning[]
  restart_required: boolean
  restart_message: string
  observations: FileObservation[]
  preview_digest: string
  can_apply: boolean
}

export interface SwitchPreviewInput {
  tool_id: string
  profile_id: string
  model?: string | null
}

export interface SwitchApplyInput extends SwitchPreviewInput {
  preview_digest: string
  observations: FileObservation[]
}

export interface WrittenFileView {
  path: string
  action: SwitchFileAction
  sha256: string
  size: number
}

export interface SwitchApplyResponse {
  tool_id: string
  profile_id: string
  snapshot_id: string
  audit_id: string
  files: WrittenFileView[]
  binding: BindingView
  warnings: SwitchWarning[]
  restart_required: boolean
  restart_message: string
  applied_at: string
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export function previewSwitch(input: SwitchPreviewInput): Promise<SwitchPreviewResponse> {
  return requestJson<SwitchPreviewResponse>(
    '/api/switch/preview',
    jsonInit('POST', input),
  )
}

export function applySwitch(input: SwitchApplyInput): Promise<SwitchApplyResponse> {
  return requestJson<SwitchApplyResponse>('/api/switch/apply', jsonInit('POST', input))
}
