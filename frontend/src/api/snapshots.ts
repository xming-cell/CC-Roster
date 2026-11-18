import { requestJson } from './client'

export type RestoredFileAction = 'restored' | 'deleted' | 'unchanged'
export type SnapshotReason = 'apply' | 'rollback'
export type SnapshotChangeAction = 'set' | 'remove'

export interface RestoredFileView {
  path: string
  action: RestoredFileAction
  sha256: string | null
  size: number
}

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

export interface RollbackResponse {
  snapshot_id: string
  pre_rollback_snapshot_id: string
  files: RestoredFileView[]
}

export function getSnapshot(snapshotId: string): Promise<SnapshotView> {
  return requestJson<SnapshotView>('/api/snapshots/' + encodeURIComponent(snapshotId))
}

export function rollbackSnapshot(snapshotId: string): Promise<RollbackResponse> {
  return requestJson<RollbackResponse>(
    '/api/snapshots/' + encodeURIComponent(snapshotId) + '/rollback',
    { method: 'POST' },
    { timeoutMs: 30_000 },
  )
}
