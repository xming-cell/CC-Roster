import { requestJson } from './client'

export type ProfileProtocol = 'anthropic' | 'openai'
export type SecretBackend = 'keyring' | 'file'
export type SecretStoreBackend = SecretBackend | 'unavailable'
export type ProfileWarningCode = 'SECRET_MISSING' | 'SECRET_STORE_ERROR'

export interface ModelEntry {
  id: string
  display_name: string | null
}

export interface ToolRef {
  tool_id: string
  display_name: string
  installed: boolean
}

export interface ProfileWarning {
  code: ProfileWarningCode
  message: string
}

export interface SecretStoreStatus {
  backend: SecretStoreBackend
  fallback: boolean
  message: string | null
}

export interface ProfileView {
  id: string
  name: string
  protocol: ProfileProtocol
  base_url: string
  models: ModelEntry[]
  created_at: string
  updated_at: string
  has_secret: boolean
  secret_preview: string | null
  secret_backend: SecretBackend | null
  used_by: ToolRef[]
  warnings: ProfileWarning[]
}

export interface BindingView {
  tool_id: string
  profile_id: string
  bound_at: string
  active: boolean
  applied_at: string | null
  snapshot_id: string | null
}

export interface ProfileListResponse {
  profiles: ProfileView[]
  bindings: BindingView[]
  secret_store: SecretStoreStatus
  warnings: ProfileWarning[]
}

export interface ProfileCreateInput {
  name: string
  protocol: ProfileProtocol
  base_url: string
  models: ModelEntry[]
  secret?: string | null
}

export interface ProfileUpdateInput {
  name?: string
  protocol?: ProfileProtocol
  base_url?: string
  models?: ModelEntry[]
  secret?: string | null
}

export interface ProfileDeleteResponse {
  deleted: boolean
  unbound_tools: ToolRef[]
}

export interface BindingDeleteResponse {
  tool_id: string
  removed: boolean
}

function jsonInit(method: string, body?: unknown): RequestInit {
  if (body === undefined) {
    return { method }
  }
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export function listProfiles(): Promise<ProfileListResponse> {
  return requestJson<ProfileListResponse>('/api/profiles')
}

export function getProfile(profileId: string): Promise<ProfileView> {
  return requestJson<ProfileView>(`/api/profiles/${encodeURIComponent(profileId)}`)
}

export function createProfile(input: ProfileCreateInput): Promise<ProfileView> {
  return requestJson<ProfileView>('/api/profiles', jsonInit('POST', input))
}

export function updateProfile(
  profileId: string,
  input: ProfileUpdateInput,
): Promise<ProfileView> {
  return requestJson<ProfileView>(
    `/api/profiles/${encodeURIComponent(profileId)}`,
    jsonInit('PATCH', input),
  )
}

export function copyProfile(profileId: string, name?: string): Promise<ProfileView> {
  const body = name === undefined ? undefined : { name }
  return requestJson<ProfileView>(
    `/api/profiles/${encodeURIComponent(profileId)}/copy`,
    jsonInit('POST', body),
  )
}

export function deleteProfile(
  profileId: string,
  confirm = false,
): Promise<ProfileDeleteResponse> {
  const query = confirm ? '?confirm=true' : ''
  return requestJson<ProfileDeleteResponse>(
    `/api/profiles/${encodeURIComponent(profileId)}${query}`,
    { method: 'DELETE' },
  )
}

export function bindToolProfile(
  toolId: string,
  profileId: string,
): Promise<BindingView> {
  return requestJson<BindingView>(
    `/api/tools/${encodeURIComponent(toolId)}/profile`,
    jsonInit('PUT', { profile_id: profileId }),
  )
}

export function unbindToolProfile(toolId: string): Promise<BindingDeleteResponse> {
  return requestJson<BindingDeleteResponse>(
    `/api/tools/${encodeURIComponent(toolId)}/profile`,
    { method: 'DELETE' },
  )
}