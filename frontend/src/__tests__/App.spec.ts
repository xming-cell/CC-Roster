import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import App from '../App.vue'
import router from '../router'
import { getByRole } from './dom'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

async function mountApp() {
  await router.push('/')
  await router.isReady()
  const wrapper = mount(App, {
    global: { plugins: [createPinia(), router] },
  })
  await flushPromises()
  return wrapper
}

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ status: 'ok' })))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the home route with backend status', async () => {
    const wrapper = await mountApp()

    expect(wrapper.text()).toContain('backend: ok')
  })

  it('shows a readable error when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const wrapper = await mountApp()

    expect(wrapper.text()).toContain('backend: error')
    expect(wrapper.text()).toContain('无法连接后端服务')
  })

  it('links to the tools route and renders the tools view', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((path: string) =>
        Promise.resolve(
          jsonResponse(path === '/api/tools' ? { tools: [], warnings: [] } : { status: 'ok' }),
        ),
      ),
    )
    const wrapper = await mountApp()

    const link = getByRole(wrapper, 'link', { name: '工具' })
    expect(link.attributes('href')).toBe('/tools')

    await router.push('/tools')
    await flushPromises()

    expect(wrapper.text()).toContain('未发现已安装的 AI 工具')
  })
})