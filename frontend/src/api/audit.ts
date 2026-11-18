import { requestJson } from './client'

export type AuditAction =
  | 'apply'
  | 'rollback'
  | 'profile_create'
  | 'profile_update'
  | 'profile_copy'
  | 'profile_delete'
  | 'profile_bind'
  | 'profile_unbind'
  | 'profile_import'

export type AuditResult = 'success' | 'failed' | 'conflict'

export interface AuditEntry {
  id: string
  created_at: string
  action: AuditAction
  tool_id: string | null
  profile_id: string | null
  snapshot_id: string | null
  files: string[]
  fields: string[]
  result: AuditResult
  message: string
}

export interface AuditListResponse {
  entries: AuditEntry[]
}

export function listAuditEntries(params: {
  toolId?: string
  limit?: number
} = {}): Promise<AuditListResponse> {
  const query = new URLSearchParams()
  if (params.toolId !== undefined) {
    query.set('tool_id', params.toolId)
  }
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit))
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return requestJson<AuditListResponse>(`/api/audit${suffix}`)
}
