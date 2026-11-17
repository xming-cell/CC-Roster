import { requestJson } from './client'

export type ProfileProtocol = 'anthropic' | 'openai'
export type SecretBackend = 'keyring' | 'file'
export type SecretStoreBackend = SecretBackend | 'unavailable'
export type ProfileWarningCode = 'SECRET_MISSING' | 'SECRET_STORE_ERROR'
export type HealthCheckStatus =
  | 'CONNECTED'
  | 'INVALID_CREDENTIALS'
  | 'INVALID_ADDRESS'
  | 'MODEL_NOT_FOUND'
  | 'TIMEOUT'
  | 'RATE_LIMITED'
  | 'SECRET_MISSING'
  | 'SECRET_STORE_ERROR'
  | 'MODEL_REQUIRED'
  | 'UNKNOWN'

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

export interface SecretStoreStatus {
  backend: SecretStoreBackend
  fallback: boolean
  message: string | null
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
  secret: string | null
}

export interface ProfileUpdateInput {
  name?: string
  protocol?: ProfileProtocol
  base_url?: string
  models?: ModelEntry[]
  secret?: string | null
}

export interface ProfileCopyInput {
  name?: string
}

export interface BindingDeleteResponse {
  tool_id: string
  removed: boolean
}

export interface ProfileDeleteResponse {
  deleted: boolean
  unbound_tools: ToolRef[]
}

export interface HealthCheckResponse {
  profile_id: string
  model: string | null
  status: HealthCheckStatus
  attempted: boolean
  duration_ms: number | null
  message: string
  checked_at: string
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export function listProfiles(toolId?: string): Promise<ProfileListResponse> {
  const query = toolId === undefined ? '' : `?tool_id=${encodeURIComponent(toolId)}`
  return requestJson<ProfileListResponse>(`/api/profiles${query}`)
}

export function createProfile(payload: ProfileCreateInput): Promise<ProfileView> {
  return requestJson<ProfileView>('/api/profiles', jsonInit('POST', payload))
}

export function updateProfile(
  profileId: string,
  payload: ProfileUpdateInput,
): Promise<ProfileView> {
  return requestJson<ProfileView>(
    `/api/profiles/${encodeURIComponent(profileId)}`,
    jsonInit('PATCH', payload),
  )
}

export function copyProfile(
  profileId: string,
  payload: ProfileCopyInput = {},
): Promise<ProfileView> {
  return requestJson<ProfileView>(
    `/api/profiles/${encodeURIComponent(profileId)}/copy`,
    jsonInit('POST', payload),
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

export function bindProfile(toolId: string, profileId: string): Promise<BindingView> {
  return requestJson<BindingView>(
    `/api/tools/${encodeURIComponent(toolId)}/profile`,
    jsonInit('PUT', { profile_id: profileId }),
  )
}

export function unbindProfile(
  toolId: string,
  profileId: string,
): Promise<BindingDeleteResponse> {
  return requestJson<BindingDeleteResponse>(
    `/api/tools/${encodeURIComponent(toolId)}/profiles/${encodeURIComponent(profileId)}`,
    { method: 'DELETE' },
  )
}

export function healthCheckProfile(
  profileId: string,
  model?: string,
): Promise<HealthCheckResponse> {
  const payload = model === undefined ? {} : { model }
  return requestJson<HealthCheckResponse>(
    `/api/profiles/${encodeURIComponent(profileId)}/health-check`,
    jsonInit('POST', payload),
  )
}
