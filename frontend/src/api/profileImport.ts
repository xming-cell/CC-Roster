import { requestJson } from './client'

export type ImportPolicy = 'skip' | 'overwrite'
export type ImportItemStatus = 'new' | 'duplicate' | 'invalid'

export interface ProfileImportItem {
  index: number
  name: string | null
  status: ImportItemStatus
  reasons: string[]
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

export function previewProfileImport(content: string): Promise<ProfileImportPreview> {
  return requestJson<ProfileImportPreview>(
    '/api/profiles/import/preview',
    jsonInit({ content }),
    { timeoutMs: 20_000 },
  )
}

export function importProfiles(
  content: string,
  policy: ImportPolicy,
): Promise<ProfileImportResult> {
  return requestJson<ProfileImportResult>(
    '/api/profiles/import',
    jsonInit({ content, policy }),
    { timeoutMs: 30_000 },
  )
}
