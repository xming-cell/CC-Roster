import { requestJson } from './client'

export interface HealthResponse {
  status: string
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/api/health')
}