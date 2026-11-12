import { requestJson } from './client'

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

export interface HealthCheckRequest {
  model?: string
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

export function checkProfileHealth(
  profileId: string,
  input: HealthCheckRequest = {},
): Promise<HealthCheckResponse> {
  return requestJson<HealthCheckResponse>(
    `/api/profiles/${encodeURIComponent(profileId)}/health-check`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    },
  )
}
