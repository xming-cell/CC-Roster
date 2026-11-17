import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import type { ProfileView } from '../api/profiles'
import { rollbackSnapshot } from '../api/snapshots'
import type { RollbackResponse } from '../api/snapshots'
import { applySwitch, previewSwitch } from '../api/switch'
import type { SwitchApplyResponse, SwitchPreviewResponse } from '../api/switch'
import type { ToolView } from '../api/tools'
import { errorText } from '../utils/profileDisplay'

export type SwitchStage = 'idle' | 'previewing' | 'ready' | 'applying' | 'applied' | 'conflict' | 'error'
export type RollbackStage = 'idle' | 'confirm' | 'rolling' | 'done'

export const useSwitchStore = defineStore('switch', () => {
  const tool = ref<ToolView | null>(null)
  const profile = ref<ProfileView | null>(null)
  const stage = ref<SwitchStage>('idle')
  const preview = ref<SwitchPreviewResponse | null>(null)
  const result = ref<SwitchApplyResponse | null>(null)
  const error = ref<string | null>(null)

  const rollbackStage = ref<RollbackStage>('idle')
  const rollbackResult = ref<RollbackResponse | null>(null)
  const rollbackError = ref<string | null>(null)

  const busy = computed(() => stage.value === 'applying' || rollbackStage.value === 'rolling')
  const open = computed(() => stage.value !== 'idle')

  function reset(): void {
    tool.value = null
    profile.value = null
    stage.value = 'idle'
    preview.value = null
    result.value = null
    error.value = null
    rollbackStage.value = 'idle'
    rollbackResult.value = null
    rollbackError.value = null
  }

  function close(): void {
    reset()
  }

  async function loadPreview(): Promise<void> {
    const currentTool = tool.value
    const currentProfile = profile.value
    if (currentTool === null || currentProfile === null) {
      return
    }
    stage.value = 'previewing'
    error.value = null
    try {
      const response = await previewSwitch({
        tool_id: currentTool.id,
        profile_id: currentProfile.id,
      })
      if (profile.value?.id !== currentProfile.id) {
        return
      }
      preview.value = response
      stage.value = 'ready'
    } catch (caught) {
      if (profile.value?.id !== currentProfile.id) {
        return
      }
      error.value = errorText(caught, '预览失败，请稍后重试')
      stage.value = 'error'
    }
  }

  async function start(nextTool: ToolView, nextProfile: ProfileView): Promise<void> {
    reset()
    tool.value = nextTool
    profile.value = nextProfile
    await loadPreview()
  }

  async function apply(): Promise<void> {
    const currentTool = tool.value
    const currentProfile = profile.value
    const currentPreview = preview.value
    if (currentTool === null || currentProfile === null || currentPreview === null) {
      return
    }
    if (stage.value !== 'ready') {
      return
    }
    stage.value = 'applying'
    error.value = null
    try {
      const response = await applySwitch({
        tool_id: currentTool.id,
        profile_id: currentProfile.id,
        preview_digest: currentPreview.preview_digest,
        observations: currentPreview.observations,
      })
      result.value = response
      stage.value = 'applied'
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === 'SWITCH_PREVIEW_STALE') {
        error.value = caught.message
        stage.value = 'conflict'
        return
      }
      error.value = errorText(caught, '应用切换失败')
      stage.value = 'ready'
    }
  }

  async function retryPreview(): Promise<void> {
    if (busy.value) {
      return
    }
    await loadPreview()
  }

  function requestRollback(): void {
    if (stage.value !== 'applied' || rollbackStage.value !== 'idle') {
      return
    }
    rollbackError.value = null
    rollbackStage.value = 'confirm'
  }

  function cancelRollback(): void {
    if (rollbackStage.value === 'rolling') {
      return
    }
    rollbackStage.value = 'idle'
    rollbackError.value = null
  }

  async function confirmRollback(): Promise<void> {
    const current = result.value
    if (current === null || rollbackStage.value !== 'confirm') {
      return
    }
    rollbackStage.value = 'rolling'
    rollbackError.value = null
    try {
      rollbackResult.value = await rollbackSnapshot(current.snapshot_id)
      rollbackStage.value = 'done'
    } catch (caught) {
      rollbackError.value = errorText(caught, '回滚失败，请稍后重试')
      rollbackStage.value = 'confirm'
    }
  }

  return {
    tool,
    profile,
    stage,
    preview,
    result,
    error,
    rollbackStage,
    rollbackResult,
    rollbackError,
    busy,
    open,
    start,
    close,
    apply,
    retryPreview,
    requestRollback,
    cancelRollback,
    confirmRollback,
  }
})
