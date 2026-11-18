import { ref } from 'vue'
import { defineStore } from 'pinia'

import { listAuditEntries } from '../api/audit'
import type { AuditEntry } from '../api/audit'
import { ApiError } from '../api/client'

export const useAuditStore = defineStore('audit', () => {
  const entries = ref<AuditEntry[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)
  const activeToolId = ref<string | null>(null)

  let requestId = 0

  async function load(toolId: string | null): Promise<void> {
    const current = ++requestId
    activeToolId.value = toolId
    loading.value = true
    loaded.value = false
    error.value = null
    entries.value = []
    try {
      const response = await listAuditEntries({
        toolId: toolId ?? undefined,
        limit: 200,
      })
      if (current !== requestId) {
        return
      }
      entries.value = response.entries
      loaded.value = true
    } catch (caught) {
      if (current !== requestId) {
        return
      }
      error.value = caught instanceof ApiError ? caught.message : '操作记录读取失败'
    } finally {
      if (current === requestId) {
        loading.value = false
      }
    }
  }

  return { entries, loading, loaded, error, activeToolId, load }
})
