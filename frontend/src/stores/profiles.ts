import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import {
  bindProfile,
  copyProfile,
  createProfile,
  deleteProfile as requestDeleteProfile,
  healthCheckProfile,
  listProfiles,
  unbindProfile,
  updateProfile as requestUpdateProfile,
} from '../api/profiles'
import type {
  BindingView,
  HealthCheckResponse,
  ProfileCreateInput,
  ProfileListResponse,
  ProfileWarning,
  ProfileView,
  SecretStoreStatus,
  ProfileUpdateInput,
} from '../api/profiles'
import { errorText } from '../utils/profileDisplay'

export interface ProviderItem {
  profile: ProfileView
  binding: BindingView
}

export interface ToolProviderSummary {
  count: number
  activeName: string | null
}

function profilesById(profiles: ProfileView[]): Map<string, ProfileView> {
  return new Map(profiles.map((profile) => [profile.id, profile]))
}

function itemsFromResponse(profiles: ProfileView[], bindings: BindingView[]): ProviderItem[] {
  const byId = profilesById(profiles)
  const result: ProviderItem[] = []
  for (const binding of bindings) {
    const profile = byId.get(binding.profile_id)
    if (profile !== undefined) {
      result.push({ profile, binding })
    }
  }
  return result
}

export const useProfilesStore = defineStore('profiles', () => {
  const summary = ref<ProfileListResponse | null>(null)
  const summaryLoading = ref(false)
  const summaryLoaded = ref(false)
  const summaryError = ref<string | null>(null)

  const selectedToolId = ref<string | null>(null)
  const items = ref<ProviderItem[]>([])
  const listLoading = ref(false)
  const listLoaded = ref(false)
  const listError = ref<string | null>(null)
  const listSecretStore = ref<SecretStoreStatus | null>(null)
  const listWarnings = ref<ProfileWarning[]>([])

  const healthResults = ref<Record<string, HealthCheckResponse>>({})
  const healthLoading = ref<Record<string, boolean>>({})
  const healthErrors = ref<Record<string, string>>({})

  let summaryRequestId = 0
  let listRequestId = 0

  const summariesByTool = computed<Record<string, ToolProviderSummary>>(() => {
    const result: Record<string, ToolProviderSummary> = {}
    const data = summary.value
    if (data === null) {
      return result
    }
    const byId = profilesById(data.profiles)
    for (const binding of data.bindings) {
      const current = result[binding.tool_id] ?? { count: 0, activeName: null }
      current.count += 1
      if (binding.active) {
        const profile = byId.get(binding.profile_id)
        current.activeName = profile?.name ?? binding.profile_id
      }
      result[binding.tool_id] = current
    }
    return result
  })

  function clearHealth(): void {
    healthResults.value = {}
    healthErrors.value = {}
    healthLoading.value = {}
  }

  async function fetchSummary(): Promise<void> {
    const requestId = ++summaryRequestId
    summaryLoading.value = true
    summaryError.value = null

    try {
      const response = await listProfiles()
      if (requestId !== summaryRequestId) {
        return
      }
      summary.value = response
      summaryLoaded.value = true
    } catch (caught) {
      if (requestId !== summaryRequestId) {
        return
      }
      summary.value = null
      summaryLoaded.value = false
      summaryError.value = errorText(caught, '供应商汇总读取失败')
    } finally {
      if (requestId === summaryRequestId) {
        summaryLoading.value = false
      }
    }
  }

  async function loadTool(toolId: string, force: boolean): Promise<void> {
    if (
      !force &&
      selectedToolId.value === toolId &&
      (listLoading.value || (listLoaded.value && listError.value === null))
    ) {
      return
    }

    const requestId = ++listRequestId
    selectedToolId.value = toolId
    items.value = []
    listLoading.value = true
    listLoaded.value = false
    listError.value = null
    listSecretStore.value = null
    listWarnings.value = []
    clearHealth()

    try {
      const response = await listProfiles(toolId)
      if (requestId !== listRequestId || selectedToolId.value !== toolId) {
        return
      }
      items.value = itemsFromResponse(response.profiles, response.bindings)
      listSecretStore.value = response.secret_store
      listWarnings.value = response.warnings
      listLoaded.value = true
    } catch (caught) {
      if (requestId !== listRequestId || selectedToolId.value !== toolId) {
        return
      }
      listError.value = errorText(caught, '供应商列表读取失败')
    } finally {
      if (requestId === listRequestId) {
        listLoading.value = false
      }
    }
  }

  function selectTool(toolId: string): Promise<void> {
    return loadTool(toolId, false)
  }

  function reloadSelected(): Promise<void> {
    const toolId = selectedToolId.value
    if (toolId === null) {
      return Promise.resolve()
    }
    return loadTool(toolId, true)
  }

  async function refreshAll(): Promise<void> {
    await fetchSummary()
    await reloadSelected()
  }

  function requireSelectedTool(): string {
    const toolId = selectedToolId.value
    if (toolId === null) {
      throw new ApiError('TOOL_NOT_SELECTED', '请先选择工具', null)
    }
    return toolId
  }

  async function createAndBind(payload: ProfileCreateInput): Promise<ProfileView> {
    const toolId = requireSelectedTool()
    const created = await createProfile(payload)

    try {
      await bindProfile(toolId, created.id)
    } catch (caught) {
      try {
        await requestDeleteProfile(created.id, true)
      } catch {
        throw new ApiError(
          'CREATE_BIND_ROLLBACK_FAILED',
          `供应商「${created.name}」已创建，但绑定失败且回滚失败：${errorText(caught, '未知错误')}`,
          null,
        )
      }
      throw new ApiError(
        'CREATE_BIND_FAILED',
        `供应商「${created.name}」已创建，但绑定失败：${errorText(caught, '未知错误')}`,
        null,
      )
    }

    await refreshAll()
    return created
  }

  async function copyAndBind(profileId: string): Promise<ProfileView> {
    const toolId = requireSelectedTool()
    const copied = await copyProfile(profileId)

    try {
      await bindProfile(toolId, copied.id)
    } catch (caught) {
      try {
        await requestDeleteProfile(copied.id, true)
      } catch {
        throw new ApiError(
          'COPY_BIND_ROLLBACK_FAILED',
          `供应商副本「${copied.name}」已创建，但绑定失败且回滚失败：${errorText(caught, '未知错误')}`,
          null,
        )
      }
      throw new ApiError(
        'COPY_BIND_FAILED',
        `供应商副本「${copied.name}」已创建，但绑定失败：${errorText(caught, '未知错误')}`,
        null,
      )
    }

    await refreshAll()
    return copied
  }

  async function updateItem(
    profileId: string,
    payload: ProfileUpdateInput,
  ): Promise<ProfileView> {
    const updated = await requestUpdateProfile(profileId, payload)
    await refreshAll()
    return updated
  }

  async function removeBinding(profileId: string): Promise<void> {
    const toolId = requireSelectedTool()
    await unbindProfile(toolId, profileId)
    await refreshAll()
  }

  async function deleteItem(profileId: string, confirm: boolean): Promise<void> {
    await requestDeleteProfile(profileId, confirm)
    await refreshAll()
  }

  async function checkHealth(profileId: string): Promise<void> {
    if (healthLoading.value[profileId] === true) {
      return
    }
    const toolId = selectedToolId.value
    healthLoading.value = { ...healthLoading.value, [profileId]: true }
    const nextResults = { ...healthResults.value }
    delete nextResults[profileId]
    healthResults.value = nextResults
    const nextErrors = { ...healthErrors.value }
    delete nextErrors[profileId]
    healthErrors.value = nextErrors

    try {
      const result = await healthCheckProfile(profileId)
      if (selectedToolId.value !== toolId) {
        return
      }
      healthResults.value = { ...healthResults.value, [profileId]: result }
    } catch (caught) {
      if (selectedToolId.value !== toolId) {
        return
      }
      healthErrors.value = {
        ...healthErrors.value,
        [profileId]: errorText(caught, '健康检查失败'),
      }
    } finally {
      if (selectedToolId.value === toolId) {
        healthLoading.value = { ...healthLoading.value, [profileId]: false }
      }
    }
  }

  return {
    summary,
    summaryLoading,
    summaryLoaded,
    summaryError,
    summariesByTool,
    selectedToolId,
    items,
    listLoading,
    listLoaded,
    listError,
    listSecretStore,
    listWarnings,
    healthResults,
    healthLoading,
    healthErrors,
    fetchSummary,
    selectTool,
    reloadSelected,
    refreshAll,
    createAndBind,
    copyAndBind,
    updateItem,
    removeBinding,
    deleteItem,
    checkHealth,
  }
})
