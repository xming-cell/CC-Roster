import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { SettingsView as SettingsData } from '../api/settings'
import type { ToolListResponse } from '../api/tools'
import SettingsView from '../views/SettingsView.vue'
import { getByRole } from './dom'

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) } as unknown as Response
}

const settings: SettingsData = {
  read_only: false,
  hotkey: 'ctrl+alt+c',
  autostart: false,
  updated_at: '2026-11-17T10:00:00+00:00',
  message: '可写模式',
  capabilities: { tray: true, hotkey: true, autostart: true },
}

const tools: ToolListResponse = {
  tools: [
    {
      id: 'claude-code', display_name: 'Claude Code', status: 'ok', installed: true, configured: true,
      version: null, provider: 'Anthropic', base_url: 'https://api.anthropic.com', model: 'claude-sonnet-4-5',
      is_third_party: false, config_path: null, last_modified: null, has_secret: true, secret_preview: null,
      warnings: [], capabilities: { read: true, write: true, sessions: false, launch: false, write_mode: 'managed_fields' },
    },
    {
      id: 'codex-cli', display_name: 'Codex CLI', status: 'ok', installed: true, configured: true,
      version: null, provider: 'OpenAI', base_url: null, model: null, is_third_party: true, config_path: null,
      last_modified: null, has_secret: false, secret_preview: null, warnings: [],
      capabilities: { read: true, write: true, sessions: false, launch: false, write_mode: 'managed_fields' },
    },
  ],
  warnings: [],
}

interface Options {
  readOnly?: boolean
  capabilities?: SettingsData['capabilities']
  failAppearance?: boolean
}

interface Call { path: string; method: string; body: Record<string, unknown> }

function mountView(calls: Call[], options: Options = {}) {
  let current: SettingsData = {
    ...settings,
    read_only: options.readOnly ?? false,
    capabilities: options.capabilities ?? settings.capabilities,
  }
  let failAppearance = options.failAppearance ?? false
  const appearances: Record<string, unknown> = {}
  vi.stubGlobal('fetch', vi.fn((input: string, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) as Record<string, unknown> : {}
    calls.push({ path, method, body })
    if (path === '/api/settings' && method === 'GET') return Promise.resolve(jsonResponse(current))
    if (path === '/api/settings' && method === 'PUT') {
      current = { ...current, ...body, message: body.read_only === true ? '只读模式已开启' : '可写模式' }
      return Promise.resolve(jsonResponse(current))
    }
    if (path === '/api/tools') return Promise.resolve(jsonResponse(tools))
    if (path === '/api/appearances' && method === 'GET') return Promise.resolve(jsonResponse({ schema_version: 1, appearances }))
    if (path.startsWith('/api/appearances/') && method === 'PUT') {
      if (failAppearance) return Promise.resolve(jsonResponse({ code: 'APPEARANCE_WRITE_FAILED', message: '外观写入失败' }, 500))
      const saved = { tool_id: path.split('/').pop(), accent_color: body.accent_color ?? null,
        background_color: body.background_color ?? null, bubble_preset: body.bubble_preset ?? null }
      appearances[String(saved.tool_id)] = saved
      return Promise.resolve(jsonResponse(saved))
    }
    if (path.startsWith('/api/appearances/') && method === 'DELETE') {
      return Promise.resolve(jsonResponse({ tool_id: path.split('/').pop(), reset: true }))
    }
    return Promise.resolve(jsonResponse({}))
  }))
  return {
    wrapper: mount(SettingsView, { global: { plugins: [createPinia()] } }),
    setFailAppearance(value: boolean) { failAppearance = value },
  }
}

async function settle(): Promise<void> {
  await flushPromises()
  await flushPromises()
}

describe('SettingsView', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('disables appearance controls in read-only mode and can turn read-only off', async () => {
    const calls: Call[] = []
    const { wrapper } = mountView(calls, { readOnly: true })
    await settle()

    expect(wrapper.text()).toContain('只读模式已开启')
    expect(wrapper.findAll('fieldset').every((field) => field.attributes('disabled') !== undefined)).toBe(true)
    const toggle = getByRole(wrapper, 'switch', { name: '只读模式' })
    expect(toggle.attributes('aria-checked')).toBe('true')

    await toggle.trigger('click')
    await settle()

    const update = calls.find((call) => call.path === '/api/settings' && call.method === 'PUT')
    expect(update?.body.read_only).toBe(false)
    expect(wrapper.text()).not.toContain('只读模式已开启，外观偏好暂不可修改')
  })

  it('optimistically saves appearance and rolls back when the write fails', async () => {
    const calls: Call[] = []
    const harness = mountView(calls)
    await settle()

    await getByRole(harness.wrapper, 'button', { name: '强调色 #06B6D4' }).trigger('click')
    await settle()
    expect(calls.some((call) => call.method === 'PUT' && call.path === '/api/appearances/claude-code' && call.body.accent_color === '#06B6D4')).toBe(true)

    harness.setFailAppearance(true)
    await getByRole(harness.wrapper, 'button', { name: '强调色 #16A34A' }).trigger('click')
    await settle()

    expect(harness.wrapper.text()).toContain('外观写入失败')
    const active = harness.wrapper.findAll('.appearance-swatch--active')
    expect(active.some((item) => item.attributes('aria-label') === '强调色 #06B6D4')).toBe(true)
  })

  it('hides unsupported desktop controls instead of showing dead switches', async () => {
    const calls: Call[] = []
    const { wrapper } = mountView(calls, {
      capabilities: { tray: false, hotkey: false, autostart: false },
    })
    await settle()

    expect(wrapper.find('input[aria-label="全局快捷键"]').exists()).toBe(false)
    expect(wrapper.find('[role="switch"][aria-label="开机自启"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('当前平台不支持的能力已隐藏')
  })
})
