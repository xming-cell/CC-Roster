import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import App from '../App.vue'
import router from '../router'
import { getByRole, getByText } from './dom'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

const defaultSettings = {
  read_only: false,
  hotkey: 'ctrl+alt+c',
  autostart: false,
  updated_at: '2026-11-17T10:00:00+00:00',
  message: '可写模式',
  capabilities: { tray: true, hotkey: true, autostart: true },
}

const emptyProfiles = {
  profiles: [],
  bindings: [],
  secret_store: { backend: 'keyring', fallback: false, message: null },
  warnings: [],
}

async function mountApp(path = '/') {
  await router.push(path)
  await router.isReady()
  const wrapper = mount(App, {
    global: { plugins: [createPinia(), router] },
  })
  await flushPromises()
  return wrapper
}

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((path: string) => {
        if (path === '/api/profiles') {
          return Promise.resolve(jsonResponse(emptyProfiles))
        }
        if (path === '/api/settings') {
          return Promise.resolve(jsonResponse(defaultSettings))
        }
        return Promise.resolve(jsonResponse({ tools: [], warnings: [] }))
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('opens the workbench at / and marks it current while keeping the provider entry available', async () => {
    const wrapper = await mountApp('/')

    const nav = getByRole(wrapper, 'navigation')
    expect(nav.findAll('a')).toHaveLength(5)

    const workbench = getByRole(nav, 'link', { name: '工作台' })
    const providers = getByRole(nav, 'link', { name: '供应商' })
    const audit = getByRole(nav, 'link', { name: '操作记录' })
    const usage = getByRole(nav, 'link', { name: '用量' })
    const settings = getByRole(nav, 'link', { name: '设置' })
    expect(workbench.attributes('href')).toBe('/')
    expect(workbench.attributes('aria-current')).toBe('page')
    expect(providers.attributes('href')).toBe('/providers')
    expect(audit.attributes('href')).toBe('/audit')
    expect(usage.attributes('href')).toBe('/usage')
    expect(settings.attributes('href')).toBe('/settings')
    expect(providers.attributes('aria-current')).toBeUndefined()

    expect(getByText(wrapper, '尚未发现已安装的 AI 工具')).toBeTruthy()
  })

  it('opens the provider page at /providers and marks its navigation entry current', async () => {
    const wrapper = await mountApp('/providers')

    const nav = getByRole(wrapper, 'navigation')
    const workbench = getByRole(nav, 'link', { name: '工作台' })
    const providers = getByRole(nav, 'link', { name: '供应商' })

    expect(providers.attributes('aria-current')).toBe('page')
    expect(workbench.attributes('aria-current')).toBeUndefined()
    expect(getByText(wrapper, '选择一个工具')).toBeTruthy()
    expect(getByText(wrapper, '按工具管理供应商与绑定关系')).toBeTruthy()
  })

  it('redirects the legacy /tools entry to the same workbench', async () => {
    const wrapper = await mountApp('/tools')

    expect(router.currentRoute.value.path).toBe('/')
    expect(getByText(wrapper, '尚未发现已安装的 AI 工具')).toBeTruthy()
  })
})
