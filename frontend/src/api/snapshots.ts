import { requestJson } from './client'

export type RestoredFileAction = 'restored' | 'deleted' | 'unchanged'

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

export function rollbackSnapshot(snapshotId: string): Promise<RollbackResponse> {
  return requestJson<RollbackResponse>(
    `/api/snapshots/${encodeURIComponent(snapshotId)}/rollback`,
    { method: 'POST' },
    { timeoutMs: 30_000 },
  )
}
