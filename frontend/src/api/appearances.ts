import { requestJson } from './client'

export type BubblePreset = 'soft' | 'rounded' | 'compact'

export interface AppearanceOverride {
  accent_color: string | null
  background_color: string | null
  bubble_preset: BubblePreset | null
}

export interface AppearanceListResponse {
  schema_version: 1
  appearances: Record<string, AppearanceOverride>
}

export interface AppearanceView extends AppearanceOverride {
  tool_id: string
}

export interface AppearanceResetResponse {
  tool_id: string
  reset: boolean
}

export function getAppearances(): Promise<AppearanceListResponse> {
  return requestJson<AppearanceListResponse>('/api/appearances')
}

export function saveAppearance(
  toolId: string,
  appearance: AppearanceOverride,
): Promise<AppearanceView> {
  return requestJson<AppearanceView>(`/api/appearances/${encodeURIComponent(toolId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(appearance),
  })
}

export function resetAppearance(toolId: string): Promise<AppearanceResetResponse> {
  return requestJson<AppearanceResetResponse>(
    `/api/appearances/${encodeURIComponent(toolId)}`,
    { method: 'DELETE' },
  )
}
