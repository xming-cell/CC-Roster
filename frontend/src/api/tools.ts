import { requestJson } from './client'

export type ToolStatus = 'ok' | 'unconfigured' | 'error'

export type WarningCode =
  | 'PARSE_ERROR'
  | 'PERMISSION_DENIED'
  | 'UNKNOWN_FORMAT'
  | 'UNSUPPORTED_VERSION'
  | 'CONFIG_EMPTY'
  | 'NO_MANAGED_FIELDS'
  | 'SECRET_IN_ENV'
  | 'ADAPTER_ERROR'

export interface ToolWarning {
  code: WarningCode
  message: string
}

export interface ToolCapabilities {
  read: boolean
  write: boolean
  sessions: boolean
  launch: boolean
  write_mode: 'none' | 'managed_fields'
}

export interface ToolView {
  id: string
  display_name: string
  status: ToolStatus
  installed: boolean
  configured: boolean
  version: string | null
  provider: string | null
  base_url: string | null
  model: string | null
  is_third_party: boolean | null
  config_path: string | null
  last_modified: string | null
  has_secret: boolean
  secret_preview: string | null
  warnings: ToolWarning[]
  capabilities: ToolCapabilities
}

export interface ToolListResponse {
  tools: ToolView[]
  warnings: ToolWarning[]
}

export function getTools(): Promise<ToolListResponse> {
  return requestJson<ToolListResponse>('/api/tools')
}

export function getTool(toolId: string): Promise<ToolView> {
  return requestJson<ToolView>(`/api/tools/${encodeURIComponent(toolId)}`)
}