import { requestJson } from './client'

export type SnapshotReason = 'apply' | 'rollback'
export type SnapshotChangeAction = 'set' | 'remove'
export type SnapshotWarningCode =
  | 'SNAPSHOT_UNREADABLE'
  | 'SNAPSHOT_VERSION_UNSUPPORTED'
export type RestoredFileAction = 'restored' | 'deleted' | 'unchanged'

export interface SnapshotChange {
  path: string
  field: string
  action: SnapshotChangeAction
  before: string | null
  after: string | null
}

export interface SnapshotFileView {
  path: string
  existed: boolean
  sha256: string | null
  size: number
  mtime_ns: number | null
  mode: number | null
}

export interface SnapshotSummary {
  id: string
  tool_id: string
  profile_id: string | null
  created_at: string
  reason: SnapshotReason
  pinned: boolean
  file_count: number
  total_size: number
  files: SnapshotFileView[]
  changes: SnapshotChange[]
}

export interface SnapshotListWarning {
  code: SnapshotWarningCode
  message: string
}

export interface SnapshotListResponse {
  snapshots: SnapshotSummary[]
  retention_limit: number
  warnings: SnapshotListWarning[]
}

export interface SnapshotView {
  schema_version: 1
  id: string
  tool_id: string
  profile_id: string | null
  created_at: string
  reason: SnapshotReason
  pinned: boolean
  files: SnapshotFileView[]
  changes: SnapshotChange[]
}

export interface RestoredFileView {
  path: string
  action: RestoredFileAction
  sha256: string | null
  size: number
}

export interface RollbackResponse {
  snapshot_id: string
  pre_rollback_snapshot_id: string
  files: RestoredFileView[]
}

export function listSnapshots(
  toolId?: string | null,
  limit?: number,
): Promise<SnapshotListResponse> {
  const params = new URLSearchParams()
  if (toolId !== undefined && toolId !== null && toolId !== '') {
    params.set('tool_id', toolId)
  }
  if (limit !== undefined) {
    params.set('limit', String(limit))
  }
  const query = params.toString()
  return requestJson<SnapshotListResponse>(
    query === '' ? '/api/snapshots' : `/api/snapshots?${query}`,
  )
}

export function setSnapshotPinned(
  snapshotId: string,
  pinned: boolean,
): Promise<SnapshotView> {
  return requestJson<SnapshotView>(
    `/api/snapshots/${encodeURIComponent(snapshotId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned }),
    },
  )
}

export function rollbackSnapshot(snapshotId: string): Promise<RollbackResponse> {
  return requestJson<RollbackResponse>(
    `/api/snapshots/${encodeURIComponent(snapshotId)}/rollback`,
    { method: 'POST' },
  )
}