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
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ tools: [], warnings: [] })))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('opens the workbench at / and marks the only available entry as current', async () => {
    const wrapper = await mountApp('/')

    const nav = getByRole(wrapper, 'navigation')
    expect(nav.findAll('a')).toHaveLength(1)

    const link = getByRole(nav, 'link', { name: '工作台' })
    expect(link.attributes('href')).toBe('/')
    expect(link.attributes('aria-current')).toBe('page')

    expect(nav.text()).not.toContain('首页')
    expect(nav.text()).not.toContain('供应商')
    expect(nav.text()).not.toContain('操作记录')
    expect(nav.text()).not.toContain('用量')
    expect(nav.text()).not.toContain('设置')

    expect(getByText(wrapper, '尚未发现已安装的 AI 工具')).toBeTruthy()
  })

  it('redirects the legacy /tools entry to the same workbench', async () => {
    const wrapper = await mountApp('/tools')

    expect(router.currentRoute.value.path).toBe('/')
    expect(getByText(wrapper, '尚未发现已安装的 AI 工具')).toBeTruthy()
  })
})
