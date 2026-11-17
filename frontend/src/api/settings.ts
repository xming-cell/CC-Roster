import { requestJson } from './client'

export interface DesktopCapabilities {
  tray: boolean
  hotkey: boolean
  autostart: boolean
}

export interface SettingsView {
  read_only: boolean
  hotkey: string
  autostart: boolean
  updated_at: string
  message: string
  capabilities: DesktopCapabilities
}

export interface SettingsUpdate {
  read_only?: boolean
  hotkey?: string
  autostart?: boolean
}

export function getSettings(): Promise<SettingsView> {
  return requestJson<SettingsView>('/api/settings')
}

export function updateSettings(payload: SettingsUpdate): Promise<SettingsView> {
  return requestJson<SettingsView>('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
