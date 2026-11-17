import { ref } from 'vue'
import { defineStore } from 'pinia'

import { getUsage } from '../api/usage'
import type { UsageResponse } from '../api/usage'
import { ApiError } from '../api/client'

export const useUsageStore = defineStore('usage', () => {
  const data = ref<UsageResponse | null>(null)
  const days = ref(7)
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  let requestId = 0

  async function load(nextDays: number): Promise<void> {
    const current = ++requestId
    days.value = nextDays
    loading.value = true
    loaded.value = false
    error.value = null
    data.value = null
    try {
      const result = await getUsage(nextDays)
      if (current !== requestId) {
        return
      }
      data.value = result
      loaded.value = true
    } catch (caught) {
      if (current !== requestId) {
        return
      }
      error.value = caught instanceof ApiError ? caught.message : '用量读取失败'
    } finally {
      if (current === requestId) {
        loading.value = false
      }
    }
  }

  return { data, days, loading, loaded, error, load }
})
