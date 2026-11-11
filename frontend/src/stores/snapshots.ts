import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import {
  listSnapshots,
  rollbackSnapshot,
  setSnapshotPinned,
} from '../api/snapshots'
import type {
  RollbackResponse,
  SnapshotListResponse,
  SnapshotListWarning,
  SnapshotSummary,
} from '../api/snapshots'

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : '快照信息读取失败'
}

export const useSnapshotsStore = defineStore('snapshots', () => {
  const toolId = ref<string | null>(null)
  const snapshots = ref<SnapshotSummary[]>([])
  const retentionLimit = ref<number | null>(null)
  const warnings = ref<SnapshotListWarning[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const refreshError = ref<string | null>(null)
  const actionError = ref<string | null>(null)
  const pinBusyId = ref<string | null>(null)
  const rollbackBusyId = ref<string | null>(null)
  const pendingRollback = ref<SnapshotSummary | null>(null)
  const lastRollback = ref<RollbackResponse | null>(null)

  const busy = computed(
    () => pinBusyId.value !== null || rollbackBusyId.value !== null,
  )

  let listRequestId = 0

  function resetForTool(nextToolId: string): void {
    if (toolId.value === nextToolId) {
      return
    }
    listRequestId += 1
    toolId.value = nextToolId
    snapshots.value = []
    retentionLimit.value = null
    warnings.value = []
    error.value = null
    refreshError.value = null
    actionError.value = null
    pendingRollback.value = null
    lastRollback.value = null
    pinBusyId.value = null
    rollbackBusyId.value = null
  }

  function applyList(response: SnapshotListResponse): void {
    snapshots.value = response.snapshots
    retentionLimit.value = response.retention_limit
    warnings.value = response.warnings
  }

  async function fetchSnapshots(nextToolId?: string): Promise<void> {
    if (nextToolId !== undefined) {
      resetForTool(nextToolId)
    }
    if (toolId.value === null) {
      return
    }
    const requestId = ++listRequestId
    loading.value = true
    error.value = null
    refreshError.value = null
    try {
      const response = await listSnapshots(toolId.value)
      if (requestId !== listRequestId) {
        return
      }
      applyList(response)
    } catch (caught) {
      if (requestId !== listRequestId) {
        return
      }
      if (snapshots.value.length > 0) {
        refreshError.value = errorMessage(caught)
      } else {
        snapshots.value = []
        retentionLimit.value = null
        warnings.value = []
        error.value = errorMessage(caught)
      }
    } finally {
      if (requestId === listRequestId) {
        loading.value = false
      }
    }
  }

  async function setPinned(snapshotId: string, pinned: boolean): Promise<boolean> {
    if (busy.value) {
      return false
    }
    pinBusyId.value = snapshotId
    actionError.value = null
    try {
      const updated = await setSnapshotPinned(snapshotId, pinned)
      const target = snapshots.value.find((snapshot) => snapshot.id === snapshotId)
      if (target !== undefined) {
        target.pinned = updated.pinned
      }
      return true
    } catch (caught) {
      actionError.value = errorMessage(caught)
      return false
    } finally {
      pinBusyId.value = null
    }
  }

  function requestRollback(snapshot: SnapshotSummary): void {
    if (busy.value) {
      return
    }
    pendingRollback.value = snapshot
    actionError.value = null
    lastRollback.value = null
  }

  function cancelRollback(): void {
    if (rollbackBusyId.value !== null) {
      return
    }
    pendingRollback.value = null
  }

  async function confirmRollback(): Promise<boolean> {
    const target = pendingRollback.value
    if (target === null || busy.value) {
      return false
    }
    rollbackBusyId.value = target.id
    actionError.value = null
    try {
      const response = await rollbackSnapshot(target.id)
      lastRollback.value = response
      pendingRollback.value = null
      await fetchSnapshots()
      return true
    } catch (caught) {
      actionError.value = errorMessage(caught)
      return false
    } finally {
      rollbackBusyId.value = null
    }
  }

  return {
    toolId,
    snapshots,
    retentionLimit,
    warnings,
    loading,
    error,
    refreshError,
    actionError,
    pinBusyId,
    rollbackBusyId,
    pendingRollback,
    lastRollback,
    busy,
    fetchSnapshots,
    setPinned,
    requestRollback,
    cancelRollback,
    confirmRollback,
  }
})