import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import type { ApiErrorDetails } from '../api/client'
import type { BindingView, ProfileView } from '../api/profiles'
import { applySwitch, previewSwitch } from '../api/switch'
import type { SwitchApplyResponse, SwitchPreviewResponse } from '../api/switch'

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : '切换操作失败，请稍后重试'
}

function errorCodeOf(error: unknown): string | null {
  return error instanceof ApiError ? error.code : null
}

function errorDetails(error: unknown): ApiErrorDetails | null {
  return error instanceof ApiError ? error.details : null
}

function defaultProfileId(
  toolId: string,
  profiles: ProfileView[],
  bindings: BindingView[],
): string | null {
  const bound = bindings.find((binding) => binding.tool_id === toolId)
  if (bound !== undefined && profiles.some((profile) => profile.id === bound.profile_id)) {
    return bound.profile_id
  }
  return profiles[0]?.id ?? null
}

function firstModelId(profileId: string | null, profiles: ProfileView[]): string | null {
  if (profileId === null) {
    return null
  }
  return (
    profiles.find((profile) => profile.id === profileId)?.models[0]?.id ?? null
  )
}

export const useSwitchesStore = defineStore('switches', () => {
  const toolId = ref<string | null>(null)
  const selectedProfileId = ref<string | null>(null)
  const selectedModelId = ref<string | null>(null)
  const preview = ref<SwitchPreviewResponse | null>(null)
  const previewing = ref(false)
  const applying = ref(false)
  const error = ref<string | null>(null)
  const errorCode = ref<string | null>(null)
  const details = ref<ApiErrorDetails | null>(null)
  const lastApplied = ref<SwitchApplyResponse | null>(null)

  let previewRequestId = 0
  let applyRequestId = 0

  const canPreview = computed(
    () => selectedProfileId.value !== null && !previewing.value && !applying.value,
  )
  const canApply = computed(
    () => preview.value?.can_apply === true && !applying.value,
  )

  function resetFeedback(): void {
    error.value = null
    errorCode.value = null
    details.value = null
  }

  function sync(
    nextToolId: string,
    profiles: ProfileView[],
    bindings: BindingView[],
  ): void {
    if (toolId.value !== nextToolId) {
      toolId.value = nextToolId
      selectedProfileId.value = null
      selectedModelId.value = null
      preview.value = null
      lastApplied.value = null
      resetFeedback()
    }

    const profileStillExists = profiles.some(
      (profile) => profile.id === selectedProfileId.value,
    )
    if (!profileStillExists) {
      selectedProfileId.value = defaultProfileId(nextToolId, profiles, bindings)
      selectedModelId.value = firstModelId(selectedProfileId.value, profiles)
      return
    }

    const modelStillExists = profiles
      .find((profile) => profile.id === selectedProfileId.value)
      ?.models.some((model) => model.id === selectedModelId.value)
    if (!modelStillExists) {
      selectedModelId.value = firstModelId(selectedProfileId.value, profiles)
    }
  }

  function selectProfile(profileId: string, profiles: ProfileView[]): void {
    selectedProfileId.value = profileId
    selectedModelId.value = firstModelId(profileId, profiles)
    preview.value = null
    lastApplied.value = null
    resetFeedback()
  }

  function selectModel(modelId: string | null): void {
    selectedModelId.value = modelId
    preview.value = null
    resetFeedback()
  }

  function clearPreview(): void {
    previewRequestId += 1
    preview.value = null
    resetFeedback()
  }

  async function startPreview(): Promise<SwitchPreviewResponse | null> {
    if (selectedProfileId.value === null || toolId.value === null || previewing.value) {
      return null
    }
    const requestId = ++previewRequestId
    previewing.value = true
    preview.value = null
    lastApplied.value = null
    resetFeedback()

    try {
      const response = await previewSwitch({
        tool_id: toolId.value,
        profile_id: selectedProfileId.value,
        model: selectedModelId.value ?? undefined,
      })
      if (requestId !== previewRequestId) {
        return null
      }
      preview.value = response
      return response
    } catch (caught) {
      if (requestId === previewRequestId) {
        error.value = errorMessage(caught)
        errorCode.value = errorCodeOf(caught)
        details.value = errorDetails(caught)
      }
      return null
    } finally {
      if (requestId === previewRequestId) {
        previewing.value = false
      }
    }
  }

  async function startApply(): Promise<SwitchApplyResponse | null> {
    const current = preview.value
    if (current === null || !current.can_apply || applying.value) {
      return null
    }
    const requestId = ++applyRequestId
    applying.value = true
    resetFeedback()

    try {
      const response = await applySwitch({
        tool_id: current.tool_id,
        profile_id: current.profile_id,
        model: current.model ?? undefined,
        preview_digest: current.preview_digest,
        observations: current.observations,
      })
      if (requestId !== applyRequestId) {
        return null
      }
      lastApplied.value = response
      preview.value = null
      return response
    } catch (caught) {
      if (requestId === applyRequestId) {
        error.value = errorMessage(caught)
        errorCode.value = errorCodeOf(caught)
        details.value = errorDetails(caught)
      }
      return null
    } finally {
      if (requestId === applyRequestId) {
        applying.value = false
      }
    }
  }

  return {
    toolId,
    selectedProfileId,
    selectedModelId,
    preview,
    previewing,
    applying,
    error,
    errorCode,
    details,
    lastApplied,
    canPreview,
    canApply,
    sync,
    selectProfile,
    selectModel,
    clearPreview,
    startPreview,
    startApply,
  }
})
