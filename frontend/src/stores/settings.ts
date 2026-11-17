import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import { getSettings, updateSettings } from '../api/settings'
import type { SettingsUpdate, SettingsView } from '../api/settings'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<SettingsView | null>(null)
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)
  const saving = ref(false)

  const readOnly = computed(() => settings.value?.read_only === true)

  let loadRequestId = 0

  async function load(): Promise<void> {
    const requestId = ++loadRequestId
    loading.value = true
    error.value = null
    try {
      const result = await getSettings()
      if (requestId !== loadRequestId) {
        return
      }
      settings.value = result
      loaded.value = true
    } catch (caught) {
      if (requestId !== loadRequestId) {
        return
      }
      error.value = caught instanceof ApiError ? caught.message : '设置读取失败'
    } finally {
      if (requestId === loadRequestId) {
        loading.value = false
      }
    }
  }

  async function update(payload: SettingsUpdate): Promise<SettingsView> {
    saving.value = true
    error.value = null
    try {
      const result = await updateSettings(payload)
      settings.value = result
      loaded.value = true
      return result
    } catch (caught) {
      error.value = caught instanceof ApiError ? caught.message : '设置保存失败'
      throw caught
    } finally {
      saving.value = false
    }
  }

  return { settings, loading, loaded, error, saving, readOnly, load, update }
})
