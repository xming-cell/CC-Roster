import { ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import { getHealth } from '../api/health'

export type BackendStatus = 'loading' | 'ok' | 'error'

export const useAppStore = defineStore('app', () => {
  const backendStatus = ref<BackendStatus>('loading')
  const backendError = ref<string | null>(null)

  async function checkBackend(): Promise<void> {
    backendStatus.value = 'loading'
    backendError.value = null
    try {
      const health = await getHealth()
      if (health.status === 'ok') {
        backendStatus.value = 'ok'
        return
      }
      backendStatus.value = 'error'
      backendError.value = `后端状态异常: ${health.status}`
    } catch (error) {
      backendStatus.value = 'error'
      backendError.value = error instanceof ApiError ? error.message : '后端状态未知'
    }
  }

  return { backendStatus, backendError, checkBackend }
})