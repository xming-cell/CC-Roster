import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { ToolView } from '../api/tools'
import ToolsView from '../views/ToolsView.vue'
import { getByRole, getByText } from './dom'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

const capabilities: ToolView['capabilities'] = {
  read: true,
  write: false,
  sessions: false,
  launch: false,
  write_mode: 'none',
}

function makeTool(overrides: Partial<ToolView>): ToolView {
  return {
    id: 'claude-code',
    display_name: 'Claude Code',
    status: 'ok',
    installed: true,
    configured: true,
    version: null,
    provider: 'Anthropic',
    base_url: 'https://api.anthropic.com',
    model: 'claude-sonnet-4',
    is_third_party: false,
    config_path: '/home/me/.claude/settings.json',
    last_modified: '2023-11-14T22:13:20+00:00',
    has_secret: true,
    secret_preview: 'sk-a****cdef',
    warnings: [],
    capabilities,
    ...overrides,
  }
}

const claudeTool = makeTool({})

const codexTool = makeTool({
  id: 'codex-cli',
  display_name: 'Codex CLI',
  status: 'unconfigured',
  configured: false,
  provider: null,
  base_url: null,
  model: null,
  is_third_party: null,
  config_path: '/home/me/.codex/config.toml',
  has_secret: false,
  secret_preview: null,
})

const brokenTool = makeTool({
  id: 'broken-tool',
  display_name: 'Broken Tool',
  status: 'error',
  configured: false,
  warnings: [{ code: 'PARSE_ERROR', message: 'settings.json 第 1 行第 2 列格式错误' }],
})

function stubApi(routes: Record<string, unknown>): void {
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string) => {
      const body = routes[path]
      if (body === undefined) {
        return Promise.reject(new TypeError(`unexpected request: ${path}`))
      }
      return Promise.resolve(jsonResponse(body))
    }),
  )
}

function mountToolsView() {
  return mount(ToolsView, { global: { plugins: [createPinia()] } })
}

describe('ToolsView', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows 检测中 while the list request is pending', async () => {
    let resolveList: ((response: Response) => void) | undefined
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveList = resolve
          }),
      ),
    )
    const wrapper = mountToolsView()
    await flushPromises()

    expect(getByText(wrapper, '检测中')).toBeTruthy()

    resolveList?.(jsonResponse({ tools: [], warnings: [] }))
    await flushPromises()
    expect(wrapper.text()).toContain('未发现已安装的 AI 工具')
  })

  it('lists tools with status badge, provider and model', async () => {
    stubApi({ '/api/tools': { tools: [claudeTool, codexTool], warnings: [] } })
    const wrapper = mountToolsView()
    await flushPromises()

    expect(getByText(wrapper, 'Claude Code')).toBeTruthy()
    expect(getByText(wrapper, '正常')).toBeTruthy()
    expect(getByText(wrapper, 'Anthropic')).toBeTruthy()
    expect(getByText(wrapper, 'claude-sonnet-4')).toBeTruthy()
    expect(getByText(wrapper, 'Codex CLI')).toBeTruthy()
    expect(getByText(wrapper, '未配置')).toBeTruthy()
    expect(getByText(wrapper, '供应商未知')).toBeTruthy()
    expect(getByText(wrapper, '模型未知')).toBeTruthy()
  })

  it('loads and renders tool detail after selecting a tool', async () => {
    stubApi({
      '/api/tools': { tools: [claudeTool, codexTool], warnings: [] },
      '/api/tools/claude-code': {
        ...claudeTool,
        base_url: 'https://relay.example.com',
        is_third_party: true,
        warnings: [
          { code: 'SECRET_IN_ENV', message: '密钥来自环境变量 MY_TEST_KEY, 本应用不读取' },
        ],
      },
    })
    const wrapper = mountToolsView()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await flushPromises()

    expect(getByText(wrapper, '工具详情')).toBeTruthy()
    expect(getByText(wrapper, 'https://relay.example.com')).toBeTruthy()
    expect(getByText(wrapper, '是')).toBeTruthy()
    expect(getByText(wrapper, 'sk-a****cdef')).toBeTruthy()
    expect(getByText(wrapper, '/home/me/.claude/settings.json')).toBeTruthy()
    expect(
      getByText(wrapper, 'SECRET_IN_ENV: 密钥来自环境变量 MY_TEST_KEY, 本应用不读取'),
    ).toBeTruthy()
    expect(wrapper.text()).toContain('最后修改时间')
    expect(wrapper.text()).toContain('2023')
  })

  it('shows an empty state when no tool is installed', async () => {
    stubApi({ '/api/tools': { tools: [], warnings: [] } })
    const wrapper = mountToolsView()
    await flushPromises()

    expect(wrapper.text()).toContain('未发现已安装的 AI 工具')
  })

  it('keeps healthy tools visible and shows top-level warnings', async () => {
    stubApi({
      '/api/tools': {
        tools: [claudeTool, brokenTool],
        warnings: [{ code: 'ADAPTER_ERROR', message: '适配器 broken-tool 读取失败: RuntimeError' }],
      },
    })
    const wrapper = mountToolsView()
    await flushPromises()

    expect(getByText(wrapper, 'Claude Code')).toBeTruthy()
    expect(getByText(wrapper, 'Broken Tool')).toBeTruthy()
    expect(getByText(wrapper, '异常')).toBeTruthy()
    expect(
      getByText(wrapper, 'ADAPTER_ERROR: 适配器 broken-tool 读取失败: RuntimeError'),
    ).toBeTruthy()
  })

  it('shows a readable error when the list request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const wrapper = mountToolsView()
    await flushPromises()

    expect(getByRole(wrapper, 'alert').text()).toContain('无法连接后端服务')
  })

  it('shows a readable error when the detail request fails', async () => {
    stubApi({ '/api/tools': { tools: [claudeTool], warnings: [] } })
    const wrapper = mountToolsView()
    await flushPromises()

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await flushPromises()

    expect(getByRole(wrapper, 'alert').text()).toContain('无法连接后端服务')
  })
})