import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { ToolView } from '../api/tools'
import WorkbenchView from '../views/WorkbenchView.vue'
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

type FetchHandler = (path: string) => Promise<Response>

function stubFetch(handler: FetchHandler) {
  const mock = vi.fn<FetchHandler>((path: string) => {
    if (path === '/api/chat/sessions') {
      return Promise.resolve(jsonResponse({ sessions: [] }))
    }
    return handler(path)
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

function mountWorkbench() {
  return mount(WorkbenchView, { global: { plugins: [createPinia()] } })
}

function detailRegion(wrapper: ReturnType<typeof mountWorkbench>) {
  return getByRole(wrapper, 'region', { name: '工具详情' })
}

describe('WorkbenchView', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a detecting state before the first scan settles', async () => {
    let resolveList: ((response: Response) => void) | undefined
    stubFetch(
      () =>
        new Promise<Response>((resolve) => {
          resolveList = resolve
        }),
    )
    const wrapper = mountWorkbench()
    await flushPromises()

    expect(getByText(wrapper, '正在检测本机工具…')).toBeTruthy()
    expect(wrapper.text()).not.toContain('正常')

    resolveList?.(jsonResponse({ tools: [claudeTool], warnings: [] }))
    await flushPromises()

    expect(getByText(wrapper, '正常')).toBeTruthy()
    expect(getByText(wrapper, '共 1 个工具 · 0 个需处理')).toBeTruthy()
  })

  it('lists tools with status, install/config, provider and model summaries', async () => {
    stubFetch(() =>
      Promise.resolve(jsonResponse({ tools: [claudeTool, codexTool, brokenTool], warnings: [] })),
    )
    const wrapper = mountWorkbench()
    await flushPromises()

    const claudeItem = getByRole(wrapper, 'button', { name: 'Claude Code' })
    const codexItem = getByRole(wrapper, 'button', { name: 'Codex CLI' })
    expect(getByRole(wrapper, 'button', { name: 'Broken Tool' })).toBeTruthy()
    expect(getByText(wrapper, '共 3 个工具 · 2 个需处理')).toBeTruthy()
    expect(claudeItem.text()).toContain('供应商：Anthropic · 模型：claude-sonnet-4')
    expect(claudeItem.text()).toContain('已安装 · 已配置')
    expect(codexItem.text()).toContain('供应商：未知 · 模型：未知')
    expect(codexItem.text()).toContain('已安装 · 未配置（无托管字段）')
  })

  it('distinguishes an empty scan from a read failure and says scanning is read-only', async () => {
    stubFetch(() => Promise.resolve(jsonResponse({ tools: [], warnings: [] })))
    const wrapper = mountWorkbench()
    await flushPromises()

    expect(getByText(wrapper, '尚未发现已安装的 AI 工具')).toBeTruthy()
    expect(getByText(wrapper, '扫描只读取本地配置，不会修改任何文件。')).toBeTruthy()
    expect(wrapper.text()).not.toContain('工具读取失败')
  })

  it('explains an empty result when discovery partially failed', async () => {
    stubFetch(() =>
      Promise.resolve(
        jsonResponse({
          tools: [],
          warnings: [
            { code: 'ADAPTER_ERROR', message: '适配器 broken-tool 读取失败: RuntimeError' },
          ],
        }),
      ),
    )
    const wrapper = mountWorkbench()
    await flushPromises()

    expect(getByText(wrapper, '未发现可读取的工具')).toBeTruthy()
    expect(getByText(wrapper, '部分工具的配置读取失败，请查看上方原因。')).toBeTruthy()
    expect(wrapper.text()).toContain('部分工具检测失败')
  })
  it('shows a readable overall error when the tool list cannot be read', async () => {
    stubFetch(() => Promise.reject(new TypeError('Failed to fetch')))
    const wrapper = mountWorkbench()
    await flushPromises()

    expect(getByText(wrapper, '工具读取失败')).toBeTruthy()
    expect(getByRole(wrapper, 'alert').text()).toContain('无法连接后端服务')
    expect(wrapper.text()).not.toContain('尚未发现已安装的 AI 工具')
  })

  it('keeps healthy tools selectable when only part of discovery fails', async () => {
    stubFetch(() =>
      Promise.resolve(
        jsonResponse({
          tools: [claudeTool, brokenTool],
          warnings: [
            { code: 'ADAPTER_ERROR', message: '适配器 broken-tool 读取失败: RuntimeError' },
          ],
        }),
      ),
    )
    const wrapper = mountWorkbench()
    await flushPromises()

    expect(getByText(wrapper, '部分工具检测失败')).toBeTruthy()
    expect(
      getByText(wrapper, 'ADAPTER_ERROR: 适配器 broken-tool 读取失败: RuntimeError'),
    ).toBeTruthy()
    expect(getByRole(wrapper, 'button', { name: 'Claude Code' })).toBeTruthy()
    expect(getByRole(wrapper, 'button', { name: 'Broken Tool' })).toBeTruthy()
  })

  it('keeps the current list visible while re-detecting', async () => {
    let listCalls = 0
    let resolveSecond: ((response: Response) => void) | undefined
    stubFetch((path) => {
      if (path !== '/api/tools') {
        return Promise.reject(new TypeError(`unexpected request: ${path}`))
      }
      listCalls += 1
      if (listCalls === 1) {
        return Promise.resolve(jsonResponse({ tools: [claudeTool], warnings: [] }))
      }
      return new Promise<Response>((resolve) => {
        resolveSecond = resolve
      })
    })
    const wrapper = mountWorkbench()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: '重新检测工具列表' }).trigger('click')
    await flushPromises()

    expect(getByText(wrapper, 'Claude Code')).toBeTruthy()
    expect(getByText(wrapper, '正在重新检测…')).toBeTruthy()

    resolveSecond?.(jsonResponse({ tools: [claudeTool, codexTool], warnings: [] }))
    await flushPromises()

    expect(wrapper.text()).not.toContain('正在重新检测…')
    expect(getByText(wrapper, '共 2 个工具 · 1 个需处理')).toBeTruthy()
  })

  it('clears partial-failure warnings after a successful rescan', async () => {
    let listCalls = 0
    stubFetch(() => {
      listCalls += 1
      const warnings =
        listCalls === 1 ? [{ code: 'ADAPTER_ERROR' as const, message: '首次失败' }] : []
      return Promise.resolve(jsonResponse({ tools: [claudeTool], warnings }))
    })
    const wrapper = mountWorkbench()
    await flushPromises()

    expect(wrapper.text()).toContain('首次失败')

    await getByRole(wrapper, 'button', { name: '重新检测工具列表' }).trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('首次失败')
    expect(wrapper.text()).not.toContain('部分工具检测失败')
  })

  it('renders the selected tool detail with masked secret and warnings', async () => {
    stubFetch((path) => {
      if (path === '/api/tools') {
        return Promise.resolve(jsonResponse({ tools: [claudeTool], warnings: [] }))
      }
      if (path === '/api/tools/claude-code') {
        return Promise.resolve(
          jsonResponse({
            ...claudeTool,
            base_url: 'https://relay.example.com',
            is_third_party: true,
            warnings: [
              { code: 'SECRET_IN_ENV', message: '密钥来自环境变量 MY_TEST_KEY, 本应用不读取' },
            ],
          }),
        )
      }
      return Promise.reject(new TypeError(`unexpected request: ${path}`))
    })
    const wrapper = mountWorkbench()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await flushPromises()

    const detail = detailRegion(wrapper)
    expect(getByText(detail, '工具详情')).toBeTruthy()
    expect(getByText(detail, 'Anthropic')).toBeTruthy()
    expect(getByText(detail, 'claude-sonnet-4')).toBeTruthy()
    expect(getByText(detail, 'https://relay.example.com')).toBeTruthy()
    expect(getByText(detail, 'sk-a****cdef')).toBeTruthy()
    expect(getByText(detail, '/home/me/.claude/settings.json')).toBeTruthy()
    expect(
      getByText(detail, 'SECRET_IN_ENV: 密钥来自环境变量 MY_TEST_KEY, 本应用不读取'),
    ).toBeTruthy()
    expect(detail.text()).toContain('最后修改时间')
    expect(detail.text()).toContain('2023')
  })

  it('opens unconfigured tools and shows unknown values without inventing them', async () => {
    stubFetch((path) => {
      if (path === '/api/tools') {
        return Promise.resolve(jsonResponse({ tools: [codexTool], warnings: [] }))
      }
      if (path === '/api/tools/codex-cli') {
        return Promise.resolve(jsonResponse(codexTool))
      }
      return Promise.reject(new TypeError(`unexpected request: ${path}`))
    })
    const wrapper = mountWorkbench()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: 'Codex CLI' }).trigger('click')
    await flushPromises()

    const detail = detailRegion(wrapper)
    expect(getByText(detail, '未配置（无托管字段）')).toBeTruthy()
    expect(getByText(detail, '未设置')).toBeTruthy()
    expect(detail.text()).toContain('未知')
    expect(detail.text()).not.toContain('Anthropic')
    expect(detail.text()).not.toContain('claude-sonnet-4')
  })

  it('shows a detail loading state while the request is pending', async () => {
    let resolveDetail: ((response: Response) => void) | undefined
    stubFetch((path) => {
      if (path === '/api/tools') {
        return Promise.resolve(jsonResponse({ tools: [claudeTool], warnings: [] }))
      }
      return new Promise<Response>((resolve) => {
        resolveDetail = resolve
      })
    })
    const wrapper = mountWorkbench()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await flushPromises()

    const detail = detailRegion(wrapper)
    expect(getByText(detail, '正在读取详情…')).toBeTruthy()

    resolveDetail?.(jsonResponse(claudeTool))
    await flushPromises()

    expect(detail.text()).toContain('Anthropic')
  })

  it('shows a readable detail error and retries the same tool', async () => {
    let detailCalls = 0
    stubFetch((path) => {
      if (path === '/api/tools') {
        return Promise.resolve(jsonResponse({ tools: [claudeTool], warnings: [] }))
      }
      detailCalls += 1
      if (detailCalls === 1) {
        return Promise.reject(new TypeError('Failed to fetch'))
      }
      return Promise.resolve(jsonResponse(claudeTool))
    })
    const wrapper = mountWorkbench()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await flushPromises()

    const detail = detailRegion(wrapper)
    expect(getByText(detail, '详情读取失败')).toBeTruthy()
    expect(getByText(detail, '无法连接后端服务')).toBeTruthy()

    await getByRole(detail, 'button', { name: '重新读取' }).trigger('click')
    await flushPromises()

    expect(detail.text()).toContain('Anthropic')
    expect(detail.text()).not.toContain('详情读取失败')
    expect(detailCalls).toBe(2)
  })

  it('clears a previous detail error when another tool is selected', async () => {
    stubFetch((path) => {
      if (path === '/api/tools') {
        return Promise.resolve(jsonResponse({ tools: [claudeTool, codexTool], warnings: [] }))
      }
      if (path === '/api/tools/claude-code') {
        return Promise.reject(new TypeError('Failed to fetch'))
      }
      if (path === '/api/tools/codex-cli') {
        return Promise.resolve(jsonResponse(codexTool))
      }
      return Promise.reject(new TypeError(`unexpected request: ${path}`))
    })
    const wrapper = mountWorkbench()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await flushPromises()

    await getByRole(wrapper, 'button', { name: 'Codex CLI' }).trigger('click')
    await flushPromises()

    const detail = detailRegion(wrapper)
    expect(detail.text()).toContain('Codex CLI')
    expect(detail.text()).not.toContain('无法连接后端服务')
    expect(wrapper.findAll('[role="alert"]')).toHaveLength(0)
  })

  it('ignores a late detail response after a faster second selection', async () => {
    let resolveClaude: ((response: Response) => void) | undefined
    let resolveCodex: ((response: Response) => void) | undefined
    stubFetch((path) => {
      if (path === '/api/tools') {
        return Promise.resolve(jsonResponse({ tools: [claudeTool, codexTool], warnings: [] }))
      }
      if (path === '/api/tools/claude-code') {
        return new Promise<Response>((resolve) => {
          resolveClaude = resolve
        })
      }
      if (path === '/api/tools/codex-cli') {
        return new Promise<Response>((resolve) => {
          resolveCodex = resolve
        })
      }
      return Promise.reject(new TypeError(`unexpected request: ${path}`))
    })
    const wrapper = mountWorkbench()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await flushPromises()
    await getByRole(wrapper, 'button', { name: 'Codex CLI' }).trigger('click')
    await flushPromises()

    resolveCodex?.(jsonResponse(codexTool))
    await flushPromises()
    resolveClaude?.(jsonResponse(claudeTool))
    await flushPromises()

    const detail = detailRegion(wrapper)
    expect(detail.text()).toContain('Codex CLI')
    expect(detail.text()).not.toContain('Claude Code')
  })

  it('does not re-request a tool that is already loading or loaded', async () => {
    let detailCalls = 0
    let resolveDetail: ((response: Response) => void) | undefined
    stubFetch((path) => {
      if (path === '/api/tools') {
        return Promise.resolve(jsonResponse({ tools: [claudeTool], warnings: [] }))
      }
      detailCalls += 1
      return new Promise<Response>((resolve) => {
        resolveDetail = resolve
      })
    })
    const wrapper = mountWorkbench()
    await flushPromises()

    const button = getByRole(wrapper, 'button', { name: 'Claude Code' })
    await button.trigger('click')
    await button.trigger('click')
    await flushPromises()

    resolveDetail?.(jsonResponse(claudeTool))
    await flushPromises()

    await button.trigger('click')
    await flushPromises()

    expect(detailCalls).toBe(1)
  })

  it('marks the selected tool with aria-pressed for assistive technology', async () => {
    stubFetch((path) => {
      if (path === '/api/tools') {
        return Promise.resolve(jsonResponse({ tools: [claudeTool, codexTool], warnings: [] }))
      }
      return Promise.resolve(jsonResponse(claudeTool))
    })
    const wrapper = mountWorkbench()
    await flushPromises()

    await getByRole(wrapper, 'button', { name: 'Claude Code' }).trigger('click')
    await flushPromises()

    expect(getByRole(wrapper, 'button', { name: 'Claude Code' }).attributes('aria-pressed')).toBe(
      'true',
    )
    expect(getByRole(wrapper, 'button', { name: 'Codex CLI' }).attributes('aria-pressed')).toBe(
      'false',
    )
  })
})

