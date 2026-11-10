import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import {
  bindToolProfile,
  copyProfile,
  createProfile,
  deleteProfile,
  listProfiles,
  unbindToolProfile,
  updateProfile,
} from '../api/profiles'
import type {
  BindingDeleteResponse,
  BindingView,
  ProfileCreateInput,
  ProfileDeleteResponse,
  ProfileListResponse,
  ProfileUpdateInput,
  ProfileView,
  ProfileWarning,
  SecretStoreStatus,
} from '../api/profiles'

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : '档案信息读取失败'
}

export const useProfilesStore = defineStore('profiles', () => {
  const profiles = ref<ProfileView[]>([])
  const bindings = ref<BindingView[]>([])
  const secretStore = ref<SecretStoreStatus | null>(null)
  const warnings = ref<ProfileWarning[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const refreshError = ref<string | null>(null)
  const selectedProfileId = ref<string | null>(null)

  const selectedProfile = computed(
    () =>
      profiles.value.find((profile) => profile.id === selectedProfileId.value) ?? null,
  )

  let listRequestId = 0

  function applyList(response: ProfileListResponse): void {
    profiles.value = response.profiles
    bindings.value = response.bindings
    secretStore.value = response.secret_store
    warnings.value = response.warnings
    if (
      selectedProfileId.value !== null &&
      !response.profiles.some((profile) => profile.id === selectedProfileId.value)
    ) {
      selectedProfileId.value = null
    }
  }

  async function fetchProfiles(): Promise<void> {
    const requestId = ++listRequestId
    loading.value = true
    error.value = null
    refreshError.value = null
    try {
      const response = await listProfiles()
      if (requestId !== listRequestId) {
        return
      }
      applyList(response)
    } catch (caught) {
      if (requestId !== listRequestId) {
        return
      }
      if (profiles.value.length > 0) {
        refreshError.value = errorMessage(caught)
      } else {
        profiles.value = []
        bindings.value = []
        secretStore.value = null
        warnings.value = []
        error.value = errorMessage(caught)
      }
    } finally {
      if (requestId === listRequestId) {
        loading.value = false
      }
    }
  }

  function selectProfile(profileId: string | null): void {
    selectedProfileId.value = profileId
  }

  async function create(input: ProfileCreateInput): Promise<ProfileView> {
    const created = await createProfile(input)
    await fetchProfiles()
    return created
  }

  async function update(
    profileId: string,
    input: ProfileUpdateInput,
  ): Promise<ProfileView> {
    const updated = await updateProfile(profileId, input)
    await fetchProfiles()
    return updated
  }

  async function copy(profileId: string): Promise<ProfileView> {
    const copied = await copyProfile(profileId)
    await fetchProfiles()
    return copied
  }

  async function remove(
    profileId: string,
    confirm: boolean,
  ): Promise<ProfileDeleteResponse> {
    const result = await deleteProfile(profileId, confirm)
    await fetchProfiles()
    return result
  }

  async function bind(toolId: string, profileId: string): Promise<void> {
    await bindToolProfile(toolId, profileId)
    await fetchProfiles()
  }

  async function unbind(toolId: string): Promise<BindingDeleteResponse> {
    const result = await unbindToolProfile(toolId)
    await fetchProfiles()
    return result
  }

  return {
    profiles,
    bindings,
    secretStore,
    warnings,
    loading,
    error,
    refreshError,
    selectedProfileId,
    selectedProfile,
    fetchProfiles,
    selectProfile,
    create,
    update,
    copy,
    remove,
    bind,
    unbind,
  }
})