import { ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import {
  getAppearances,
  resetAppearance as resetAppearanceRequest,
  saveAppearance as saveAppearanceRequest,
} from '../api/appearances'
import type { AppearanceOverride } from '../api/appearances'

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : '好友外观操作失败'
}

export const useAppearancesStore = defineStore('appearances', () => {
  const appearances = ref<Record<string, AppearanceOverride>>({})
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  const operationError = ref<string | null>(null)

  async function fetchAppearances(): Promise<void> {
    loading.value = true
    loadError.value = null
    try {
      appearances.value = (await getAppearances()).appearances
    } catch (caught) {
      loadError.value = errorMessage(caught)
    } finally {
      loading.value = false
    }
  }

  async function save(toolId: string, appearance: AppearanceOverride): Promise<boolean> {
    operationError.value = null
    try {
      const saved = await saveAppearanceRequest(toolId, appearance)
      const { tool_id: savedToolId, ...override } = saved
      appearances.value = { ...appearances.value, [savedToolId]: override }
      return true
    } catch (caught) {
      operationError.value = errorMessage(caught)
      return false
    }
  }

  async function reset(toolId: string): Promise<boolean> {
    operationError.value = null
    try {
      await resetAppearanceRequest(toolId)
      const next = { ...appearances.value }
      delete next[toolId]
      appearances.value = next
      return true
    } catch (caught) {
      operationError.value = errorMessage(caught)
      return false
    }
  }

  function clearOperationError(): void {
    operationError.value = null
  }

  return {
    appearances,
    loading,
    loadError,
    operationError,
    fetchAppearances,
    save,
    reset,
    clearOperationError,
  }
})
