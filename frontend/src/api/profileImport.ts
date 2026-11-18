import { requestJson } from './client'

export type ImportPolicy = 'skip' | 'overwrite'
export type ImportItemStatus = 'new' | 'duplicate' | 'invalid'

export interface ProfileImportItem {
  index: number
  name: string | null
  status: ImportItemStatus
  reasons: string[]
  notes: string[]
  has_secret: boolean
  conflict_profile_id: string | null
}

export interface ProfileImportTotals {
  new: number
  duplicate: number
  invalid: number
}

export interface ProfileImportPreview {
  schema_version: number
  items: ProfileImportItem[]
  totals: ProfileImportTotals
  can_import: boolean
  source: 'content' | 'codex_config' | 'local_config'
  source_path: string | null
  format: 'json' | 'toml'
  tool_id: string | null
}

export interface ProfileImportResult {
  imported: number
  overwritten: number
  skipped: number
  profile_ids: string[]
}

function jsonInit(body: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export function previewProfileImport(
  content: string,
  toolId?: string,
): Promise<ProfileImportPreview> {
  return requestJson<ProfileImportPreview>(
    '/api/profiles/import/preview',
    jsonInit({ content, tool_id: toolId ?? null }),
    { timeoutMs: 20_000 },
  )
}

export function importProfiles(
  content: string,
  policy: ImportPolicy,
  toolId?: string,
): Promise<ProfileImportResult> {
  return requestJson<ProfileImportResult>(
    '/api/profiles/import',
    jsonInit({ content, policy, tool_id: toolId ?? null }),
    { timeoutMs: 30_000 },
  )
}

export function previewCodexConfigImport(): Promise<ProfileImportPreview> {
  return requestJson<ProfileImportPreview>(
    '/api/profiles/import/codex/preview',
    { method: 'POST' },
    { timeoutMs: 20_000 },
  )
}

export function importCodexProfiles(policy: ImportPolicy): Promise<ProfileImportResult> {
  return requestJson<ProfileImportResult>(
    '/api/profiles/import/codex',
    jsonInit({ policy }),
    { timeoutMs: 30_000 },
  )
}

export function previewLocalConfigImport(toolId: string): Promise<ProfileImportPreview> {
  return requestJson<ProfileImportPreview>(
    `/api/profiles/import/local/${encodeURIComponent(toolId)}/preview`,
    { method: 'POST' },
    { timeoutMs: 20_000 },
  )
}

export function importLocalProfiles(
  toolId: string,
  policy: ImportPolicy,
): Promise<ProfileImportResult> {
  return requestJson<ProfileImportResult>(
    `/api/profiles/import/local/${encodeURIComponent(toolId)}`,
    jsonInit({ policy }),
    { timeoutMs: 30_000 },
  )
}