import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  listAppearances,
  resetAppearance as requestReset,
  saveAppearance as requestSave,
} from '../api/appearances'
import type { AppearanceOverride } from '../api/appearances'
import { ApiError } from '../api/client'

export const useAppearancesStore = defineStore('appearances', () => {
  const appearances = ref<Record<string, AppearanceOverride>>({})
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await listAppearances()
      appearances.value = response.appearances
      loaded.value = true
    } catch (caught) {
      error.value = caught instanceof ApiError ? caught.message : '外观偏好读取失败'
    } finally {
      loading.value = false
    }
  }

  async function save(toolId: string, payload: AppearanceOverride): Promise<void> {
    const saved = await requestSave(toolId, payload)
    appearances.value = {
      ...appearances.value,
      [toolId]: {
        accent_color: saved.accent_color,
        background_color: saved.background_color,
        bubble_preset: saved.bubble_preset,
      },
    }
  }

  async function reset(toolId: string): Promise<void> {
    await requestReset(toolId)
    const next = { ...appearances.value }
    delete next[toolId]
    appearances.value = next
  }

  return { appearances, loading, loaded, error, load, save, reset }
})
