import { requestJson } from './client'

export interface DirectoryPickResponse {
  path: string | null
  cancelled: boolean
}

export function pickDirectory(): Promise<DirectoryPickResponse> {
  return requestJson<DirectoryPickResponse>(
    '/api/system/pick-directory',
    { method: 'POST' },
    { timeoutMs: 125_000 },
  )
}
