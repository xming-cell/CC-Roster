import { requestJson } from './client'
import type { ModelEntry } from './profiles'

export type SwitchFileAction = 'created' | 'updated' | 'unchanged'
export type SnapshotChangeAction = 'set' | 'remove'

export interface SnapshotChange {
  path: string
  field: string
  action: SnapshotChangeAction
  before: string | null
  after: string | null
}

export interface FileObservation {
  path: string
  exists: boolean
  sha256: string | null
  size: number
  mtime_ns: number | null
}

export interface SwitchBlocker {
  code: string
  message: string
  path: string | null
}

export interface SwitchWarning {
  code: string
  message: string
}

export interface SwitchFilePreview {
  path: string
  format: string
  action: SwitchFileAction
  before_sha256: string | null
  after_sha256: string
  before_size: number
  after_size: number
  changes: SnapshotChange[]
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
  model?: string
}

export interface WrittenFileView {
  path: string
  action: SwitchFileAction
  sha256: string
  size: number
}

export interface BindingState {
  tool_id: string
  profile_id: string
  bound_at: string
  active: boolean
  applied_at: string | null
  snapshot_id: string | null
}

export interface SwitchApplyInput extends SwitchPreviewInput {
  preview_digest: string
  observations: FileObservation[]
}

export interface SwitchApplyResponse {
  tool_id: string
  profile_id: string
  snapshot_id: string
  audit_id: string
  files: WrittenFileView[]
  binding: BindingState
  warnings: SwitchWarning[]
  restart_required: boolean
  restart_message: string
  applied_at: string
}

function jsonInit(body: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export function previewSwitch(input: SwitchPreviewInput): Promise<SwitchPreviewResponse> {
  return requestJson<SwitchPreviewResponse>('/api/switch/preview', jsonInit(input))
}

export function applySwitch(input: SwitchApplyInput): Promise<SwitchApplyResponse> {
  return requestJson<SwitchApplyResponse>('/api/switch/apply', jsonInit(input), {
    timeoutMs: 30_000,
  })
}
